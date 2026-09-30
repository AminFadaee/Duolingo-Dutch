import json
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx

USER_AGENT = "duolingo-anki (+https://github.com/AminFadaee/Duolingo-Dutch)"


@dataclass(frozen=True)
class Download:
    url: str
    path: Path
    last_modified: str | None


def download(url: str, cache_dir: Path, name: str | None = None) -> Download:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / (name or url.rsplit("/", 1)[1])
    meta_path = path.with_name(f"{path.name}.meta.json")
    meta = json.loads(meta_path.read_text()) if path.exists() and meta_path.exists() else {}
    headers = {"User-Agent": USER_AGENT}
    if meta.get("etag"):
        headers["If-None-Match"] = meta["etag"]
    if meta.get("last_modified"):
        headers["If-Modified-Since"] = meta["last_modified"]
    with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=60) as response:
        if response.status_code != httpx.codes.NOT_MODIFIED:
            response.raise_for_status()
            print(f"Downloading {url}", file=sys.stderr)
            partial = path.with_name(f"{path.name}.part")
            with partial.open("wb") as file:
                for chunk in response.iter_bytes():
                    file.write(chunk)
            partial.replace(path)
            meta = {"etag": response.headers.get("etag"), "last_modified": response.headers.get("last-modified")}
            meta_path.write_text(json.dumps(meta))
    return Download(url, path, meta.get("last_modified"))
