# OnTheGoNav distance readout repair — October 12, 2026

The user reported an apparently frozen destination distance while flying. Live MCP
inspection found that `OnTheGoNav_Component.RefreshNav` already recomputes distance
from the local player's controlled pawn on its repeating timer. The widget's
`Get Distance Text` function reads the component's current `Distance to Player`.
No extra Tick update or second timer was added.

## Cause and repair

For distances between 1,000 km and 1 AU, the reachable text branch used
`Floor(DistanceCM / 100000000)` and appended `,000 km`. This quantized the displayed
distance into 1,000 km blocks. Flying a few kilometres therefore appeared to leave
the number frozen even though the underlying distance changed.

The existing `/Game/OnTheGoNAV/OnTheGoNAV` Widget Blueprint now formats the live
`DistanceCM / 100000` kilometre value with native `Conv_DoubleToString`, then appends
` km`. Both kilometre branches use that live value, and the metre branch also
formats its unrounded converted distance. Six native pin connections were verified
in both directions. Unit-selection branches, styles, destination position/offset,
astronomical unit formatting and scene transforms were preserved.

A temporary component PrintString emitted `ForgeNavDistanceCM=` to the Editor log,
with on-screen printing disabled. After the user's flight test, native reviewed
cleanup restored the original refresh execution chain, disconnected both execution
pins of the diagnostic print and set `bPrintToLog=false`. The diagnostic nodes
remain disconnected because the current tool has no node-deletion operation; they
do not execute or print. The user saved both repaired assets and the final cleanup.

## Verification

Widget edit, diagnostic insertion and cleanup each compiled with zero errors and
zero warnings. Native final inspection reports both assets up to date. The user
confirmed: **NUMBERS ARE MOVING AGAIN**.

The user-operated PIE run lasted 59.235 seconds. Its log contained 15,570 raw
distance samples across multiple destination components. In the observed nearby
range of 1e11–1e12 cm, 1,557 samples contained 1,264 unique values, from
168009079990.4113 to 168009284310.51804 cm. The unlabelled diagnostic stream is
interleaved across instances; do not attribute arbitrary adjacent samples to one
actor. The test log contained zero divide-by-zero, Accessed None or missing-media
errors. Visual movement confirmation came from the user; no automated screenshots
or fresh-Editor-process reopen were performed during this repair.

Original packages were copied and SHA-256 verified before editing under the target
project's `Saved/ForgeRepairs/DistanceReadout-20261012/` directory. Saved final hashes:

- Widget: `4112b3e03326d78ab92e476cb81b8021abf123836672272285b45c47950b4dfb`.
- Component after cleanup:
  `2315714e2ad3da88cc55d1a3fc8e21df985239d2ee757791f362784e13aaac2d`.

Token-free before/after inspections, typed recipes, previews, apply responses and
the verification report are retained in `G:/ForgeMCP/Saved/DistanceReadoutRepair/`.
No native C++ source changes, plugin rebuild, new global scripting interface or
project/level actor edits were needed.

## Remaining boundaries

The component still clamps distance at 1e14 cm, and the AU/LY branches retain their
original coarse rounding. The test exposed multiple values at that cap; very distant
markers can therefore still saturate. This repair addresses the confirmed moving
metre/kilometre readout and does not claim arbitrary astronomical precision.
Distance remains relative to the existing destination component position plus
NavOffset. Centre distance remains nonzero on a planet's surface; surface-arrival
distance would require a separate radius/surface definition.
