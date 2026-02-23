1. Critical Username squatting is possible without login via /hub/users/ensure.
main.py:2757, main.py:2763, main.py:2766, main.py:495, main.py:2083. Any caller with just a guest cookie can create arbitrary hub_users rows, and signup later rejects those usernames as already taken.

2. Critical Guest users can create/publish named hub artifacts via username routes, contradicting the intended auth model.
main.py:2017, main.py:2021, main.py:2808, main.py:2812, main.py:2827, main.py:2831
_require_write_identity allows username == guest with any guest cookie; this enables unauthenticated creation/publish under shared guest ownership.

3. Critical Render process control is global, not per user/session; users can disrupt each other.
   main.py:3050, main.py:3065, main.py:3069, main.py:3895, main.py:3898
   /stop can terminate global task slots for any authenticated/guest caller; new renders also terminate prior same-task renders globally.
   
4. High No rate limiting on expensive /render/* endpoints.
   main.py:3928, main.py:3935, main.py:3942, main.py:3949, main.py:51
   Auth endpoints are rate-limited, but rendering endpoints are not, making CPU exhaustion straightforward.
5. High Session and guest cookies are not marked secure.
   main.py:1190, main.py:2063
   Without secure=True, cookies can be sent over plain HTTP in non-TLS deployments.
6. High Arbitrary Python execution is exposed through render/code paths; safe only if strongly network-isolated.
   main.py:3453, main.py:3462, main.py:3845, start_gui.sh:88, main.py:3970
   exec is used on user-provided code, and default startup binds backend to 0.0.0.0.
7. High Race condition when clearing current_processes can clobber a newer process reference.
   main.py:3916, main.py:3917
   Slot is set to None unconditionally after join; concurrent newer process assignment can be lost.
8. Medium Potential request hangs from unbounded join() while holding lock.
   main.py:3070, main.py:3899
   Both joins are unbounded; if termination stalls, requests can block while process_lock is held.
9. Medium postMessage handlers rely on origin but do not validate message source window.
   frontend/src/App.jsx:1347, frontend/src/App.jsx:2052
   Messages from unintended same-origin/null-origin contexts can mutate UI state or spoof thumbnail responses.
10. Medium GADM indexes are read without lock while background rebuild can mutate them.
   main.py:811, main.py:864, main.py:912, main.py:939, main.py:964
   Read/write synchronization is inconsistent.
11. Medium Render cache key ignores external dependency freshness (e.g., xatrahub content changes).
   main.py:3874, main.py:3877, main.py:3883
   Same request payload can serve stale render output after imported hub artifacts change.
12. Medium N+1 query patterns in high-traffic listing endpoints.
   main.py:2334, main.py:2388, main.py:2398, main.py:2432, main.py:2967, main.py:3024
   /explore, /users, and /hub/registry do repeated per-row queries.
13. Low Startup migration rewrites all map metadata rows every boot.
   main.py:438, main.py:442, main.py:456
   Idempotent but O(n) writes at startup.
14. Low Multiple silent except/pass blocks hide failures and complicate debugging.
   main.py:386, main.py:437, main.py:829, main.py:884, main.py:3422, main.py:3750
15. Low Legacy URL parsing bug for old-style version path without v prefix.
   frontend/src/App.jsx:56, frontend/src/App.jsx:58
   /{username}/map/{name}/1 is treated as alpha instead of version 1.
16. Low Frontend lint baseline has real maintainability debt (unused state, hook deps, config lint mismatch).
   frontend/src/App.jsx:174, frontend/src/App.jsx:1928, frontend/src/components/Builder.jsx:1, frontend/src/components/GlobalOptions.jsx:71, frontend/vite.config.js:8

--------

Review of Code review

Point 1.

CONFIRMED, FIXABLE

  The attack chain is real:
  1. Any request to the server gets an xatra_guest cookie automatically
  2. Guest calls POST /hub/users/ensure with {"username": "alice"}
  3. _hub_ensure_user does INSERT OR IGNORE INTO hub_users(username, created_at) — creates a row with no password_hash
  4. Alice tries to sign up later; auth_signup at line 2083 does SELECT id FROM hub_users WHERE username = ?, finds the row, returns 409

Is the endpoint even needed by the frontend? No — the frontend has zero calls to /hub/users/ensure.

Suggested action: remove /hub/users/ensure.

Point 2.

CONFIRMED, but lower severity than labelled

  The _require_write_identity exemption at lines 2017-2023 does allow any guest to PUT /hub/guest/map/anything/alpha or POST /hub/guest/map/anything/publish directly via the API. Confirmed.

  However, the frontend guards this at line 2184:
  if (!currentUser.is_authenticated || isReadOnlyMap || !normalizedMapName) return;
  The alpha auto-save bails immediately for unauthenticated users. So this is not reachable through normal UI use — it requires deliberate raw API calls. That makes it an API-level
  vulnerability, not a UI one.

  The consequence: a bad actor with a guest cookie can pollute the public /explore listing with spam maps under the shared guest username, and any guest can clobber any other guest's hub
  artifacts (since all guests share the guest username).

  Fix: Remove the guest exemption entirely from _require_write_identity. Lines 2017-2023 become just:
  raise HTTPException(status_code=401, detail="Login required")
  This is safe because: (a) the frontend already never reaches this path for guests, and (b) guest work goes through /draft/current, not hub artifact routes. No frontend behavior changes.

  ---
  On "critical" labelling: Issue 1 genuinely earns critical since it can permanently block any username from being registered with just a guest cookie and a single HTTP call (rate-limited to
   10/hour/IP, so ~240 squats/day per IP, trivially scripted across IPs). Issue 2 is more "medium" in practice — it requires deliberate API abuse, and the shared guest namespace provides no
  persistent identity advantage to the attacker. The reviewer likely labeled it critical because of the stated auth model violation, not the practical impact.

  Both 1 and 2 are straightforward single-location fixes.

Point 3 (Critical) — Global render process control: LEGIT.
Confirmed at lines 3065-3072 and 3895-3901. The current_processes dict is flat by task type, not keyed by user/session. Any authenticated caller can /stop anyone else's active render.
Genuinely problematic in a multi-user context.

Point 4 (High) — No rate limiting on /render/*: LEGIT.
Lines 3928-3954 confirm no rate-limiting middleware. A client could spawn concurrent render subprocesses freely. The processes do have a 60s timeout, but CPU exhaustion is still easy.

Point 5 (High) — Cookies not marked secure: LEGIT.
Confirmed at both sites. Lines 1190 and 2063 set httponly=True, samesite="lax" but no secure=True. Tokens can be transmitted over plain HTTP.

Point 6 (High) — Arbitrary Python exec: LEGIT, but it's an acknowledged design constraint.
The exec() calls at 3453/3459/3462 are intentional — the app is a Python execution sandbox. The real exposure (noted by the reviewer) is that start_gui.sh binds to 0.0.0.0 by default,
meaning it's reachable from the network without any sandboxing. This is accurate but more of a deployment note than a code bug.

Point 7 (High) — Race condition clobbering current_processes: LEGIT and subtle.
The sequence: (1) Render A acquires lock, registers current_processes[t] = p_A, releases lock. (2) queue.get(timeout=60) runs outside the lock. (3) Meanwhile Render B acquires lock,
terminates p_A, registers current_processes[t] = p_B. (4) Render A finishes its queue.get(), then acquires lock and sets current_processes[t] = None — clobbering p_B's reference. p_B can
now never be terminated by /stop or by a subsequent render. This is a genuine bug.

Point 8 (Medium) — Unbounded join() while holding lock: LEGIT.
Both /stop (line 3070) and run_in_process (line 3899) call previous.join() inside with process_lock:. If a subprocess ignores SIGTERM (e.g., stuck in C-level I/O), the lock is held
indefinitely, blocking all other render threads.

Point 9 (Medium) — postMessage without source validation: LEGIT but overstated.
Main handler (line 1347) checks event.origin but not event.source, so any same-origin script could spoof messages. The thumbnail handler at line 2052 doesn't check origin at all — any
window could race a fake xatra_thumbnail_response. Practically low-risk since same-origin code execution already implies compromise, but the thumbnail handler has no guard.

Point 10 (Medium) — GADM indexes read without lock: MOSTLY THEORETICAL.
rebuild_country_indexes() (line 793, 797) replaces the module-level list/dict references rather than mutating in place. In CPython, due to the GIL, a for item in GADM_INDEX loop captures a
reference to the list object at start of iteration — replacing GADM_INDEX mid-loop doesn't corrupt the ongoing iteration. The "medium" severity is an overstatement for CPython. It would
matter in implementations without a GIL.

Point 11 (Medium) — Cache key ignores xatrahub dependency freshness: LEGIT.
Cache is keyed on the raw request payload hash (line 3881). If code calls xatrahub() and the referenced hub artifact is updated, the cache returns stale HTML. Accurate.

Point 12 (Medium) — N+1 queries in listing endpoints: LEGIT.
/explore (lines 2388-2389) calls _map_vote_count and _map_view_count per row. /users (line 2432) calls _user_public_profile per row. These are extra SELECTs per result. Not a crisis at
current scale but a real inefficiency.

Point 13 (Low) — Startup migration rewrites all metadata every boot: LEGIT.
Lines 438-460 do an unconditional UPDATE on every map artifact and version row every startup. It's idempotent but wasteful. A guard checking whether the description key actually exists in
alpha_metadata before rewriting would avoid the O(n) writes.

Point 14 (Low) — Silent except: pass blocks: LEGIT.
Confirmed at the listed lines. Swallowing exceptions silently is real debugging debt.

Point 15 (Low) — Legacy URL version parsing bug: LEGIT.
Line 58: /srajma/map/indic/1 doesn't match /^v\d+$/i (needs the v prefix), so falls through to the final else if (which checks for "alpha"), then fails that too — leaving version at its
initialized 'alpha' value. Old-style integer version URLs silently open alpha. This is a real bug in the backwards-compat path.

Point 16 (Low) — Frontend lint debt: LEGIT.
Consistent with the scale of App.jsx (~3200 lines). Not individually verified but plausible.

