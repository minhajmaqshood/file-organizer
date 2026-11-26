# File Organizer

A small local web app with a Python backend. Pick any folder on this computer, preview exactly how its files will be grouped, then move them — with a one-click undo for the whole run.

Nothing is uploaded, and the server only listens on `127.0.0.1`.

## Run it

Double-click `run.cmd`, or from a terminal:

```
cd D:\xampp\htdocs\test1\file-organizer
python -m uvicorn app:app --host 127.0.0.1 --port 8767
```

Then open:

```
http://127.0.0.1:8767/
```

Requirements: Python 3.10+ with `fastapi` and `uvicorn` (both already installed here).

## Using it

1. **Choose the folder** — paste a path, click one of the suggested folders, or use **Browse folders…** to walk the directory tree and click **Select this folder**.
2. **Choose how to organise**:
   - **By type** → `PDF/`, `Images/`, `Video/`, `Audio/`, `Documents/`, `Ebooks/`, `Archives/`, `Code/`, `Software/`, `Other/`
   - **By date** → `2026-11/`, `2026-10/`, … using each file's modified date
   - **Type + date** → `Images/2026-11/`, `Documents/2026-11/`, …
3. Options: include subfolders (on by default), include hidden files (off), and exclude folder names by comma (e.g. `temp, backups`).
4. Click **Preview changes**. Nothing moves at this stage — you get a table of every source → destination path, plus totals by category.
5. Click **Organise files** and confirm.
6. **Recent runs** at the bottom lists every run. **Undo this run** puts all its files back and removes the folders it created (if empty).

## Safety rules

* Files are only ever **moved inside the folder you selected** — never copied, deleted, or sent anywhere.
* Drive roots (`D:\`), Windows/Program Files/ProgramData, this tool's own folder, symlinks, and common system/cache folders (`node_modules`, `.git`, `__pycache__`, `AppData`, `$RECYCLE.BIN`, …) are refused or skipped.
* A file already sitting in its correct destination folder is left alone, so re-running the tool is safe.
* Name collisions are resolved with ` (1)`, ` (2)`, … — existing files are never overwritten.
* A preview is required before organising; the server re-checks the plan when you confirm and independently re-checks collisions at move time.
* Undo logs are JSON files in `history/`. Keep them if you want to reverse a run later.
* The HTTP service rejects any request not coming from localhost and is bound to `127.0.0.1`.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/status` | Python version, port, suggested folders, history count |
| GET | `/api/browse?path=…` | List subfolders for the folder picker |
| POST | `/api/preview` | Build the move plan, no changes |
| POST | `/api/organize` | Execute the plan (requires `confirm: true`) |
| GET | `/api/history` | List undo entries |
| POST | `/api/undo` | Restore a run by `log_id` |

Preview/organise body:

```json
{
  "path": "D:\\Downloads",
  "mode": "type",
  "recursive": true,
  "include_hidden": false,
  "exclude": "temp, backups"
}
```

## Files

```
file-organizer/
├── app.py              FastAPI service and routes
├── organizer.py        browse / plan / move / undo logic
├── config.py           categories, protected paths, settings
├── static/             index.html, style.css, app.js
├── history/            undo logs (created at runtime)
├── run.cmd             launcher
└── README.md
```
