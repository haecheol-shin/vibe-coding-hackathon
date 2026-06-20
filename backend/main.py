from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from copilotkit import Action, CopilotKitRemoteEndpoint
from copilotkit.integrations.fastapi import add_fastapi_endpoint
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - dependency is installed in normal runs
    load_dotenv = None


if load_dotenv:
    load_dotenv()


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"

app = FastAPI(title="Personal Productivity Copilot API")
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
    request: str = Field(min_length=1, max_length=1000)
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
            description="Create a practical focus plan from the user's tasks, energy level, and available time.",
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


def _copilot_token() -> str | None:
    return (
        os.getenv("COPILOT_GITHUB_TOKEN")
        or os.getenv("GH_TOKEN")
        or os.getenv("GITHUB_TOKEN")
    )


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
        raise RuntimeError("github-copilot-sdk is not installed") from exc

    model = os.getenv("COPILOT_MODEL", "gpt-5")
    timeout = float(os.getenv("COPILOT_REQUEST_TIMEOUT_SECONDS", "90"))
    token = _copilot_token()
    if not token:
        raise RuntimeError("COPILOT_GITHUB_TOKEN is not configured")

    client_options: dict[str, str] = {
        "working_directory": str(PROJECT_DIR),
        "github_token": token,
    }

    def deny_tool_execution(request, invocation):
        return PermissionDecisionReject(
            feedback="Tool execution is disabled for this public web app."
        )

    async with CopilotClient(**client_options) as client:
        async with await client.create_session(
            model=model,
            streaming=False,
            on_permission_request=deny_tool_execution,
            system_message={
                "mode": "append",
                "content": (
                    "You are embedded in a personal productivity web app. Act as "
                    "a concise productivity coach. Turn the user's tasks, energy, "
                    "and schedule into practical next actions. Keep responses short, "
                    "specific, and humane. Do not attempt shell commands, file edits, "
                    "or other runtime tool execution."
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
                    errors.append(getattr(data, "message", "Copilot session error"))
                    done.set()
                elif event_type == "session.idle" or data_type == "SessionIdleData":
                    done.set()

            unsubscribe = session.on(on_event)
            try:
                if context:
                    prompt = f"Current productivity state:\n{context}\n\nUser request:\n{prompt}"
                await session.send(prompt)
                await asyncio.wait_for(done.wait(), timeout=timeout)
            finally:
                if callable(unsubscribe):
                    unsubscribe()

            if errors:
                raise RuntimeError(errors[-1])
            if not messages:
                raise RuntimeError("Copilot did not return a response")

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
        raise HTTPException(status_code=504, detail="Copilot request timed out") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ChatResponse(answer=answer, model=os.getenv("COPILOT_MODEL", "gpt-5"))


@app.post("/api/productivity/coach", response_model=ProductivityCoachResponse)
async def productivity_coach(
    request: ProductivityCoachRequest,
) -> ProductivityCoachResponse:
    try:
        answer = await ask_copilot(request.request, _productivity_context(request))
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Copilot request timed out") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    completed_tasks = sum(1 for task in request.tasks if task.done)
    return ProductivityCoachResponse(
        answer=answer,
        model=os.getenv("COPILOT_MODEL", "gpt-5"),
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