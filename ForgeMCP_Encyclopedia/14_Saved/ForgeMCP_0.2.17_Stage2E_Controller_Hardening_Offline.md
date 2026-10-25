# ForgeMCP 0.2.17 — Stage 2E Controller Hardening (Offline)

Verdict: **PASS — controller hardening and offline tests completed.** This is a test-harness verdict. Stage 2E independent reload remains **BLOCKED / NOT TESTED**; the prior one-launch authorization is consumed.

## Confirmed failure and limits of diagnosis

The approved isolated Editor PID 18304 had reached private DDC and shader compilation. At approximately 230.562 seconds, `run_approved_once_v2.py` called `ps()` from its every-30-second progress block with:

```powershell
Get-CimInstance Win32_Process -Filter "Name='ShaderCompileWorker.exe' OR Name='CrashReportClient.exe' OR Name='CrashReportClientEditor.exe'" | Select-Object ProcessId,ParentProcessId,ExecutablePath | ConvertTo-Json -Compress
```

`ps()` ran a new PowerShell process with `subprocess.run(..., timeout=12)`. That command timed out and raised `subprocess.TimeoutExpired`. The controller stopped the verified disposable process and retained workers. This was a process-observation failure before map acceptance, not the 900-second startup deadline. Its internal cause (CIM service latency, PowerShell startup, or another Windows delay) was not established. No Unreal crash, Landscape serialization error, or DDC error was proved.

The broad name-filtered CIM query collected processes unrelated to the isolated Editor, then filtered them in Python. Repeating it every 30 seconds was unnecessary once worker handles and immutable creation identities had been retained. A targeted CIM query for the root process's command line remains once at launch, with a four-second bound; it is not used in the polling loop or shutdown.

## Revised test-only design

New files are under `Saved/stage2e_controller_hardening/`:

- `worker_observer.py`: a short-lived Windows Toolhelp snapshot helper returning only PID, parent PID and selected worker names. The parent controller runs it with a **three-second subprocess timeout**. A timeout is labeled `ObservationFailure` and never labeled an Unreal crash.
- `run_revised_once.py`: a separate copy of the controller with the broad CIM polling removed. It requires `--execute`, a **new plan root**, and an explicit new approval ID matching a new `revised_launch_plan.json`. It rejects the consumed Stage2E_Alpha_20261023T232404Z root. Original scripts, marker and launch plan were not edited.
- `test_offline.py`: synthetic ownership, timeout and shutdown tests.
- `audit_readonly.py`: full source/clone manifest verification without writes.

The snapshot only nominates candidates. A candidate is retained only when its parent is a live retained-handle process with the expected creation time, its own handle is live, its creation time follows the parent, and its exact executable path matches the installed worker path. Production PID is explicitly excluded. Handles and creation times are rechecked before any termination. The root still requires its retained handle, executable, creation time and independently observed isolated-project command line. A failed check blocks termination and is recorded; it cannot authorize killing by process name.

The three-second snapshot process can still time out; that becomes a controlled observation failure. The helper does not remove the need to prove startup, map loading or independent disk-backed heights. In the unusual case that root command-line verification fails immediately after process creation, the revised controller refuses to terminate an unverified process and reports that safety failure for manual handling. This is intentionally conservative and needs a dry-run review before a further live attempt.

## Offline verification

`python -B -m unittest -v test_offline.py`: **14/14 passed**, with individual results in `stage2e_controller_hardening/offline_test_results.json`. Required cases covered: normal observation, bounded slow query, hung query, process exit, PID reuse, missing worker, multiple workers, worker executable mismatch, production PID exclusion, verified disposable shutdown targets, startup observation failure, and 900-second deadline. Extra cases covered an older worker creation time and a reused worker handle. No test issues a real process termination.

Python AST parsing passed for all new scripts. A read-only Toolhelp snapshot ran successfully within the helper's three-second bound. Invoking the revised controller without approval arguments failed at argument parsing, before any Editor launch. These offline tests do not prove live Unreal startup or that all possible Windows process races are eliminated.

## Preservation audit

The original launch evidence, controller scripts, logs, checkpoint manifests and consumed marker remain in the historical Stage 2E root. This work created only the new Saved test-harness files and this report. It did not launch an Editor, request an editing session, save or modify production assets, sculpt terrain, restore a checkpoint, or perform cleanup.

Full read-only SHA-256 and membership audit: **1745/1745 production source files and 1745/1745 clone files matched**, with zero mismatches, additions or missing files. The result is recorded in `stage2e_controller_hardening/source_clone_audit_result.json`. No current native session read was necessary to modify the test harness, and no native mutation call was made.

## Proposed next single-attempt plan — not approved or executed

1. Prepare a **new** isolated project copy and test root from the current saved source. Record fresh complete source/clone manifests, expected height arrays and a fresh `revised_launch_plan.json`; retain all old evidence. Revalidate production identity, clean Content, both affected Landscape files, source hashes, free disk and the six historical checkpoint pins.
2. Use the installed UE 5.6.1 executable with the independent project, ordinary rendered startup, private DDC graph and isolated registry, user, localappdata, temp and log paths. Validate all graph fallbacks, plugin/module BuildIds, exact command line and writable paths before launch. Production Editor remains untouched.
3. Obtain a **new explicit owner authorization for one attempt** with a maximum 900-second startup window and no automatic retry. Use the new approval ID and new plan root; never reuse the prior marker, plan or authorization.
4. On launch, verify retained process creation identity, executable, parent and exact isolated project command line. Monitor workers via bounded snapshots and retained handles. On any identity, DDC, fatal, observation or deadline failure, stop only verified disposable processes, retain diagnostics, and report the exact condition.
5. Accept a map load only after the private authenticated child reports the target level and Landscape. Verify ForgeTerrain MD5 `08cbe382a59441d8148a674cf0d83851`, Original Layer MD5 `9f43572fbc2c06ef497da015879cdb23`, all 120 modified and 101 preserved carved samples, 16 loaded proxies, and 64 Landscape plus 64 collision components. Gather close-up and collision evidence only through supported read-only methods. Reaudit production preservation afterward.

The machine-readable proposal is `stage2e_controller_hardening/revised_single_attempt_plan_template.json`. It is deliberately a template; a fresh copy, hashes, exact paths and new authorization must be bound before a runnable launch plan exists.

No Stage 2E persistence or Phase 6C release acceptance is claimed by this offline repair.

## Follow-up during fresh Stage 2E preparation — October 24, 2026

The controller was reviewed again while preparing a new isolated copy. Its safety checks now also hash-pin the controller and observer, take a bounded worker snapshot immediately before shutdown, and verify worker absence afterward. A shutdown observation or termination failure is recorded as incomplete. The initial root command-line failure remains fail closed: it does not terminate an unverified process.

The offline suite was extended from 14 to **17 synthetic tests**. The additional tests cover a dead parent, a production PID presented as the root shutdown target, and a wrong project command line. The full 17-test run passed with no real process termination. Python AST parsing and a bounded live Toolhelp snapshot passed. A fresh source/clone audit later checked 1,745 files in each tree with zero hash mismatches, additions or missing files.

The new plan root and proposed launch are recorded in `Saved/ForgeMCP_0.2.17_Stage2E_IndependentReload_Preparation_20261024T001332Z.md`. It is prepared and awaiting new owner approval. The prior authorization remains consumed; no new Editor launch occurred.
