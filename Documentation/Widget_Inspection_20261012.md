# Bounded Unreal widget inspection and text hiding

MCP server 0.3.3 and Unreal bridge 0.2.9 extend existing Blueprint inspection with
the Widget Blueprint designer tree and editor bindings. Inspection reports at most
256 widgets and 512 bindings; it does not report live viewport instances or inherited
trees. Text fields include template text, font size and automatic wrapping.

Existing Blueprint edit recipes accept an optional `widgets` array, with at most
32 exact-name `hide_text` operations. The native operation accepts only existing
TextBlocks, collapses the selected field and removes its Visibility binding so that
the binding cannot immediately override the change. Text bindings and other fields
are preserved. No widget is deleted and no existing asset is saved automatically.
Visibility and complete editor-binding recovery are included in stale-preview
fingerprints and rollback snapshots. Oversized mutation snapshots are rejected.
Graph-only payloads omit the empty array for compatibility with older bridges.

Validation: 303 Python tests and Ruff passed. The UE 5.6.1 Editor target completed
DLL linking and target metadata generation. Both native automation tests passed
in a disposable host: exact-text hiding and visibility-binding recovery, and
oversized-tree mutation rejection. The first commandlet launch in ForgeMCPDev
failed at Editor startup with a SharedPointer assertion before running tests; the
isolated host completed with exit code 0. Evidence is in
`Saved/WidgetBridge029/` and `Saved/WidgetNativeTests029/`.

The tested plugin was installed into OnTheGoNav after the user saved and closed
Unreal. The installer backed up the previous plugin and project descriptor. The
reopened session `unreal-2132` confirmed the correct project, and the loaded DLL
path and SHA-256 matched the tested build:
`F71803794AB2391F523ADAD9182028F4A1F7856275813B16CBE922681C8A2470`.

Live inspection of `/Game/OnTheGoNAV/OnTheGoNAV` found seven template widgets and
11 bindings. Its two TextBlocks are `DistanceText` and `Location`; the latter
reads the component's `Nav Text`, while the former binds to the distance function.
There is no second distance field in this template. No `hide_text` mutation was
applied to it. During the user-operated Play run, actor enumeration listed ten
planet destinations. Detailed actor/component inspection is currently blocked
during PIE. Overlapping marker instances remain a hypothesis requiring isolation
and visual confirmation.

The isolation test temporarily set only the loaded `BP_Planet_1` navigation
component's `DistanceTextVisible` from true to false through reviewed native
component preview/apply. The user then ran Play and confirmed one distance line
remained. This establishes that the two observed lines belong to separate markers,
rather than two text fields in one widget. After Play stopped, a second reviewed
edit restored true and a fresh inspection verified it. Neither diagnostic edit
saved the level. The permanent display treatment is awaiting the user's preference;
the duplicate-line repair is not yet complete.
