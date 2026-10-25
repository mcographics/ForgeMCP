# ForgeMCP — TestArea quick read-only inspection

Date: October 22, 2026 (America/Toronto)  
Verdict: **Native Landscape identified; exact visual failure not confirmed. Leading hypothesis: visibility/culling or Landscape-to-HLOD mismatch, rather than camera-relative terrain generation.**

## Confirmed from saved files

- The level is `Content/Levels/TestArea.umap`. Its external actor packages reference one native Landscape, 64 Landscape streaming proxies and 64 World Partition HLOD actors. These are saved-package findings, not a live loaded-actor inventory.
- The main Landscape package is `Content/__ExternalActors__/Levels/TestArea/D/SN/4H39SLIT99B3RAZ8H7S5HX.uasset`. It records `ReimportHeightmapFilePath` as **D:/Users/arran/Desktop/Blur_H.png**. That original file is absent at the recorded path. This identifies the saved reimport source; it does not prove it is the latest import, and its absence alone does not establish the reported visual failure.
- Landscape/proxy packages reference native Landscape components, embedded heightmap data and **/Engine/OpenWorldTemplate/LandscapeMaterial/M_ProcGrid**. A representative proxy is `Content/__ExternalActors__/Levels/TestArea/0/2V/D8TFLT7DUV8I19HRTJ2J8H.uasset`.
- The terrain HLOD packages reference the Open World template HLOD layer, grid material, and source Landscape proxies under **/Engine/Maps/Templates/OpenWorld**. Example: `Content/__ExternalActors__/Levels/TestArea/0/1X/L75H3QUVW529F4XV64DP11.uasset`. Those retained template references warrant checking whether the HLOD representation matches the imported terrain; they do **not** by themselves prove stale HLODs.
- The inspected external packages contain Ultra Dynamic Sky/Weather Blueprint references, but no identified Blueprint/PCG/procedural-mesh terrain generator. The project source search found no TestArea-specific camera-follow terrain implementation. The referenced M_ProcGrid asset contains a WorldPosition expression; no CameraPosition expression name was found in its extracted strings. This is not a complete material graph/link inspection.

## Likely cause and limits

**Working hypothesis:** the terrain is remaining in world space while a view-dependent rendering, bounds, streaming or HLOD transition makes its visible representation disappear or appear displaced. The saved native Landscape/proxy/HLOD structure supports investigating that path first. Camera-relative spawning or a camera-follow Blueprint is **not supported by the evidence collected**.

Actual actor movement, invalid component bounds, occlusion, distance culling, proxy loading/unloading, HLOD replacement and actor destruction remain **unverified**. Serialized property names do not reveal their effective runtime values. No particular Blueprint, PCG graph, material node or component has been proven defective.

## Smallest recommended correction

Do not rewrite placement logic or add camera offsets on this evidence. If a stale/mismatched terrain HLOD is confirmed later, refresh **only TestArea's affected terrain HLOD representation**. If the proxies' bounds are instead inconsistent with the imported heights, correct **only the affected Landscape component bounds/data**. These are conditional recommendations, not verified fixes; the current evidence is insufficient to choose between them safely.

## Read-only boundary

ForgeMCP live inspection tools were unavailable in this chat, so this was limited to existing configuration/logs and printable metadata/reference strings in saved assets. No Editor was launched, level opened/switched, camera moved, graph executed, test run or plugin rebuilt. No asset, code, setting or level was modified; only this report was created. **L_City_World_Master was untouched.** No further investigation or repair was initiated. The Python host refresh and /Script/SlateCore dirty-package blockers remain separate and unchanged.
