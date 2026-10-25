# ForgeMCP Stage A7K46-C0B-R18 — Direct Child and Connection Acceptance

Date: 2026-10-22 UTC  
Engine target: Unreal Engine 5.6.1 / changelist 44394996  
Disposition: **DIRECT-CHILD LAUNCH VERIFIED OFFLINE; LIVE NATIVE CONNECTION FAILED.** The one authorized host attempt was consumed. The corrected helper launch did not eliminate the host-side pre-module timeout, so the R16 root cause remains unresolved. No native inspector ran. Production Phase 6C remains **NO-GO**.

## Launch-chain finding and isolated correction

R17 showed that launching `G:\ForgeMCP\.venv\Scripts\python.exe` through `subprocess.Popen` returned a different PID from the Python process executing the listener helper. The venv's `pyvenv.cfg` identifies `C:\Program Files\Python\Python311\python.exe` as its base interpreter. R18 confirmed `sys.executable` was the venv path, `sys._base_executable` was that installed Python 3.11.9 base executable, and the runtime was 64-bit. This verifies a redirector/child-ownership problem in the previous helper launch chain. It does **not** establish that the redirector caused R16's timeout.

Only the isolated C0B Python source and a directly related test were edited:

| File | Before SHA-256 | After SHA-256 | Change |
|---|---|---|---|
| `source/server/core/process_identity.py` | `F9403E67BE247F98F2CF9A1DDA55C45BF61DB5F80856FDB9AF3D7419ED2FF693` | `8053DA234276E2BE9915CF0CE5F0385E276D25C2BF3C57037E1ECE69F7E547B2` | Validate absolute base-interpreter and adjacent helper-file presence; launch `[base, -I, -S, absolute_helper_file, port]`. No fallback to the venv redirector. |
| `source/server/core/windows_tcp_listener.py` | `AC704E69A7D8F45DD6BFDCB472B02522E4588CDE93382FDFB04F70C14A60E380` | `310BC15CE49F110AC9013E2D5C3D4545A1A70813B54BDD2A5DD6929519B98B59` | Add PID to opt-in sanitized helper phase markers. JSON stdout schema and IPv4/IPv6 queries unchanged. |
| `source/tests/test_host_config.py` | R17 baseline retained in prior evidence | `77BB030BF39CA3D91B3D2A2B430524B99B63BCC93BD4B47789BCAF85C64E1A24` | Assert the direct `-I -S` absolute-script launch shape. |

The listener helper imports only standard-library modules and ran successfully with the verified base interpreter in isolated/no-site mode. The host still uses the same `WindowsProcessIdentityProbe`, one **30-second aggregate** deadline, fresh process/project/start/listener checks before each native request, unique loopback ownership, both IP families, exact session allowlist, private registration and native token authentication. Missing launch paths fail closed. No native C++ code or plugin binary changed.

## Offline ownership, cleanup and regression gates

The direct launch returned the exact JSON row `listener_pids=[42880]`, `listener_addresses=[127.0.0.1]`, exit code 0 and empty stderr. Windows `QueryFullProcessImageNameW` on the `Popen` handle returned `C:\Program Files\Python\Python311\python.exe`. After the helper marker gained a PID, a second direct run showed **Popen PID 16844 = executing helper PID 16844**. This is operating-system handle evidence plus in-process marker evidence, unlike the R17 venv redirector case.

R18-owned synthetic direct-interpreter cases exercised normal completion (exit 0), import failure (exit 1), malformed stdout, and a deliberately stalled script. The stall case recorded **Popen PID = executing PID 39080**; after its two-second watchdog, the direct process was reaped and absent in an OS process check. Existing tests verify malformed listener output and failed helper categories are rejected, and wrong/missing/wildcard owners and other identity mismatches fail closed. The real listener helper source contains no subprocess/descendant-spawn call. An arbitrary diagnostic descendant tree was **not** created or contained with a Job Object; cleanup guarantees are proven for the directly executing helper, not for hypothetical descendants.

Focused host/session/security/dirty-package/native-contract and listener-specific tests: **111 passed in 8.90 seconds**. Ruff `check server tests scripts`: **PASS**. Python `compileall -q server tests scripts`: **PASS**. No Python environment or dependency was installed.

The corrected full combined identity probe was then run in a fresh process with the R18 private-host-equivalent environment, exact private registration and stage-owned diagnostic log. `IsolatedHostConfig.from_env`, registration validation, `WindowsProcessIdentityProbe` and `validate_process_snapshot` all passed. It returned disposable PID **42880**, creation UTC **2026-10-22T06:37:06.5248750Z**, unique owner 42880 and `127.0.0.1:59863` in **6,047 ms**. PowerShell completed at **5,703 ms**, leaving **24,297 ms** for the direct helper; helper IPv4, IPv6 and serialization markers completed, parent saw exit 0 at 6,047 ms, and marked helper PID **28352** was absent afterward. No Unreal socket connection was made by this preflight.

Before the live attempt, passive checks again matched the pinned disposable process, exact StageA7G executable and disposable project argument. The three mapped disposable DLL hashes remained the R7/R8 values: MajesticForge Editor `A79131D390DC7F5FAFFB37F964E5AD7687EF4AE3CD0BBF73A77D06DFA4C5EC37`, Runtime `2DB7050DBA230BC7E19987AF6030DC49F86043375EFD48BD599D299102FFC62F`, and project module `E618A09CA2CD04A31C8ED333774FBADB204D24E30A636B1AFE34AADD52DD21A7`.

## One live isolated host attempt

Exactly **one** R18 dedicated host was launched with the existing private `unreal-42880` registration and `preservation_readonly` profile. The actual catalog was exactly `unreal_project_info`, `unreal_inspect_dirty_packages`, `unreal_inspect_static_mesh` and `unreal_inspect_world_save_scope`, each `readOnlyHint=true`. Missing and unallowlisted session IDs returned `session_id_required` (**5.853 ms**) and `session_not_allowed` (**4.139 ms**) without contacting an Editor. No mutation tool or shared-session fallback was exposed.

The one exact-session `unreal_project_info` call returned public `identity_preflight_failed` after **30,200.765 ms**. Sanitized host stderr recorded `listener_timeout` for overlapping internal health and foreground project-info checks. The R18 markers show the two PowerShell children completed at **3.188 s** and **3.516 s**, leaving **26.812 s** and **26.484 s** at listener launch. Neither listener child emitted its first `process_entry` marker. Parent `listener_timeout` and `listener_child_reaped` markers occurred at **30.078 s** and **30.141 s**. The corrected direct-child mechanism passed offline but **did not restore the live host connection**. No native socket request or Unreal token validation happened for the failed exact-session call. There was no retry and no second host launch.

This result weakens the venv redirector as a sufficient explanation for the R16 timeout. It still does not distinguish Windows process creation, base-interpreter initialization, very early helper execution or diagnostic-file access under the concurrent host workload. The monitor's periodic health request and the foreground request can overlap, but concurrency's causal contribution remains unproven. No timeout, identity predicate or monitor interval was changed after the failure.

## Inspector, indicator and preservation result

Because native project-info failed, **no dirty-package inventory, world-save-scope result or StaticMesh result exists for R18**. No already-loaded mesh was identified for a positive case. Save As and package saving were not attempted. Native inspector side-effect acceptance is **INCOMPLETE**.

The disposable plugin's source turns green only for a listener with authenticated native activity within six seconds and yellow after older authenticated activity. R18 had no authenticated native response and did not safely observe the live UI dot; actual green/yellow behavior is **NOT VERIFIED**. No UI source, heartbeat, token or credential was changed.

The host client compared the same five disposable Content/Config files before and after its host context: **zero hash changes**. This bounded file result does not prove complete loaded-package preservation. The R18 host context exited; a final process query found no matching R18 host or listener helper process. No host exit code was retained. Disposable Editor PID 42880 remained open with its pinned start time. The protected A7K41 Editor was not contacted; the closed production city project remained closed. No Editor was restarted, no package was saved/discarded, and no official Engine file was changed.

Key live evidence is under `runtime/R8-20261022T063606Z-5cfa33bbc9f14e95805e09c8b7e80c06/R18Live-20261022T163347Z-522287c527674014b47ecad3467ea9e0`: `evidence/result.json` SHA-256 `D434EA39C33D4992040F20EE3FA83455754FF02176D7AF02F0216BD562AEF8B6`, `logs/identity-markers.jsonl` `84CA4A356D97D006058A4C4973E9319C3A2FE54753871F0876EF7884501DEA13`, and sanitized `logs/host-stderr.txt` `A7450D1ED57C81B45912CB06E2DB1A22A179C7991075FA33EAFEC5764A6BB6E0`. Offline direct-launch and synthetic evidence is under `runtime/R18-20261022T163124Z-d279358a94d545a482788e6e4411c51e`. Historical evidence was retained.

## Disposition and next boundary

| Gate | R18 result |
|---|---|
| Direct executing child ownership | **PASS** for tested base-interpreter helper launches. |
| Direct child timeout cleanup | **PASS** for R18-owned stalled script; arbitrary descendant-tree containment untested. |
| Focused regressions and corrected combined preflight | **PASS** offline. |
| Host catalog and session rejection | **PASS** for one isolated host. |
| Authenticated native connection | **FAIL** — host identity preflight timed out before native request. |
| Dirty/world/mesh inspector acceptance | **NOT TESTED**. |
| Live connection indicator | **NOT VERIFIED**. |
| Official-engine deployment readiness | **NO-GO**; no authenticated C0B native acceptance. |

The R18 one-host authorization is consumed. The next narrowly scoped work is offline correlation of the **direct** helper's parent process-creation return/PID and child earliest possible marker during overlapping host checks, with a bounded, verified way to identify and reap only stage-owned processes. Do not infer that changing the interpreter fixed the repeated timeout or deploy this candidate to the official Unreal installation. A further live host attempt requires new authorization. Production Phase 6C remains **NO-GO**.
