"""Build local version-scoped reference indexes from installed official API sources."""

import argparse
from pathlib import Path

from server.core.knowledge import index_blender, index_unreal

parser = argparse.ArgumentParser()
parser.add_argument(
    "--database",
    default=str(Path(__file__).resolve().parents[1] / "Saved/Knowledge/forge-api.sqlite"),
)
parser.add_argument("--unreal-engine")
parser.add_argument("--blender-jsonl")
args = parser.parse_args()
if args.unreal_engine:
    print(index_unreal(args.database, args.unreal_engine))
if args.blender_jsonl:
    print(index_blender(args.database, args.blender_jsonl))
if not args.unreal_engine and not args.blender_jsonl:
    parser.error("Specify an installed engine or native Blender RNA export.")
