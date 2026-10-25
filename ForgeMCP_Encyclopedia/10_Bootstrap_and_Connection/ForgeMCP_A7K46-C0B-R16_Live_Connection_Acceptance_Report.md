# ForgeMCP Stage A7K46-C0B-R16 — Live Connection Acceptance

Date: 2026-10-22 UTC  
Engine target: Unreal Engine 5.6.1 / changelist 44394996  
Disposition: **STOPPED at host-side identity preflight.** The one authorized isolated host launched and exposed the exact read-only catalog, but its exact-session native request failed before reaching Unreal. R15 diagnostics narrowed the timeout to before the listener child emitted its first module marker. Production Phase 6C remains **NO-GO**.

## Baseline and fresh disposable identity

The R15 report and its two marker files were reviewed. The isolated source hashes still matched R15: `process_identity.py` `F9403E67BE247F98F2CF9A1DDA55C45BF61DB5F80856FDB9AF3D7419ED2FF693`; `windows_tcp_listener.py` `AC704E69A7D8F45DD6BFDCB472B02522E4588CDE93382FDFB04F70C14A60E380`. The source retained the one **30-second** monotonic deadline, exact process/project/listener validation, IPv4 and IPv6 owner-PID table checks, fail-closed outcomes, exact isolated-session allowlisting and native token authentication. The new diagnostic path was under the R16 stage root and passed a write/read check before use. No unrelated source edit or native rebuild was performed.

The stage-owned client performed a fresh combined `WindowsProcessIdentityProbe` and `validate_process_snapshot` before launching the host. It returned disposable PID **42880**, creation UTC **2026-10-22T06:37:06.5248750Z**, unique listener owner 42880 and `127.0.0.1` at port **59863**. Passive OS checks also matched the exact StageA7G UnrealEditor executable, owner `ALIENWARE-PC\Kenne`, and sole exact C0B disposable `.uproject` argument. The existing private registration identified `unreal-42880`, kind `unreal`, PID 42880, host `127.0.0.1`, port 59863 and an existing token; its value was never emitted. No other Editor was substituted. The client used the C0B source working directory and `PYTHONPATH`.

## One host launch and session security

Exactly **one** R16 dedicated host was launched against the private registration with `preservation_readonly`. The actual catalog contained exactly `unreal_project_info`, `unreal_inspect_dirty_packages`, `unreal_inspect_static_mesh`, and `unreal_inspect_world_save_scope`; all four declared `readOnlyHint=true`. No mutation tool or shared-session fallback was exposed. A missing session ID returned `session_id_required` in **4.601 ms**. An unallowlisted ID returned `session_not_allowed` in **4.778 ms**. Those negative checks did not contact an Editor.

The single exact-session `unreal_project_info` call returned `identity_preflight_failed` in **30,059.790 ms**. Sanitized host stderr recorded the internal category **`listener_timeout`**, including an internal health check failure. No native socket exchange or token validation occurred for that failed request. Consequently there is **no R16 authenticated `project_info` response**. The client stopped, made no dirty-package or other inspector call, did not retry, and did not launch another host.

## Parent watchdog and listener phase evidence

R16 enabled the R15 persistent `FORGE_IDENTITY_DIAGNOSTIC_LOG` for the client preflight, host and helper subprocesses. Its shared JSONL file has no probe correlation ID or absolute timestamp, so overlapping host checks cannot be assigned individual child rows with certainty. The ordered markers nevertheless show three completed combined checks followed by **two host-side checks that timed out**:

| Observed phase | Completed checks | Two timed-out checks |
|---|---|---|
| PowerShell child | completed in about **0.94–1.00 s** | completed in **2.125 s** and **2.141 s** |
| Listener launch remaining deadline | about **29.0 s** | **27.875 s** and **27.859 s** |
| Listener child markers | module entry/import, IPv4, IPv6, serialization and return success | **none** after either listener launch |
| Parent listener result | completed in about **1.25–1.44 s** total | `listener_timeout` and `listener_child_reaped` at **30.015 s** and **30.047 s** total |

For the successful children, IPv4 and IPv6 query/serialization markers completed within the helper's millisecond resolution, and the parent observed exit code 0. For the failed checks, the **last confirmed parent phase was `listener_launch`**; the child produced no `process_entry` or `module_import_complete` marker. The deadline was not exhausted by PowerShell: roughly **27.9 seconds remained** when each listener child was launched. The parent timeout path records the direct child reaped. No stage-owned listener helper or isolated host process remained in the post-run process check.

This narrows the failure to the interval between parent listener launch and the helper's first module marker, or an exceptionally delayed marker write. It does **not** distinguish Windows process creation, Python interpreter startup, early module import, environment/profile effects, or diagnostic-file I/O. It is evidence against attributing this particular timeout to the marked IPv4/IPv6 query bodies: neither query-start marker appeared. Overlap between host checks is visible, but causality from concurrency is an **inference, not proven**. No speculative repair, timeout increase, authentication bypass or second attempt was made.

The diagnostic helper's own stderr cannot exist when it has not reached its exception/output code; the host stderr contains only sanitized categories. The marker file and result record are preserved without registration contents or secrets.

## Inspection, indicator and preservation

Because the first native request failed, **no dirty-package inventory, world-save-scope response or StaticMesh response exists**. No already-loaded disposable mesh was identified for a positive test. There is no before/after native package-state comparison, so inspector safety is **INCOMPLETE**. Save As was not attempted; no asset was loaded, created, saved or discarded.

The native status implementation uses a loopback listener plus authenticated-request age: green for a request within six seconds and yellow after six seconds of prior authenticated activity. R16 did not produce an authenticated native response and did not safely observe the disposable UI dot during the host run. Its actual color and idle transition are **NOT VERIFIED**. A host-side identity failure is distinct from a native authentication failure or an idle but otherwise healthy connection.

The client compared the same five disposable Content/Config files before and after its host context; their recorded SHA-256 values were unchanged. The R15 source hashes and previously verified binary identities were not intentionally altered. This bounded file check does not establish full package preservation or exclude ordinary Editor background writes outside the monitored paths. No A7K41 connection, production city operation, Landscape operation, plugin rebuild, Editor restart or package save/discard occurred. The original production city project remained closed; the disposable Editor remained open with the pinned start and executable at the final passive check.

The R16 host context exited and no matching host/helper process remained. No host exit code was retained, so cleanup is reported as verified process absence. Historical reports, private registrations and earlier evidence were retained.

## Evidence and independent verdicts

Stage evidence root: `runtime/R8-20261022T063606Z-5cfa33bbc9f14e95805e09c8b7e80c06/R16-20261022T161333Z-e4997d2886e14c7a9c9217da9588e90d`.

| Evidence | Bytes | SHA-256 |
|---|---:|---|
| `evidence/runtime_client.py` | 15,390 | `BF86D71F45535117E334D69598C97CF0081F54755FF60D41E0FC51877832D106` |
| `evidence/result.json` | 4,690 | `BE8864E56E4A1209C0A8CBC653EDB14C5794349B9EE57EB8101D38927ACC69BA` |
| `logs/identity-markers.jsonl` | 4,293 | `66BF0C9B61B1C7FC95BA8B8779F942FF208F794A5691BAA5381982B8A8AB9CA2` |
| `logs/host-stderr.txt` | 679 | `A7450D1ED57C81B45912CB06E2DB1A22A179C7991075FA33EAFEC5764A6BB6E0` |

| Gate | Verdict |
|---|---|
| HOST OPERATIONAL | **PARTIAL** — initialized, catalog and negative-session gates passed; exact-session preflight timed out. |
| NATIVE CONNECTION | **FAIL** — no authenticated native response in R16. |
| CONNECTION INDICATOR | **NOT VERIFIED** — source semantics known, live disposable color unobserved. |
| INSPECTOR SAFETY | **INCOMPLETE** — no native inspector ran and no package comparison exists. |
| OFFICIAL ENGINE DEPLOYMENT | **NOT READY** — core live connection and inspector acceptance remain blocked. |

The R16 one-host authorization is consumed. The narrow next step is an offline study of child startup before module entry under the exact host environment, with a probe correlation ID and a parent-recorded child PID/start/exit. It must preserve the 30-second aggregate budget and every identity/authentication predicate. A future live retest requires its own authorization; no further R16 host attempt or lifecycle operation is authorized. Production Phase 6C remains **NO-GO**.
