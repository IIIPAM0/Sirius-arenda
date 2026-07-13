from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user
from app.models import Booking, BookingCreate, UserPublic
from app.services import has_overlap
from app.storage import bookings_table, rooms_table

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=Booking, status_code=status.HTTP_201_CREATED)
def create_booking(booking_in: BookingCreate, current_user: UserPublic = Depends(get_current_user)):
    """Создание бронирования с проверкой доступности пространства."""
    if rooms_table.get("id", booking_in.room_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пространство не найдено")

    if has_overlap(booking_in.room_id, booking_in.start_time, booking_in.end_time):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Пространство уже забронировано на выбранное время",
        )

    booking = {
        "id": bookings_table.next_id(),
        "room_id": booking_in.room_id,
        "start_time": booking_in.start_time.isoformat(),
        "end_time": booking_in.end_time.isoformat(),
        "username": booking_in.username,
        "status": "active",
        "owner_id": current_user.id,
    }
    bookings_table.insert(booking)
    return booking


@router.get("/mine", response_model=list[Booking])
def my_bookings(current_user: UserPublic = Depends(get_current_user)):
    """Список бронирований текущего пользователя (для удобного отображения в интерфейсе)."""
    return [b for b in bookings_table.all() if b.get("owner_id") == current_user.id]


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_booking(booking_id: int, current_user: UserPublic = Depends(get_current_user)):
    """Отмена бронирования. Пользователь может отменять только свои брони."""
    booking = bookings_table.get("id", booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Бронирование не найдено")
    if booking.get("owner_id") != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нельзя отменить чужое бронирование")
    if booking["status"] == "cancelled":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Бронирование уже отменено")

    def updater(existing: dict) -> dict:
        existing["status"] = "cancelled"
        return existing

    bookings_table.update("id", booking_id, updater)
