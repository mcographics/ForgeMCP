"""Create an independent minimal Unreal development host without copying local settings."""

import argparse
import json
import shutil
from pathlib import Path


def create_host(destination: Path, engine_version: str = "5.6") -> Path:
    repository = Path(__file__).resolve().parents[1]
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError("Destination exists; choose a new development-host directory.")
    plugin = repository / "Plugins" / "MajesticForge"
    if not (plugin / "MajesticForge.uplugin").is_file():
        raise FileNotFoundError("ForgeMCP plugin source was not found.")
    destination.mkdir(parents=True)
    target = destination / "Plugins" / "MajesticForge"
    target.mkdir(parents=True)
    for folder in ("Source", "Config", "Resources"):
        if (plugin / folder).is_dir():
            shutil.copytree(plugin / folder, target / folder)
    shutil.copy2(plugin / "MajesticForge.uplugin", target / "MajesticForge.uplugin")
    if (plugin / "LICENSE.txt").is_file():
        shutil.copy2(plugin / "LICENSE.txt", target / "LICENSE.txt")
    project = destination / "ForgeMCPDev.uproject"
    project.write_text(json.dumps({"FileVersion":3,"EngineAssociation":engine_version,
        "Category":"Development","Description":"Minimal ForgeMCP plugin development host",
        "Plugins":[{"Name":"MajesticForge","Enabled":True},
                   {"Name":"GameplayAbilities","Enabled":True}]},indent=2)+"\n",encoding="utf-8")
    return project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination",type=Path,required=True)
    parser.add_argument("--engine-version",default="5.6")
    args = parser.parse_args()
    print(create_host(args.destination,args.engine_version))


if __name__ == "__main__":
    main()
