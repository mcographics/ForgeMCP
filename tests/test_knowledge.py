import json
from pathlib import Path

import pytest

from server.core.knowledge import index_blender, index_unreal, search_api


def test_local_retrieval_never_executes_stubs_and_filters_versions(tmp_path):
    engine = tmp_path / "Engine"
    (engine / "Build").mkdir(parents=True)
    (engine / "Build/Build.version").write_text(
        json.dumps({"MajorVersion": 5, "MinorVersion": 6, "PatchVersion": 1})
    )
    stub = engine / "Plugins/Experimental/PythonScriptPlugin/SphinxDocs/modules/unreal.py"
    stub.parent.mkdir(parents=True)
    marker = tmp_path / "must_not_exist"
    stub.write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\nclass Actor:\n    def set_location(self):\n        '''Set actor transform location.'''\n        ...\n"
    )
    database = tmp_path / "docs.sqlite"
    result = index_unreal(database, tmp_path)
    assert result["version"] == "5.6.1" and not marker.exists()
    hits = search_api(database, "unreal", "5.6.1", "Actor set_location")
    assert hits["indexed"] and hits["results"]
    assert any(r["symbol"] == "unreal.Actor.set_location" for r in hits["results"])
    mismatch = search_api(database, "unreal", "5.5.4", "Actor")
    assert not mismatch["indexed"] and mismatch["results"] == []
    assert index_unreal(database, tmp_path)["chunks"] == result["chunks"]


def test_native_blender_reference_retrieval_and_query_syntax_are_data(tmp_path):
    source = tmp_path / "rna.jsonl"
    source.write_text(
        json.dumps(
            {
                "version": "5.2.2",
                "symbol": "bpy.types.Mesh.from_pydata",
                "source": "native RNA",
                "text": "Create mesh vertices and faces with from_pydata.",
            }
        )
        + "\n"
    )
    database = tmp_path / "docs.sqlite"
    assert index_blender(database, source)["chunks"] == 1
    hits = search_api(database, "blender", "5.2.2", 'from_pydata OR " DROP TABLE api_docs --')
    assert hits["results"]
    assert search_api(database, "blender", "5.2.2", "mesh")["indexed"]
    with pytest.raises(ValueError):
        search_api(database, "blender", "5.2", "mesh")
    assert not search_api(Path(tmp_path / "absent.sqlite"), "blender", "5.2.2", "mesh")["indexed"]
