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

## Key File Navigation

Both `main.py` and `App.jsx` are ~3200 lines. Key locations:

**main.py**:
- `run_rendering_task()` — the subprocess entry point for all rendering (~line 2542)
- `POST /sync/code_to_builder` — AST-based code→builder parsing (~line 1224)
- `_parse_territory_expr()` — parses Python territory AST nodes to builder JSON
- `_hub_db_conn()` / DB schema init — near the top of the file

**App.jsx**:
- `generatePythonCode()` — builder→code synthesis (~line 2007)
- `formatTerritory(value)` — converts builder territory objects to Python expression strings
- `parseCodeToBuilder()` — calls `/sync/code_to_builder` and updates builder state
- `handleRender()` — orchestrates render requests
- `apiFetch()` — authenticated fetch wrapper used throughout

## Territory Value Format

The most non-obvious data structure in the app. Builder stores territories as nested objects; the backend and Python code use operator expressions (`|`, `-`, `&`).

**Builder JSON format** (stored in `element.value`):
```javascript
// Single GADM string shorthand
"IND"

// Array of operation parts
[
  { op: "union",        type: "gadm",       value: "IND" },
  { op: "union",        type: "gadm",       value: ["PAK", "BGD"] },  // multi-GADM
  { op: "difference",   type: "polygon",    value: "[[lat,lng],...]" },
  { op: "union",        type: "predefined", value: "KURU" },
  { op: "intersection", type: "group",      value: [ ...nested parts ] }
]
```

**Python expression equivalent**:
```python
gadm("IND") | gadm("PAK") | gadm("BGD") - polygon([...]) & KURU
```

`formatTerritory(value)` in App.jsx converts builder→Python. `_parse_territory_expr()` in main.py converts Python AST→builder.

## Python Value Wrapper

Fields that accept arbitrary Python expressions (e.g., `icon`, `position`) use a special wrapper object:
```javascript
{ __pythonExpr__: "some_variable_name" }
```
When generating code, check for this wrapper and emit the raw expression instead of a quoted string. The `getPythonExpr()` utility handles this.

## Builder State Schema

```javascript
// elements array — passed as BuilderRequest.elements
{
  type: "flag"|"river"|"point"|"text"|"path"|"admin"|"admin_rivers"|"dataframe"|"titlebox"|"css"|"python",
  label: string,
  value: any,           // territory for flag, [lat,lng] for point, etc.
  args: {
    period: [start, end],   // time period filter
    note: string,
    level: int,             // admin level (admin type)
    source_type: "naturalearth"|"overpass",  // river type
    icon: object,           // point icon config
    data_column: string,    // dataframe column
    class_name: string,     // css class
  }
}

// options object — passed as BuilderRequest.options
{
  basemaps: [{ url_or_provider, name?, default? }],
  zoom: int,
  focus: [lat, lng],
  slider: { start, end, speed },
  css_rules: [{ selector, style }],
  flag_color_sequences: [{ class_name, colors, step_h, step_s, step_l }],
  admin_color_sequences: [{ colors, step_h, step_s, step_l }],
  data_colormap: { type: "LinearSegmented"|<named>, colors?: string }
}
```

## API Endpoints Summary

**Rendering**: `POST /render/code`, `/render/builder`, `/render/picker`, `/render/territory-library` · `POST /stop`

**Sync**: `POST /sync/code_to_builder` → `{ elements, options, error?, predefined_code? }`

**Search**: `GET /search/gadm?q=`, `GET /search/countries?q=`, `GET /gadm/levels?country=`

**Territory library**: `GET /territory_library/names`, `POST /territory_library/catalog`

**Hub/artifacts**: `GET|PUT /hub/{username}/{kind}/{name}[/{version}]`, `POST .../publish`, `GET /hub/registry`

**Auth**: `POST /auth/signup|login|logout`, `GET /auth/me`, `PUT /auth/me/profile|password`

**Maps**: `GET /maps/{username}/{map_name}`, `POST .../view|vote`, `GET /explore`, `GET /users[/{username}]`

**Draft**: `PUT|GET /draft/current`

## Rendering Pipeline Detail

All rendering runs in a spawned subprocess (not forked) via `multiprocessing`. The subprocess receives a `(task_type, data)` tuple and returns results via a `Queue`. Four task types:

- **`code`** — executes user Python directly; exec globals include xatra, gadm, naturalearth, polygon, overpass, and a `xatrahub()` resolver
- **`builder`** — converts `BuilderRequest` elements/options to xatra method calls, then renders
- **`picker`** — renders a reference admin map for territory selection in the UI
- **`territory_library`** — renders predefined territories as flags for the library browser

Only one subprocess per task type runs at a time (`current_processes` dict + `process_lock`). Rendered HTML is cached in an `OrderedDict` (max 24 entries) keyed by input hash.

## Synchronization Requirements

When modifying data structures or layer types, changes are typically needed in multiple places:

| What you change | Also update |
|---|---|
| Add/modify a layer type | `run_rendering_task` builder branch · `generatePythonCode()` · `/sync/code_to_builder` · `LayerItem.jsx` UI · `Builder.jsx` add-element logic |
| Add a builder option | `BuilderRequest` model · `run_rendering_task` options section · `generatePythonCode()` · `GlobalOptions.jsx` UI · `/sync/code_to_builder` options parsing |
| Add a territory operand type | `_parse_territory_expr()` · `_parse_territory_operand()` · `formatTerritory()` · `TerritoryBuilder.jsx` |
| Change River `source_type` | `run_rendering_task` river branch · `App.jsx` code gen · `/sync/code_to_builder` |

## Auth & Sessions

- Session cookie name: `xatra_session`; guest cookie: `xatra_guest`
- Sessions stored in `hub_sessions` (TTL: 30 days); token stored as SHA256 hash
- Guest users get full functionality; drafts keyed by guest cookie ID
- Reserved usernames (cannot be registered): `guest`, `admin`, `explore`, `users`, `login`, etc.
- Artifact/username names: lowercase alphanumeric + `_`, `.` only

## gadm_index.json

31.8 MB pre-computed GADM search index loaded at startup. Format: `[{ gid, name?, country, level, varname? }, ...]`. Used by `/search/gadm` and `/search/countries` for autocomplete. Do not regenerate casually — it takes time to build.

## Backward Compatibility

Two areas require care when making changes: the database schema and the project JSON format. Both are live data that users accumulate, so breaking changes silently corrupt existing work.

### Database Schema

The database is `xatra_hub.db` (SQLite). Current schema (all tables):

```sql
hub_users       (id, username, password_hash, full_name, bio, is_admin, created_at)
hub_artifacts   (id, user_id, kind, name, alpha_content, alpha_metadata, created_at, updated_at)
                  -- kind ∈ {"map", "lib", "theme"}
                  -- alpha_content: JSON string of the current working version
                  -- alpha_metadata: JSON string of artifact-level metadata
hub_artifact_versions (id, artifact_id, version, content, metadata, created_at)
                  -- version: integer (1, 2, 3 …); exposed as "v1", "v2" etc. in URLs
hub_sessions    (id, user_id, token_hash, created_at, expires_at)
hub_votes       (id, artifact_id, user_id, created_at)
hub_map_views   (id, artifact_id, viewer_key, viewed_at)
hub_drafts      (id, owner_key, project_json, updated_at)
                  -- owner_key: "user:{user_id}" or "guest:{guest_id}"
```

**Migration pattern**: `_init_hub_db()` (main.py ~line 203) runs on every startup. After the `CREATE TABLE IF NOT EXISTS` block it has a lightweight migration section (~line 279) that checks `PRAGMA table_info` and issues `ALTER TABLE … ADD COLUMN` for any columns that don't exist yet. Follow this exact pattern for schema additions.

**Rules for schema changes**:
- **Adding a column**: Add `ALTER TABLE … ADD COLUMN … DEFAULT …` in the migration block. Always supply a sensible default so old rows are valid.
- **Renaming or removing a column**: SQLite makes this painful. Instead, add the new column and write migration logic to populate it from the old one; leave the old column in place (SQLite `ALTER TABLE` cannot drop columns in older versions). If removal is truly required, use `CREATE TABLE … AS SELECT … / DROP TABLE / ALTER TABLE RENAME`.
- **Adding a table**: A `CREATE TABLE IF NOT EXISTS` in the schema block is sufficient; no migration entry needed.
- **Adding a data migration**: Write it inside `_init_hub_db()` after the column migration block. Keep it idempotent (safe to run on every startup). See the existing examples (strip `description` from map metadata, seed default library content) for the pattern.

### Project JSON Format

There are three distinct JSON formats in use. All loading paths already use `|| ''` / `|| {}` / `|| []` guards, so adding new optional fields is safe. **Removing or renaming fields is a breaking change** — old stored data will silently lose that field.

#### Format A — Hub artifact content (current version: **v1**, no version field yet)

Stored in `hub_artifacts.alpha_content` and `hub_artifact_versions.content`. Written by `buildMapArtifactContent()` (App.jsx ~line 1689). Read by `loadMapFromHub()` (App.jsx ~line 687).

```json
{
  "imports_code":    "string  — hub import statements (xatrahub calls)",
  "theme_code":      "string  — CSS theme code",
  "predefined_code": "string  — predefined/territory library code",
  "map_code":        "string  — main Python map code",
  "runtime_code":    "string  — runtime Python code",
  "picker_options": {
    "entries":     [{ "country": "string", "level": "int" }],
    "adminRivers": "boolean"
  },
  "project": {
    "elements":      [...],   // MapElement[] — builder layer array (see Builder State Schema)
    "options":       {...},   // BuilderOptions (see Builder State Schema)
    "predefinedCode": "string",
    "importsCode":   "string",
    "themeCode":     "string",
    "runtimeCode":   "string"
  }
}
```

Note: top-level keys use `snake_case`; keys inside `project` use `camelCase` (mirrors frontend state names). The `project` sub-object mirrors the builder state so the builder can be restored without re-parsing the Python code.

#### Format B — Draft (auto-saved working state)

Stored in `hub_drafts.project_json`. Written by the auto-save `useEffect` (App.jsx ~line 760). Read by `loadDraft()` (App.jsx ~line 731).

```json
{
  "map_name": "string",
  "project": {
    "elements":      [...],
    "options":       {...},
    "code":          "string  — Python code tab contents",
    "predefinedCode": "string",
    "importsCode":   "string",
    "themeCode":     "string",
    "runtimeCode":   "string",
    "pickerOptions": { "entries": [...], "adminRivers": "boolean" }
  }
}
```

Differs from Format A: includes `code` (the raw code-tab text) and `pickerOptions` inside `project`; no top-level code fields.

#### Format C — Exported project file (`project.json` download)

Written by `handleSaveProject()` (App.jsx ~line 1667). This is the user-facing "Save Project" file.

```json
{
  "elements":      [...],
  "options":       {...},
  "predefinedCode": "string",
  "importsCode":   "string",
  "themeCode":     "string",
  "runtimeCode":   "string"
}
```

This is a flat subset of the builder state (no top-level code fields, no picker options).

#### Rules for format changes

1. **Adding a field**: Safe. All loaders use optional chaining / fallback defaults. Just add it.
2. **Removing or renaming a field**: Update the version and add a migration shim:
   - Increment the version comment above (e.g., "current version: **v2**") and add a note describing what changed.
   - In every loading path that reads this format, add a compat check: `const newField = parsed.new_field ?? parsed.old_field ?? defaultValue;`
   - For Format A stored in the database, add a one-time data migration in `_init_hub_db()` to rewrite existing rows.
3. **Structural changes**: Treat like a rename — add a version field (`"format_version": 2`) to the JSON and branch on it in all loaders.
4. **Keep this section updated**: After any format change, update the field listing above and bump the version label.
