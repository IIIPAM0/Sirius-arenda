"""
Тесты для API «Сириус.Аренда».

Перед запуском тестов данные хранятся во временной директории,
чтобы не затрагивать «боевые» JSON-файлы приложения (см. фикстуру client).
"""
import importlib
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Изолируем хранилище: указываем данным временную директорию
    import app.storage as storage_module

    monkeypatch.setattr(storage_module, "DATA_DIR", tmp_path)
    storage_module._locks.clear()
    storage_module.rooms_table = storage_module.JSONTable("rooms.json")
    storage_module.bookings_table = storage_module.JSONTable("bookings.json")
    storage_module.users_table = storage_module.JSONTable("users.json")

    # Патчим ссылки на таблицы в модулях, которые их уже импортировали
    import app.routers.bookings as bookings_router
    import app.routers.rooms as rooms_router
    import app.auth as auth_module

    monkeypatch.setattr(rooms_router, "rooms_table", storage_module.rooms_table)
    monkeypatch.setattr(rooms_router, "bookings_table", storage_module.bookings_table)
    monkeypatch.setattr(bookings_router, "bookings_table", storage_module.bookings_table)
    monkeypatch.setattr(bookings_router, "rooms_table", storage_module.rooms_table)
    monkeypatch.setattr(auth_module, "users_table", storage_module.users_table)

    from app.main import app as fastapi_app

    with TestClient(fastapi_app) as c:
        yield c


def register_and_login(client, username="ivan", password="secret123"):
    client.post("/auth/register", json={"username": username, "password": password})
    res = client.post("/auth/login", data={"username": username, "password": password})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_room(client):
    headers = register_and_login(client)
    res = client.post(
        "/rooms",
        json={"name": "Переговорная 101", "capacity": 6, "equipment": ["Проектор", "Доска"]},
        headers=headers,
    )
    assert res.status_code == 201
    room = res.json()
    assert room["name"] == "Переговорная 101"

    res = client.get("/rooms")
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_booking_conflict_returns_409(client):
    headers = register_and_login(client)
    room = client.post(
        "/rooms", json={"name": "Ауд. 5", "capacity": 20, "equipment": []}, headers=headers
    ).json()

    booking_payload = {
        "room_id": room["id"],
        "start_time": "2026-08-01T10:00:00",
        "end_time": "2026-08-01T11:00:00",
        "username": "Пётр",
    }
    res1 = client.post("/bookings", json=booking_payload, headers=headers)
    assert res1.status_code == 201

    overlapping_payload = {
        "room_id": room["id"],
        "start_time": "2026-08-01T10:30:00",
        "end_time": "2026-08-01T11:30:00",
        "username": "Мария",
    }
    res2 = client.post("/bookings", json=overlapping_payload, headers=headers)
    assert res2.status_code == 409


def test_cancel_booking_only_by_owner(client):
    headers_ivan = register_and_login(client, "ivan", "secret123")
    headers_anna = register_and_login(client, "anna", "secret456")

    room = client.post(
        "/rooms", json={"name": "Ауд. 7", "capacity": 10, "equipment": []}, headers=headers_ivan
    ).json()

    booking = client.post(
        "/bookings",
        json={
            "room_id": room["id"],
            "start_time": "2026-08-02T09:00:00",
            "end_time": "2026-08-02T10:00:00",
            "username": "Ivan",
        },
        headers=headers_ivan,
    ).json()

    # Чужой пользователь не может отменить бронь
    res_forbidden = client.delete(f"/bookings/{booking['id']}", headers=headers_anna)
    assert res_forbidden.status_code == 403

    # Владелец может отменить
    res_ok = client.delete(f"/bookings/{booking['id']}", headers=headers_ivan)
    assert res_ok.status_code == 204


def test_room_not_found_returns_404(client):
    res = client.get("/rooms/999")
    assert res.status_code == 404


def test_my_bookings_only_shows_own(client):
    headers_ivan = register_and_login(client, "ivan", "secret123")
    headers_anna = register_and_login(client, "anna", "secret456")

    room = client.post(
        "/rooms", json={"name": "Ауд. 9", "capacity": 8, "equipment": []}, headers=headers_ivan
    ).json()

    client.post(
        "/bookings",
        json={
            "room_id": room["id"],
            "start_time": "2026-08-04T09:00:00",
            "end_time": "2026-08-04T10:00:00",
            "username": "Ivan",
        },
        headers=headers_ivan,
    )
    client.post(
        "/bookings",
        json={
            "room_id": room["id"],
            "start_time": "2026-08-04T11:00:00",
            "end_time": "2026-08-04T12:00:00",
            "username": "Anna",
        },
        headers=headers_anna,
    )

    res_ivan = client.get("/bookings/mine", headers=headers_ivan)
    assert res_ivan.status_code == 200
    assert len(res_ivan.json()) == 1
    assert res_ivan.json()[0]["username"] == "Ivan"

    res_anna = client.get("/bookings/mine", headers=headers_anna)
    assert len(res_anna.json()) == 1
    assert res_anna.json()[0]["username"] == "Anna"
    headers = register_and_login(client)
    room1 = client.post(
        "/rooms", json={"name": "A", "capacity": 5, "equipment": []}, headers=headers
    ).json()
    room2 = client.post(
        "/rooms", json={"name": "B", "capacity": 5, "equipment": []}, headers=headers
    ).json()

    client.post(
        "/bookings",
        json={
            "room_id": room1["id"],
            "start_time": "2026-08-03T09:00:00",
            "end_time": "2026-08-03T10:00:00",
            "username": "X",
        },
        headers=headers,
    )

    res = client.get(
        "/rooms/available",
        params={"start": "2026-08-03T09:30:00", "end": "2026-08-03T09:45:00"},
    )
    ids = [r["id"] for r in res.json()]
    assert room1["id"] not in ids
    assert room2["id"] in ids
