from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import auth, bookings, rooms

app = FastAPI(
    title="Сириус.Аренда",
    description="REST API для бронирования переговорных комнат и учебных пространств",
    version="1.0.0",
)

app.include_router(auth.router)
app.include_router(rooms.router)
app.include_router(bookings.router)

STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Сириус.Аренда API. См. документацию на /docs"}
