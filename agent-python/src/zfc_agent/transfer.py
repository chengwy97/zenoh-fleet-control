from __future__ import annotations

import hashlib
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .filesystem import resolve_in_root


@dataclass(frozen=True)
class TransferRef:
    version: str
    transfer_id: str
    backend: str
    uri: str
    name: str
    archive: str
    size: int
    sha256: str
    created_at: int

    def to_dict(self) -> dict:
        return asdict(self)


class TransferBackend:
    name = "base"

    def stage_upload(self, source: Path) -> TransferRef:
        raise NotImplementedError

    def import_to_cwd(self, ref: TransferRef, cwd: Path, target_path: str | None, root: Path | None = None) -> Path:
        raise NotImplementedError

    def export_from_cwd(self, cwd: Path, source_path: str | None) -> TransferRef:
        raise NotImplementedError

    def materialize(self, ref: TransferRef, output_dir: Path) -> Path:
        raise NotImplementedError


class LocalSpoolTransferBackend(TransferBackend):
    name = "local_spool"

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def stage_upload(self, source: Path) -> TransferRef:
        source = source.expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(f"source does not exist: {source}")
        transfer_id = f"transfer_{uuid.uuid4().hex}"
        archive = self.root / f"{transfer_id}.zip"
        self._zip_path(source, archive)
        return self._ref(transfer_id, archive, source.name)

    def import_to_cwd(self, ref: TransferRef, cwd: Path, target_path: str | None, root: Path | None = None) -> Path:
        archive = self._archive_path(ref)
        self._verify(ref, archive)
        destination = resolve_in_root(root or cwd, cwd, target_path or ".")
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                target = (destination / member.filename).resolve()
                if target != destination and destination not in target.parents:
                    raise ValueError("archive entry escapes destination")
            zf.extractall(destination)
        return destination

    def export_from_cwd(self, cwd: Path, source_path: str | None, root: Path | None = None) -> TransferRef:
        source = resolve_in_root(root or cwd, cwd, source_path or ".")
        if not source.exists():
            raise FileNotFoundError("export source does not exist")
        transfer_id = f"transfer_{uuid.uuid4().hex}"
        archive = self.root / f"{transfer_id}.zip"
        self._zip_path(source, archive)
        return self._ref(transfer_id, archive, source.name)

    def materialize(self, ref: TransferRef, output_dir: Path) -> Path:
        archive = self._archive_path(ref)
        self._verify(ref, archive)
        output_dir = output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                target = (output_dir / member.filename).resolve()
                if target != output_dir and output_dir not in target.parents:
                    raise ValueError("archive entry escapes output directory")
            zf.extractall(output_dir)
        return output_dir

    def _archive_path(self, ref: TransferRef) -> Path:
        if ref.backend != self.name:
            raise ValueError(f"unsupported transfer backend: {ref.backend}")
        path = Path(ref.uri.removeprefix("file://")).expanduser().resolve()
        if path != self.root and self.root not in path.parents:
            raise ValueError("transfer uri escapes spool root")
        return path

    def _ref(self, transfer_id: str, archive: Path, name: str) -> TransferRef:
        data = archive.read_bytes()
        return TransferRef(
            version="v1",
            transfer_id=transfer_id,
            backend=self.name,
            uri=f"file://{archive}",
            name=name,
            archive="zip",
            size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            created_at=int(time.time()),
        )

    def _verify(self, ref: TransferRef, archive: Path) -> None:
        data = archive.read_bytes()
        if len(data) != ref.size or hashlib.sha256(data).hexdigest() != ref.sha256:
            raise ValueError("transfer archive checksum or size mismatch")

    @staticmethod
    def _zip_path(source: Path, archive: Path) -> None:
        archive.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            if source.is_dir():
                for path in sorted(source.rglob("*")):
                    if path.is_file():
                        zf.write(path, path.relative_to(source.parent))
            else:
                zf.write(source, source.name)


def backend_from_config(name: str, store: Path) -> TransferBackend:
    if name == "local_spool":
        return LocalSpoolTransferBackend(store)
    if name in {"tus", "s3", "minio"}:
        raise NotImplementedError(f"{name} backend is planned but not implemented in the Python prototype")
    raise ValueError(f"unknown transfer backend: {name}")


def ref_from_dict(data: dict) -> TransferRef:
    return TransferRef(**data)
