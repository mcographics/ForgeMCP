from pathlib import Path

ADDON_SOURCE = Path(__file__).resolve().parents[1] / "blender-addon" / "majestic_forge" / "__init__.py"


def test_blender_release_advertises_compatible_protocol_and_bidirectional_transfer():
    source = ADDON_SOURCE.read_text(encoding="utf-8")

    assert '"version": (0, 2, 36)' in source
    assert 'ADDON_VERSION = "0.2.36-alpha.1"' in source
    assert "BRIDGE_PROTOCOL_VERSION = 1" in source
    assert "TRANSFER_CONTRACT_VERSION = 1" in source
    assert '"bridge_protocol_version": BRIDGE_PROTOCOL_VERSION' in source
    assert '"transfer_contract_version": TRANSFER_CONTRACT_VERSION' in source
    for capability in ("export_preview", "export_apply", "import_preview", "import_apply"):
        assert f'"{capability}"' in source
    assert 'text="Bridge running"' in source
    assert '"Last authenticated request:' in source
