"""Local-only web frontend for the Python File Organizer."""

from __future__ import annotations

import sys

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import organizer
from config import APP_DIR, HOST, PORT, STATIC_DIR

app = FastAPI(title="File Organizer", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

ALLOWED_HOSTS = {"127.0.0.1", "::1", "localhost"}


@app.middleware("http")
async def local_only(request: Request, call_next):
    host = request.client.host if request.client else ""
    if host not in ALLOWED_HOSTS:
        return JSONResponse(
            status_code=403,
            content={"ok": False, "message": "This tool only runs on this computer (localhost)."},
        )
    return await call_next(request)


class Options(BaseModel):
    path: str = ""
    mode: str = "type"
    recursive: bool = True
    include_hidden: bool = False
    exclude: str = ""
    confirm: bool = False


class UndoRequest(BaseModel):
    log_id: str


def fail(exc: Exception, status: int = 400) -> JSONResponse:
    return JSONResponse(status_code=status, content={"ok": False, "message": str(exc)})


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
def status():
    return {
        "ok": True,
        "python": sys.version.split()[0],
        "host": HOST,
        "port": PORT,
        "suggestions": organizer.suggested_roots(),
        "history_count": len(organizer.list_history()),
    }


@app.get("/api/browse")
def browse(path: str = ""):
    try:
        return {"ok": True, **organizer.browse(path)}
    except organizer.OrganizerError as exc:
        return fail(exc)


@app.post("/api/preview")
def preview(options: Options):
    try:
        return {"ok": True, **organizer.plan_to_dict(organizer.build_plan(options.model_dump()))}
    except organizer.OrganizerError as exc:
        return fail(exc)


@app.post("/api/organize")
def organize(options: Options):
    try:
        return organizer.apply_plan(options.model_dump(), confirm=options.confirm)
    except organizer.OrganizerError as exc:
        return fail(exc)


@app.get("/api/history")
def history():
    return {"ok": True, "entries": organizer.list_history()}


@app.post("/api/undo")
def undo(payload: UndoRequest):
    try:
        return organizer.undo(payload.log_id)
    except organizer.OrganizerError as exc:
        return fail(exc)


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
