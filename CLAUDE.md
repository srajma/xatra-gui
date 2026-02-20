# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Xatra Studio GUI — a full-stack web app for creating interactive historical/administrative maps. It's the visual interface for the `xatra` Python library ("the matplotlib of maps"). Users build maps via a visual Builder or a Python code editor, with bidirectional sync between the two.

## Commands

```bash
# Start everything (backend on :8088, frontend on :5188)
./start_gui.sh
```

## Architecture

**Backend**: FastAPI (`main.py`, single large file) — handles map rendering, GADM search, user auth, and the XatraHub artifact platform (maps/libraries/themes with versioning). SQLite database (`xatra_hub.db`). Map rendering runs in isolated subprocesses via multiprocessing.

**Frontend**: React 19 + Vite (rolldown-vite) + Tailwind CSS 4. Main app logic in `frontend/src/App.jsx` (large file). Components in `frontend/src/components/`.

**Key frontend components**:
- `Builder.jsx` — visual map builder with layer management
- `CodeEditor.jsx` — Monaco-based Python code editor
- `TerritoryBuilder.jsx` — territory composition UI (union `|`, subtract `-`, intersect `&`)
- `MapPreview.jsx` — Leaflet-based map renderer
- `GlobalOptions.jsx` — map-level settings
- `LayerItem.jsx` — individual layer configuration
- `AutocompleteInput.jsx` — GADM territory search

**Rendering pipeline**: Frontend → `POST /render` → backend spawns subprocess → executes xatra Python code → returns HTML string → displayed in iframe.

**Bidirectional sync**: Builder state ↔ Python code. `POST /sync/code_to_builder` parses Python back to Builder JSON. Code-to-builder direction goes through the backend; builder-to-code is done client-side.

## Dependencies

- Python 3.12+ required (xatra requirement). Uses `uv` for dependency management.
- The `xatra` library is installed as an editable dependency from `../xatra.master` (sibling directory).
- Frontend uses npm. `vite` is overridden to `rolldown-vite@7.2.5`.

## Layer Types

Flag, River, Admin, AdminRivers, Path, Point, Text, Dataframe, TitleBox, CSS, Python — each has corresponding builder UI and Python code generation.

## Database

XatraHub platform with tables: `hub_users`, `hub_artifacts`, `hub_artifact_versions`, `hub_sessions`, `hub_votes`, `hub_map_views`, `hub_drafts`. Auth uses PBKDF2 password hashing with session tokens.
