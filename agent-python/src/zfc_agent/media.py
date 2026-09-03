from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


_SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]+$")


@dataclass(frozen=True)
class MediaManifest:
    version: str
    username: str
    device_id: str
    session_id: str
    asset_id: str
    name: str
    media_type: str
    size: int
    sha256: str
    chunk_count: int = 0
    transfer: dict[str, Any] | None = None
    description: str | None = None
    created_at: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


class MediaStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._lock = threading.Lock()

    def write_chunk(self, asset_id: str, index: int, payload: bytes) -> None:
        self._validate_asset_id(asset_id)
        with self._lock:
            directory = self._asset_dir(asset_id) / "chunks"
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f"{index:08d}.part").write_bytes(payload)

    def finalize(self, manifest: MediaManifest) -> Path:
        self._validate_asset_id(manifest.asset_id)
        if manifest.chunk_count <= 0 or manifest.size < 0:
            raise ValueError("invalid media manifest")
        with self._lock:
            asset_dir = self._asset_dir(manifest.asset_id)
            chunks_dir = asset_dir / "chunks"
            target = asset_dir / self._safe_name(manifest.name)
            if not chunks_dir.exists():
                raise ValueError("media chunks are missing")
            digest = hashlib.sha256()
            written = 0
            with target.open("wb") as output:
                for index in range(manifest.chunk_count):
                    chunk = chunks_dir / f"{index:08d}.part"
                    if not chunk.exists():
                        raise ValueError(f"missing media chunk {index}")
                    data = chunk.read_bytes()
                    output.write(data)
                    digest.update(data)
                    written += len(data)
            self._verify_payload(manifest, target, written, digest.hexdigest())
            self._write_manifest(asset_dir, manifest)
            for chunk in chunks_dir.glob("*.part"):
                chunk.unlink()
            chunks_dir.rmdir()
            return target

    def finalize_materialized(self, manifest: MediaManifest, extracted_root: Path) -> Path:
        self._validate_asset_id(manifest.asset_id)
        source = extracted_root / self._safe_name(manifest.name)
        if not source.exists() or not source.is_file():
            candidates = [path for path in extracted_root.rglob("*") if path.is_file()]
            if len(candidates) != 1:
                raise FileNotFoundError(f"media payload is missing after transfer extraction: {manifest.name}")
            source = candidates[0]
        with self._lock:
            asset_dir = self._asset_dir(manifest.asset_id)
            asset_dir.mkdir(parents=True, exist_ok=True)
            target = asset_dir / self._safe_name(manifest.name)
            if source.resolve() != target.resolve():
                target.write_bytes(source.read_bytes())
            data = target.read_bytes()
            self._verify_payload(manifest, target, len(data), hashlib.sha256(data).hexdigest())
            self._write_manifest(asset_dir, manifest)
            return target

    def resolve(self, asset_id: str) -> tuple[MediaManifest, Path]:
        self._validate_asset_id(asset_id)
        with self._lock:
            asset_dir = self._asset_dir(asset_id)
            manifest_path = asset_dir / "manifest.json"
            if not manifest_path.exists():
                raise FileNotFoundError(f"media asset is not ready: {asset_id}")
            manifest = MediaManifest(**json.loads(manifest_path.read_text(encoding="utf-8")))
            target = asset_dir / self._safe_name(manifest.name)
            if not target.exists():
                raise FileNotFoundError(f"media payload is missing: {asset_id}")
            return manifest, target

    def _asset_dir(self, asset_id: str) -> Path:
        return self.root / asset_id

    def _write_manifest(self, asset_dir: Path, manifest: MediaManifest) -> None:
        asset_dir.mkdir(parents=True, exist_ok=True)
        (asset_dir / "manifest.json").write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _verify_payload(self, manifest: MediaManifest, target: Path, written: int, digest: str) -> None:
        if written != manifest.size:
            target.unlink(missing_ok=True)
            raise ValueError("media size mismatch")
        if digest != manifest.sha256:
            target.unlink(missing_ok=True)
            raise ValueError("media checksum mismatch")

    @staticmethod
    def _safe_name(name: str) -> str:
        return Path(name).name or "asset.bin"

    @staticmethod
    def _validate_asset_id(asset_id: str) -> None:
        if not _SAFE_ID.fullmatch(asset_id):
            raise ValueError("invalid asset_id")
