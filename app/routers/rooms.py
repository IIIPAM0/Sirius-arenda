from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import get_current_user
from app.models import Booking, Room, RoomCreate, RoomUpdate, UserPublic
from app.services import parse_dt, room_is_free_for_window
from app.storage import bookings_table, rooms_table

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.post("", response_model=Room, status_code=status.HTTP_201_CREATED)
def create_room(room_in: RoomCreate, current_user: UserPublic = Depends(get_current_user)):
    """Создание нового пространства (требуется авторизация)."""
    room = {"id": rooms_table.next_id(), **room_in.model_dump()}
    rooms_table.insert(room)
    return room


@router.get("", response_model=list[Room])
def list_rooms(
    min_capacity: int | None = Query(default=None, ge=1, description="Минимальная вместимость"),
    equipment: list[str] | None = Query(default=None, description="Требуемое оборудование"),
):
    """Список пространств с опциональной фильтрацией по вместимости и оборудованию."""
    rooms = rooms_table.all()
    if min_capacity is not None:
        rooms = [r for r in rooms if r["capacity"] >= min_capacity]
    if equipment:
        required = {e.lower() for e in equipment}
        rooms = [r for r in rooms if required.issubset({e.lower() for e in r.get("equipment", [])})]
    return rooms


@router.get("/available", response_model=list[Room])
def available_rooms(
    start: datetime = Query(..., description="Начало интересующего интервала, ISO 8601"),
    end: datetime = Query(..., description="Конец интересующего интервала, ISO 8601"),
    capacity: int | None = Query(default=None, ge=1, description="Минимальная вместимость"),
):
    """Поиск свободных пространств на заданный интервал (доп. балл)."""
    if end <= start:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "end должен быть позже start")
    rooms = rooms_table.all()
    if capacity is not None:
        rooms = [r for r in rooms if r["capacity"] >= capacity]
    return [r for r in rooms if room_is_free_for_window(r["id"], start, end)]


@router.get("/{room_id}", response_model=Room)
def get_room(room_id: int):
    room = rooms_table.get("id", room_id)
    if room is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пространство не найдено")
    return room


@router.put("/{room_id}", response_model=Room)
def update_room(
    room_id: int, room_in: RoomUpdate, current_user: UserPublic = Depends(get_current_user)
):
    """Редактирование пространства (требуется авторизация)."""
    if rooms_table.get("id", room_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пространство не найдено")

    def updater(existing: dict) -> dict:
        data = room_in.model_dump(exclude_unset=True)
        existing.update(data)
        return existing

    return rooms_table.update("id", room_id, updater)


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(room_id: int, current_user: UserPublic = Depends(get_current_user)):
    """Удаление пространства (требуется авторизация)."""
    if not rooms_table.delete("id", room_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пространство не найдено")


@router.get("/{room_id}/bookings", response_model=list[Booking])
def room_bookings_for_date(room_id: int, date: date = Query(..., description="Дата в формате YYYY-MM-DD")):
    """Список бронирований конкретной комнаты на выбранную дату."""
    if rooms_table.get("id", room_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пространство не найдено")
    result = []
    for b in bookings_table.all():
        if b["room_id"] != room_id:
            continue
        if parse_dt(b["start_time"]).date() == date:
            result.append(b)
    return result
