from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Keyspace:
    username: str
    device_id: str
    session_id: str

    @property
    def device_prefix(self) -> str:
        return f"u/{self.username}/fleet/{self.device_id}"

    @property
    def session_prefix(self) -> str:
        return f"{self.device_prefix}/sessions/{self.session_id}"

    @property
    def presence(self) -> str:
        return f"{self.device_prefix}/presence"

    @property
    def status(self) -> str:
        return f"{self.device_prefix}/status"

    @property
    def session_state(self) -> str:
        return f"{self.session_prefix}/state"

    @property
    def commands(self) -> str:
        return f"{self.session_prefix}/commands/*"

    @property
    def control(self) -> str:
        return f"{self.session_prefix}/control/*"

    @property
    def media_chunks(self) -> str:
        return f"{self.session_prefix}/media/*/chunks/*"

    @property
    def media_manifests(self) -> str:
        return f"{self.session_prefix}/media/*/manifest"

    def command(self, cmd_id: str) -> str:
        return f"{self.session_prefix}/commands/{cmd_id}"

    def control_message(self, cmd_id: str) -> str:
        return f"{self.session_prefix}/control/{cmd_id}"

    def media_chunk(self, asset_id: str, index: int) -> str:
        return f"{self.session_prefix}/media/{asset_id}/chunks/{index:08d}"

    def media_manifest(self, asset_id: str) -> str:
        return f"{self.session_prefix}/media/{asset_id}/manifest"

    def event(self, event_id: str) -> str:
        return f"{self.session_prefix}/events/{event_id}"

    def result(self, cmd_id: str) -> str:
        return f"{self.session_prefix}/results/{cmd_id}"

    @property
    def directory_queryable(self) -> str:
        return f"{self.device_prefix}/directory"
