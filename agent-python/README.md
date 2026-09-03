# agent-python

Python implementation of the terminal agent for validation and early prototyping.

## Dependencies

The local router can use the already built `zenohd` binary:

```bash
/home/eame/Documents/magiclab/zenoh/zenoh/target/release/zenohd
```

The Python agent only needs the Python binding installed in the project virtual environment:

```bash
cd /home/eame/cwy/zenoh/zenoh-fleet-control/agent-python
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Local validation flow

Terminal 1: start local zenohd.

```bash
/home/eame/Documents/magiclab/zenoh/zenoh/target/release/zenohd
```

Terminal 2: start the agent.

```bash
cd /home/eame/cwy/zenoh/zenoh-fleet-control/agent-python
source .venv/bin/activate
zfc-agent --username eame --device-id dev_local --session-id sess_local --root /home/eame --cwd /home/eame
```

Terminal 3: watch the event stream.

```bash
zfc-watch-session --username eame --device-id dev_local --session-id sess_local
```

Terminal 4: send a Codex message.

```bash
zfc-send-command --username eame --device-id dev_local --session-id sess_local   --tool codex --prompt "Explain the current repository"
```

A second `run_ai(tool=codex)` message in the same ZFC session resumes the saved Codex thread. When a task is already running, later AI messages are queued and run after the current turn completes.

Cancel the active task:

```bash
zfc-send-control --username eame --device-id dev_local --session-id sess_local   --type cancel --cmd-id <running_cmd_id>
```

End the session and interrupt its active task:

```bash
zfc-send-control --username eame --device-id dev_local --session-id sess_local   --type end_session --cmd-id <running_cmd_id>
```

## Prototype scope

Implemented:

- device/session `idle`, `running`, `ending`, and `ended` state publication
- `run_shell` and `run_ai(tool=codex)`
- Codex JSONL event conversion
- persisted `ZFC session -> Codex thread` mapping in `<cwd>/.zfc/sessions/`
- queued follow-up AI messages in one running session
- `cancel` and `end_session` control messages

Not implemented yet:

- approval forwarding to the mobile app
- Codex TUI slash commands such as `/goal`
- durable queued-message storage across agent restarts
- real Claude CLI adapter
- cloud TLS/mTLS setup


## Real media upload

The mobile app should upload the actual binary bytes, not a phone-local path. In the chat UI this still behaves as an attachment: users attach an image/video/file and add a description; the app and agent hide the storage location details.

```bash
zfc-send-media --username eame --device-id dev_media --session-id sess_media \
  --path /path/to/image.png --description "检查这张截图的布局"
```

For real phone-style transfer through file-api/MinIO:

```bash
zfc-send-media --username eame --device-id dev_media --session-id sess_media \
  --path /path/to/image.png --description "检查这张截图的布局" \
  --transfer-backend s3 --file-api-url http://127.0.0.1:8080 --file-api-token dev-token-change-me
```

Use the returned `asset_id` in an AI command:

```bash
zfc-send-command --username eame --device-id dev_media --session-id sess_media \
  --tool codex --prompt "分析图片" --media "<asset_id>=关注布局和按钮"
```

The agent validates media size and SHA-256 before saving it under `.zfc/media`. With `s3`/`minio`, Zenoh carries only the manifest and `TransferRef`; the binary payload is downloaded by the agent in the background. The Codex adapter passes images as image inputs. Video files are handled by an agent-side preprocessing policy; the prototype extracts up to three frames when `ffmpeg` is available. Audio and ordinary files are passed to the selected agent as validated local paths with the user description; the agent/tool decides whether to transcribe, inspect, convert, or otherwise process them.

Configuration example: [config.example.json](config.example.json)

## File and directory transfer

The prototype exposes a backend abstraction for file transfer. The current runnable backend is `local_spool`: it archives files or directories as zip files in a local transfer store and sends only a `TransferRef` over Zenoh.

Upload a local file or directory into the agent session cwd:

```bash
zfc-send-transfer --username eame --device-id dev_local --session-id sess_local \
  --path /path/to/local/file-or-dir --target-path .
```

Fetch a file or directory from the agent session cwd:

```bash
zfc-fetch-transfer --username eame --device-id dev_local --session-id sess_local \
  --path . --output-dir /tmp/zfc-download
```

The command semantics stay stable across `local_spool` and the file-api backed `s3`/`minio` backend.

`local_spool` requires a shared filesystem path between the validation CLI and the agent. For a real phone app, use `s3` or `minio` with `--file-api-url` and `--file-api-token`; file bytes go through presigned HTTP URLs while Zenoh only carries commands and `TransferRef`.
