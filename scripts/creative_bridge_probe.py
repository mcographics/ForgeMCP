"""Disposable background bridge loop for real MCP acceptance, never an open user scene."""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender-addon"))
import majestic_forge

majestic_forge.register()
root = Path(os.environ["FORGE_CREATIVE_TEST_ROOT"])
(root / "bridge-ready").write_text("ready", encoding="ascii")
deadline = time.monotonic() + 240
while time.monotonic() < deadline and not (root / "stop").exists():
    majestic_forge._bridge.tick()
    time.sleep(0.01)
majestic_forge.unregister()
