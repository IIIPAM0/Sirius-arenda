"""
Простое потокобезопасное JSON-хранилище.

Каждая "таблица" — это отдельный .json файл со списком объектов (dict).
Все операции защищены threading.Lock, чтобы избежать гонок при
одновременных запросах (FastAPI может обрабатывать запросы в разных потоках).
"""
import json
import threading
from pathlib import Path
from typing import Any, Callable, TypeVar

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

T = TypeVar("T")

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _get_lock(name: str) -> threading.Lock:
    with _locks_guard:
        if name not in _locks:
            _locks[name] = threading.Lock()
        return _locks[name]


class JSONTable:
    """Обёртка над одним JSON-файлом, хранящим список записей."""

    def __init__(self, filename: str):
        self.path = DATA_DIR / filename
        self.lock = _get_lock(filename)
        if not self.path.exists():
            self._write_raw([])

    def _read_raw(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            return json.loads(content)

    def _write_raw(self, data: list[dict[str, Any]]) -> None:
        tmp_path = self.path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        tmp_path.replace(self.path)

    def all(self) -> list[dict[str, Any]]:
        with self.lock:
            return self._read_raw()

    def get(self, id_field: str, id_value: Any) -> dict[str, Any] | None:
        with self.lock:
            for item in self._read_raw():
                if item.get(id_field) == id_value:
                    return item
        return None

    def insert(self, item: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            data = self._read_raw()
            data.append(item)
            self._write_raw(data)
        return item

    def update(
        self, id_field: str, id_value: Any, updater: Callable[[dict[str, Any]], dict[str, Any]]
    ) -> dict[str, Any] | None:
        with self.lock:
            data = self._read_raw()
            for i, item in enumerate(data):
                if item.get(id_field) == id_value:
                    updated = updater(item)
                    data[i] = updated
                    self._write_raw(data)
                    return updated
        return None

    def delete(self, id_field: str, id_value: Any) -> bool:
        with self.lock:
            data = self._read_raw()
            new_data = [item for item in data if item.get(id_field) != id_value]
            if len(new_data) == len(data):
                return False
            self._write_raw(new_data)
        return True

    def next_id(self) -> int:
        """Простой инкрементный ID на основе текущего максимума."""
        with self.lock:
            data = self._read_raw()
            if not data:
                return 1
            return max(item.get("id", 0) for item in data) + 1


rooms_table = JSONTable("rooms.json")
bookings_table = JSONTable("bookings.json")
users_table = JSONTable("users.json")
