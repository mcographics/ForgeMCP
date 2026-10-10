"""Version-scoped local API retrieval. Indexing never imports or executes source text."""

import json
import re
import sqlite3
from pathlib import Path


def schema(connection):
    connection.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS api_docs USING fts5(application UNINDEXED, version UNINDEXED, symbol, source UNINDEXED, line UNINDEXED, text)"
    )


def index_unreal(database, engine_root):
    engine_root = Path(engine_root)
    build = json.loads((engine_root / "Engine/Build/Build.version").read_text())
    version = ".".join(
        str(build[field]) for field in ("MajorVersion", "MinorVersion", "PatchVersion")
    )
    source = (
        engine_root / "Engine/Plugins/Experimental/PythonScriptPlugin/SphinxDocs/modules/unreal.py"
    )
    if not source.is_file() or source.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Expected the installed engine's bounded official Python API stub.")
    database = Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with sqlite3.connect(database) as connection:
        schema(connection)
        connection.execute(
            "DELETE FROM api_docs WHERE application=? AND version=?", ("unreal", version)
        )
        owner, symbol, start, lines = "", "unreal", 1, []

        def emit():
            nonlocal count
            if lines:
                connection.execute(
                    "INSERT INTO api_docs VALUES (?,?,?,?,?,?)",
                    ("unreal", version, symbol, str(source), start, "".join(lines)[:6000]),
                )
                count += 1

        with source.open(encoding="utf-8-sig") as stream:
            for number, line in enumerate(stream, 1):
                cls = re.match(r"^class ([A-Za-z_][A-Za-z0-9_]*)", line)
                method = re.match(r"^    (?:async )?def ([A-Za-z_][A-Za-z0-9_]*)", line)
                if cls or method or len(lines) >= 60:
                    emit()
                    lines, start = [], number
                    if cls:
                        owner, symbol = cls[1], "unreal." + cls[1]
                    elif method:
                        symbol = "unreal." + owner + "." + method[1]
                lines.append(line)
            emit()
    return {"application": "unreal", "version": version, "chunks": count, "source": str(source)}


def index_blender(database, source):
    source = Path(source)
    database = Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    count, versions = 0, set()
    with sqlite3.connect(database) as connection:
        schema(connection)
        with source.open(encoding="utf-8") as stream:
            for line in stream:
                record = json.loads(line)
                version = record["version"]
                if version not in versions:
                    connection.execute(
                        "DELETE FROM api_docs WHERE application=? AND version=?",
                        ("blender", version),
                    )
                    versions.add(version)
                connection.execute(
                    "INSERT INTO api_docs VALUES (?,?,?,?,?,?)",
                    (
                        "blender",
                        version,
                        record["symbol"],
                        record["source"],
                        0,
                        record["text"][:6000],
                    ),
                )
                count += 1
    return {"application": "blender", "versions": sorted(versions), "chunks": count}


def search_api(database, application, version, query, limit=5):
    if (
        application not in {"unreal", "blender"}
        or not re.fullmatch(r"\d+\.\d+\.\d+", version)
        or not 1 <= limit <= 20
        or not isinstance(query, str)
        or len(query) > 400
    ):
        raise ValueError("Use an application, exact numeric version, bounded query and limit.")
    terms = re.findall(r"[A-Za-z0-9_]+", query)[:12]
    if not terms:
        raise ValueError("Query must contain API names or keywords.")
    database = Path(database)
    if not database.is_file():
        return {"indexed": False, "application": application, "version": version, "results": []}
    # Read-only SQLite connection; model query text is never executable SQL or FTS syntax.
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        versions = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT version FROM api_docs WHERE application=?", (application,)
            )
        ]
        expression = " OR ".join('"' + term + '"' for term in terms)
        rows = connection.execute(
            "SELECT symbol, source, line, text FROM api_docs WHERE api_docs MATCH ? AND application=? AND version=? ORDER BY bm25(api_docs) LIMIT ?",
            (expression, application, version, limit),
        ).fetchall()
    return {
        "indexed": version in versions,
        "application": application,
        "version": version,
        "available_versions": sorted(versions),
        "results": [
            {"symbol": symbol, "source": source, "line": line, "excerpt": text[:2500]}
            for symbol, source, line, text in rows
        ],
        "execution": "Reference data only; check native capabilities before constructing a recipe.",
    }
