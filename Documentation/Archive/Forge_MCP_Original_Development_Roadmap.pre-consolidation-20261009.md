# Majestic Forge MCP

## Original Development Roadmap — Unreal Engine + Blender + VS Code + OpenAI Codex

**Organization:** Majestic Creations\
**Project name:** Majestic Forge MCP (working title)\
**Document version:** 1.0 — Initial Planning\
**Date:** October 8, 2026\
**Project status:** Concept and architecture planning\
**Primary development environment:** Visual Studio Code with OpenAI Codex

---

## 1. Project Decision: Build Our Own From Scratch

**Majestic Forge MCP will be an original software project.**

We will not fork, copy, or build upon gimmeDG's Unreal Engine MCP repository, and we will not depend on a third-party Unreal or Blender MCP implementation. The objective is to build and maintain our own source code, architecture, command system, editor integrations, documentation, and workflows.

The system will use **open standards and documented development APIs**, including the Model Context Protocol (MCP), Unreal Engine editor APIs, and Blender's Python API. Using an official protocol SDK is different from copying another developer's Unreal Engine integration: the integrations and application logic will be authored for this project.

**Non-negotiable direction:**

- Original MCP server and tool definitions.
- Original Unreal Engine C++ editor plugin.
- Original Blender Python add-on.
- Native compatibility with **OpenAI Codex in Visual Studio Code** as the primary tested client.
- **No required Claude or Cursor dependency.**
- Provider-independent MCP interfaces so other compatible clients could be supported later.
- A shared Unreal/Blender asset and automation pipeline developed and controlled by Majestic Creations.

---

## 2. Purpose and Vision

Build a **Codex-first, AI-assisted game-development automation platform** that allows a developer to enter natural-language instructions in VS Code and have a local MCP server coordinate actions in Unreal Engine and Blender.

The ambition goes beyond running isolated scripts. The finished system should be capable of:

- Inspecting a project's state before performing a task.
- Creating and modifying Unreal actors, levels, assets, and Blueprint graphs.
- Compiling Blueprints and reporting actionable errors.
- Editing objects, rigs, materials, and animation data in Blender.
- Transferring validated assets from Blender into Unreal Engine.
- Orchestrating multi-step workflows across both applications.
- Producing clear status reports, diagnostic information, and recoverable changes.

Codex is the preferred user-facing AI agent, **not a hard dependency built into the MCP protocol server**. The server should expose standards-compliant tools to any client that is appropriately configured and authorized.

---

## 3. Original System Architecture

```text
                  ┌──────────────────────────────────┐
                  │  Visual Studio Code + Codex     │
                  │  AI instructions / orchestration │
                  └─────────────────┬────────────────┘
                                    │
                            MCP (local stdio)
                                    │
                  ┌─────────────────▼────────────────┐
                  │      MAJESTIC FORGE CORE         │
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
```

### Architecture principles

1. **Single MCP entry point:** The core server exposes tools to Codex and routes them to the correct application adapter.
2. **Application-specific bridges:** Unreal and Blender each execute commands using their own native APIs and execution models.
3. **Local communication by default:** Do not expose the editor-control interfaces publicly on the network.
4. **Validate before modifying:** Inspect available sessions, project state, asset compatibility, and command arguments before actions.
5. **Keep boundaries clean:** Do not embed Codex-specific agent logic inside the Unreal or Blender adapters.
6. **Use structured results:** Return machine-readable results along with useful human-readable explanations.

---

## 4. Planned Technology Stack

| Component | Planned technology | Responsibility |
|---|---|---|
| Development IDE | Visual Studio Code | Coding, debugging, repository work |
| Primary AI agent | OpenAI Codex | Initiating and coordinating MCP tool calls |
| MCP server | Python 3.11+ (external runtime) | Tool registration, dispatch, validation, orchestration |
| MCP library | Official Python MCP SDK, supported stable release | Standards-compliant MCP transport and schemas |
| Unreal Engine target | Unreal Engine 5.6 initially | Primary game-development environment |
| Unreal editor integration | Original C++ Editor plugin | Native Blueprint, editor, graph, and asset operations |
| Unreal automation | Unreal Python API where suitable | Supported editor scripting and batch operations |
| Blender integration | Original Python add-on using `bpy` | Scene, mesh, rig, material, and animation operations |
| MCP transport | `stdio` initially | Codex-to-server connection |
| Application transport | Local authenticated IPC | Core-to-editor communication |
| Commands/metadata | JSON and validated schemas | Requests, tool results, status, manifests |
| Asset interchange | FBX / glTF / USD as appropriate | Blender-to-Unreal assets, subject to format capabilities |
| Automated tests | `pytest` + Unreal Automation Tests | Core logic and editor behavior |
| Source control | Git + original GitHub repository | Code history and release management |

**Implementation note:** Unreal's embedded Python runtime and Blender's Python runtime may differ from the standalone MCP server's Python environment. The adapters must communicate across process boundaries rather than assume the same Python environment or package versions.

---

## 5. Feature Modules

### 5.1 Unreal Engine Control Module

Planned capabilities:

- Inspect engine version, loaded project, current level, and editor state.
- List, create, place, inspect, modify, and organize level actors.
- Create and edit Blueprint assets, classes, variables, components, functions, and event graphs.
- Create Blueprint nodes and connect pins with validation.
- Compile Blueprints; collect errors, warnings, and success status.
- Create and modify material assets and material instances.
- Support Gameplay Ability System (GAS) workflows.
- Support procedural level generation and PCG workflows.
- Inspect and work with skeletal meshes, animations, and retargeting assets.
- Import, export, locate, rename, and validate assets.
- Query editor logs and project diagnostics.

**Engineering consideration:** Blueprint graph creation requires native editor-facing APIs for reliable, comprehensive operations. The Unreal bridge should be a hybrid of C++ editor functionality and Python automation where documented and suitable, not a Python-only system.

### 5.2 Blender Control Module

The Blender integration will be an **original add-on**, written specifically for Majestic Forge MCP. Planned capabilities:

- Detect Blender sessions and identify the active file and scene.
- List and inspect objects, collections, modifiers, and transforms.
- Create and modify mesh objects and geometry.
- Create and inspect materials and texture references.
- Inspect armatures, bones, bone naming, parenting, and skin weights.
- Create and modify keyframes, actions, and animation data.
- Configure animation frame rates (including 30 FPS workflows).
- Validate scale, coordinate-system conversion, mesh data, and exports.
- Export supported asset formats using explicit preset configurations.
- Return structured scene and operation reports to Codex.

**Engineering consideration:** Run Blender scene modifications in an appropriate main-thread execution context. Do not directly mutate Blender data from arbitrary background threads.

### 5.3 Cross-Application Asset Pipeline

This pipeline coordinates Blender and Unreal rather than treating them as unrelated tools.

Planned workflow:

1. Inspect an object, rig, or animation in Blender.
2. Check scale, transforms, hierarchy, bones, skin weights, material dependencies, and timing.
3. Produce a structured asset manifest and validation report.
4. Export using an appropriate format and tested settings.
5. Hand off the manifest and exported files to the Unreal adapter.
6. Import assets into the target Unreal project.
7. Assign or validate the intended skeleton where applicable.
8. Verify import results and report errors or incompatibilities.

This could later support DAZ-to-Unreal character-processing workflows, but those are **future integrations**, not part of the first milestone. Licensing and commercial-use eligibility must be checked separately from technical conversion.

---

## 6. Development Roadmap

### Phase 1 — Original MCP Foundation

**Goal:** Build the server from an empty repository, with no third-party Unreal/Blender MCP code.

- Initialize repository, package structure, and development environment.
- Implement the MCP server using the official SDK.
- Create the tool registry, argument schemas, and structured response conventions.
- Create configuration, log files, status reporting, and error handling.
- Implement session discovery, health checks, and task dispatch.
- Configure Codex in VS Code to communicate with the new server.

**Exit criterion:** Codex recognizes Majestic Forge MCP and can call its diagnostic tools.

### Phase 2 — Original Unreal Engine Plugin

**Goal:** Implement reliable engine integration for Unreal Engine 5.6 initially.

- Create an Unreal Editor plugin in C++.
- Provide a secure local command endpoint.
- Expose engine/project metadata, editor connectivity, and actor inspection.
- Ensure engine APIs run in the appropriate editor context/thread.
- Return structured success/errors for every operation.

**Exit criterion:** Codex can read project metadata and list actors in the active level.

### Phase 3 — Blueprint Engineering

**Goal:** Make programmatic Blueprint construction and validation practical.

- Create Blueprint assets and classes.
- Add variables, components, and functions.
- Create nodes and connect graph pins.
- Validate graph integrity and compile assets.
- Return compiler warnings/errors and affected asset paths.
- Expand to reusable gameplay and GAS templates.

**Exit criterion:** Codex creates, compiles, and places a working Blueprint actor in a test level.

### Phase 4 — Original Blender Add-on

**Goal:** Implement independent Blender control using an original Python add-on.

- Establish session connection and scene inspection.
- Implement object/collection operations.
- Add mesh, material, rig, and animation tools.
- Expose safe execution and consistent error responses.
- Implement export presets and asset checks.

**Exit criterion:** Codex can inspect and modify a Blender scene using Majestic Forge tools.

### Phase 5 — Unified Unreal + Blender Workflows

**Goal:** Coordinate supported tasks across both applications.

- Define shared asset manifest schemas.
- Add reliable Blender export and Unreal import transactions.
- Implement coordinate, scale, material, skeleton, and animation checks.
- Report each step and prevent silent partial failures.
- Track output assets and maintain workflow logs.

**Exit criterion:** Codex modifies a simple Blender asset and imports it into Unreal with a validation report.

### Phase 6 — Context, Intelligence, Reliability, and Packaging

**Goal:** Prepare the platform for larger real-world projects.

- Add version-aware Unreal and Blender API documentation retrieval.
- Build project-specific indexing and diagnostics.
- Introduce previews/dry-run modes for destructive operations.
- Implement approval gates, operation logs, and recoverability.
- Add comprehensive tests, installer/setup utilities, and documentation.
- Prepare a distribution strategy for Majestic Creations.

**Exit criterion:** Repeatable workflows, understandable diagnostics, tested safeguards, and documented installation.

---

## 7. First Milestone: Five Original MCP Tools

The first working version should expose exactly the following foundational tool interfaces (names are provisional):

| MCP tool | Purpose | Initial behavior |
|---|---|---|
| `forge_status` | Overall bridge health | Reports MCP status and connected adapter health |
| `forge_list_sessions` | Discover running targets | Lists authorized Unreal and Blender sessions |
| `unreal_project_info` | Inspect the active Unreal project | Returns engine version, project name, and relevant metadata |
| `unreal_list_actors` | Inspect the current Unreal level | Returns actor identifiers, names, classes, and paths where available |
| `blender_scene_info` | Inspect the active Blender scene | Returns scene name, objects summary, frame settings, and add-on status |

**Milestone acceptance test:** Codex in VS Code discovers all five tool definitions, invokes each appropriate tool, and receives correct, structured results from the MCP server and the connected applications.

### Recommended first demonstration

In VS Code, ask Codex:

> Connect to Majestic Forge MCP. Report which Unreal Engine and Blender sessions are running. Read the active Unreal project's version and level actors. Read the active Blender scene and frame rate. Do not modify either project.

**Expected result:** A complete read-only report, with useful errors if an application is closed or the relevant plugin/add-on is not installed.

---

## 8. Second Milestone: Blueprint + Blender Proof of Concept

### Unreal demonstration

> Create a new Blueprint actor in the test project, add a component, compile the Blueprint, place one instance in the test level, and report whether compilation and placement succeeded.

### Blender-to-Unreal demonstration

> Inspect and modify a simple mesh in Blender, validate its transforms, export it, import it into the current Unreal project, and report the new asset path and any import warnings.

Both demos should be **repeatable on a clean test project** without manual intervention in the graph editor or repetitive asset-import dialogs.

---

## 9. Safety, Reliability, and Ownership Requirements

### Project safety

- Restrict editor control to local, authorized sessions by default.
- Validate tool arguments and project paths before executing commands.
- Require explicit confirmation for deletion, overwriting, arbitrary code execution, and other high-impact actions.
- Disable unrestricted Python execution by default.
- Provide preview/dry-run modes for dangerous operations where feasible.
- Maintain operation logs and clear diagnostics.
- Use source control, asset backups, or editor transactions for recovery, as appropriate.
- Avoid returning success unless the target application confirms the requested action completed.

### Execution correctness

- Route Unreal editor modifications through valid Unreal editor APIs and threading contexts.
- Route Blender mutations through appropriate Blender execution contexts.
- Treat export/import workflows as multi-stage transactions; document partial completion.
- Version-check the connected Unreal and Blender installations.
- Keep adapter contracts explicit and test them independently.

### Originality and independence

- Do **not** fork, copy, or adapt implementation code from the gimmeDG repository.
- Do **not** make Claude, Cursor, or an existing third-party Blender MCP a runtime prerequisite.
- Build the editor plugins, tool schemas, workflows, and orchestration code within Majestic Forge.
- Use official protocols, public documentation, language runtimes, libraries, and APIs subject to their applicable licenses.
- Keep branding, architecture, and release decisions under Majestic Creations.

---

## 10. Initial Repository Structure

```text
MajesticForge-MCP/
│
├── server/
│   ├── main.py
│   ├── core/
│   │   ├── connection_manager.py
│   │   ├── task_router.py
│   │   ├── safety_manager.py
│   │   └── project_context.py
│   ├── adapters/
│   │   ├── unreal_adapter.py
│   │   └── blender_adapter.py
│   └── tools/
│       ├── forge.py
│       ├── editor.py
│       ├── blueprints.py
│       ├── animations.py
│       └── asset_pipeline.py
│
├── unreal-plugin/
│   └── MajesticForge/
│       ├── Source/
│       └── Resources/
│
├── blender-addon/
│   └── majestic_forge/
│
├── pipelines/
│   ├── manifests/
│   ├── exporters/
│   └── validators/
│
├── knowledge/
├── tests/
├── docs/
├── AGENTS.md
├── README.md
└── LICENSE
```

`AGENTS.md` should tell Codex when to inspect project state, when to use native Unreal APIs rather than Python, when Blender operations are appropriate, and how to verify results and respect approval requirements.

The choice of **LICENSE** and the precise commercialization model can be decided before publication.

---

## 11. Long-Term Direction

Majestic Forge MCP should evolve into a comprehensive AI-assisted creative development infrastructure able to:

- Implement gameplay features and construct complex Blueprint graphs.
- Assemble and edit Unreal levels and assets.
- Create and animate objects and characters in Blender.
- Coordinate asset transfer and compatibility checks.
- Validate changes and explain compilation, scripting, and import failures.
- Support higher-level workflows with explicit operator control.
- Remain accessible through standard MCP clients, while keeping **VS Code + Codex** as the main development workflow.

The aim is **not to create another Claude or Cursor**. It is to create the independent software layer that authorized AI agents use to interact with Unreal Engine and Blender—a layer owned and controlled by Majestic Creations.

---

## 12. Immediate Next Actions

1. Create an empty `MajesticForge-MCP` repository.
2. Establish Python tooling, the official MCP SDK, linting, and tests.
3. Implement the server skeleton with `forge_status`.
4. Configure Codex in VS Code to connect to the new local server.
5. Create the original Unreal C++ Editor plugin and a read-only project-information endpoint.
6. Create the original Blender add-on and a read-only scene-information endpoint.
7. Implement the remaining first-milestone tools and run the complete Codex demonstration.
8. Only then begin modifying Blueprints, objects, and assets.

**Foundation objective:** An original MCP server, an original Unreal Engine C++ plugin, and an original Blender add-on communicating reliably—without relying on someone else's Unreal or Blender MCP implementation.

---

## Official Documentation to Consult During Implementation

- Model Context Protocol: https://modelcontextprotocol.io/
- Official MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- OpenAI Codex documentation: https://developers.openai.com/codex/
- Unreal Engine documentation: https://dev.epicgames.com/documentation/en-us/unreal-engine/
- Blender Python API: https://docs.blender.org/api/current/

> **Document note:** This is a planning roadmap, not a claim that any plugin, server, Blueprint tool, or cross-application feature has already been implemented or tested. API availability and version compatibility must be confirmed during development.

**© 2026 Majestic Creations — Project planning document.**
