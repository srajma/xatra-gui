  ---                                                                                                                                                                                         
  Code Review: Actionable Issues                                                                                                                                                              
                                                                                                                                                                                              
  Security                                                                                                                                                                                    
                                                                                                                                                                          !!! FALSE ALARM !!!
  !!! DO NOT TRY FIXING S1, IT IS FINE !!!
  !!! Misunderstands the intended design. The CLAUDE.md explicitly states guest users get full functionality including rendering. Adding
  _require_write_identity would break the entire guest flow. Rate limiting (S2) is the correct fix. !!!                      
  #: S1
  Severity: Critical
  Location: main.py:3266-3278
  Issue: No auth on render endpoints. /render/code, /render/builder, etc. accept arbitrary Python code and execute it in subprocesses with no authentication or authorization. CORS only provides client-side protection.
  Action: Add _require_write_identity / session check before spawning any subprocess.
  ────────────────────────────────────────
  #: S2
  Severity: Critical
  Location: main.py:3197-3250
  Issue: No rate limiting on render endpoints. The subprocess-based render pipeline has no rate limiting whatsoever, making CPU-exhaustion trivial.
  Action: Add _check_rate_limit calls to /render/* endpoints.
  ────────────────────────────────────────
  #: S3
  Severity: High
  Location: main.py:48-60
  Issue: _rate_limit_store is per-process and leaks. Doesn't work with multiple workers. The outer dict grows indefinitely — every unique IP key accumulates forever; only timestamps within
    the sliding window are pruned.
  Action: Add a periodic cleanup pass or use a TTL cache; or use Redis if multi-worker.
  ────────────────────────────────────────
  
  !!! FALSE ALARM !!!
  !!! DO NOT TRY FIXING s4, IT'S FINE !!!
  
  #: S4
  Severity: High
  Location: App.jsx:295, 977, 1245, 1259
  Issue: postMessage uses '*' wildcard target origin. Parent↔iframe messages (map feature picks, draft points, selection state) are sent without target-origin restriction. Any injected frame

    could intercept.
  Action: Replace '*' with 'null' (for srcdoc iframes) or window.location.origin.

  !!! The fix is incorrect — 'null' is not a valid targetOrigin string and throws a SyntaxError. The reviewer's alternative suggestion of window.location.origin also wouldn't work since srcdoc iframes have origin null, not the parent's origin. The receive-side check already provides the meaningful protection here. !!!


  ────────────────────────────────────────
  #: S5
  Severity: High
  Location: main.py:1808-1815, 980-983
  Issue: Session and guest cookies lack secure=True. Cookies will be transmitted over plain HTTP in non-HTTPS deployments.
  Action: Add secure=True when setting both cookies.
  ────────────────────────────────────────
  #: S6
  Severity: Medium
  Location: main.py:317-328
  Issue: Admin account has a hardcoded personal username. INSERT OR IGNORE with username 'srajma' makes the admin login predictable. When ADMIN_PASSWORD env var isn't set, a random password
    is printed to stdout and then unretrievable after the process restarts.
  Action: Use a configurable ADMIN_USERNAME env var; only print the password once and advise storing it.
  ────────────────────────────────────────
  #: S7
  Severity: Medium
  Location: main.py (all endpoints)
  Issue: No CSRF protection. Cookie-based sessions with no CSRF tokens. The CORS allowlist mitigates this for browser clients, but direct HTTP clients (scripts, curl) are unaffected.
  Action: Add a SameSite=Strict cookie attribute and/or a CSRF double-submit token for state-mutating endpoints.
  ────────────────────────────────────────
  #: S8
  Severity: Low
  Location: App.jsx:1062-1063
  Issue: Iframe origin check allows any null-origin content. if (event.origin !== 'null' && event.origin !== window.location.origin) return — any script running in a null-origin context
    (e.g., data: URIs) can send accepted messages.
  Action: Verify the message source is one of the known iframe refs: event.source === iframeRef.current?.contentWindow.

  ---
  Bugs

  #: B1
  Severity: High
  Location: main.py:3240-3241
  Issue: Race condition clearing current_processes. After p.join(timeout=5), the code does current_processes[task_type] = None inside the lock. If a concurrent request already stored a new
    process in that slot, the new reference is clobbered, making it untrackable and uninterruptible.
  Action: Check current_processes[task_type] is p before nulling it.
  ────────────────────────────────────────
  #: B2
  Severity: High
  Location: main.py:605-670
  Issue: GADM index globals read without lock. search_gadm at line 707 reads the GADM_INDEX list (which can be replaced wholesale by build_gadm_index) without acquiring _gadm_lock. Similarly

    COUNTRY_SEARCH_INDEX in search_countries.
  Action: Acquire _gadm_lock in search_gadm/search_countries, or take a local reference under the lock.
  ────────────────────────────────────────
  #: B3
  Severity: High
  Location: App.jsx:759-780
  Issue: pickerOptions missing from draft auto-save deps. The draft useEffect watches all other editor state but not pickerOptions, even though it includes picker options in the saved body.
    Picker changes won't trigger an auto-draft-save.
  Action: Add pickerOptions to the dependency array.
  ────────────────────────────────────────
  #: B4
  Severity: High
  Location: App.jsx:1023-1058, 1087-1095
  Issue: Stale closure in updateElementFromDraft. The function reads builderElements directly from the enclosing scope rather than using a functional update form (setBuilderElements(prev =>
    ...)). When called from inside setDraftPoints(prev => ...) (line 1093), builderElements may be stale if state changed since the last render.
  Action: Convert updateElementFromDraft to a functional setState call.
  ────────────────────────────────────────
  #: B5
  Severity: Medium
  Location: main.py:936-962
  Issue: Double DB query in _session_user_from_token. Fetches the user row via JOIN on token_hash, then makes a second query for expires_at using the same token_hash. The expiry column is on

    hub_sessions which is already accessed in the first query.
  Action: Include expires_at in the first query's SELECT via the JOIN.
  ────────────────────────────────────────
  #: B6
  Severity: Medium
  Location: main.py:1254-1265
  Issue: _parse_territory_expr misassigns op on left-side parse failure. When the left operand of a BinOp produces zero parts, the right operand is given op="union" regardless of the actual
    operator (e.g., - or &). So A - B where A fails to parse becomes [{op:"union", ...B}] instead of an empty list.
  Action: When len(parts) == 0, set right_part["op"] = "union" only if the outer op is BitOr, else skip.
  ────────────────────────────────────────
  #: B7
  Severity: Medium
  Location: main.py:433-455
  Issue: _init_hub_db rewrites all map metadata on every startup. Lines 433-455 SELECT all map artifacts and UPDATE every one to strip description, even if already clean. For large databases

    this is O(n) writes on every server start.
  Action: Add an idempotency flag (e.g., a migration version table or a WHERE alpha_metadata LIKE '%"description"%' filter).
  ────────────────────────────────────────
  B8 — loadMapFromHub falls back to stale predefinedCode closure value                                                                                                                        
                                                                                                                                                                                              
  Location: App.jsx:701                                                                                                                                                                       

  setPredefinedCode(parsed.predefined_code || predefinedCode);

  Issue: The || fallback uses predefinedCode — the state value captured in the closure at the time loadMapFromHub was invoked. If a loaded map intentionally has no predefined code (empty
  string or absent field), the || condition is falsy, so the function silently keeps whatever predefinedCode happened to be from the previous map still open in the editor. The user loads a
  new map and gets the old map's territory library code mixed in — incorrect and hard to notice.

  The same pattern appears one line above:
  setCode(parsed.map_code || code);
  Same bug: a map with genuinely empty map_code would retain the previous map's code.

  Action: Use nullish coalescing instead of ||, and default to empty string explicitly:

  setPredefinedCode(parsed.predefined_code ?? '');
  setCode(parsed.map_code ?? '');
  setRuntimeCode(parsed.runtime_code ?? '');

  This ensures loading a map always fully replaces the relevant state, even when the incoming value is an empty string.

  

  ────────────────────────────────────────
  #: B9
  Severity: Low
  Location: App.jsx:2249
  Issue: generatePythonCode has a hidden side effect on themeCode. It calls setThemeCode(themeLines.join('\n')) as a side effect. When called non-interactively from buildMapArtifactContent,
    it mutates UI state, triggering re-renders and re-firing the auto-save effect.
  Action: Separate the code generation from the state mutation; return { code, themeCode } and let callers decide whether to set state.
  ────────────────────────────────────────
  
  !!! False alarm: The reviewer contradicts themselves — they confirm "1" works fine as a bare integer at the API layer. Not a real bug. Do not try fixing B10. !!!

  #: B10
  Severity: Low
  Location: App.jsx:47-49
  Issue: URL version routing uses v{n} prefix but API accepts bare integers. The router parses parts[3] as version = parts[3].slice(1) (strips the v). Sharing a URL like /{user}/map/{name}/1

    (no v prefix) would not be parsed correctly and would be sent as "1" to the API, but hub_get_artifact_version rejects non-alpha, non-digit values. Actually "1" is a digit so it does work

    — but this path is never generated by the frontend, meaning external links with bare version numbers load incorrectly.
  Action: Be consistent: either always use v{n} format in both the router and the API, or handle both.

  ---
  Performance / Inefficiencies

  #: P1
  Severity: High
  Location: main.py:2085-2090
  Issue: N+1 queries in /explore. Each of up to 12 map results triggers 2 separate COUNT queries (_map_vote_count, _map_view_count). That's up to 25 round-trips per page request.
  Action: Use the aggregated COUNT(DISTINCT ...) already present in /hub/registry — bring those joins into the explore query.
  ────────────────────────────────────────
  #: P2
  Severity: High
  Location: main.py:2128-2130
  Issue: N+1 queries in /users. _user_public_profile is called per user and internally fires 2 more queries (maps count, views count). Up to 60+ queries per page.
  Action: Aggregate in SQL with LEFT JOIN / COUNT.
  ────────────────────────────────────────
  #: P3
  Severity: High
  Location: main.py:2415
  Issue: Extra per-artifact query in hub_registry. The registry loop queries alpha_metadata individually per artifact (SELECT alpha_metadata FROM hub_artifacts WHERE id = ?), even though the

    main query already reads from hub_artifacts.
  Action: Include a.alpha_metadata in the main SELECT clause.
  ────────────────────────────────────────
  #: P4
  Severity: Medium
  Location: main.py:700-725
  Issue: Linear scan of 31.8MB GADM index per search request. Every call to search_gadm iterates all entries in a Python loop with no indexing. Under concurrent load this is a bottleneck.
  Action: Pre-build a trie or dict-based lookup (e.g., dicts keyed by GID prefix and lowercased name) at index-load time.
  ────────────────────────────────────────
  #: P5
  Severity: Medium
  Location: main.py:849-893
  Issue: Redundant query in _hub_artifact_response. Already fetches all version rows, then makes a second query for the latest version's content.
  Action: Include content in the versions query with LIMIT 1 ORDER BY version DESC, or filter from the already-fetched rows.
  ────────────────────────────────────────
  #: P6
  Severity: Low
  Location: main.py:3199-3202
  Issue: Render cache key serializes full payload. Full Python code strings and builder state are JSON-serialized for every cache check. For large states this is slow, and the sort_keys=True

    pass is O(n log n).
  Action: Hash the payload with a fast digest (e.g., hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()) and use that as the key.

  ---
  Technical Debt / Clumsy Code

  #: T1
  Severity: Medium
  Location: main.py:841-846
  Issue: _hub_kind_label is a pure identity function. Returns "map"→"map", "lib"→"lib", "css"→"css" — no transformation. Called in ~15 places. Exists presumably for a planned "css"→"theme"
    rename that was never done.
  Action: Either do the rename and update callers, or delete the function and inline the string directly.
  ────────────────────────────────────────
  
  !!! FALSE ALARM: They write to different endpoints (/draft/current vs /hub/.../alpha), so they're not actually racing on anything shared. This is intentional
  separation. Do not try fixing T2. !!!
  
  #: T2
  Severity: Medium
  Location: App.jsx:759-780, 2341-2354
  Issue: Two overlapping auto-save effects watch the same state. The draft save (800ms debounce) and the alpha auto-save (3s debounce) both trigger on the same set of state vars. When both
    fire together they race to serialize the current state.
  Action: Consolidate into one effect that dispatches both saves, or chain them explicitly.
  ────────────────────────────────────────
  #: T3
  Severity: Medium
  Location: frontend/src/config.js:1
  Issue: API_BASE hardcoded to http://localhost:8088. No environment variable support. Deploying to any non-localhost host requires a code change.
  Action: Use import.meta.env.VITE_API_BASE with a .env default.
  ────────────────────────────────────────
  #: T4
  Severity: Medium
  Location: main.py:656, 2773, 2954
  Issue: Bare except: pass swallows errors silently. GADM file parse errors, hub content load errors, and predefined-code exec errors all fail silently, making bugs hard to diagnose.
  Action: At minimum, log the exception with print(f"...: {e}", file=sys.stderr).
  ────────────────────────────────────────
  #: T5
  Severity: Low
  Location: CLAUDE.md and main.py:1034
  Issue: Docs describe __pythonExpr__ but code uses __xatra_python__. The CLAUDE.md documentation says the Python value wrapper key is __pythonExpr__, but actual code in both pythonValue.js
    and main.py uses __xatra_python__.
  Action: Update CLAUDE.md to match the code.
  ────────────────────────────────────────
  #: T6
  Severity: Low
  Location: Throughout codebase
  Issue: Magic number 1.6180339887 repeated without a name. Appears at least 8 times across main.py and App.jsx as a bare float literal.
  Action: Define GOLDEN_RATIO = 1.6180339887 once and reference it.
  ────────────────────────────────────────
  #: T7
  Severity: Low
  Location: main.py:1798-1816
  Issue: _create_session_cookie computes session expiry redundantly. Uses datetime.now(timezone.utc) for now, then datetime.fromtimestamp(now.timestamp() + ...) for expiry — a roundabout way

    of doing datetime.now(timezone.utc) + timedelta(days=...).
  Action: Use _session_expiry_iso() which already exists at line 896.
  ────────────────────────────────────────
  #: T8
  Severity: Low
  Location: App.jsx:1516
  Issue: postMessage('getCurrentView', '*') sends a string, not an object. All other postMessage calls send structured objects; this is the only one that sends a plain string, requiring
    special-case handling in the iframe's listener.
  Action: Change to postMessage({ type: 'getCurrentView' }, '*') (and fix the target origin per S4).
  ────────────────────────────────────────
  #: T9
  Severity: Low
  Location: main.py:1841
  Issue: auth_signup re-queries the row it just inserted. Uses SELECT * FROM hub_users WHERE username = ? to retrieve the newly created user. conn.lastrowid after the INSERT could be used
    instead.
  Action: Use SELECT * FROM hub_users WHERE id = ? with conn.lastrowid.
  ────────────────────────────────────────
  #: T10
  Severity: Low
  Location: main.py:619
  Issue: build_gadm_index has bare except: clauses. At lines 623 and 656, exceptions inside the GADM build loop are silently swallowed with except: pass or except Exception as e: pass where
  e
    is never used.
  Action: Log these as warnings so index build failures are visible.
  ────────────────────────────────────────
  #: T11
  Severity: Low
  Location: main.py / App.jsx
  Issue: Both files exceed 3,000 lines. main.py is a 3,295-line monolith and App.jsx is ~3,200 lines. This makes navigation, testing, and code review difficult.
  Action: Split into logical modules (e.g., auth.py, hub.py, render.py for backend; component split for frontend).

