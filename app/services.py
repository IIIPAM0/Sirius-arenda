from datetime import datetime

from app.storage import bookings_table


def parse_dt(value) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def has_overlap(room_id: int, start: datetime, end: datetime, exclude_booking_id: int | None = None) -> bool:
    """Проверяет, пересекается ли [start, end) с любой активной бронью этой комнаты."""
    for b in bookings_table.all():
        if b["room_id"] != room_id or b["status"] != "active":
            continue
        if exclude_booking_id is not None and b["id"] == exclude_booking_id:
            continue
        existing_start = parse_dt(b["start_time"])
        existing_end = parse_dt(b["end_time"])
        # Пересечение интервалов: start < existing_end AND end > existing_start
        if start < existing_end and end > existing_start:
            return True
    return False


def room_is_free_for_window(room_id: int, start: datetime, end: datetime) -> bool:
    return not has_overlap(room_id, start, end)
