"""Validate the local single-file React tab and its script CSP hash."""

import argparse
import base64
import hashlib
import html
import re
from html.parser import HTMLParser
from pathlib import Path


class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.scripts = []
        self.styles = []
        self.external = []
        self.root_found = False
        self._target = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            self.scripts.append({"attrs": attrs, "body": []})
            self._target = self.scripts[-1]["body"]
        elif tag == "style":
            self.styles.append([])
            self._target = self.styles[-1]
        elif tag == "link" and attrs.get("rel") in {"stylesheet", "modulepreload"}:
            self.external.append((tag, attrs))
        elif tag == "img" and attrs.get("src", "").startswith(("http:", "https:", "file:")):
            self.external.append((tag, attrs))
        elif tag == "div" and attrs.get("id") == "root":
            self.root_found = True

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self._target = None

    def handle_data(self, data):
        if self._target is not None:
            self._target.append(data)


def validate_html(document: str) -> dict[str, object]:
    parser = _Page()
    parser.feed(document)
    if len(parser.scripts) != 1 or parser.scripts[0]["attrs"].get("type") != "module":
        raise AssertionError("React bundle must be exactly one inline module script")
    if parser.scripts[0]["attrs"].get("src"):
        raise AssertionError("React module must not load from a file URL")
    if len(parser.styles) != 1 or parser.external:
        raise AssertionError("All UI styles and resources must be local and inlined")
    if not parser.root_found:
        raise AssertionError("React mount node is missing")
    if "If this message remains, the React tab failed to start." not in document:
        raise AssertionError("A visible startup diagnostic must remain if React cannot mount")

    script = "".join(parser.scripts[0]["body"])
    digest = base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii")
    policy = re.search(
        r'<meta\s+http-equiv="Content-Security-Policy"\s+content="([^"]+)"', document
    )
    if not policy:
        raise AssertionError("Content Security Policy is missing")
    directives = html.unescape(policy.group(1))
    if f"script-src 'sha256-{digest}'" not in directives:
        raise AssertionError("Inline script is not covered by its CSP hash")
    if "default-src 'none'" not in directives or "connect-src 'none'" not in directives:
        raise AssertionError("UI CSP must deny undeclared and network access")
    if "createRoot" not in script or "window.ue" not in script:
        raise AssertionError("React mount or native Unreal bridge is absent")
    if not re.search(r"\.ue\?\.forge", script):
        raise AssertionError("Native Unreal bridge must be resolved dynamically after page startup")
    if "getstate" not in script or "dispatch" not in script:
        raise AssertionError("React UI must call the lowercase methods exposed by Unreal's JS binding")
    if "Unreal has not connected this panel to the bridge yet" not in script:
        raise AssertionError("Missing Unreal bridge must produce a visible action diagnostic")
    if script.count("data:image/svg+xml,") < 2:
        raise AssertionError("Official Unreal Engine and Blender SVG marks must be bundled locally")
    if "data:image/" not in script or re.search(r"(?:src|href)=['\"](?:\./|assets/)", document):
        raise AssertionError("UI still depends on a sibling asset")
    style_text = "".join(parser.styles[0])
    if ".shell" not in style_text or ".card" not in style_text:
        raise AssertionError("The inlined ForgeMCP stylesheet is missing")
    return {"sha256": hashlib.sha256(document.encode("utf-8")).hexdigest(),
            "script_csp_sha256": digest, "bytes": len(document.encode("utf-8"))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html_file", type=Path)
    args = parser.parse_args()
    result = validate_html(args.html_file.resolve(strict=True).read_text(encoding="utf-8"))
    print(f"FORGEMCP_SELF_CONTAINED_REACT_UI_PASS {result}")


if __name__ == "__main__":
    main()
