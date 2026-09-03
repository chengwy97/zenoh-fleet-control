from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import platform


@dataclass(frozen=True)
class AgentConfig:
    username: str
    device_id: str
    session_id: str
    root: Path
    cwd: Path
    name: str
    connect: str | None
    transfer_backend: str
    transfer_store: Path

    @classmethod
    def from_args(cls, args) -> "AgentConfig":
        file_cfg = {}
        if getattr(args, "config", None):
            config_path = Path(args.config).expanduser().resolve()
            file_cfg = json.loads(config_path.read_text(encoding="utf-8"))
        root = Path(getattr(args, "root", None) or file_cfg.get("root") or args.cwd or file_cfg.get("cwd") or os.getcwd()).expanduser().resolve()
        cwd = Path(args.cwd or file_cfg.get("cwd") or root).expanduser().resolve()
        if cwd != root and root not in cwd.parents:
            raise ValueError("cwd must be inside root")
        transfer_store = Path(
            getattr(args, "transfer_store", None)
            or file_cfg.get("transfer_store")
            or os.getenv("ZFC_TRANSFER_STORE", str(cwd / ".zfc" / "transfers"))
        ).expanduser().resolve()
        return cls(
            username=args.username or file_cfg.get("username") or os.getenv("ZFC_USERNAME", "eame"),
            device_id=args.device_id or file_cfg.get("device_id") or os.getenv("ZFC_DEVICE_ID", platform.node() or "dev_local"),
            session_id=args.session_id or file_cfg.get("session_id") or os.getenv("ZFC_SESSION_ID", "sess_local"),
            root=root,
            cwd=cwd,
            name=args.name or file_cfg.get("name") or os.getenv("ZFC_DEVICE_NAME", platform.node() or "local-agent"),
            connect=args.connect or file_cfg.get("connect") or os.getenv("ZFC_CONNECT"),
            transfer_backend=getattr(args, "transfer_backend", None) or file_cfg.get("transfer_backend") or os.getenv("ZFC_TRANSFER_BACKEND", "local_spool"),
            transfer_store=transfer_store,
        )
