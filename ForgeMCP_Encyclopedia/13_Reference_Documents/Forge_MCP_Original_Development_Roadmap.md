ForgeMCP

Original Development Roadmap — Unreal Engine + Blender + VS Code + OpenAI Codex

Organization: Majestic Creations
Project name: ForgeMCP
Document version: 1.1 — Roadmap updated against implementation
Date: October 11, 2026
Project status: Active implementation; pre-v1.0
Primary development environment: Visual Studio Code with OpenAI Codex

## October 16, 2026 — Native Landscape extension

The native Landscape extension targets bounded disposable test maps.
See [Landscape automation](LandscapeAutomation.md) for typed operations, native
APIs, progressive jobs, recovery, and explicit limits. The phased objective still
includes World Partition streaming-proxy/external-package compatibility; those
mutations remain unsupported pending their own implementation and acceptance.
This work does not authorize constructing the nine-kilometre city or changing
Ultra Dynamic Sky. Compilation and live acceptance are reported separately in
[the dated Landscape acceptance evidence](Landscape_Acceptance_20261016.md).

## Next Unreal priority — Splines, PCG and reference-based cities

October 16, 2026: prioritize comprehensive native spline and PCG exposure for
roads, junctions, city blocks and realistic city reconstruction from reference
images. Include standard splines, spline meshes, Landscape splines, PCG graph
authoring/execution/debugging, district generation and calibrated references.
The target is 1:1 real-world scale with measured geometric and visual fidelity;
exact reconstruction requires sufficient calibrated source data and declared
tolerances. A single uncalibrated photograph cannot guarantee exact dimensions.

The [implementation specification](Splines_PCG_City_Reconstruction.md) defines
coverage, delivery order, architecture, recovery and acceptance criteria. This is
the next development priority, not a claim of implemented spline/PCG support;
the full existing roadmap and remaining release gates remain in scope.

## October 16, 2026 — Engine-wide Unreal alpha

Plugin **0.2.13-alpha.1** introduces a separately packaged UE **5.6.1 Win64
Development Editor** alpha and a validated engine-wide installer. Feature work
continues in the project-local development plugin. Engine installation makes the
alpha available across projects using that engine; each project explicitly enables
it. This milestone does not close the remaining v1.0 feature or acceptance gates.
See [UE 5.6 alpha](UE56_Alpha.md) for installation, updating, rollback and scope.

The engine-installed alpha is now **0.2.13-alpha.9**, with MCP server source
**0.3.13** and Blender add-on **0.2.35-alpha.6**. Alpha.9 brings a locally bundled
React interface into the Unreal editor tab while retaining its native C++ bridge and
reviewed transfer flow. The initial file-based bundle showed a white panel; its
self-contained bundle fix is verified and documented in [alpha.9 white-tab fix](UE56_Alpha9_White_Tab_Fix_20261016.md). See also [alpha.9 UI acceptance](UE56_Alpha9_React_Tab_UI_20261016.md).
The transfer actions now use the official Unreal Engine and Blender marks; see
[alpha.9 logo integration evidence](UE56_Alpha9_Official_Partner_Logos_20261016.md).
The compact reference-matched spacing and icons are documented in
[alpha.9 layout refinement](UE56_Alpha9_Compact_Layout_20261016.md).
Alpha.4 uses `/Game/Content/Returns/` for Blender-to-Unreal transfers and retains
the exact source object name in both directions. It reports exact-name collisions
instead of generating prefixes or numeric suffixes. Native source remains
engine-wide at the user's request. See [alpha.4 transfer-name evidence](UE56_Alpha4_Transfer_Names_20261016.md),
[alpha.3 evidence](UE56_Alpha3_Transfer_UX_20261016.md), and
[alpha.2 evidence](UE56_Alpha2_Transfer_Fix_20261016.md) for the earlier engine
mesh handoff fix and acceptance results.

The Blender add-on release is **0.2.35-alpha.6** (Blender's numeric add-on
metadata remains **0.2.35**); its package and bridge health report the full
prerelease version. The Blender sidebar refinement is recorded in
[alpha.6 UI acceptance](Blender_Alpha6_Tab_Visual_Refinement_20261016.md).

## October 13, 2026 — Blender flexibility checkpoint

The latest server source is **0.3.6** and Blender add-on **0.2.33**, with **104 MCP
tools** in the source registry. The original October 11 baseline below is retained
as historical evidence. Blender now exposes complete registered operator discovery
and native parameter/RNA schemas, plus reviewed creative authoring, camera/light
and render configuration, expanded shader graphs, numeric animation, modifiers,
constraints, new `.blend` copies and asynchronous PNG render jobs/cancellation.
Disposable native and real stdio MCP tests produced and decoded 4096 × 2304
animated frames. Complete operator discovery is not universal operator execution.
See [Blender creative automation](Blender_Creative_Automation.md) for coverage,
installation and the remaining adapters.

## Current implementation baseline — October 11, 2026

This document retains the original product vision and records the implementation
state so that future work builds on verified systems instead of treating ForgeMCP as
a greenfield project. The authoritative execution plan and evidence log are
`Documentation/Active_Development_Plan.md` and
`Documentation/Development_Status.md`; this roadmap supplies the product direction
and v1.0 completion gates.

Current component versions are MCP server source **0.3.1**, Unreal plugin **0.2.8**,
and Blender add-on **0.2.32**. These are development versions, not a v1.0 release.
The source registers 85 MCP tools. On October 11, the Codex-connected ForgeMCP host
reported server 0.3.1 and connected Unreal session `unreal-12640` in ForgeMCPDev,
with Unreal bridge 0.2.8. Project/asset/actor queries and reviewed Blueprint
creation, compilation, saving and opening succeeded through that host. A fresh
source stdio subprocess independently discovered 85 tools and verified the saved
showcase graph and unchanged package bytes. This validates those operations in
ForgeMCPDev; the newest DataAsset operations and the user's JasperPrismDev Editor
still need their own live acceptance. See `Unreal_MCP_Showcase.md` for evidence.

The current implementation already includes authenticated local Unreal and Blender
bridges; explicit session selection; typed, preview/apply operations; bounded
inspection; stale-state checks; and transaction/rollback behavior across several
workflows. Unreal support includes actor and component inspection/editing, Blueprint
creation and selected existing-graph edits, native material and material-instance
graph authoring, asset discovery, DataTable inspection, DataAsset discovery/schema/
creation and reviewed edits, mesh import/export, and transfer binding operations.
Blender support includes object, mesh, material, collection, rig and animation
inspection; selected mesh, material-node, modifier and animation edits; and transfer
operations. Static-mesh transfer supports reviewed FBX and OBJ paths, revision checks,
stable bindings and guarded replacement workflows.

The latest DataAsset editing increment adds `unreal_preview_data_asset_edit` and
`unreal_apply_data_asset_edit`. In a disposable UE 5.6.1 project, the tests verified
guarded changes to two boolean fields, rejection of wrong confirmation and stale
preview, preservation of the original package, and persisted values after reopening
in a fresh Editor process. The Unreal 0.2.8 package passed clean-project plugin-load
verification. The full ForgeMCPDev Editor target and interactive JasperPrismDev
session were not verified for that increment.

Progress is estimated at **55% overall** toward v1.0: Unreal automation **58%**,
Blender automation **62%**, bidirectional file transfer **60%**, and installation,
live integration and recovery **42%**. These are engineering estimates based on
feature breadth, workflow validation and release gates, not a count of MCP tools.

## Product workflow direction

ForgeMCP's first cross-application milestone is a reliable, user-directed round trip:

1. In Blender, users send a selected supported asset to Unreal using the action label
   **Send to Unreal**. The operation exports and transfers a supported FBX or OBJ,
   then Unreal imports it through a reviewed workflow with a clear receipt.
2. In Unreal, users can choose **Send to Blender** to export a selected supported
   asset as FBX or OBJ for Blender work. **Import from Blender** provides a separate
   pull/import route for an asset already prepared in the Blender handoff location,
   including cases where the user did not start from Unreal's Send to Blender action.
3. Both directions report source, destination, format, target session, binding or
   revision state, and the outcome. Existing assets are protected by previews,
   conflict checks, explicit replacement choices and recovery evidence.

These are explicit user-triggered transfers, not live synchronization. Real-time
two-way updating remains a later goal. It requires a defined ownership/conflict
model, debounced change detection, stable asset identity, cancellable transfer jobs,
recovery across either application's failure, and clear UI feedback. Do not describe
the current round-trip workflow as seamless or real time until those properties are
implemented and tested.

## Revised delivery path to v1.0

### Track A — Restore the live integration baseline

- Refresh or restart the Codex-connected ForgeMCP server so it runs the current
  source, and confirm the MCP tool registry exposes the current operations.
- Start the intended Unreal and Blender editors, rediscover their registrations,
  and prove session identity and `connected: true` through the MCP host.
- Run harmless project/scene and asset queries through that same host. Recheck after
  reconnects so stale session files cannot be mistaken for a live editor.
- Use JasperPrismDev as a read-only integration target until the user authorizes
  specific asset edits; use disposable projects for mutation acceptance by default.

### Track B — Complete dependable Unreal workflows

- Expand reviewed Blueprint graph editing in bounded, typed increments, preserving
  compile feedback, scratch-asset rollback and existing-asset protection.
- Continue material and material-instance workflows with inspect, preview, validate,
  apply, compile, save and read-back evidence; validate visual output separately.
- Broaden asset and level operations only with explicit target selection, path and
  class validation, stale-preview rejection, save boundaries and recoverable failure.
- Prioritize common gaps such as UMG, World Partition/data layers, PCG and Niagara
  only after each operation has a safe typed contract and an isolated acceptance test.
- Establish skeletal mesh, animation and retargeting workflows; these currently lack
  asset-specific implementation and acceptance.

### Track C — Complete dependable Blender workflows

- Extend rig and weight editing with deformation checks and rollback.
- Add safe editing/removal for existing modifiers and material graph nodes/links,
  plus broader mesh/object operations with topology and custom-data safeguards.
- Continue animation editing with copied Actions, key/interpolation validation and
  explicit activation behavior.
- Verify transfer panels and operations in clean Blender profiles and live sessions.

### Track D — Harden cross-application handoff

- Complete matching **Send to Unreal**, **Send to Blender**, and **Import from Blender**
  user flows for supported FBX/OBJ static meshes, with deterministic paths and
  transfer receipts.
- Validate source and destination identities, formats, transforms, material/mesh
  scope, binding/revision comparison, duplicate handling, cancellation and recovery.
- Treat broader content (materials, rigs, animation, scenes) as separate profiles;
  do not imply those are included in static-mesh support.
- Design real-time synchronization only after file handoff is reliable. Specify
  conflict ownership, change detection, latency targets, pause/resume, and recovery
  before adding watchers or background updates.

### Track E — Release and operational readiness

- Provide repeatable clean installation and upgrade/uninstall paths for both adapters
  and the server, with version compatibility checks and no machine-specific paths.
- Verify supported Unreal/Blender versions, package contents, signatures/hashes,
  startup, reconnect, logging and actionable failure messages.
- Test failure recovery, stale previews, repeated requests, editor shutdown/restart,
  network/bridge loss, save failure and rollback behavior.
- Publish capability boundaries and known limitations; do not promote development
  package evidence as an end-user release.

## v1.0 completion gates

The coordinated v1.0.0 release is ready only when all of these gates pass:

- **Live MCP integration:** current server, Unreal and Blender sessions are discoverable
  and connected through the intended Codex MCP host; project identity and harmless
  read-only queries succeed through that host.
- **Core workflows:** supported Unreal and Blender inspection/editing tasks complete
  with target validation, preview/confirmation where appropriate, application-level
  result checks and clear limitations.
- **Round trip:** both send directions and the Blender pull/import route work for the
  declared formats, with duplicate/conflict handling and recoverable errors.
- **Safety and recovery:** stale state and wrong confirmation are rejected; failures
  do not silently leave partial changes; saved outputs can be reopened and verified.
- **Clean installation:** packages install and load in fresh supported environments,
  survive restart/reconnect and report incompatible versions clearly.
- **Documentation and release:** capabilities, setup, constraints, tests, versions
  and known gaps match the shipped artifacts. Real-time sync is either validated as
  a v1.0 feature or clearly remains outside the v1.0 promise.

Until these gates are evidenced, maintain component development versions and report
progress by validated workflow. Do not use the 1.0 label merely because the initial
feature list is present.

1. Project Decision: Build Our Own From Scratch

ForgeMCP will be an original software project.

We will not fork, copy, or build upon gimmeDG's Unreal Engine MCP repository, and we will not depend on a third-party Unreal or Blender MCP implementation. The objective is to build and maintain our own source code, architecture, command system, editor integrations, documentation, and workflows.

The system will use open standards and documented development APIs, including the Model Context Protocol (MCP), Unreal Engine editor APIs, and Blender's Python API. Using an official protocol SDK is different from copying another developer's Unreal Engine integration: the integrations and application logic will be authored for this project.

Non-negotiable direction:

Original MCP server and tool definitions.

Original Unreal Engine C++ editor plugin.

Original Blender Python add-on.

Native compatibility with OpenAI Codex in Visual Studio Code as the primary tested client.

No required Claude or Cursor dependency.

Provider-independent MCP interfaces so other compatible clients could be supported later.

A shared Unreal/Blender asset and automation pipeline developed and controlled by Majestic Creations.

2. Purpose and Vision

Build a Codex-first, AI-assisted game-development automation platform that allows a developer to enter natural-language instructions in VS Code and have a local MCP server coordinate actions in Unreal Engine and Blender.

The ambition goes beyond running isolated scripts. The finished system should be capable of:

Inspecting a project's state before performing a task.

Creating and modifying Unreal actors, levels, assets, and Blueprint graphs.

Compiling Blueprints and reporting actionable errors.

Editing objects, rigs, materials, and animation data in Blender.

Transferring validated assets from Blender into Unreal Engine.

Orchestrating multi-step workflows across both applications.

Producing clear status reports, diagnostic information, and recoverable changes.

Codex is the preferred user-facing AI agent, not a hard dependency built into the MCP protocol server. The server should expose standards-compliant tools to any client that is appropriately configured and authorized.

3.  Original System Architecture

                  ┌──────────────────────────────────┐
                  │  Visual Studio Code + Codex     │
                  │  AI instructions / orchestration │
                  └─────────────────┬────────────────┘
                                    │
                            MCP (local stdio)
                                    │
                  ┌─────────────────▼────────────────┐
                  │         ForgeMCP CORE            │
                  │                                  │
                  │  • Tool registry and schemas     │
                  │  • Command and task routing      │
                  │  • Permission and safety rules   │
                  │  • Session/connection manager    │
                  │  • Project context and telemetry │
                  │  • Diagnostics and validation    │
                  └─────────────┬───────────┬────────┘
                                │           │
                     local IPC  │           │ local IPC
                                │           │
                 ┌──────────────▼───┐   ┌───▼────────────────┐
                 │   UNREAL BRIDGE  │   │   BLENDER BRIDGE   │
                 │   Original C++   │   │  Original Python   │
                 │   Editor plugin  │   │       add-on        │
                 │                  │   │                    │
                 │ • Blueprints     │   │ • Meshes / objects │
                 │ • Levels / actors│   │ • Armatures / rigs │
                 │ • Materials      │   │ • Keyframes / anim │
                 │ • Gameplay / GAS │   │ • Materials        │
                 │ • Asset import   │   │ • Asset export     │
                 └──────────┬───────┘   └─────────┬──────────┘
                            │                     │
                            └──────────┬──────────┘
                                       │
                         ┌─────────────▼────────────┐
                         │ CROSS-APPLICATION PIPELINE│
                         │ Asset manifests + checks │
                         │ FBX / glTF / USD where   │
                         │ supported; import/export │
                         │ reports and validation   │
                         └──────────────────────────┘

Architecture principles

Single MCP entry point: The core server exposes tools to Codex and routes them to the correct application adapter.

Application-specific bridges: Unreal and Blender each execute commands using their own native APIs and execution models.

Local communication by default: Do not expose the editor-control interfaces publicly on the network.

Validate before modifying: Inspect available sessions, project state, asset compatibility, and command arguments before actions.

Keep boundaries clean: Do not embed Codex-specific agent logic inside the Unreal or Blender adapters.

Use structured results: Return machine-readable results along with useful human-readable explanations.

4. Planned Technology Stack

Component

Planned technology

Responsibility

Development IDE

Visual Studio Code

Coding, debugging, repository work

Primary AI agent

OpenAI Codex

Initiating and coordinating MCP tool calls

MCP server

Python 3.11+ (external runtime)

Tool registration, dispatch, validation, orchestration

MCP library

Official Python MCP SDK, supported stable release

Standards-compliant MCP transport and schemas

Unreal Engine target

Unreal Engine 5.6 initially

Primary game-development environment

Unreal editor integration

Original C++ Editor plugin

Native Blueprint, editor, graph, and asset operations

Unreal automation

Unreal Python API where suitable

Supported editor scripting and batch operations

Blender integration

Original Python add-on using bpy

Scene, mesh, rig, material, and animation operations

MCP transport

stdio initially

Codex-to-server connection

Application transport

Local authenticated IPC

Core-to-editor communication

Commands/metadata

JSON and validated schemas

Requests, tool results, status, manifests

Asset interchange

FBX / glTF / USD as appropriate

Blender-to-Unreal assets, subject to format capabilities

Automated tests

pytest + Unreal Automation Tests

Core logic and editor behavior

Source control

Git + original GitHub repository

Code history and release management

Implementation note: Unreal's embedded Python runtime and Blender's Python runtime may differ from the standalone MCP server's Python environment. The adapters must communicate across process boundaries rather than assume the same Python environment or package versions.

5. Feature Modules

5.1 Unreal Engine Control Module

Planned capabilities:

Inspect engine version, loaded project, current level, and editor state.

List, create, place, inspect, modify, and organize level actors.

Create and edit Blueprint assets, classes, variables, components, functions, and event graphs.

Create Blueprint nodes and connect pins with validation.

Compile Blueprints; collect errors, warnings, and success status.

Create and modify material assets and material instances.

Support Gameplay Ability System (GAS) workflows.

Support procedural level generation and PCG workflows.

Inspect and work with skeletal meshes, animations, and retargeting assets.

Import, export, locate, rename, and validate assets.

Query editor logs and project diagnostics.

Engineering consideration: Blueprint graph creation requires native editor-facing APIs for reliable, comprehensive operations. The Unreal bridge should be a hybrid of C++ editor functionality and Python automation where documented and suitable, not a Python-only system.

5.2 Blender Control Module

The Blender integration will be an original add-on, written specifically for ForgeMCP. Planned capabilities:

Detect Blender sessions and identify the active file and scene.

List and inspect objects, collections, modifiers, and transforms.

Create and modify mesh objects and geometry.

Create and inspect materials and texture references.

Inspect armatures, bones, bone naming, parenting, and skin weights.

Create and modify keyframes, actions, and animation data.

Configure animation frame rates (including 30 FPS workflows).

Validate scale, coordinate-system conversion, mesh data, and exports.

Export supported asset formats using explicit preset configurations.

Return structured scene and operation reports to Codex.

Engineering consideration: Run Blender scene modifications in an appropriate main-thread execution context. Do not directly mutate Blender data from arbitrary background threads.

5.3 Cross-Application Asset Pipeline

This pipeline coordinates Blender and Unreal rather than treating them as unrelated tools.

Planned workflow:

Inspect an object, rig, or animation in Blender.

Check scale, transforms, hierarchy, bones, skin weights, material dependencies, and timing.

Produce a structured asset manifest and validation report.

Export using an appropriate format and tested settings.

Hand off the manifest and exported files to the Unreal adapter.

Import assets into the target Unreal project.

Assign or validate the intended skeleton where applicable.

Verify import results and report errors or incompatibilities.

This could later support DAZ-to-Unreal character-processing workflows, but those are future integrations, not part of the first milestone. Licensing and commercial-use eligibility must be checked separately from technical conversion.

6. Development Roadmap

Phase 1 — Original MCP Foundation

Goal: Build the server from an empty repository, with no third-party Unreal/Blender MCP code.

Initialize repository, package structure, and development environment.

Implement the MCP server using the official SDK.

Create the tool registry, argument schemas, and structured response conventions.

Create configuration, log files, status reporting, and error handling.

Implement session discovery, health checks, and task dispatch.

Configure Codex in VS Code to communicate with the new server.

Exit criterion: Codex recognizes ForgeMCP and can call its diagnostic tools.

Phase 2 — Original Unreal Engine Plugin

Goal: Implement reliable engine integration for Unreal Engine 5.6 initially.

Create an Unreal Editor plugin in C++.

Provide a secure local command endpoint.

Expose engine/project metadata, editor connectivity, and actor inspection.

Ensure engine APIs run in the appropriate editor context/thread.

Return structured success/errors for every operation.

Exit criterion: Codex can read project metadata and list actors in the active level.

Phase 3 — Blueprint Engineering

Goal: Make programmatic Blueprint construction and validation practical.

Create Blueprint assets and classes.

Add variables, components, and functions.

Create nodes and connect graph pins.

Validate graph integrity and compile assets.

Return compiler warnings/errors and affected asset paths.

Expand to reusable gameplay and GAS templates.

Exit criterion: Codex creates, compiles, and places a working Blueprint actor in a test level.

Phase 4 — Original Blender Add-on

Goal: Implement independent Blender control using an original Python add-on.

Establish session connection and scene inspection.

Implement object/collection operations.

Add mesh, material, rig, and animation tools.

Expose safe execution and consistent error responses.

Implement export presets and asset checks.

Exit criterion: Codex can inspect and modify a Blender scene using ForgeMCP tools.

Phase 5 — Unified Unreal + Blender Workflows

Goal: Coordinate supported tasks across both applications.

Define shared asset manifest schemas.

Add reliable Blender export and Unreal import transactions.

Implement coordinate, scale, material, skeleton, and animation checks.

Report each step and prevent silent partial failures.

Track output assets and maintain workflow logs.

Exit criterion: Codex modifies a simple Blender asset and imports it into Unreal with a validation report.

Phase 6 — Context, Intelligence, Reliability, and Packaging

Goal: Prepare the platform for larger real-world projects.

Add version-aware Unreal and Blender API documentation retrieval.

Build project-specific indexing and diagnostics.

Introduce previews/dry-run modes for destructive operations.

Implement approval gates, operation logs, and recoverability.

Add comprehensive tests, installer/setup utilities, and documentation.

Prepare a distribution strategy for Majestic Creations.

Exit criterion: Repeatable workflows, understandable diagnostics, tested safeguards, and documented installation.

7. First Milestone: Five Original MCP Tools

The first working version should expose exactly the following foundational tool interfaces (names are provisional):

MCP tool

Purpose

Initial behavior

forge_status

Overall bridge health

Reports MCP status and connected adapter health

forge_list_sessions

Discover running targets

Lists authorized Unreal and Blender sessions

unreal_project_info

Inspect the active Unreal project

Returns engine version, project name, and relevant metadata

unreal_list_actors

Inspect the current Unreal level

Returns actor identifiers, names, classes, and paths where available

blender_scene_info

Inspect the active Blender scene

Returns scene name, objects summary, frame settings, and add-on status

Milestone acceptance test: Codex in VS Code discovers all five tool definitions, invokes each appropriate tool, and receives correct, structured results from the MCP server and the connected applications.

Recommended first demonstration

In VS Code, ask Codex:

Connect to ForgeMCP. Report which Unreal Engine and Blender sessions are running. Read the active Unreal project's version and level actors. Read the active Blender scene and frame rate. Do not modify either project.

Expected result: A complete read-only report, with useful errors if an application is closed or the relevant plugin/add-on is not installed.

8. Second Milestone: Blueprint + Blender Proof of Concept

Unreal demonstration

Create a new Blueprint actor in the test project, add a component, compile the Blueprint, place one instance in the test level, and report whether compilation and placement succeeded.

Blender-to-Unreal demonstration

Inspect and modify a simple mesh in Blender, validate its transforms, export it, import it into the current Unreal project, and report the new asset path and any import warnings.

Both demos should be repeatable on a clean test project without manual intervention in the graph editor or repetitive asset-import dialogs.

9. Safety, Reliability, and Ownership Requirements

Project safety

Restrict editor control to local, authorized sessions by default.

Validate tool arguments and project paths before executing commands.

Require explicit confirmation for deletion, overwriting, arbitrary code execution, and other high-impact actions.

Disable unrestricted Python execution by default.

Provide preview/dry-run modes for dangerous operations where feasible.

Maintain operation logs and clear diagnostics.

Use source control, asset backups, or editor transactions for recovery, as appropriate.

Avoid returning success unless the target application confirms the requested action completed.

Execution correctness

Route Unreal editor modifications through valid Unreal editor APIs and threading contexts.

Route Blender mutations through appropriate Blender execution contexts.

Treat export/import workflows as multi-stage transactions; document partial completion.

Version-check the connected Unreal and Blender installations.

Keep adapter contracts explicit and test them independently.

Originality and independence

Do not fork, copy, or adapt implementation code from the gimmeDG repository.

Do not make Claude, Cursor, or an existing third-party Blender MCP a runtime prerequisite.

Build the editor plugins, tool schemas, workflows, and orchestration code within ForgeMCP.

Use official protocols, public documentation, language runtimes, libraries, and APIs subject to their applicable licenses.

Keep branding, architecture, and release decisions under Majestic Creations.

10. Initial Repository Structure

ForgeMCP/
│
├── server/
│ ├── main.py
│ ├── core/
│ │ ├── connection_manager.py
│ │ ├── task_router.py
│ │ ├── safety_manager.py
│ │ └── project_context.py
│ ├── adapters/
│ │ ├── unreal_adapter.py
│ │ └── blender_adapter.py
│ └── tools/
│ ├── forge.py
│ ├── editor.py
│ ├── blueprints.py
│ ├── animations.py
│ └── asset_pipeline.py
│
├── unreal-plugin/
│ └── ForgeMCP/
│ ├── Source/
│ └── Resources/
│
├── blender-addon/
│ └── forgemcp/
│
├── pipelines/
│ ├── manifests/
│ ├── exporters/
│ └── validators/
│
├── knowledge/
├── tests/
├── docs/
├── AGENTS.md
├── README.md
└── LICENSE

AGENTS.md should tell Codex when to inspect project state, when to use native Unreal APIs rather than Python, when Blender operations are appropriate, and how to verify results and respect approval requirements.

The choice of LICENSE and the precise commercialization model can be decided before publication.

11. Long-Term Direction

ForgeMCP should evolve into a comprehensive AI-assisted creative development infrastructure able to:

Implement gameplay features and construct complex Blueprint graphs.

Assemble and edit Unreal levels and assets.

Create and animate objects and characters in Blender.

Coordinate asset transfer and compatibility checks.

Validate changes and explain compilation, scripting, and import failures.

Support higher-level workflows with explicit operator control.

Remain accessible through standard MCP clients, while keeping VS Code + Codex as the main development workflow.

The aim is not to create another Claude or Cursor. It is to create the independent software layer that authorized AI agents use to interact with Unreal Engine and Blender—a layer owned and controlled by Majestic Creations.

12. Immediate Next Actions

Create an empty ForgeMCP repository.

Establish Python tooling, the official MCP SDK, linting, and tests.

Implement the server skeleton with forge_status.

Configure Codex in VS Code to connect to the new local server.

Create the original Unreal C++ Editor plugin and a read-only project-information endpoint.

Create the original Blender add-on and a read-only scene-information endpoint.

Implement the remaining first-milestone tools and run the complete Codex demonstration.

Only then begin modifying Blueprints, objects, and assets.

Foundation objective: An original MCP server, an original Unreal Engine C++ plugin, and an original Blender add-on communicating reliably—without relying on someone else's Unreal or Blender MCP implementation.

Official Documentation to Consult During Implementation

Model Context Protocol: https://modelcontextprotocol.io/

Official MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk

OpenAI Codex documentation: https://developers.openai.com/codex/

Unreal Engine documentation: https://dev.epicgames.com/documentation/en-us/unreal-engine/

Blender Python API: https://docs.blender.org/api/current/

Document note: This is a planning roadmap, not a claim that any plugin, server, Blueprint tool, or cross-application feature has already been implemented or tested. API availability and version compatibility must be confirmed during development.

© 2026 Majestic Creations — Project planning document.

## Public Unreal-MCP reference audit

The public reference command catalog and conservative Forge coverage comparison are
maintained in [Reference_Audits/Unreal_MCP_Comparison.md](Reference_Audits/Unreal_MCP_Comparison.md).
JSON and CSV companions retain every source-declared registration, signature, RPC
name and pinned source link. This is a feature requirements reference; third-party
implementation code is not a dependency. Missing commands remain development work,
subject to native APIs, explicit task authorization and the security requirements above.

## Current implementation record

The manual bidirectional handoff stage uses **Send to Unreal** in Blender and
**Send to Blender** / **Import from Blender** in Unreal. Its scope, preservation
rules and future real-time synchronization stages are documented in
[Roundtrip_Workflow.md](Roundtrip_Workflow.md). It is a bounded static-mesh stage;
the full feature roadmap remains the target.

The roadmap remains the full target. Concrete source progress, build/test results, and
remaining work are tracked separately in
[Development_Status.md](Development_Status.md); current implementation must not be
inferred from this planning document alone.

The current reference-city construction workflow is documented in
[Reference_City_Nine_Regions.md](Reference_City_Nine_Regions.md). It divides the
numbered image into nine regions with smaller spatial mesh chunks and native
editor loading-volume controllers. Saved assets, persisted level placement,
interactive streaming and performance are tracked as separate acceptance steps.
This construction workflow does not establish full spline or PCG API exposure.
