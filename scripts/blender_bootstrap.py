"""Run with Blender --python; enables the source add-on for this session only."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender-addon"))
import majestic_forge

majestic_forge.register()
print("ForgeMCP add-on enabled for this Blender session.")
