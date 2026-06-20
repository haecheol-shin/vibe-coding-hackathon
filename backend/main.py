from __future__ import annotations

import asyncio
import ast
import json
import os
import secrets
import subprocess
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen
from uuid import uuid4

from copilotkit import Action, CopilotKitRemoteEndpoint
from copilotkit.integrations.fastapi import add_fastapi_endpoint
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from azure.cosmos import CosmosClient, PartitionKey
except ModuleNotFoundError:  # pragma: no cover - 로컬 메모리 저장소로 실행 가능
    CosmosClient = None
    PartitionKey = None

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - 일반 실행 환경에서는 의존성이 설치되어 있음
    load_dotenv = None


if load_dotenv:
    load_dotenv()


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"

app = FastAPI(title="개인 생산성 코파일럿 API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    context: str | None = Field(default=None, max_length=6000)


class ChatResponse(BaseModel):
    answer: str
    model: str


class UserProfileResponse(BaseModel):
    user_id: str
    name: str
    github_username: str
    github_url: str
    avatar_url: str | None = None
    available_minutes: int
    invests_in_kospi: bool
    registered_at: datetime
    message: str


class DiaryEntryRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    mood_score: float = Field(ge=1, le=10)
    entry_date: date | None = None


class DiaryEntryResponse(BaseModel):
    entry_id: str
    user_id: str
    entry_date: date
    created_at: datetime
    headline: str
    content: str
    mood_score: float
    base_mood_score: float | None = None
    kospi_change_rate: float | None = None
    adjusted_by_kospi: bool = False
    mood_sample_count: int = 1
    message: str


class MarketIndexPoint(BaseModel):
    trading_date: date
    close: float
    change: float
    change_rate: float


class ProductivityTask(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    priority: str = Field(default="medium", pattern="^(high|medium|low|normal)$")
    duration_minutes: int = Field(default=30, ge=30, le=480)
    block_count: int = Field(default=1, ge=1, le=16)
    done: bool = False


class AvailabilityWindow(BaseModel):
    start: str = Field(pattern="^([01]\\d|2[0-3]):[0-5]\\d$")
    end: str = Field(pattern="^([01]\\d|2[0-3]):[0-5]\\d$")


class UserProfile(BaseModel):
    name: str = Field(default="", max_length=80)
    availability_windows: list[AvailabilityWindow] = Field(default_factory=list, max_length=12)
    available_minutes: int = Field(default=0, ge=0)
    usage_minutes: int = Field(default=0, ge=0)
    invests_in_kospi: bool = False


class ProductivityCoachRequest(BaseModel):
    request: str = Field(min_length=1, max_length=6000)
    user_profile: UserProfile | None = None
    tasks: list[ProductivityTask] = Field(default_factory=list, max_length=30)
    energy: int = Field(default=3, ge=1, le=5)
    mood: str = Field(default="calm", max_length=40)
    focus_sessions: int = Field(default=0, ge=0, le=50)


class ProductivityCoachResponse(BaseModel):
    answer: str
    model: str
    open_tasks: int
    completed_tasks: int


class UserProfileSummaryResponse(BaseModel):
    user_profile: UserProfile
    total_available_minutes: int
    availability_summary: str
    invests_in_kospi: bool


class ProductivityPlanRequest(BaseModel):
    tasks: list[ProductivityTask] = Field(default_factory=list, max_length=30)
    energy: str = Field(default="medium", pattern="^(low|medium|high)$")
    available_minutes: int = Field(default=90, ge=0, le=1440)
    user_profile: UserProfile | None = None


def build_schedule_slots(windows: list[AvailabilityWindow], block_minutes: int) -> list[tuple[int, int]]:
    slots = []

    for window in windows:
        start = minutes_from_time(window.start)
        end = minutes_from_time(window.end)
        range_end = end if end > start else end + 1440
        cursor = start

        while cursor + block_minutes <= range_end:
            slots.append((cursor, cursor + block_minutes))
            cursor += block_minutes

    return slots


def score_schedule_slot(start: int, invests_in_kospi: bool) -> int:
    time_of_day = start % 1440
    score = 40

    if 9 * 60 <= time_of_day < 11 * 60 + 30:
        score = 100
    elif 14 * 60 <= time_of_day < 16 * 60 + 30:
        score = 88
    elif 7 * 60 <= time_of_day < 9 * 60:
        score = 76
    elif 16 * 60 + 30 <= time_of_day < 18 * 60:
        score = 68
    elif 11 * 60 + 30 <= time_of_day < 14 * 60:
        score = 54
    elif 18 * 60 <= time_of_day < 22 * 60:
        score = 48

    if invests_in_kospi and 9 * 60 <= time_of_day < 9 * 60 + 30:
        score -= 28

    return score


def optimize_schedule_slots(
    slots: list[tuple[int, int]], invests_in_kospi: bool
) -> list[tuple[int, int]]:
    return sorted(
        slots,
        key=lambda slot: (-score_schedule_slot(slot[0], invests_in_kospi), slot[0]),
    )


def select_best_schedule_slots(
    slots: list[tuple[int, int]], block_count: int, invests_in_kospi: bool
) -> list[tuple[int, int]]:
    if not slots:
        return []

    ordered_slots = sorted(slots, key=lambda slot: slot[0])
    best_run: list[tuple[int, int]] = []
    best_score = -1

    for index in range(len(ordered_slots)):
        run = [ordered_slots[index]]

        for next_slot in ordered_slots[index + 1 :]:
            if run[-1][1] == next_slot[0]:
                run.append(next_slot)
            elif next_slot[0] > run[-1][1]:
                break

            if len(run) == block_count:
                break

        if len(run) == block_count:
            run_score = sum(score_schedule_slot(slot[0], invests_in_kospi) for slot in run)

            if run_score > best_score:
                best_run = run
                best_score = run_score

    if best_run:
        return best_run

    return optimize_schedule_slots(slots, invests_in_kospi)[:block_count]


def build_focus_plan(
    tasks: list[dict[str, Any]],
    energy: str,
    available_minutes: int,
    user_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_profile = normalize_user_profile(user_profile)
    planning_minutes = normalized_profile.available_minutes or available_minutes
    high_priority = [task for task in tasks if task.get("priority") == "high"]
    normal_priority = [task for task in tasks if task.get("priority") != "high"]
    ordered_tasks = high_priority + normal_priority
    selected_tasks = ordered_tasks

    block_length = 30
    schedule_slots = build_schedule_slots(normalized_profile.availability_windows, block_length)
    max_blocks = max(1, len(schedule_slots) or planning_minutes // max(block_length, 1))
    focus_blocks = []

    def append_focus_block(task_name: str, slot: tuple[int, int] | None = None) -> None:
        block_number = len(focus_blocks) + 1
        block = {
            "label": f"Block {block_number}",
            "minutes": block_length,
            "task": task_name,
        }

        if slot:
            start, end = slot
            start_time = minutes_to_time(start)
            end_time = minutes_to_time(end)
            block.update(
                {
                    "start_time": start_time,
                    "end_time": end_time,
                    "time_range": f"{start_time}-{end_time}",
                }
            )

        focus_blocks.append(block)

    for task in selected_tasks:
        duration_minutes = int(task.get("duration_minutes") or 30)
        task_block_count = int(task.get("block_count") or 0) or -(-duration_minutes // block_length)
        selected_slots = select_best_schedule_slots(
            schedule_slots,
            min(max(1, task_block_count), max_blocks - len(focus_blocks)),
            normalized_profile.invests_in_kospi,
        )

        for index in range(max(1, task_block_count)):
            if len(focus_blocks) >= max_blocks:
                break

            slot = selected_slots[index] if index < len(selected_slots) else None
            append_focus_block(task.get("title", "Untitled task"), slot)

            if slot in schedule_slots:
                schedule_slots.remove(slot)

        if len(focus_blocks) >= max_blocks:
            break

    if not focus_blocks:
        default_blocks = [
            "가용 시간 안에서 첫 집중 블록을 시작하세요.",
            "중간에 짧게 쉬면서 다음 블록의 집중 주제를 정하세요.",
            "마무리 전에 오늘 남은 가용 시간을 다시 확인하세요.",
        ]
        block_minutes = min(block_length, planning_minutes or block_length)
        block_count = min(len(default_blocks), max_blocks)

        for block_text in default_blocks[:block_count]:
            selected_slots = select_best_schedule_slots(
                schedule_slots,
                1,
                normalized_profile.invests_in_kospi,
            )
            slot = selected_slots[0] if selected_slots else None
            append_focus_block(block_text, slot)
            focus_blocks[-1]["minutes"] = block_minutes

            if slot in schedule_slots:
                schedule_slots.remove(slot)

    user_name = normalized_profile.name or "there"
    availability_text = format_minutes(normalized_profile.available_minutes)
    window_text = format_availability_windows(normalized_profile.availability_windows)
    kospi_note = (
        "Include a light portfolio check-in, but keep focus work separate from market watching."
        if normalized_profile.invests_in_kospi
        else "No investment check-in is needed for this plan."
    )

    return {
        "summary": "Use the available windows to protect one practical focus rhythm.",
        "focus_blocks": focus_blocks,
        "next_action": focus_blocks[0]["task"],
        "user_profile": normalized_profile.model_dump(),
        "copilot_note": (
            f"Generated for {user_name} through the CopilotKit productivity planning action. "
            f"Available time: {availability_text} across {window_text}. {kospi_note}"
        ),
    }


def suggest_focus_plan(
    tasks: list[dict[str, Any]],
    energy: str = "medium",
    available_minutes: int = 90,
    user_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_focus_plan(tasks, energy, available_minutes, user_profile)


copilot_sdk = CopilotKitRemoteEndpoint(
    actions=[
        Action(
            name="suggest_focus_plan",
            description="사용자의 작업, 에너지 수준, 사용 가능한 시간을 바탕으로 실용적인 집중 계획을 만듭니다.",
            parameters=[
                {
                    "name": "tasks",
                    "type": "object[]",
                    "description": "Today todo items with title, duration_minutes, and block_count fields. Each block is 30 minutes.",
                    "required": True,
                },
                {
                    "name": "energy",
                    "type": "string",
                    "description": "Current energy level: low, medium, or high.",
                },
                {
                    "name": "available_minutes",
                    "type": "number",
                    "description": "Minutes available for focused work today.",
                },
                {
                    "name": "user_profile",
                    "type": "object",
                    "description": "User profile with name, availability_windows, available_minutes, and invests_in_kospi fields.",
                },
            ],
            handler=suggest_focus_plan,
        )
    ]
)

add_fastapi_endpoint(app, copilot_sdk, "/copilotkit")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

class MemoryStorage:
    def __init__(self) -> None:
        self.oauth_states: set[str] = set()
        self.user_profiles: dict[str, UserProfileResponse] = {}
        self.session_user_ids: dict[str, str] = {}
        self.seeded_diary_user_ids: set[str] = set()
        self.diary_entries: list[DiaryEntryResponse] = []

    def add_oauth_state(self, state: str) -> None:
        self.oauth_states.add(state)

    def consume_oauth_state(self, state: str) -> bool:
        if state not in self.oauth_states:
            return False

        self.oauth_states.remove(state)
        return True

    def save_user_profile(self, profile: UserProfileResponse) -> None:
        self.user_profiles[profile.user_id] = profile

    def get_user_profile(self, user_id: str) -> UserProfileResponse | None:
        return self.user_profiles.get(user_id)

    def save_session(self, session_id: str, user_id: str) -> None:
        self.session_user_ids[session_id] = user_id

    def get_session_user_id(self, session_id: str) -> str | None:
        return self.session_user_ids.get(session_id)

    def has_seeded_diaries(self, user_id: str) -> bool:
        return user_id in self.seeded_diary_user_ids

    def mark_seeded_diaries(self, user_id: str) -> None:
        self.seeded_diary_user_ids.add(user_id)

    def add_diary(self, diary: DiaryEntryResponse) -> None:
        self.diary_entries.append(diary)

    def list_diaries(self, user_id: str) -> list[DiaryEntryResponse]:
        return [diary for diary in self.diary_entries if diary.user_id == user_id]

    def delete_diary(self, user_id: str, entry_id: str) -> bool:
        for index, diary in enumerate(self.diary_entries):
            if diary.entry_id == entry_id and diary.user_id == user_id:
                self.diary_entries.pop(index)
                return True

        return False


class CosmosStorage:
    def __init__(self) -> None:
        if CosmosClient is None or PartitionKey is None:
            raise RuntimeError("azure-cosmos가 설치되어 있지 않습니다")

        endpoint = os.getenv("COSMOS_ENDPOINT")
        key = os.getenv("COSMOS_KEY")
        database_name = os.getenv("COSMOS_DATABASE", "daily-mood-journal")
        if not endpoint or not key:
            raise RuntimeError("Cosmos DB 환경 변수가 필요합니다")

        client = CosmosClient(endpoint, credential=key)
        database = client.create_database_if_not_exists(database_name)
        self.users = database.create_container_if_not_exists(
            id=os.getenv("COSMOS_USERS_CONTAINER", "users"),
            partition_key=PartitionKey(path="/user_id"),
        )
        self.sessions = database.create_container_if_not_exists(
            id=os.getenv("COSMOS_SESSIONS_CONTAINER", "sessions"),
            partition_key=PartitionKey(path="/session_id"),
            default_ttl=60 * 60 * 24 * 14,
        )
        self.diaries = database.create_container_if_not_exists(
            id=os.getenv("COSMOS_DIARIES_CONTAINER", "diaries"),
            partition_key=PartitionKey(path="/user_id"),
        )

    def add_oauth_state(self, state: str) -> None:
        self.sessions.upsert_item({"id": state, "session_id": state, "kind": "oauth_state"})

    def consume_oauth_state(self, state: str) -> bool:
        try:
            item = self.sessions.read_item(item=state, partition_key=state)
        except Exception:
            return False

        if item.get("kind") != "oauth_state":
            return False

        self.sessions.delete_item(item=state, partition_key=state)
        return True

    def save_user_profile(self, profile: UserProfileResponse) -> None:
        existing = self._read_user_item(profile.user_id) or {}
        item = profile.model_dump(mode="json")
        item["id"] = profile.user_id
        item["sample_diaries_seeded"] = bool(existing.get("sample_diaries_seeded", False))
        self.users.upsert_item(item)

    def get_user_profile(self, user_id: str) -> UserProfileResponse | None:
        item = self._read_user_item(user_id)
        return UserProfileResponse.model_validate(item) if item else None

    def save_session(self, session_id: str, user_id: str) -> None:
        self.sessions.upsert_item(
            {
                "id": session_id,
                "session_id": session_id,
                "kind": "login_session",
                "user_id": user_id,
                "created_at": datetime.now().isoformat(),
            }
        )

    def get_session_user_id(self, session_id: str) -> str | None:
        try:
            item = self.sessions.read_item(item=session_id, partition_key=session_id)
        except Exception:
            return None

        return str(item.get("user_id")) if item.get("kind") == "login_session" else None

    def has_seeded_diaries(self, user_id: str) -> bool:
        item = self._read_user_item(user_id)
        return bool(item and item.get("sample_diaries_seeded"))

    def mark_seeded_diaries(self, user_id: str) -> None:
        item = self._read_user_item(user_id)
        if not item:
            return

        item["sample_diaries_seeded"] = True
        self.users.upsert_item(item)

    def add_diary(self, diary: DiaryEntryResponse) -> None:
        item = diary.model_dump(mode="json")
        item["id"] = diary.entry_id
        self.diaries.upsert_item(item)

    def list_diaries(self, user_id: str) -> list[DiaryEntryResponse]:
        items = self.diaries.query_items(
            query="SELECT * FROM c WHERE c.user_id = @user_id",
            parameters=[{"name": "@user_id", "value": user_id}],
            partition_key=user_id,
        )
        return [DiaryEntryResponse.model_validate(item) for item in items]

    def delete_diary(self, user_id: str, entry_id: str) -> bool:
        try:
            self.diaries.delete_item(item=entry_id, partition_key=user_id)
        except Exception:
            return False

        return True

    def _read_user_item(self, user_id: str) -> dict[str, Any] | None:
        try:
            return self.users.read_item(item=user_id, partition_key=user_id)
        except Exception:
            return None


def create_storage() -> MemoryStorage | CosmosStorage:
    if os.getenv("COSMOS_ENDPOINT") and os.getenv("COSMOS_KEY"):
        return CosmosStorage()

    return MemoryStorage()


storage = create_storage()
kospi_cache: list[MarketIndexPoint] = []
kospi_cache_date: date | None = None


def fetch_github_profile(username: str) -> dict[str, Any]:
    normalized_username = username.strip().lstrip("@")
    if not normalized_username:
        raise HTTPException(status_code=422, detail="깃허브 사용자명이 필요합니다")

    request = UrlRequest(
        f"https://api.github.com/users/{normalized_username}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "daily-mood-journal",
        },
    )

    try:
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            raise HTTPException(status_code=404, detail="깃허브 계정을 찾을 수 없습니다") from exc
        raise HTTPException(status_code=502, detail="깃허브 계정 확인에 실패했습니다") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="깃허브 계정 확인에 실패했습니다") from exc

    return payload


def github_oauth_redirect_uri(request: Request) -> str:
    return os.getenv("GITHUB_OAUTH_REDIRECT_URI") or str(request.url_for("github_oauth_callback"))


def github_oauth_configured() -> bool:
    return bool(os.getenv("GITHUB_CLIENT_ID") and os.getenv("GITHUB_CLIENT_SECRET"))


def github_oauth_settings() -> tuple[str, str]:
    client_id = os.getenv("GITHUB_CLIENT_ID")
    client_secret = os.getenv("GITHUB_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="깃허브 OAuth 환경 변수가 필요합니다")

    return client_id, client_secret


def local_github_access_token() -> str | None:
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN") or os.getenv("COPILOT_GITHUB_TOKEN")
    if token:
        return token

    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            cwd=PROJECT_DIR,
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError, TimeoutError):
        return None

    if result.returncode != 0:
        return None

    return result.stdout.strip() or None


def is_local_request(request: Request) -> bool:
    return (request.url.hostname or "") in {"127.0.0.1", "::1", "localhost"}


def exchange_github_oauth_code(code: str, redirect_uri: str) -> str:
    client_id, client_secret = github_oauth_settings()
    body = urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
    ).encode("utf-8")
    request = UrlRequest(
        "https://github.com/login/oauth/access_token",
        data=body,
        headers={"Accept": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="깃허브 OAuth 토큰 발급에 실패했습니다") from exc

    access_token = payload.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="깃허브 OAuth 토큰을 받지 못했습니다")

    return str(access_token)


def fetch_github_oauth_user(access_token: str) -> dict[str, Any]:
    request = UrlRequest(
        "https://api.github.com/user",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "daily-mood-journal",
        },
    )

    try:
        with urlopen(request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="깃허브 사용자 정보를 불러오지 못했습니다") from exc


def build_user_profile_from_github(github_profile: dict[str, Any]) -> UserProfileResponse:
    github_username = str(github_profile.get("login") or "")
    if not github_username:
        raise HTTPException(status_code=502, detail="깃허브 사용자명이 비어 있습니다")

    github_id = github_profile.get("id") or github_username

    return UserProfileResponse(
        user_id=f"github-{github_id}",
        name=str(github_profile.get("name") or github_username),
        github_username=github_username,
        github_url=str(github_profile.get("html_url") or f"https://github.com/{github_username}"),
        avatar_url=github_profile.get("avatar_url"),
        available_minutes=90,
        invests_in_kospi=True,
        registered_at=datetime.now(),
        message="깃허브 OAuth로 회원가입을 완료했습니다.",
    )


def current_user_id(request: Request) -> str:
    session_id = request.cookies.get("session_id")
    user_id = storage.get_session_user_id(session_id or "")
    if not user_id or storage.get_user_profile(user_id) is None:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")

    return user_id


def current_user_profile(request: Request) -> UserProfileResponse:
    profile = storage.get_user_profile(current_user_id(request))
    if profile is None:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")

    return profile


def user_diary_entries(user_id: str) -> list[DiaryEntryResponse]:
    return storage.list_diaries(user_id)


def build_diary_headline(content: str) -> str:
    first_line = content.strip().splitlines()[0] if content.strip() else "Untitled diary"
    headline = first_line.strip()
    return headline if len(headline) <= 54 else f"{headline[:51]}..."


def average_score(values: list[float]) -> float:
    return round(sum(values) / len(values), 2)


def build_daily_mood_summary(entry_date: date, entries: list[DiaryEntryResponse]) -> DiaryEntryResponse:
    sorted_entries = sorted(entries, key=lambda diary: diary.created_at)
    latest_entry = sorted_entries[-1]
    base_scores = [
        float(entry.base_mood_score if entry.base_mood_score is not None else entry.mood_score)
        for entry in sorted_entries
    ]
    adjusted_entries = [entry for entry in sorted_entries if entry.adjusted_by_kospi]

    return DiaryEntryResponse(
        entry_id=f"summary-{entry_date.isoformat()}",
        user_id=latest_entry.user_id,
        entry_date=entry_date,
        created_at=latest_entry.created_at,
        headline=f"{entry_date.isoformat()} 평균 기분 점수",
        content=latest_entry.content,
        mood_score=average_score([float(entry.mood_score) for entry in sorted_entries]),
        base_mood_score=average_score(base_scores),
        kospi_change_rate=adjusted_entries[-1].kospi_change_rate if adjusted_entries else None,
        adjusted_by_kospi=bool(adjusted_entries),
        mood_sample_count=len(sorted_entries),
        message="저장된 다이어리 항목으로 하루 기분 점수 평균을 계산했습니다.",
    )


def seed_mock_diary_entries(user_id: str) -> None:
    if storage.has_seeded_diaries(user_id):
        return

    today = date.today()

    past_snippets = [
        "아침 루틴을 지키며 하루를 시작했다. 작은 습관이 컨디션을 떠받쳤다.",
        "집중 블록을 두 번 돌렸다. 방해 요소를 줄이니 진척이 보였다.",
        "회의가 길었지만 결론을 남겼다. 다음 액션이 분명해졌다.",
        "코드 리뷰에서 배운 점이 많았다. 피드백을 바로 반영하니 속도가 붙었다.",
        "작업량을 줄이고 우선순위에 집중했다. 마음이 한결 가벼워졌다.",
        "예상치 못한 이슈가 있었지만 차분히 처리했다. 회복 탄력을 느꼈다.",
        "산책으로 머리를 식혔다. 오후 집중이 한결 잘 됐다.",
    ]
    past_scores = [6, 5, 7, 4, 6, 8, 7, 5, 6, 7, 5, 4, 6, 8, 7, 6, 5, 7, 6, 8, 5, 7]

    mock_entries: list[tuple[date, str, int]] = []
    for step, offset in enumerate(range(29, 7, -1)):
        entry_date = today - timedelta(days=offset)
        mock_entries.append(
            (
                entry_date,
                past_snippets[step % len(past_snippets)],
                past_scores[step % len(past_scores)],
            )
        )

    mock_entries.extend(
        [
            (today - timedelta(days=7), "월요일 아침, 업무 우선순위를 다시 세웠다. 회의 전에 핵심 세 가지를 정리하니 하루 시작이 가벼웠다.", 5),
            (today - timedelta(days=6), "프로젝트 방향 확정 후 집중 시간이 늘었다. 기능 범위를 줄이자 해야 할 일이 더 선명하게 보였다.", 6),
            (today - timedelta(days=5), "사용자 정보 입력 흐름을 잡으며 안정감을 회복했다. 작은 저장 성공이 다음 작업의 리듬을 만들었다.", 6),
            (today - timedelta(days=4), "투두 보드 개선으로 오후 작업 속도가 올랐다. 우선순위가 보이니 결정 피로가 줄었다.", 7),
            (today - timedelta(days=3), "배포와 협업 규칙 정리로 에너지를 많이 썼다. 그래도 팀이 같은 화면을 보게 된 점은 수확이었다.", 4),
            (today - timedelta(days=2), "기능 단위 진행으로 역할 경계가 부드러워졌다. 프론트와 백엔드보다 사용자 흐름을 먼저 보기로 했다.", 7),
            (today - timedelta(days=1), "일기 입력 기능 준비가 끝났다. 기분 점수와 시장 흐름을 함께 보는 아이디어가 데모 포인트가 됐다.", 6),
            (today, "오전 업데이트, 기분 차트가 주식 그래프처럼 움직였다. 점수 변화가 한눈에 보여 회고가 더 쉬워졌다.", 8),
            (today, "점심 이후 점검, KOSPI 반영 문구를 다듬었다. 기본 점수와 조정된 점수를 분리하니 의미가 분명해졌다.", 7),
            (today, "마감 전 뉴스 피드 목업을 확인했다. 일기가 쌓이는 느낌이 생기니 앱의 기록성이 살아났다.", 8),
        ]
    )

    for index, (entry_date, content, mood_score) in enumerate(mock_entries):
        storage.add_diary(
            DiaryEntryResponse(
                entry_id=f"mock-{entry_date.isoformat()}-{index}",
                user_id=user_id,
                entry_date=entry_date,
                created_at=datetime.combine(entry_date, datetime.min.time())
                + timedelta(hours=9, minutes=index),
                headline=build_diary_headline(content),
                content=content,
                mood_score=float(mood_score),
                base_mood_score=float(mood_score),
                kospi_change_rate=0,
                adjusted_by_kospi=False,
                message="기분 차트용 샘플 다이어리 항목입니다.",
            )
        )

    storage.mark_seeded_diaries(user_id)


def _market_points_from_closes(rows: list[tuple[date, float]], limit: int = 7) -> list[MarketIndexPoint]:
    ordered_rows = sorted(rows, key=lambda item: item[0])
    selected_rows = ordered_rows[-limit:]
    points: list[MarketIndexPoint] = []

    for trading_date, close in selected_rows:
        row_index = ordered_rows.index((trading_date, close))
        previous_close = ordered_rows[row_index - 1][1] if row_index > 0 else close
        change = close - previous_close
        change_rate = 0 if previous_close == 0 else (change / previous_close) * 100
        points.append(
            MarketIndexPoint(
                trading_date=trading_date,
                close=round(close, 2),
                change=round(change, 2),
                change_rate=round(change_rate, 2),
            )
        )

    return points


def fetch_kospi_points_from_pykrx(limit: int = 7) -> list[MarketIndexPoint]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            from pykrx import stock
    except ModuleNotFoundError as exc:
        raise RuntimeError("pykrx가 설치되어 있지 않습니다") from exc

    end_date = date.today()
    start_date = end_date - timedelta(days=370)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            dataframe = stock.get_index_ohlcv_by_date(
                start_date.strftime("%Y%m%d"),
                end_date.strftime("%Y%m%d"),
                "1001",
                name_display=False,
            )
    except Exception as exc:
        raise RuntimeError("pykrx 코스피 요청에 실패했습니다") from exc

    if dataframe.empty or "종가" not in dataframe.columns:
        raise RuntimeError("pykrx가 코스피 지수 데이터를 반환하지 않았습니다")

    rows = [
        (row_date.date(), float(row["종가"]))
        for row_date, row in dataframe.iterrows()
        if row.get("종가") is not None
    ]

    if not rows:
        raise RuntimeError("pykrx가 비어 있는 코스피 종가 데이터를 반환했습니다")

    return _market_points_from_closes(rows, limit=limit)


def fetch_kospi_points_from_naver(limit: int = 7) -> list[MarketIndexPoint]:
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=370)
        query = urlencode(
            {
                "symbol": "KOSPI",
                "requestType": 1,
                "startTime": start_date.strftime("%Y%m%d"),
                "endTime": end_date.strftime("%Y%m%d"),
                "timeframe": "day",
            }
        )
        request = UrlRequest(
            f"https://api.finance.naver.com/siseJson.naver?{query}",
            headers={"User-Agent": "Mozilla/5.0"},
        )

        with urlopen(request, timeout=10) as response:
            payload = response.read().decode("euc-kr", errors="ignore")

        table = ast.literal_eval(payload.strip())
        rows: list[tuple[date, float]] = []

        for row in table[1:]:
            if not row or len(row) < 5:
                continue

            trading_date = date.fromisoformat(f"{row[0][:4]}-{row[0][4:6]}-{row[0][6:8]}")
            rows.append((trading_date, float(row[4])))
    except Exception as exc:
        raise RuntimeError("네이버 금융 코스피 요청에 실패했습니다") from exc

    if not rows:
        raise RuntimeError("네이버 금융이 코스피 지수 데이터를 반환하지 않았습니다")

    return _market_points_from_closes(rows, limit=limit)


def fetch_kospi_points(limit: int = 7) -> list[MarketIndexPoint]:
    try:
        return fetch_kospi_points_from_pykrx(limit=limit)
    except RuntimeError:
        return fetch_kospi_points_from_naver(limit=limit)


def clamp_mood_score(score: float) -> float:
    return round(min(10, max(1, score)), 2)


def latest_kospi_change_rate() -> float:
    points = get_kospi_points()
    if not points:
        raise RuntimeError("코스피 변동률을 불러올 수 없습니다")

    return points[-1].change_rate


def _copilot_token() -> str | None:
    return local_github_access_token()


def _productivity_context(request: ProductivityCoachRequest) -> str:
    task_lines = [
        f"- [{'done' if task.done else 'open'}] {task.title} ({task.priority})"
        for task in request.tasks
    ]
    user_profile = normalize_user_profile(
        request.user_profile.model_dump() if request.user_profile else None
    )

    return "\n".join(
        [
            f"User name: {user_profile.name or 'unknown'}",
            f"Available time: {format_minutes(user_profile.available_minutes)}",
            f"Availability windows: {format_availability_windows(user_profile.availability_windows)}",
            f"Invests in KOSPI: {'yes' if user_profile.invests_in_kospi else 'no'}",
            f"Energy: {request.energy}/5",
            f"Mood: {request.mood}",
            f"Focus sessions completed: {request.focus_sessions}",
            "Tasks:",
            "\n".join(task_lines) if task_lines else "- none",
        ]
    )


async def ask_copilot(prompt: str, context: str | None = None) -> str:
    try:
        from copilot import CopilotClient
        from copilot.rpc import PermissionDecisionReject
    except ModuleNotFoundError as exc:
        raise RuntimeError("github-copilot-sdk가 설치되어 있지 않습니다") from exc

    model = os.getenv("COPILOT_MODEL", "gpt-4.1")
    timeout = float(os.getenv("COPILOT_REQUEST_TIMEOUT_SECONDS", "90"))
    token = _copilot_token()
    if not token:
        raise RuntimeError("COPILOT_GITHUB_TOKEN이 설정되어 있지 않고 gh auth token도 사용할 수 없습니다")

    client_options: dict[str, str] = {
        "working_directory": str(PROJECT_DIR),
        "github_token": token,
    }

    def deny_tool_execution(request, invocation):
        return PermissionDecisionReject(
            feedback="이 공개 웹앱에서는 도구 실행이 비활성화되어 있습니다."
        )

    async with CopilotClient(**client_options) as client:
        async with await client.create_session(
            model=model,
            streaming=False,
            on_permission_request=deny_tool_execution,
            system_message={
                "mode": "append",
                "content": (
                    "당신은 개인 생산성 웹앱 안에 포함된 코치입니다. "
                    "간결한 생산성 코치처럼 행동하세요. 사용자의 작업, 에너지, "
                    "일정을 실천 가능한 다음 행동으로 바꾸세요. 답변은 짧고, "
                    "구체적이고, 다정하게 유지하세요. 셸 명령, 파일 수정, "
                    "기타 런타임 도구 실행은 시도하지 마세요."
                ),
            },
        ) as session:
            done = asyncio.Event()
            messages: list[str] = []
            errors: list[str] = []

            def on_event(event) -> None:
                event_type = getattr(event, "type", "")
                data = getattr(event, "data", None)
                data_type = type(data).__name__ if data is not None else ""

                if event_type == "assistant.message" or data_type == "AssistantMessageData":
                    content = getattr(data, "content", "")
                    if content:
                        messages.append(content)
                elif event_type == "session.error":
                    errors.append(getattr(data, "message", "코파일럿 세션 오류"))
                    done.set()
                elif event_type == "session.idle" or data_type == "SessionIdleData":
                    done.set()

            unsubscribe = session.on(on_event)
            try:
                if context:
                    prompt = f"현재 생산성 상태:\n{context}\n\n사용자 요청:\n{prompt}"
                await session.send(prompt)
                await asyncio.wait_for(done.wait(), timeout=timeout)
            finally:
                if callable(unsubscribe):
                    unsubscribe()

            if errors:
                raise RuntimeError(errors[-1])
            if not messages:
                raise RuntimeError("코파일럿이 응답을 반환하지 않았습니다")

            return messages[-1].strip()


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/user-profile/summary", response_model=UserProfileSummaryResponse)
def user_profile_summary(user_profile: UserProfile) -> UserProfileSummaryResponse:
    normalized_profile = normalize_user_profile(user_profile)

    return UserProfileSummaryResponse(
        user_profile=normalized_profile,
        total_available_minutes=normalized_profile.available_minutes,
        availability_summary=format_availability_windows(normalized_profile.availability_windows),
        invests_in_kospi=normalized_profile.invests_in_kospi,
    )


@app.get("/auth/github/login")
def github_oauth_login(request: Request) -> RedirectResponse:
    if not github_oauth_configured():
        if not is_local_request(request):
            raise HTTPException(status_code=503, detail="깃허브 OAuth 환경 변수가 필요합니다")

        access_token = local_github_access_token()
        if not access_token:
            raise HTTPException(
                status_code=503,
                detail="깃허브 OAuth 환경 변수가 필요합니다. 로컬에서는 gh auth login 후 다시 시도하세요.",
            )

        profile = build_user_profile_from_github(fetch_github_oauth_user(access_token))
        profile.message = "로컬 깃허브 인증으로 회원가입을 완료했습니다."
        return create_login_session_response(profile, "local")

    client_id, _ = github_oauth_settings()
    state = secrets.token_urlsafe(24)
    storage.add_oauth_state(state)
    params = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": github_oauth_redirect_uri(request),
            "scope": "read:user",
            "state": state,
            "allow_signup": "true",
        }
    )
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{params}")


def create_login_session_response(profile: UserProfileResponse, auth_status: str = "success") -> RedirectResponse:
    storage.save_user_profile(profile)
    seed_mock_diary_entries(profile.user_id)

    session_id = secrets.token_urlsafe(32)
    storage.save_session(session_id, profile.user_id)
    response = RedirectResponse(f"/?auth={auth_status}")
    response.set_cookie(
        "session_id",
        session_id,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 14,
    )
    return response


@app.get("/auth/github/callback")
def github_oauth_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None) -> RedirectResponse:
    if error:
        return RedirectResponse("/?auth=cancelled")
    if not code or not state or not storage.consume_oauth_state(state):
        raise HTTPException(status_code=400, detail="깃허브 OAuth 요청을 확인할 수 없습니다")

    access_token = exchange_github_oauth_code(code, github_oauth_redirect_uri(request))
    profile = build_user_profile_from_github(fetch_github_oauth_user(access_token))
    return create_login_session_response(profile)


@app.get("/api/users/profile", response_model=UserProfileResponse)
def get_user_profile(request: Request) -> UserProfileResponse:
    return current_user_profile(request)


@app.post("/api/diaries/today", response_model=DiaryEntryResponse)
def save_today_diary(request: Request, diary_request: DiaryEntryRequest) -> DiaryEntryResponse:
    user_id = current_user_id(request)
    content = diary_request.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="다이어리 내용이 필요합니다")

    try:
        kospi_change_rate = latest_kospi_change_rate()
    except (HTTPException, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="코스피 변동률을 불러올 수 없습니다") from exc

    base_mood_score = round(diary_request.mood_score, 2)
    adjusted_mood_score = clamp_mood_score(base_mood_score + kospi_change_rate)
    entry_date = diary_request.entry_date or date.today()
    created_at = datetime.now()
    diary = DiaryEntryResponse(
        entry_id=uuid4().hex,
        user_id=user_id,
        entry_date=entry_date,
        created_at=created_at,
        headline=build_diary_headline(content),
        content=content,
        mood_score=adjusted_mood_score,
        base_mood_score=base_mood_score,
        kospi_change_rate=kospi_change_rate,
        adjusted_by_kospi=True,
        message="다이어리와 코스피가 반영된 기분 점수를 저장했습니다.",
    )
    storage.add_diary(diary)
    today_entries = [entry for entry in user_diary_entries(user_id) if entry.entry_date == entry_date]
    return build_daily_mood_summary(entry_date, today_entries)


@app.get("/api/diaries/today", response_model=DiaryEntryResponse)
def get_today_diary(request: Request) -> DiaryEntryResponse:
    user_id = current_user_id(request)
    today = date.today()
    today_entries = [diary for diary in user_diary_entries(user_id) if diary.entry_date == today]
    if not today_entries:
        raise HTTPException(status_code=404, detail="오늘 저장된 다이어리가 없습니다")

    return build_daily_mood_summary(today, today_entries)


@app.get("/api/diaries", response_model=list[DiaryEntryResponse])
def list_diaries(request: Request) -> list[DiaryEntryResponse]:
    return sorted(user_diary_entries(current_user_id(request)), key=lambda diary: diary.created_at, reverse=True)


@app.delete("/api/diaries/{entry_id}", status_code=204)
def delete_diary(entry_id: str, request: Request) -> None:
    user_id = current_user_id(request)
    if not storage.delete_diary(user_id, entry_id):
        raise HTTPException(status_code=404, detail="다이어리 항목을 찾을 수 없습니다")


@app.get("/api/markets/kospi", response_model=list[MarketIndexPoint])
def get_kospi_points() -> list[MarketIndexPoint]:
    global kospi_cache, kospi_cache_date

    today = date.today()
    if kospi_cache and kospi_cache_date == today:
        return kospi_cache

    try:
        kospi_cache = fetch_kospi_points(limit=30)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    kospi_cache_date = today
    return kospi_cache


@app.post("/api/productivity/plan")
def productivity_plan(payload: ProductivityPlanRequest) -> dict[str, Any]:
    return build_focus_plan(
        tasks=[task.model_dump() for task in payload.tasks],
        energy=payload.energy,
        available_minutes=payload.available_minutes,
        user_profile=payload.user_profile,
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        answer = await ask_copilot(request.prompt, request.context)
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="코파일럿 요청 시간이 초과되었습니다") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ChatResponse(answer=answer, model=os.getenv("COPILOT_MODEL", "gpt-4.1"))


@app.post("/api/productivity/coach", response_model=ProductivityCoachResponse)
async def productivity_coach(
    request: ProductivityCoachRequest,
) -> ProductivityCoachResponse:
    try:
        answer = await ask_copilot(request.request, _productivity_context(request))
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="코파일럿 요청 시간이 초과되었습니다") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    completed_tasks = sum(1 for task in request.tasks if task.done)
    return ProductivityCoachResponse(
        answer=answer,
        model=os.getenv("COPILOT_MODEL", "gpt-4.1"),
        open_tasks=len(request.tasks) - completed_tasks,
        completed_tasks=completed_tasks,
    )


def minutes_from_time(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def minutes_to_time(minutes: int) -> str:
    normalized_minutes = minutes % 1440
    hours = normalized_minutes // 60
    remaining_minutes = normalized_minutes % 60

    return f"{hours:02d}:{remaining_minutes:02d}"


def availability_window_minutes(window: AvailabilityWindow) -> int:
    start = minutes_from_time(window.start)
    end = minutes_from_time(window.end)
    duration = end - start if end > start else end + 1440 - start

    return min(duration, 1440)


def format_minutes(minutes: int) -> str:
    hours = minutes // 60
    remaining_minutes = minutes % 60

    return f"{hours}h {remaining_minutes}m" if hours else f"{remaining_minutes}m"


def format_availability_windows(windows: list[AvailabilityWindow]) -> str:
    if not windows:
        return "no availability windows"

    return ", ".join(
        f"{window.start}-{window.end} ({format_minutes(availability_window_minutes(window))})"
        for window in windows
    )


def normalize_user_profile(user_profile: dict[str, Any] | UserProfile | None) -> UserProfile:
    if isinstance(user_profile, UserProfile):
        profile = user_profile
    else:
        profile = UserProfile.model_validate(user_profile or {})

    computed_minutes = sum(
        availability_window_minutes(window) for window in profile.availability_windows
    )
    available_minutes = computed_minutes or profile.available_minutes or profile.usage_minutes

    return profile.model_copy(
        update={
            "available_minutes": min(available_minutes, 1440),
            "usage_minutes": min(available_minutes, 1440),
        }
    )