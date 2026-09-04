from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .auth import extract_bearer, is_authorized
from .config import Settings
from .storage import MinioTransferStore


class CreateTransferRequest(BaseModel):
    username: str
    device_id: str
    session_id: str
    name: str
    archive: str = "zip"
    size: int | None = None
    sha256: str | None = None


class ExistingTransferRequest(BaseModel):
    username: str
    device_id: str
    session_id: str
    transfer_id: str = Field(pattern=r"^transfer_[a-f0-9]+$")
    name: str
    archive: str = "zip"
    size: int | None = None
    sha256: str | None = None
def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = MinioTransferStore(settings)
    app = FastAPI(title="zfc-file-api", version="0.1.0")

    def require_auth(request: CreateTransferRequest | ExistingTransferRequest, authorization: str | None = Header(default=None)) -> None:
        token = extract_bearer(authorization)
        if is_authorized(token, request.username, request.device_id, settings):
            return
        raise HTTPException(status_code=401, detail="unauthorized")

    @app.on_event("startup")
    def startup() -> None:
        store.ensure_bucket()

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.post("/v1/transfers/uploads")
    def create_upload(request: CreateTransferRequest, authorization: str | None = Header(default=None)) -> dict:
        require_auth(request, authorization)
        return store.create_upload(
            request.username, request.device_id, request.session_id, request.name, request.archive, request.size, request.sha256
        ).to_dict()

    @app.post("/v1/transfers/downloads")
    def create_download(request: ExistingTransferRequest, authorization: str | None = Header(default=None)) -> dict:
        require_auth(request, authorization)
        return store.create_download_for_existing(
            request.username, request.device_id, request.session_id, request.transfer_id, request.name, request.archive, request.size, request.sha256
        ).to_dict()

    return app


app = create_app()
