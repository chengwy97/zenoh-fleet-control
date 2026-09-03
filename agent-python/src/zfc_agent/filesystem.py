from __future__ import annotations

from pathlib import Path


def resolve_in_root(root: Path, base: Path, requested: str | None) -> Path:
    root = root.expanduser().resolve()
    base = base.expanduser().resolve()
    if base != root and root not in base.parents:
        raise ValueError("base path escapes agent root")
    if not requested or requested == ".":
        path = base
    else:
        candidate = Path(requested).expanduser()
        path = candidate if candidate.is_absolute() else base / candidate
    path = path.resolve()
    if path != root and root not in path.parents:
        raise ValueError("path escapes agent root")
    return path


def resolve_inside(root: Path, requested: str | None) -> Path:
    root = root.expanduser().resolve()
    return resolve_in_root(root, root, requested)


def list_directory(root: Path, base: Path, requested: str | None) -> dict:
    root = root.expanduser().resolve()
    directory = resolve_in_root(root, base, requested)
    if not directory.exists():
        raise FileNotFoundError("directory does not exist")
    if not directory.is_dir():
        raise NotADirectoryError("path is not a directory")

    entries = []
    for item in sorted(directory.iterdir(), key=lambda value: (not value.is_dir(), value.name.lower())):
        stat = item.stat()
        entries.append({
            "name": item.name,
            "kind": "directory" if item.is_dir() else "file",
            "size": None if item.is_dir() else stat.st_size,
            "modified_at": int(stat.st_mtime),
            "relative_path": str(item.relative_to(root)),
        })
    return {
        "path": str(directory),
        "relative_path": str(directory.relative_to(root) or "."),
        "entries": entries,
    }
