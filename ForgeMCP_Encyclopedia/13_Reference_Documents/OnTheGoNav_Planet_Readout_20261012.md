# Single-planet distance readout replacement

The user requested removal and replacement of the cluttered distance display,
leading to the planet in the scene. The previous isolation test established that
separate destination instances contributed the two number lines. The user also
reported that the remaining readout looked jumbled.

The intended replacement targets the loaded `BP_Planet_1` actor in `NewMap`.
Its saved object name is
`BP_Planet_1_C_UAID_701CE7E4608772BA02_1615562978`. Component widget setup will
check its owner's exact name before creating a marker and use local player
controller index 0. Other planet actors and their physical properties are
preserved; their navigation components will not create additional markers.
Renaming or recreating the target actor requires updating this explicit target.

The widget's distance binding will read the existing live `Distance to Player`,
convert centimetres to kilometres, and format through native `Conv_DoubleToText`
with grouping and at most one fraction digit. The single line is
`Planet: 1,680,092.8 km`. The old separate destination-title field will be collapsed.
World projection, the icon, the existing 30 Hz timer and pawn distance calculation
are retained. This does not add collision avoidance for multiple destination labels.

Both saved Blueprints were copied and SHA-256 verified under
`OnTheGoNav/Saved/ForgeRepairs/PlanetReadout-20261012/` before any asset edits:

- Widget: `e013b585fd0e9d17cc03b0ebc9fcf6e8f2ceb7f70196c3588d1a11e5c82b748b`.
- Component: `2315714e2ad3da88cc55d1a3fc8e21df985239d2ee757791f362784e13aaac2d`.

Server 0.3.4 and native bridge 0.2.10 add exact-GUID removal of bounded native
graph nodes (excluding events, tunnels, graph terminators and structural nodes),
with original node objects retained through compilation and reinstated before
snapshot rollback on failure. These removals require explicit task authorization
and a separate binary asset backup. The recovery journal alone is not that backup.
Five exact pure native read/format functions are allowlisted: component GetOwner,
GetObjectName, GetPlayerController, Conv_DoubleToText and Conv_TextToString.
No general execution interface is introduced.

Four typed edit recipes are staged in `Saved/PlanetReadoutRebuild/`: replacement
formatting, two bounded cleanup batches removing 53 obsolete formatting nodes,
and single-target setup replacing controller enumeration. At this checkpoint
these recipes passed Python schema validation and were applied in `unreal-31644`.
Python regression: 307 passed. Ruff passed. Full Editor build linked successfully.
The native removal/recovery and precision test passed with exit code 0 in the
disposable host. Two earlier launches failed because the test Blueprint was not
fully initialized; that fixture was corrected before the passing run. Evidence
is retained in `Saved/PlanetBridge0210/NativeTestsFinal/` and `native-final.log`.
The tested bridge was installed after the user saved and closed OnTheGoNav.
Its DLL SHA-256 is `f807af568d682afd11b9f627fdfd8f56ef706889aaf2d407d85e42d9df29910c`.

All four live edits completed with zero compiler errors and warnings. Final
inspection verified 55 removed nodes (53 formatting nodes and two controller-loop
nodes), 14 new/rewired connections in both directions, the collapsed title field
and removal of its Visibility binding. The repaired distance graph contains 17
nodes, including four unused return nodes retained because graph terminators are
outside the removal allowlist. Widget setup contains 16 nodes. The functional
distance path has one valid return and one invalid-parent fallback. Existing
unrelated graphs and scene actor transforms were preserved. The user save and
flight test completed for the kilometre version: the user reported it looks good
so far and requested a space-game unit presentation. Both repaired packages were
saved, with hashes `ab13c4e366a32e206d03b3268eb5d140e10da0f6770c86464cdc789b04d7d174`
(widget) and `83b23f2f1a1856892e586b397b7f425fe92da7cac0a3d0619e4f9fdd70d30e9a`
(component). The latest completed Play run logged no Accessed None or division
errors; it did log an unrelated duplicate `Dodge` animation-slot warning.

## Space-game unit presentation

The subsequent formatting edit keeps the single target and live distance source,
and selects unit, divisor and maximum fraction digits together:

| Raw distance | Presentation | Maximum fraction digits |
| --- | --- | --- |
| Below 1 km | metres (`m`) | 0 |
| 1 km to below 1,000 km | kilometres (`km`) | 1 |
| 1,000 km and above | light-seconds (`ls`) | 7 |

One light-second is 299,792.458 km, derived from the exact speed of light
299,792,458 m/s in the [BIPM metre definition](https://www.bipm.org/en/si-base-units/metre).
The raw centimetre divisor is therefore 29,979,245,800. The initial four-decimal
presentation meant approximately 29.98-kilometre display steps, which hid normal
flight movement. The final seven-decimal presentation uses approximately
29.98-metre steps. The example old readout 1,680,092.834 km becomes approximately
`Planet: 5.6041865 ls`. Earlier conversational estimates of 30 metres for four
decimals and 3 centimetres for seven were incorrect; these are corrected here.

The kilometre-only widget was backed up before this edit under
`Saved/ForgeRepairs/SpaceReadout-20261012/` in the target project. The typed edit
added eight pure native selection nodes and 14 connections. Live apply compiled
with zero errors and warnings; fresh inspection confirmed all 14 links in both
directions. Eight boundary/sample cases were checked by interpreting the inspected
graph's selection pins and constants; this is an offline structural/numeric check,
not live UFunction invocation. Evidence is in `Saved/SpaceReadoutRepair/`.
The initial four-decimal widget was saved with SHA-256
`984938822f878212940655574187ee869bc2f075f7e663dc96499efb978982fb`.
The user reported that version was clear but its numbers did not move.
The existing 1e14-cm component clamp remains; no interstellar-range support is claimed.

## Precision correction and final acceptance

A reviewed edit changed the distant-unit precision selector from four to seven
decimal places. A temporary log-only probe sampled the single active destination's
live raw distance. The 54.502-second flight run produced 1,633 samples with 1,618
distinct raw values, spanning 168009064214.688049 to 168009284215.21317 cm. All
samples round to one displayed value at four decimal places in light-seconds;
seven decimal places produce 75 distinct displayed values. The user confirmed
that the readout moves. The latest run logged no Accessed None or division errors.

After the run, four diagnostic nodes were removed through reviewed native edits
and the direct refresh execution chain was restored. Precision, probe setup and
cleanup all compiled with zero errors and warnings. Final native inspection
verified the diagnostic nodes are absent and the original refresh link is present.
The user saved the widget and confirmed the final component cleanup was saved.
Final disk hashes:

- Widget: `0844e56d2532a1862a0428d365fe28b48626641721398cc8b71f5c520378fd91`.
- Component: `8834436ede762f2697283e51232bd7529dcfe428563475037c0e5656151e7ece`.

Pre-edit packages are backed up under the target project's
`Saved/ForgeRepairs/SpacePrecision-20261012/`. Recipes, previews, apply responses,
cleanup inspection and runtime verification are retained in
`G:/ForgeMCP/Saved/SpacePrecisionRepair/`. No native plugin source change or rebuild
was needed for this precision correction.
