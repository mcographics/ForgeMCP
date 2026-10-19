"""Copy the self-contained React production build into the engine plugin resources."""

from __future__ import annotations

import argparse
import base64
import hashlib
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from verify_unreal_tab_ui import validate_html


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plugin",
        type=Path,
        default=Path(r"G:\Program Files\EpicGames\UE_5.6\Engine\Plugins\Marketplace\Forge"),
        help="Authoritative engine plugin source folder",
    )
    args = parser.parse_args()
    source = repo / "web-ui" / "dist"
    destination = args.plugin.resolve(strict=True) / "Resources" / "ReactUI"
    if not (source / "index.html").is_file():
        raise SystemExit("Build web-ui first with npm run build.")
    files = sorted(path for path in source.rglob("*") if path.is_file())
    if not files or any(path.is_symlink() for path in files):
        raise SystemExit("The React UI build is empty or contains a symlink.")
    html = (source / "index.html").read_text(encoding="utf-8")
    if "connect-src 'none'" not in html:
        raise SystemExit("The generated UI must keep a local-only content security policy.")
    script_tag = re.search(r'<script\s+type="module"[^>]*src="([^"]+)"[^>]*></script>', html)
    style_tag = re.search(r'<link\s+rel="stylesheet"[^>]*href="([^"]+)"[^>]*>', html)
    if not script_tag or not style_tag:
        raise SystemExit("Expected one Vite module bundle and one stylesheet link.")

    def read_build_asset(relative: str) -> str:
        path = (source / relative).resolve(strict=True)
        path.relative_to(source.resolve(strict=True))
        return path.read_text(encoding="utf-8")

    javascript = read_build_asset(script_tag.group(1))
    css = read_build_asset(style_tag.group(1))
    if re.search(r"(?m)^\s*(?:import\s|export\s)", javascript):
        raise SystemExit("Expected a self-contained Vite JavaScript bundle without module imports.")
    if "data:image/" not in javascript or re.search(r"url\((?!data:)[^)]+\)", css):
        raise SystemExit("The inlined UI must not depend on sibling file assets.")

    script_hash = base64.b64encode(hashlib.sha256(javascript.encode("utf-8")).digest()).decode("ascii")
    inline_script = f'<script type="module">{javascript}</script>'
    inline_style = f"<style>{css}</style>"
    html = html.replace(script_tag.group(0), inline_script, 1)
    html = html.replace(style_tag.group(0), inline_style, 1)
    html, csp_count = re.subn(
        r"script-src 'self' file:", f"script-src 'sha256-{script_hash}'", html, count=1
    )
    if csp_count != 1 or re.search(r"<(?:script|link)[^>]+(?:src|href)=", html):
        raise SystemExit("Inline HTML failed the CSP or external-resource checks.")
    if "connect-src 'none'" not in html or "default-src 'none'" not in html:
        raise SystemExit("The generated single-file UI must keep its restrictive content policy.")
    validate_html(html)

    destination.mkdir(parents=True, exist_ok=True)
    target = destination / "index.html"
    payload = html.encode("utf-8")
    if target.exists() and target.read_bytes() != payload:
        backup_root = repo / "Artifacts" / "Backups"
        backup_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = backup_root / f"ForgeMCP-ReactUI-index-{stamp}.html"
        shutil.copy2(target, backup)
        print(f"Previous React UI entry preserved at {backup}")
    with tempfile.NamedTemporaryFile(dir=destination, prefix="index-", suffix=".tmp", delete=False) as temp:
        staged = Path(temp.name)
        temp.write(payload)
        temp.flush()
    staged.replace(target)
    digest = hashlib.sha256(payload).hexdigest()
    print(f"Bundled one self-contained React UI file into {destination}; SHA256: {digest}")


if __name__ == "__main__":
    main()
