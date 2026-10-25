# Controlled native adoption activation

Status: Native activation and both native automation tests verified. Actual-chat discovery of the new MCP tools and read-only adoption preflight remain pending.

The user explicitly authorized one controlled restart and activation. PID 18588 received CloseMainWindow and exited normally. No force termination occurred. Absence of Editor processes and exclusive file access confirmed the old DLLs were unloaded before installation.

All five staged binary/metadata files were reverified against StagedBinaryManifest.json, installed as a complete set, and destination SHA-256 hashes verified. The existing project was started once using UE 5.6.1; new PID 22604 and session unreal-22604 were rediscovered through actual ForgeMCP authentication.

Startup opened the configured TestArea default. The existing open-asset tool opened L_City_World_Master in the same Editor, with saved:false. A subsequent authenticated project-info call confirmed ForgeMCPDev, UE 5.6.1, L_City_World_Master and PIE false.

Native health now advertises landscape_adoption_preflight and landscape_adoption_request. Landscape inspection reports adoption_workflow_supported:true. The production Landscape retains GUID BD45FDD94EC2A29617B50794F2DE4E9D, 2041x2041 vertices, 16 loaded proxies, and the original visible/unlocked Layer. Its height checksum remains 9f43572fbc2c06ef497da015879cdb23, with min/max 0 cm.

No adoption grant, ForgeTerrain layer, sculpting or production save occurred. No source rebuild, redesign, connection configuration change, extra Editor instance or unrelated connection repair occurred. Existing authenticated inspection works; rollback has not been invoked because native activation succeeded.

The current Codex tool namespace still lacks unreal_landscape_adoption_preflight and unreal_request_landscape_adoption. There is no exposed registered-host refresh control; the user has been asked to refresh the existing entry in the owning Codex client, preserving -B, bootstrap and the 60-second timeout. No surrogate MCP client was used as actual-client proof.

The user reported the host refresh succeeded and both tests finished. Saved/Logs/ForgeMCPDev.log independently confirms both exact native outcomes:

- Forge.Landscape.Adoption.Authorization: Test Completed, Result={Success}, line 1089; queue reports one test performed.
- Forge.Landscape.Adoption.BackupIntegrity: Test Completed, Result={Success}, line 1120; queue reports one test performed.

After that reported refresh, this chat's available tool catalog was inspected again and still contains neither new adoption MCP tool. Existing authenticated calls remain successful and native health advertises both adoption commands. This is an incomplete actual-client tool-discovery gate; no surrogate client or direct native request was used to substitute for the missing MCP preflight tool.

Fresh session/process checks still identify unreal-22604 / PID 22604 in ForgeMCPDev and L_City_World_Master, PIE stopped. Post-test Landscape inspection confirms the same GUID, all 16 proxies loaded, adoption support true, and unchanged original Layer checksum 9f43572fbc2c06ef497da015879cdb23. No ForgeTerrain exists. The two native tests passed, but actual runtime adoption preflight has not executed.

After the client refresh, discover both new MCP tools, revalidate unreal-22604/current PID and production actor identity, inspect exact native test outcomes from Saved/Logs/ForgeMCPDev.log, and execute only the read-only adoption preflight. Recompare the original Layer checksum. Do not issue an adoption request/grant, create a layer, sculpt or save.
