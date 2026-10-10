"""Real Blender background probe; own factory scene, no existing user file touched."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender-addon"))
import majestic_forge

majestic_forge.register()
try:
    # Background Blender doesn't run the interactive event loop. Pump the same
    # bridge callback on this main thread while the external MCP client inspects it.
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        majestic_forge._tick()
        time.sleep(0.02)
finally:
    majestic_forge.unregister()
