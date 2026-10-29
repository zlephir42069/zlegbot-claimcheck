"""Pull file paths and MD5 sums out of a plain-text done report.

This is a starter, not a verdict. It does not open the files it names.
Patterns it recognizes are documented in the README. Anything else is left
for a person to add by hand.
"""

from __future__ import annotations

import json
import re

_URL = re.compile(r"https?://[^\s)>\]\"']+", re.IGNORECASE)
_MD5 = r"[0-9a-fA-F]{32}"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")

# Bare mentions have to look like a source or data file. Explicit `file:`,
# `path:`, verb, and md5 lines may also name a path that only contains a
# slash or a dot.
_EXTENSIONS = {
    "py", "pyi", "js", "mjs", "cjs", "jsx", "ts", "tsx", "json", "jsonl",
    "yml", "yaml", "md", "markdown", "txt", "csv", "tsv", "html", "htm",
    "css", "toml", "ini", "cfg", "conf", "xml", "sql", "sh", "bash", "zsh",
    "rs", "go", "rb", "java", "kt", "kts", "c", "h", "cc", "cpp", "hpp",
    "cs", "php", "swift", "scala", "lua", "r", "pl", "lock", "rst",
    "png", "jpg", "jpeg", "gif", "webp", "svg", "pdf", "zip", "gz", "tgz",
    "tar", "log", "out", "diff", "patch", "service", "timer", "mod", "sum",
    "gradle", "properties", "tf", "vue", "svelte", "proto", "graphql", "gql",
    "ipynb", "ndjson", "env", "example", "gitignore", "editorconfig",
}
_SPECIAL = {
    "makefile", "dockerfile", "license", "readme", "containerfile",
    "procfile", "gemfile", "rakefile", "justfile", ".env", ".gitignore",
    ".gitattributes", ".editorconfig",
}
_KEYWORDS = {
    "the", "a", "an", "of", "for", "is", "to", "file", "path", "md5",
    "checksum", "and", "or", "this", "that", "with", "from", "into", "output",
}

_GNU = re.compile(rf"^({_MD5})\s+\*?(\S.*?)\s*$")
_BSD = re.compile(rf"^MD5 \((.+)\) = ({_MD5})\s*$", re.IGNORECASE)
_PROSE = (
    re.compile(rf"\bmd5(?:sum)?\s+of\s+(\S+)\s+(?:is|=|:)\s+({_MD5})\b", re.IGNORECASE),
    re.compile(rf"\bchecksum\s+of\s+(\S+)\s+(?:is|=|:)\s+({_MD5})\b", re.IGNORECASE),
    re.compile(rf"(\S+)\s+\(?\bmd5\b\s*[:=]?\s*({_MD5})\b", re.IGNORECASE),
    re.compile(rf"(\S+)\s+\bchecksum\b\s*[:=]\s*({_MD5})\b", re.IGNORECASE),
    re.compile(rf"\b(?:md5|checksum)\b\s*[:=]?\s*({_MD5})\b\s+(?:for|of)\s+(\S+)", re.IGNORECASE),
)
# The last prose pattern stores the digest first.
_PROSE_HASH_FIRST = {4}

_VERB = re.compile(
    r"\b(?:created|wrote|written|updated|added|modified|generated|saved|edited|produced)\s+"
    r"(`[^`]+`|\"[^\"]+\"|'\S+'|\S+)",
    re.IGNORECASE,
)
_LABEL = re.compile(
    r"\b(?:file|path|output)\s*[:=]\s*(`[^`]+`|\"[^\"]+\"|'\S+'|\S+)",
    re.IGNORECASE,
)
_TICK = re.compile(r"`([^`\n]+)`")
_BARE = re.compile(
    r"(?<![\w./-])((?:\.{1,2}/|~/|/)?(?:[\w.+-]+/)*[\w.+-]+\.[A-Za-z][A-Za-z0-9]{0,15})"
    r"(?![\w./-])"
)
_SPECIAL_BARE = re.compile(
    r"(?<![\w./-])(Makefile|Dockerfile|LICENSE|README|Containerfile|Procfile|"
    r"Gemfile|Rakefile|justfile|\.env|\.gitignore)(?![\w./-])"
)


def extract_claims(text: str) -> list[dict]:
    """Return claim dicts in the order the report mentions them."""
    events: list[tuple] = []
    seen_exists: set[str] = set()
    seen_md5: set[tuple[str, str]] = set()

    def add_exists(raw: str, *, explicit: bool) -> None:
        path = clean_path(raw)
        if not _accept(path, explicit=explicit):
            return
        if path in seen_exists:
            return
        seen_exists.add(path)
        events.append(("exists", path))

    def add_md5(raw: str, digest: str) -> None:
        path = clean_path(raw)
        if not _accept(path, explicit=True):
            return
        digest = digest.lower()
        if not re.fullmatch(_MD5, digest):
            return
        if path not in seen_exists:
            seen_exists.add(path)
            events.append(("exists", path))
        key = (path, digest)
        if key in seen_md5:
            return
        seen_md5.add(key)
        events.append(("md5", path, digest))

    for line in text.splitlines():
        _scan_line(mask_urls(line), add_exists, add_md5)

    used: set[str] = set()
    claims = []
    for event in events:
        if event[0] == "exists":
            claims.append(
                {
                    "name": _unique(used, _slug("exists", event[1])),
                    "type": "file_exists",
                    "path": event[1],
                }
            )
        else:
            claims.append(
                {
                    "name": _unique(used, _slug("md5", event[1])),
                    "type": "file_md5",
                    "path": event[1],
                    "md5": event[2],
                }
            )
    return claims


def render_claims(claims: list[dict], source: str) -> str:
    """YAML text a person can review and then pass to `claimcheck run`."""
    safe_source = " ".join(source.split()) or "report"
    lines = [
        "# Starter claims produced by claimcheck extract.",
        f"# Source: {safe_source}",
        "# Review every path and hash before you trust this file.",
        "# Extract does not open files and does not decide PASS or FAIL.",
    ]
    if not claims:
        lines.append("claims: []")
    else:
        lines.append("claims:")
    for claim in claims:
        lines.append(f"  - name: {claim['name']}")
        lines.append(f"    type: {claim['type']}")
        lines.append(f"    path: {_yaml_quote(claim['path'])}")
        if claim["type"] == "file_md5":
            lines.append(f"    md5: {claim['md5']}")
    lines.append("")
    return "\n".join(lines)


def mask_urls(line: str) -> str:
    return _URL.sub(lambda match: " " * len(match.group(0)), line)


def clean_path(raw: str) -> str:
    text = raw.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "`\"'":
        text = text[1:-1].strip()
    text = text.strip("`")
    text = text.rstrip(".,;:")
    if text.endswith(")") and "(" not in text:
        text = text[:-1]
    return text.strip()


def _scan_line(line: str, add_exists, add_md5) -> None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return
    gnu = _GNU.fullmatch(stripped)
    if gnu and "md5" not in stripped.lower() and "checksum" not in stripped.lower():
        add_md5(gnu.group(2), gnu.group(1))
    bsd = _BSD.fullmatch(stripped)
    if bsd:
        add_md5(bsd.group(1), bsd.group(2))
    for index, pattern in enumerate(_PROSE):
        for match in pattern.finditer(stripped):
            if index in _PROSE_HASH_FIRST:
                add_md5(match.group(2), match.group(1))
            else:
                add_md5(match.group(1), match.group(2))
    for match in _VERB.finditer(stripped):
        add_exists(match.group(1), explicit=True)
    for match in _LABEL.finditer(stripped):
        add_exists(match.group(1), explicit=True)
    for match in _TICK.finditer(stripped):
        add_exists(match.group(1), explicit=True)
    for match in _BARE.finditer(stripped):
        add_exists(match.group(1), explicit=False)
    for match in _SPECIAL_BARE.finditer(stripped):
        add_exists(match.group(1), explicit=False)


def _accept(path: str, *, explicit: bool) -> bool:
    if not path or path.lower() in _KEYWORDS:
        return False
    lowered = path.lower()
    if "://" in lowered or lowered.startswith("http"):
        return False
    if re.fullmatch(_MD5, path):
        return False
    if any(char in path for char in "\n\r\t*?<>|"):
        return False
    if looks_like_path(path):
        return True
    if not explicit:
        return False
    if not re.fullmatch(r"[A-Za-z0-9_ ./+~\\-]+", path):
        return False
    return "/" in path or "\\" in path or "." in path


def looks_like_path(path: str) -> bool:
    if not path or "://" in path or any(char.isspace() for char in path):
        return False
    if "@" in path and "/" not in path and "\\" not in path:
        return False
    if not re.fullmatch(r"[A-Za-z0-9_./+~\\-]+", path):
        return False
    name = path.replace("\\", "/").split("/")[-1]
    if name.lower() in _SPECIAL:
        return True
    if "." not in name:
        return False
    ext = name.rsplit(".", 1)[-1].lower()
    return ext in _EXTENSIONS


def _slug(prefix: str, path: str) -> str:
    body = re.sub(r"[^A-Za-z0-9]+", "_", path).strip("_").lower() or "path"
    name = f"{prefix}_{body}"
    if len(name) > 64:
        name = name[:64].rstrip("_")
    if not _NAME.fullmatch(name):
        name = ("p_" + name)[:64].rstrip("_")
    return name


def _unique(used: set[str], base: str) -> str:
    name = base[:64].rstrip("_") or "claim"
    if name not in used and _NAME.fullmatch(name):
        used.add(name)
        return name
    number = 2
    while True:
        suffix = f"_{number}"
        trimmed = (base[: 64 - len(suffix)].rstrip("_") + suffix)
        if trimmed not in used and _NAME.fullmatch(trimmed):
            used.add(trimmed)
            return trimmed
        number += 1


def _yaml_quote(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./+-]+", value):
        return value
    return json.dumps(value, ensure_ascii=False)
