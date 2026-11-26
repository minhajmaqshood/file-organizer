"""Core filesystem logic: browse, plan, move and undo."""

from __future__ import annotations

import json
import os
import shutil
import stat
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from config import (
    APP_DIR,
    CATEGORIES,
    CATEGORY_NAMES,
    DATE_PATTERN,
    EXT_TO_CATEGORY,
    HISTORY_DIR,
    MODE_DATE,
    MODE_TYPE,
    MODE_TYPE_DATE,
    PROTECTED_PREFIXES,
    SKIP_DIR_NAMES,
    VALID_MODES,
)


class OrganizerError(Exception):
    """A safe, user-facing error."""


@dataclass
class PlanItem:
    source: str
    destination: str
    category: str
    date: str
    size: int
    name: str


@dataclass
class PlanResult:
    root: str
    mode: str
    items: list[PlanItem]
    skipped_same_place: int
    by_category: dict[str, int]
    total_size: int
    warnings: list[str]


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _is_inside(path: Path, parent: Path) -> bool:
    try:
        return path == parent or parent in path.parents
    except OSError:
        return False


def resolve_path(raw: str, *, allow_drive_root: bool = False) -> Path:
    """Resolve and validate a user-supplied directory path."""
    text = (raw or "").strip().strip('"').strip("'")
    if not text:
        raise OrganizerError("Choose a folder first.")
    try:
        path = Path(text).expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise OrganizerError(f"Folder does not exist: {text}") from exc
    except OSError as exc:
        raise OrganizerError(f"Cannot open that path: {exc}") from exc
    if not path.is_dir():
        raise OrganizerError(f"Not a folder: {text}")
    if not allow_drive_root and path.parent == path:
        raise OrganizerError("Select a folder inside the drive, not the drive root itself.")
    if _is_inside(path, APP_DIR):
        raise OrganizerError("That folder contains this organizer's own files. Pick another folder.")
    return path


def validate_root(raw: str) -> Path:
    path = resolve_path(raw)
    for protected in PROTECTED_PREFIXES:
        if _is_inside(path, protected):
            raise OrganizerError(f"That folder is protected and cannot be reorganised: {protected}")
    return path


def is_hidden(path: Path) -> bool:
    if path.name.startswith("."):
        return True
    try:
        attrs = path.stat().st_file_attributes
        return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0))
    except (OSError, AttributeError):
        return False


def parse_excludes(raw: str | None) -> set[str]:
    if not raw:
        return set()
    parts = raw.replace("\n", ",").replace(";", ",").split(",")
    return {part.strip().lower() for part in parts if part.strip()}


def suggested_roots() -> list[str]:
    home = Path.home()
    names = ("Downloads", "Documents", "Desktop")
    result: list[str] = []
    for name in names:
        candidate = home / name
        if candidate.is_dir():
            result.append(str(candidate))
    return result


# ---------------------------------------------------------------------------
# Directory browser
# ---------------------------------------------------------------------------

def browse(path: str = "") -> dict:
    target = resolve_path(path or str(Path.home()), allow_drive_root=True)
    dirs: list[dict] = []
    try:
        entries = list(target.iterdir())
    except OSError as exc:
        raise OrganizerError(f"Cannot list that folder: {exc}") from exc
    for entry in entries:
        try:
            if entry.is_dir() and not entry.is_symlink():
                dirs.append({"name": entry.name, "path": str(entry), "hidden": is_hidden(entry)})
        except OSError:
            continue
    dirs.sort(key=lambda item: item["name"].lower())
    parent = target.parent if target.parent != target else None
    return {
        "path": str(target),
        "parent": str(parent) if parent else None,
        "dirs": dirs,
        "file_count": sum(1 for entry in entries if entry.is_file()),
    }


# ---------------------------------------------------------------------------
# Scanning and planning
# ---------------------------------------------------------------------------

def scan_files(
    root: Path,
    *,
    recursive: bool,
    include_hidden: bool,
    excludes: set[str],
) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(dirpath)
        kept: list[str] = []
        for name in dirnames:
            low = name.lower()
            child = current / name
            if low in SKIP_DIR_NAMES or low in excludes:
                continue
            if not include_hidden and is_hidden(child):
                continue
            if child.is_symlink() or _is_inside(child, APP_DIR):
                continue
            kept.append(name)
        dirnames[:] = kept

        for name in filenames:
            candidate = current / name
            try:
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                if not include_hidden and is_hidden(candidate):
                    continue
            except OSError:
                continue
            found.append(candidate)

        if not recursive:
            break
    return found


def category_for(path: Path) -> str:
    return EXT_TO_CATEGORY.get(path.suffix.lower().lstrip("."), "Other")


def date_folder_for(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m")
    except OSError:
        return datetime.now().strftime("%Y-%m")


def destination_dir(root: Path, mode: str, category: str, date_folder: str) -> Path:
    if mode == MODE_TYPE:
        return root / category
    if mode == MODE_DATE:
        return root / date_folder
    return root / category / date_folder


def build_plan(options: dict) -> PlanResult:
    root = validate_root(str(options.get("path", "")))
    mode = str(options.get("mode", MODE_TYPE))
    if mode not in VALID_MODES:
        raise OrganizerError(f"Unknown organisation mode: {mode}")

    recursive = bool(options.get("recursive", True))
    include_hidden = bool(options.get("include_hidden", False))
    excludes = parse_excludes(options.get("exclude"))

    files = scan_files(root, recursive=recursive, include_hidden=include_hidden, excludes=excludes)
    items: list[PlanItem] = []
    by_category: dict[str, int] = {name: 0 for name in CATEGORY_NAMES}
    reserved: set[str] = set()
    skipped = 0
    total_size = 0

    for source in files:
        category = category_for(source)
        date_folder = date_folder_for(source)
        dest_dir = destination_dir(root, mode, category, date_folder)

        # Already in the correct destination folder: do nothing on a re-run.
        try:
            if source.parent.resolve() == dest_dir.resolve():
                skipped += 1
                continue
        except OSError:
            pass

        destination = dest_dir / source.name
        key = str(destination).lower()
        if key in reserved or destination.exists():
            stem, suffix = destination.stem, destination.suffix
            counter = 1
            while True:
                candidate = dest_dir / f"{stem} ({counter}){suffix}"
                if str(candidate).lower() not in reserved and not candidate.exists():
                    destination = candidate
                    break
                counter += 1
            key = str(destination).lower()
        reserved.add(key)

        try:
            size = source.stat().st_size
        except OSError:
            size = 0
        total_size += size
        by_category[category] += 1
        items.append(
            PlanItem(
                source=str(source),
                destination=str(destination),
                category=category,
                date=date_folder,
                size=size,
                name=source.name,
            )
        )

    items.sort(key=lambda item: (item.category, item.name.lower()))
    warnings: list[str] = []
    if skipped:
        warnings.append(f"{skipped} file(s) were already in the right folder and were left alone.")
    if not items:
        warnings.append("No files to move with these options.")
    return PlanResult(
        root=str(root),
        mode=mode,
        items=items,
        skipped_same_place=skipped,
        by_category={key: value for key, value in by_category.items() if value},
        total_size=total_size,
        warnings=warnings,
    )


def plan_to_dict(plan: PlanResult) -> dict:
    data = asdict(plan)
    data["count"] = len(plan.items)
    return data


# ---------------------------------------------------------------------------
# Apply and undo
# ---------------------------------------------------------------------------

def _safe_target(destination: Path) -> Path:
    """Avoid overwriting a file that appeared after the preview was built."""
    if not destination.exists():
        return destination
    stem, suffix = destination.stem, destination.suffix
    counter = 1
    while True:
        candidate = destination.with_name(f"{stem} ({counter}){suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _write_history(payload: dict) -> str:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_id = f"{stamp}-{uuid.uuid4().hex[:6]}"
    payload["id"] = log_id
    payload["created"] = datetime.now().isoformat(timespec="seconds")
    target = HISTORY_DIR / f"{log_id}.json"
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return log_id


def apply_plan(options: dict, *, confirm: bool = False) -> dict:
    if not confirm:
        raise OrganizerError("Confirmation is required before moving files.")
    plan = build_plan(options)
    root = Path(plan.root)
    moves: list[dict] = []
    errors: list[dict] = []

    for item in plan.items:
        source = Path(item.source)
        destination = Path(item.destination)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            final = _safe_target(destination)
            shutil.move(str(source), str(final))
            moves.append({"from": str(source), "to": str(final)})
        except OSError as exc:
            errors.append({"name": item.name, "error": str(exc)})

    log_id = _write_history(
        {
            "root": str(root),
            "mode": plan.mode,
            "moves": moves,
            "errors": errors,
            "undone": False,
        }
    )
    return {
        "ok": True,
        "log_id": log_id,
        "moved": len(moves),
        "failed": len(errors),
        "errors": errors,
        "root": str(root),
        "mode": plan.mode,
    }


def _history_path(log_id: str) -> Path:
    if not log_id or not all(ch.isalnum() or ch in "-_" for ch in log_id):
        raise OrganizerError("Invalid history entry.")
    return HISTORY_DIR / f"{log_id}.json"


def list_history() -> list[dict]:
    if not HISTORY_DIR.exists():
        return []
    entries: list[dict] = []
    for path in sorted(HISTORY_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        entries.append(
            {
                "id": data.get("id", path.stem),
                "created": data.get("created", ""),
                "root": data.get("root", ""),
                "mode": data.get("mode", ""),
                "moved": len(data.get("moves", [])),
                "undone": bool(data.get("undone", False)),
            }
        )
    return entries


def undo(log_id: str) -> dict:
    path = _history_path(log_id)
    if not path.exists():
        raise OrganizerError("That history entry no longer exists.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise OrganizerError(f"Could not read that history entry: {exc}") from exc
    if data.get("undone"):
        raise OrganizerError("That run has already been undone.")
    moves = data.get("moves", [])
    if not moves:
        raise OrganizerError("That run did not move any files.")

    restored: list[str] = []
    errors: list[dict] = []
    for move in reversed(moves):
        origin = Path(move.get("from", ""))
        current = Path(move.get("to", ""))
        try:
            if not current.exists():
                errors.append({"name": current.name, "error": "file no longer exists"})
                continue
            origin.parent.mkdir(parents=True, exist_ok=True)
            target = _safe_target(origin)
            shutil.move(str(current), str(target))
            restored.append(str(target))
        except OSError as exc:
            errors.append({"name": current.name, "error": str(exc)})

    # Remove destination folders that are now empty, but never the root itself.
    root = Path(data.get("root", ""))
    folders = sorted(
        {Path(move.get("to", "")).parent for move in moves},
        key=lambda item: len(item.parts),
        reverse=True,
    )
    cleaned = 0
    for folder in folders:
        current = folder
        while current != root and current.exists() and current.parent != current:
            try:
                if any(current.iterdir()):
                    break
                current.rmdir()
                cleaned += 1
            except OSError:
                break
            current = current.parent

    data["undone"] = True
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass

    return {
        "ok": True,
        "restored": len(restored),
        "failed": len(errors),
        "folders_removed": cleaned,
        "errors": errors,
    }
