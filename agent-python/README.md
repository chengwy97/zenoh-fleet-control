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

The mobile app should upload the actual binary bytes, not a phone-local path. During local validation:

```bash
zfc-send-media --username eame --device-id dev_media --session-id sess_media \
  --path /path/to/image.png --description "检查这张截图的布局"
```

Use the returned `asset_id` in an AI command:

```bash
zfc-send-command --username eame --device-id dev_media --session-id sess_media \
  --tool codex --prompt "分析图片" --media "<asset_id>=关注布局和按钮"
```

The agent validates media size and SHA-256 before saving it under `.zfc/media`. The Codex adapter passes images as image inputs. Video files are handled by an agent-side preprocessing policy; the prototype extracts up to three frames when `ffmpeg` is available. Audio is explicitly rejected until a transcription adapter is added.

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

The command semantics are intended to stay stable when replacing `local_spool` with `tus`, `s3`, or `minio`.

`local_spool` requires a shared filesystem path between the validation CLI and the agent. For a real phone app, replace it with `tus`, `s3`, or `minio` so the transfer reference points to an HTTP/object-storage endpoint instead of `file://`.
