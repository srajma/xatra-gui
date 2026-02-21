How Drafts Work                                                                                                                                                                             
                                                                                                                                                                                            
What a "draft" is vs. the alpha version                                                                                                                                                     
                                                                                                                                                                                            
These are two completely separate concepts that are easy to confuse:

- Draft (hub_drafts table): A single auto-saved workspace state. It captures the full working state of the editor (code, builder elements, options, predefined code, etc.) — essentially
"what's currently open in my editor tab." It is not a named artifact; it has no version history.
- Alpha version (hub_artifacts.alpha_content): The current working version of a named, owned map artifact (e.g., /srajma/map/indic). It is the mutable tip of a named map. When you publish,
  a snapshot of alpha is copied to hub_artifact_versions (v1, v2, ...) and alpha continues to be editable. Alpha ≠ draft — it's a named artifact that belongs to a specific user under a
specific map name.

So: draft = "unsaved scratch pad"; alpha = "saved-but-unpublished version of a named map you own."

One draft per user (and per guest)

The hub_drafts table has owner_key TEXT NOT NULL UNIQUE. The owner key is either user:{id} for logged-in users or guest:{guest_id} for guests. Because it's UNIQUE, each identity gets
exactly one draft — there is no concept of multiple named drafts.

Non-logged-in users and drafts

Yes, guests can have a draft. When the frontend calls PUT /draft/current unauthenticated, the backend calls _ensure_guest_id() which:
1. Reads the xatra_guest cookie (a random 24-char hex token)
2. If absent, generates one and sets it as an httponly; samesite=lax; max_age=1 year cookie

The guest's draft is stored in the database (hub_drafts), keyed by guest:{guest_id}. The xatra_guest cookie is only the key to look up that DB row — the actual content lives server-side,
not in a browser storage API. One draft per guest identity (cookie).

Auto-save timing

The auto-save fires via a useEffect with an 800ms debounce — it runs 800ms after any change to: normalizedMapName, builderElements, builderOptions, code, predefinedCode, importsCode,
themeCode, or runtimeCode. So it triggers on essentially every edit, debounced. There is no "first save" concept; it's continuous.

Drafts are never cleared

There is no code anywhere that deletes a draft row. The PUT /draft/current always does an upsert (INSERT ... ON CONFLICT DO UPDATE). Drafts accumulate in the table forever unless you
manually purge them from the DB. This is a potential issue — guest drafts in particular will pile up indefinitely with no expiry or cleanup mechanism.

When is the draft loaded?

On page load, if the route is the editor without a specific owner/map (i.e., the scratch editor), and route.newMap is false, loadDraft() is called. If route.newMap is true,
applyNewMapDefaults() is called instead (blank slate). So navigating to "new map" skips the draft restore.

---
Map Access and Visibility

Are all maps publicly visible?

Sort of — but with a nuance:

- Alpha version: Only accessible by the owner. hub_get_artifact_version explicitly checks: if version == "alpha", it requires the caller to be authenticated as the artifact owner,
otherwise returns 403. So alpha_content is private.
- Published versions (v1, v2, ...): No auth check — fully public, returned to anyone.
- Explore page (GET /explore): Lists all maps from all users (no filter for "published only" — it lists maps that exist in hub_artifacts, including ones that have never been published,
using their alpha_metadata). This is a subtle issue: a map can appear in explore even if it has no published version.

Are drafts publicly visible?

No. There are no GET endpoints for another user's draft. GET /draft/current only returns the calling user's own draft (identified by their session or guest cookie).

Editing and authentication

Write access is enforced by _require_write_identity() on PUT /hub/{username}/{kind}/{name}/alpha and POST /hub/{username}/{kind}/{name}/publish. The check:
- If logged in: your username must match the URL {username}, else 403.
- If not logged in: the URL {username} must be "guest", and you must have a guest cookie; otherwise 401.

So authenticated users can only write to their own artifacts. The frontend enforces this too: isReadOnlyMap is true when route.owner !== normalizedHubUsername or the version isn't alpha.
When read-only, the UI shows a "Fork" button instead of "Save."

---
Issues / Things That Don't Quite Follow Best Practices

1. No draft TTL/cleanup: Guest drafts accumulate forever. In a real deployment you'd want a periodic cleanup job (e.g., DELETE FROM hub_drafts WHERE owner_key LIKE 'guest:%' AND updated_at
  < datetime('now', '-90 days')).
2. Explore shows unpublished maps: GET /explore lists all hub_artifacts of kind map regardless of whether they have any published version. A map that's been created but never published
shows up in explore, but clicking it would 403 (since maps_get defaults to version=alpha which is owner-only). The frontend would need to handle that gracefully. Probably you want explore
to only list maps that have at least one published version, or the frontend should default to the latest published version when loading someone else's map.
3. Guest writes to "guest" namespace: Guests can save alpha artifacts under the guest username. All guest users share a single guest namespace in hub_artifacts — so any guest can overwrite
  any other guest's named map if they happen to pick the same map name (there's no per-cookie isolation for artifacts, only for drafts). This is probably fine if guests aren't expected to
have persistent named maps, but it's worth being aware of.
4. Draft ≠ alpha, but no explicit link: If you're working on /srajma/map/indic, the editor auto-saves both to the draft (workspace state) and to alpha (via handleAutoSave → PUT
/hub/.../alpha). These are independent saves. If you then navigate away and come back without a specific map URL, you'll restore from draft (which may or may not match the last-saved
alpha). The relationship isn't formally tracked.


--------

 Yes — and there's a significant security hole here. Let me lay it all out.                                                                                                                  
                                                                                                                                                                                              
  How xatrahub imports work                                                                                                                                                                   
                                                                                                                                                                                              
  Default version is alpha                                                                                                                                                                    
                                                                                                                                                                                              
  buildImportPath always bakes the version into the path string (App.jsx:469-471):                                                                                                            
                                                                                                                                                                                              
  const v = String(versionOverride ?? entry.selected_version ?? 'alpha');
  return `/${entry.username}/${entry.kind}/${entry.name}/${v}`;

  So serializeHubImports always emits something like xatrahub("/srajma/lib/indic/alpha") unless the user has explicitly chosen a published version. The default indic import hardcodes /alpha
  as well (main.py:373). When you add a new import via the UI, addHubImportLine (App.jsx:597) tries to pick the latest published version from artifactVersionOptions, but falls back to
  'alpha' if the artifact has no published versions yet.

  The security hole: alpha is NOT protected in the rendering subprocess

  The HTTP endpoint hub_get_artifact_version (main.py:2294-2339) explicitly blocks alpha access for non-owners:

  if str(version).strip().lower() == "alpha":
      caller = _request_user(conn, http_request)
      if caller is None or caller["username"] != artifact["username"]:
          raise HTTPException(status_code=403, detail="Alpha content is only accessible by the owner")

  But the xatrahub() function inside the rendering subprocess calls _hub_load_content() directly (main.py:2646), which has no such check:

  if str(version).lower() == "alpha":
      return {
          ...
          "content": artifact["alpha_content"] or "",  # no auth check
      }

  So any user can write xatrahub("/otheruser/lib/mylib/alpha") in their map code, trigger a render, and read that other user's unpublished alpha content. The HTTP-level protection is
  completely bypassed by going through the render path.

  This means alpha is not actually private — it's only private at the REST API layer. Any authenticated or guest user with access to the render endpoint can read any artifact's alpha
  content.

  The _draft_version field

  _draft_version is just a transient UI state for the version picker dropdown — the pending selection before the user clicks "Apply." It doesn't affect the path that gets serialized; only
  selected_version does. When you apply a version switch, both are set to the chosen value (App.jsx:854-858). It's a minor UI wart but otherwise harmless.

  ---
  Summary of issues

  Issue: Alpha content readable via render path
  Impact: Any user can read any other user's unpublished alpha artifact by importing it as xatrahub("/victim/lib/name/alpha")
  ────────────────────────────────────────
  Issue: Default version is "alpha"
  Impact: Imports to artifacts with no published versions silently pin to alpha, so they break for other users if the owner's alpha changes
  ────────────────────────────────────────
  Issue: No "latest published" fallback
  Impact: If you import /srajma/lib/indic/alpha and publish v1, other users' imports still track the mutable alpha tip rather than the stable published version

  The fix for the security hole would be to add an auth/ownership check in _hub_load_content — or alternatively, pass the rendering user's identity into the subprocess and check it there
  before returning alpha content.

