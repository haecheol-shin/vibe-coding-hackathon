from pathlib import Path
from typing import Any

from copilotkit import Action, CopilotKitRemoteEndpoint
from copilotkit.integrations.fastapi import add_fastapi_endpoint
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Vibe Coding Hackathon API")


def build_focus_plan(tasks: list[dict[str, Any]], energy: str, available_minutes: int) -> dict[str, Any]:
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


def suggest_focus_plan(tasks: list[dict[str, Any]], energy: str = "medium", available_minutes: int = 90) -> dict[str, Any]:
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

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# Basic endpoint used to verify that the API is running.
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