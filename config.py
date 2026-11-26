"""Configuration and category rules for the File Organizer."""

from __future__ import annotations

import os
import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
HISTORY_DIR = APP_DIR / "history"
STATIC_DIR = APP_DIR / "static"

# Ordered: earlier entries win when an extension appears in more than one list.
CATEGORIES: dict[str, tuple[str, ...]] = {
    "PDF": ("pdf",),
    "Ebooks": ("epub", "mobi", "azw", "azw3", "djvu", "fb2", "prc", "lit"),
    "Documents": (
        "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp",
        "rtf", "txt", "md", "csv", "tsv", "json", "xml", "yaml", "yml", "tex",
    ),
    "Images": (
        "jpg", "jpeg", "png", "gif", "bmp", "svg", "webp", "ico", "tif",
        "tiff", "heic", "avif", "psd", "raw", "cr2", "nef",
    ),
    "Video": (
        "mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "mpeg", "mpg",
        "3gp", "m4v", "ts", "m2ts", "vob",
    ),
    "Audio": ("mp3", "wav", "flac", "aac", "ogg", "wma", "m4a", "opus", "aiff", "aif"),
    "Archives": ("zip", "rar", "7z", "tar", "gz", "bz2", "xz", "tgz", "cab", "iso"),
    "Code": (
        "py", "js", "ts", "jsx", "tsx", "html", "htm", "css", "scss", "sass",
        "java", "c", "cpp", "h", "hpp", "cs", "go", "rs", "php", "rb", "sh",
        "ps1", "bat", "cmd", "sql", "swift", "kt", "dart", "vue", "svelte", "lua",
    ),
    "Software": ("exe", "msi", "apk", "deb", "rpm", "appimage", "dmg", "pkg", "jar"),
    "Other": (),
}

EXT_TO_CATEGORY: dict[str, str] = {}
for _folder, _extensions in CATEGORIES.items():
    for _ext in _extensions:
        EXT_TO_CATEGORY.setdefault(_ext, _folder)

CATEGORY_NAMES = tuple(CATEGORIES.keys())
MODE_TYPE = "type"
MODE_DATE = "date"
MODE_TYPE_DATE = "type_date"
VALID_MODES = (MODE_TYPE, MODE_DATE, MODE_TYPE_DATE)

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}$")

# Directories that are never walked into, and never used as destinations.
SKIP_DIR_NAMES = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    "env", ".idea", ".vscode", ".file_organizer_history", "history",
    "System Volume Information", "$RECYCLE.BIN", "AppData",
    "Temporary Internet Files", ".cache", "dist", "build",
}

# Paths the organizer refuses to touch. APP_DIR is protected so the tool cannot
# reorganise its own source files when a parent folder is selected.
def _protected_prefixes() -> list[Path]:
    candidates = [
        os.environ.get("WINDIR", r"C:\Windows"),
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.environ.get("ProgramData", r"C:\ProgramData"),
        str(APP_DIR),
    ]
    seen: list[Path] = []
    for raw in candidates:
        try:
            p = Path(raw).resolve()
        except OSError:
            continue
        if p not in seen:
            seen.append(p)
    return seen


PROTECTED_PREFIXES = _protected_prefixes()

PORT = 8767
HOST = "127.0.0.1"
