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

