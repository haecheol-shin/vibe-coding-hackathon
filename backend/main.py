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
    done: bool = False


class ProductivityCoachRequest(BaseModel):
    request: str = Field(min_length=1, max_length=1000)
    tasks: list[ProductivityTask] = Field(default_factory=list, max_length=30)
    energy: int = Field(default=3, ge=1, le=5)
    mood: str = Field(default="calm", max_length=40)
    focus_sessions: int = Field(default=0, ge=0, le=50)


class ProductivityCoachResponse(BaseModel):
    answer: str
    model: str
    open_tasks: int
    completed_tasks: int


def build_focus_plan(
    tasks: list[dict[str, Any]], energy: str, available_minutes: int
) -> dict[str, Any]:
    high_priority = [task for task in tasks if task.get("priority") == "high"]
    normal_priority = [task for task in tasks if task.get("priority") != "high"]
    ordered_tasks = high_priority + normal_priority
    selected_tasks = ordered_tasks[:3]

    block_length = 25 if energy == "low" else 45 if energy == "high" else 35
    max_blocks = max(1, available_minutes // max(block_length, 1))
    focus_blocks = []

    for index, task in enumerate(selected_tasks[:max_blocks], start=1):
        focus_blocks.append(
            {
                "label": f"Block {index}",
                "minutes": block_length,
                "task": task.get("title", "Untitled task"),
            }
        )

    if not focus_blocks:
        focus_blocks.append(
            {
                "label": "Block 1",
                "minutes": min(25, available_minutes),
                "task": "Capture one small task to start momentum",
            }
        )

    return {
        "summary": "Start with the highest-leverage task, then protect one short review window.",
        "focus_blocks": focus_blocks,
        "next_action": focus_blocks[0]["task"],
        "copilot_note": "Generated through the CopilotKit productivity planning action.",
    }


def suggest_focus_plan(
    tasks: list[dict[str, Any]], energy: str = "medium", available_minutes: int = 90
) -> dict[str, Any]:
    return build_focus_plan(tasks, energy, available_minutes)


copilot_sdk = CopilotKitRemoteEndpoint(
    actions=[
        Action(
            name="suggest_focus_plan",
            description="Create a practical focus plan from the user's tasks, energy level, and available time.",
            parameters=[
                {
                    "name": "tasks",
                    "type": "object[]",
                    "description": "Tasks with title and priority fields.",
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

    return "\n".join(
        [
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


@app.post("/api/productivity/plan")
def productivity_plan(payload: dict[str, Any]) -> dict[str, Any]:
    return build_focus_plan(
        tasks=payload.get("tasks", []),
        energy=payload.get("energy", "medium"),
        available_minutes=int(payload.get("available_minutes", 90)),
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