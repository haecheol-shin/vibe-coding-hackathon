from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    done: bool = False


class TodoUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    done: bool | None = None


class Todo(TodoCreate):
    id: int


def create_app() -> FastAPI:
    app = FastAPI(title="Vibe Coding Hackathon API")
    app.state.todos: dict[int, Todo] = {}
    app.state.next_id = 1

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/todos", response_model=list[Todo])
    def list_todos() -> list[Todo]:
        return list(app.state.todos.values())

    @app.post("/todos", response_model=Todo, status_code=status.HTTP_201_CREATED)
    def create_todo(payload: TodoCreate) -> Todo:
        todo = Todo(id=app.state.next_id, title=payload.title, done=payload.done)
        app.state.todos[todo.id] = todo
        app.state.next_id += 1
        return todo

    @app.get("/todos/{todo_id}", response_model=Todo)
    def get_todo(todo_id: int) -> Todo:
        todo = app.state.todos.get(todo_id)
        if todo is None:
            raise HTTPException(status_code=404, detail="Todo not found")
        return todo

    @app.patch("/todos/{todo_id}", response_model=Todo)
    def update_todo(todo_id: int, payload: TodoUpdate) -> Todo:
        todo = app.state.todos.get(todo_id)
        if todo is None:
            raise HTTPException(status_code=404, detail="Todo not found")

        if payload.title is not None:
            todo.title = payload.title
        if payload.done is not None:
            todo.done = payload.done

        app.state.todos[todo_id] = todo
        return todo

    @app.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_todo(todo_id: int) -> None:
        if todo_id not in app.state.todos:
            raise HTTPException(status_code=404, detail="Todo not found")
        del app.state.todos[todo_id]

    return app


app = create_app()