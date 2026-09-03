from __future__ import annotations

import hashlib
import json
import tempfile
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .filesystem import resolve_in_root


@dataclass(frozen=True)
class TransferRef:
    version: str
    transfer_id: str
    backend: str
    uri: str
    name: str
    archive: str
    size: int | None = None
    sha256: str | None = None
    created_at: int | None = None
    upload_url: str | None = None
    download_url: str | None = None
    bucket: str | None = None
    object_key: str | None = None
    expires_at: int | None = None

    def to_dict(self, include_upload_url: bool = False) -> dict:
        data = asdict(self)
        if not include_upload_url:
            data.pop("upload_url", None)
        return {key: value for key, value in data.items() if value is not None}


class TransferBackend:
    name = "base"

    def stage_upload(self, source: Path) -> TransferRef:
        raise NotImplementedError

    def import_to_cwd(self, ref: TransferRef, cwd: Path, target_path: str | None, root: Path | None = None) -> Path:
        raise NotImplementedError

    def export_from_cwd(self, cwd: Path, source_path: str | None, root: Path | None = None) -> TransferRef:
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
        zip_path(source, archive)
        return self._ref(transfer_id, archive, source.name)

    def import_to_cwd(self, ref: TransferRef, cwd: Path, target_path: str | None, root: Path | None = None) -> Path:
        archive = self._archive_path(ref)
        verify_archive(ref, archive)
        destination = resolve_in_root(root or cwd, cwd, target_path or ".")
        extract_zip_safely(archive, destination)
        return destination

    def export_from_cwd(self, cwd: Path, source_path: str | None, root: Path | None = None) -> TransferRef:
        source = resolve_in_root(root or cwd, cwd, source_path or ".")
        if not source.exists():
            raise FileNotFoundError("export source does not exist")
        transfer_id = f"transfer_{uuid.uuid4().hex}"
        archive = self.root / f"{transfer_id}.zip"
        zip_path(source, archive)
        return self._ref(transfer_id, archive, source.name)

    def materialize(self, ref: TransferRef, output_dir: Path) -> Path:
        archive = self._archive_path(ref)
        verify_archive(ref, archive)
        output_dir = output_dir.expanduser().resolve()
        extract_zip_safely(archive, output_dir)
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


class FileApiTransferBackend(TransferBackend):
    name = "s3"

    def __init__(self, store: Path, file_api_url: str, file_api_token: str, username: str, device_id: str, session_id: str) -> None:
        self.store = store.expanduser().resolve()
        self.store.mkdir(parents=True, exist_ok=True)
        self.file_api_url = file_api_url.rstrip("/")
        self.file_api_token = file_api_token
        self.username = username
        self.device_id = device_id
        self.session_id = session_id

    def stage_upload(self, source: Path) -> TransferRef:
        source = source.expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(f"source does not exist: {source}")
        with tempfile.NamedTemporaryFile(prefix="zfc-upload-", suffix=".zip", dir=self.store, delete=False) as temp:
            archive = Path(temp.name)
        try:
            zip_path(source, archive)
            ref = self._create_upload(source.name, archive)
            self._put_bytes(ref.upload_url, archive.read_bytes())
            return without_upload_url(ref)
        finally:
            archive.unlink(missing_ok=True)

    def import_to_cwd(self, ref: TransferRef, cwd: Path, target_path: str | None, root: Path | None = None) -> Path:
        ref = self._refresh_download_url(ref)
        archive = self._download_archive(ref)
        try:
            verify_archive(ref, archive)
            destination = resolve_in_root(root or cwd, cwd, target_path or ".")
            extract_zip_safely(archive, destination)
            return destination
        finally:
            archive.unlink(missing_ok=True)

    def export_from_cwd(self, cwd: Path, source_path: str | None, root: Path | None = None) -> TransferRef:
        source = resolve_in_root(root or cwd, cwd, source_path or ".")
        if not source.exists():
            raise FileNotFoundError("export source does not exist")
        with tempfile.NamedTemporaryFile(prefix="zfc-export-", suffix=".zip", dir=self.store, delete=False) as temp:
            archive = Path(temp.name)
        try:
            zip_path(source, archive)
            ref = self._create_upload(source.name, archive)
            self._put_bytes(ref.upload_url, archive.read_bytes())
            return without_upload_url(ref)
        finally:
            archive.unlink(missing_ok=True)

    def materialize(self, ref: TransferRef, output_dir: Path) -> Path:
        ref = self._refresh_download_url(ref)
        archive = self._download_archive(ref)
        try:
            verify_archive(ref, archive)
            output_dir = output_dir.expanduser().resolve()
            extract_zip_safely(archive, output_dir)
            return output_dir
        finally:
            archive.unlink(missing_ok=True)

    def _create_upload(self, name: str, archive: Path) -> TransferRef:
        data = archive.read_bytes()
        payload = {
            "username": self.username,
            "device_id": self.device_id,
            "session_id": self.session_id,
            "name": name,
            "archive": "zip",
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        return ref_from_dict(self._request_json("POST", "/v1/transfers/uploads", payload))

    def _refresh_download_url(self, ref: TransferRef) -> TransferRef:
        if ref.backend not in {"s3", "minio"}:
            raise ValueError(f"unsupported transfer backend: {ref.backend}")
        if ref.download_url and (ref.expires_at is None or ref.expires_at - int(time.time()) > 30):
            return ref
        payload = {
            "username": self.username,
            "device_id": self.device_id,
            "session_id": self.session_id,
            "transfer_id": ref.transfer_id,
            "name": ref.name,
            "archive": ref.archive,
            "size": ref.size,
            "sha256": ref.sha256,
        }
        return ref_from_dict(self._request_json("POST", "/v1/transfers/downloads", payload))

    def _download_archive(self, ref: TransferRef) -> Path:
        if not ref.download_url:
            raise ValueError("transfer ref has no download_url")
        request = Request(ref.download_url, method="GET")
        with urlopen(request, timeout=60) as response:
            data = response.read()
        archive = self.store / f"{ref.transfer_id}.zip"
        archive.write_bytes(data)
        return archive

    def _put_bytes(self, url: str | None, data: bytes) -> None:
        if not url:
            raise ValueError("file-api did not return upload_url")
        request = Request(url, data=data, method="PUT")
        with urlopen(request, timeout=60) as response:
            if response.status not in {200, 201, 204}:
                raise RuntimeError(f"upload failed with HTTP {response.status}")

    def _request_json(self, method: str, path: str, payload: dict) -> dict:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self.file_api_url}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.file_api_token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"file-api request failed: HTTP {exc.code}: {detail}") from exc


def without_upload_url(ref: TransferRef) -> TransferRef:
    return TransferRef(**{**asdict(ref), "upload_url": None})


def verify_archive(ref: TransferRef, archive: Path) -> None:
    data = archive.read_bytes()
    if ref.size is not None and len(data) != ref.size:
        raise ValueError("transfer archive size mismatch")
    if ref.sha256 is not None and hashlib.sha256(data).hexdigest() != ref.sha256:
        raise ValueError("transfer archive checksum mismatch")


def extract_zip_safely(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            target = (destination / member.filename).resolve()
            if target != destination and destination not in target.parents:
                raise ValueError("archive entry escapes destination")
        zf.extractall(destination)


def zip_path(source: Path, archive: Path) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        if source.is_dir():
            for path in sorted(source.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(source.parent))
        else:
            zf.write(source, source.name)


def backend_from_config(
    name: str,
    store: Path,
    *,
    username: str = "eame",
    device_id: str = "dev_local",
    session_id: str = "sess_local",
    file_api_url: str | None = None,
    file_api_token: str | None = None,
) -> TransferBackend:
    if name == "local_spool":
        return LocalSpoolTransferBackend(store)
    if name in {"s3", "minio"}:
        if not file_api_url or not file_api_token:
            raise ValueError("s3/minio transfer backend requires file_api_url and file_api_token")
        return FileApiTransferBackend(store, file_api_url, file_api_token, username, device_id, session_id)
    if name == "tus":
        raise NotImplementedError("tus backend is planned but not implemented in the Python prototype")
    raise ValueError(f"unknown transfer backend: {name}")


def ref_from_dict(data: dict) -> TransferRef:
    allowed = TransferRef.__dataclass_fields__.keys()
    return TransferRef(**{key: value for key, value in data.items() if key in allowed})
