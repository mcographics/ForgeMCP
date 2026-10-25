"""Offline schema, MCP boundary and native safety-contract tests; no Editor mutations."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from server import main
from server.core.landscape import LandscapeRequest
from server.core.landscape_adoption import LandscapeAdoptionRequest

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "Plugins/Forge/Source/MajesticForge/Private"


def request(**changes):
    data = dict(
        actor_path="/Game/World.World:PersistentLevel.Landscape",
        landscape_guid="a" * 32,
        project_file="G:/Project/Game.uproject",
        world_path="/Game/World",
        world_partition=True,
        editor_pid=123,
        region=[999, 999, 1041, 1041],
        actions=["raise"],
        lifetime_seconds=600,
    )
    data.update(changes)
    return data


@pytest.mark.parametrize("change", [
    {"approved": True}, {"origin": "adopted_existing_landscape"},
    {"authorization_id": "b" * 32}, {"revoked": False},
    {"backup_root": "G:/fake"}, {"actions": ["save"]}, {"actions": ["eval"]},
    {"actions": ["raise", "raise"]}, {"actions": ["setup_layer", "raise"]},
    {"actions": []}, {"region": [10, 10, 9, 11]}, {"region": [0, 0, 2040, 2040]},
    {"lifetime_seconds": 3601}, {"lifetime_seconds": 0}, {"landscape_guid": "bad"},
    {"world_path": "/Game/World.World"}, {"world_partition": "yes"}, {"editor_pid": 0},
])
def test_adoption_cannot_supply_approval_or_unbounded_scope(change):
    with pytest.raises(ValidationError):
        LandscapeAdoptionRequest(**request(**change))


def test_layer_setup_is_separate_from_sculpt_and_original_creation_still_parses():
    assert LandscapeAdoptionRequest(**request(actions=["setup_layer"])).actions == ["setup_layer"]
    assert LandscapeAdoptionRequest(**request(actions=["setup_layer"], region=[0, 0, 2040, 2040]))
    assert LandscapeRequest(action="setup_layer", actor_path="Landscape", region=[0, 0, 2040, 2040])
    assert LandscapeRequest(action="create", map_path="/Game/ForgeMCPTests/Landscape/NewTerrain").action == "create"
    assert LandscapeRequest(action="setup_layer", actor_path="/Game/World.World:PersistentLevel.Landscape",
                            adoption_id="b" * 32).action == "setup_layer"


@pytest.mark.asyncio
@pytest.mark.parametrize(("function", "command"), [
    ("unreal_landscape_adoption_preflight", "landscape_adoption_preflight"),
    ("unreal_request_landscape_adoption", "landscape_adoption_request"),
])
async def test_mcp_only_sends_scoped_request_never_approval(monkeypatch, function, command):
    calls = []

    async def dispatch(kind, name, session, args):
        calls.append((kind, name, session, args))
        return {"ok": True, "data": {"state": "pending_local_approval"}}

    monkeypatch.setattr(main.connections, "dispatch", dispatch)
    typed = LandscapeAdoptionRequest(**request())
    await getattr(main, function)(typed, "unreal-123")
    assert calls == [("unreal", command, "unreal-123", {"request": typed.model_dump()})]
    assert "approved" not in calls[0][3]["request"]


@pytest.mark.asyncio
async def test_adoption_tools_annotations_and_schema_have_no_approval_capability():
    tools = {t.name: t for t in await main.mcp.list_tools()}
    preflight = tools["unreal_landscape_adoption_preflight"]
    assert preflight.annotations.readOnlyHint is True
    assert "unreal_approve_landscape_adoption" not in tools
    assert "unreal_revoke_landscape_adoption" not in tools
    assert tools["unreal_request_landscape_adoption"].annotations.readOnlyHint is True


def test_native_apply_has_independent_identity_scope_and_backup_checks():
    source = (NATIVE / "ForgeLandscape.cpp").read_text(encoding="utf-8")
    adoption = (NATIVE / "ForgeLandscapeAdoption.inl").read_text(encoding="utf-8")
    assert "AdoptionIdentityValues" in adoption
    for guard in ("G.bRevoked", "G.Expires>Now", "G.Actions.Contains(Action)", "G.bUsed"):
        assert guard in adoption
    apply = source[source.index("FAdoptedLandscapeGrant* ApplyAdoption=nullptr;"):]
    assert apply.index("AdoptionBackupsValid") < apply.index("Target->CreateLayer")
    assert apply.index("AdoptionClean") < apply.index("Target->CreateLayer")
    assert apply.index("AdoptionCheckpointScopeMatches") < apply.index("Target->CreateLayer")
    assert 'const bool bAuthorizedExistingWorldOperation = !Adoption && bPreviewGrant' in source
    assert 'P.bHasExistingWorldAuthorization=false;' in source
    assert 'LexToString(Manifest)!=G.ManifestHash' in adoption
    assert "ReadRegion(P.Actor.Get(),P.Layer,P.Bounds" in apply
    assert "FindAdoption(J.Plan.AdoptionId,W,L,Action,&J.Plan.Bounds,true)" in source
    assert "AdoptionBackupFilesPresent(*Grant)" in source
    # Original grant-created ownership checks remain in force.
    assert "AuthorizedExistingWorldLandscapes.Find(PreviewGrant.Id)" in source
    assert "ReadExistingWorldAuthorization" in source


def test_preview_and_preflight_never_create_layers_or_approve():
    source = (NATIVE / "ForgeLandscape.cpp").read_text(encoding="utf-8")
    preview = source[source.index('if (Command == TEXT("landscape_preview"))'):
                     source.index('if(Command != TEXT("landscape_apply"))')]
    for forbidden in ("CreateLayer(", "SetHeightData(", "SavePackage(", "BackupExistingWorldWriteScope("):
        assert forbidden not in preview
    adoption = (NATIVE / "ForgeLandscapeAdoption.inl").read_text(encoding="utf-8")
    handler = adoption[adoption.index("bool HandleAdoptionRequest"):adoption.index("void ApproveLandscapeAdoption")]
    assert "bApproved=true" not in handler
    assert "BackupExistingWorldWriteScope" not in handler
    assert 'if (Command==TEXT("landscape_adoption_preflight")) return true;' in handler
    approval = adoption[adoption.index("void ApproveLandscapeAdoption"):]
    assert approval.index("FMessageDialog::Open") < approval.index("BackupExistingWorldWriteScope")
    assert approval.index("BackupExistingWorldWriteScope") < approval.index("G->bApproved=true")


def test_localized_read_skips_unaffected_texture_data():
    source = (NATIVE / "ForgeLandscape.cpp").read_text(encoding="utf-8")
    read = source[source.index("bool ReadRegion("):source.index("bool ParseInclusiveRegion(")]
    assert read.index("if(LocalX2<LocalX1 || LocalY2<LocalY1) continue;") < read.index("Texture->Source.GetMipData")


def test_layer_setup_preserves_original_layers_and_has_recovery():
    source = (NATIVE / "ForgeLandscape.cpp").read_text(encoding="utf-8")
    setup = source[source.index('if (Action==TEXT("setup_layer"))', source.index("FAdoptedLandscapeGrant* ApplyAdoption")):
                   source.index('if(Action==TEXT("create") || Action==TEXT("create_in_place"))', source.index("FAdoptedLandscapeGrant* ApplyAdoption"))]
    assert 'CreateLayer(FName(TEXT("ForgeTerrain")))' in setup
    assert "DeleteLayers(" not in setup
    assert "SetLayerName" not in setup
    assert "Target->DeleteLayer(Index)" in setup
    assert "Transaction.Cancel()" in setup
    assert 'SetBoolField(TEXT("saved"),false)' in setup
