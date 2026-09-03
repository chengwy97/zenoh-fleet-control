from __future__ import annotations

from dataclasses import asdict, dataclass
import time
import uuid

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from .config import Settings


@dataclass(frozen=True)
class TransferRef:
    version: str
    transfer_id: str
    backend: str
    uri: str
    upload_url: str | None
    download_url: str
    bucket: str
    object_key: str
    name: str
    archive: str
    size: int | None
    sha256: str | None
    expires_at: int
    created_at: int

    def to_dict(self) -> dict:
        return asdict(self)


class MinioTransferStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.endpoint_url,
            aws_access_key_id=settings.access_key,
            aws_secret_access_key=settings.secret_key,
            region_name=settings.region,
            config=Config(signature_version="s3v4"),
        )

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.settings.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.settings.bucket)

    def create_upload(self, username: str, device_id: str, session_id: str, name: str, archive: str, size: int | None, sha256: str | None) -> TransferRef:
        transfer_id = f"transfer_{uuid.uuid4().hex}"
        object_key = f"u/{username}/fleet/{device_id}/sessions/{session_id}/transfers/{transfer_id}/{name}"
        upload_url = self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.settings.bucket, "Key": object_key},
            ExpiresIn=self.settings.url_expires_seconds,
        )
        return self._ref(transfer_id, object_key, name, archive, size, sha256, upload_url)

    def describe_download(self, transfer_id: str, object_key: str, name: str, archive: str, size: int | None, sha256: str | None) -> TransferRef:
        return self._ref(transfer_id, object_key, name, archive, size, sha256, None)

    def create_download_for_existing(self, username: str, device_id: str, session_id: str, transfer_id: str, name: str, archive: str, size: int | None, sha256: str | None) -> TransferRef:
        object_key = f"u/{username}/fleet/{device_id}/sessions/{session_id}/transfers/{transfer_id}/{name}"
        return self.describe_download(transfer_id, object_key, name, archive, size, sha256)

    def _ref(self, transfer_id: str, object_key: str, name: str, archive: str, size: int | None, sha256: str | None, upload_url: str | None) -> TransferRef:
        download_url = self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.settings.bucket, "Key": object_key},
            ExpiresIn=self.settings.url_expires_seconds,
        )
        now = int(time.time())
        return TransferRef(
            version="v1",
            transfer_id=transfer_id,
            backend="s3",
            uri=f"s3://{self.settings.bucket}/{object_key}",
            upload_url=upload_url,
            download_url=download_url,
            bucket=self.settings.bucket,
            object_key=object_key,
            name=name,
            archive=archive,
            size=size,
            sha256=sha256,
            expires_at=now + self.settings.url_expires_seconds,
            created_at=now,
        )
