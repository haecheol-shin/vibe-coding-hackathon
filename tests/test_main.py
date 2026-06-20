from fastapi.testclient import TestClient

from main import create_app


def test_health_check() -> None:
    client = TestClient(create_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_todo_crud_flow() -> None:
    client = TestClient(create_app())

    create_res = client.post("/todos", json={"title": "first task"})
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["id"] == 1
    assert created["title"] == "first task"
    assert created["done"] is False

    list_res = client.get("/todos")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    get_res = client.get("/todos/1")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "first task"

    patch_res = client.patch("/todos/1", json={"done": True, "title": "updated"})
    assert patch_res.status_code == 200
    assert patch_res.json()["done"] is True
    assert patch_res.json()["title"] == "updated"

    delete_res = client.delete("/todos/1")
    assert delete_res.status_code == 204

    not_found_res = client.get("/todos/1")
    assert not_found_res.status_code == 404
