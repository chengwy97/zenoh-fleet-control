# 消息协议

## 目标

消息协议定义 App、Agent、Router 和缓存层之间传输的结构化数据。

要求：

- 所有消息都可 JSON 编码
- 所有消息都带用户、设备和时间信息
- 命令和事件可以关联
- 支持流式输出、审批、结果和错误
- 后续可平滑增加字段

## 通用字段

所有消息建议包含：

```json
{
  "version": "v1",
  "username": "eame",
  "device_id": "dev_001",
  "timestamp": 1725330000
}
```

字段说明：

- `version`：协议版本
- `username`：用户命名空间
- `device_id`：目标或来源设备
- `timestamp`：Unix 时间戳，秒或毫秒需在实现中统一

## DeviceStatus

```json
{
  "version": "v1",
  "username": "eame",
  "device_id": "dev_001",
  "name": "ubuntu-workstation",
  "platform": "linux",
  "status": "online",
  "agent_version": "0.1.0",
  "active_session_id": "sess_001",
  "last_seen": 1725330000,
  "capabilities": ["shell", "codex", "media"]
}
```

`status` 可选值：

- `online`
- `offline`
- `busy`
- `degraded`

## SessionState

```json
{
  "version": "v1",
  "username": "eame",
  "device_id": "dev_001",
  "session_id": "sess_001",
  "cwd": "/home/eame/project-a",
  "status": "idle",
  "active_cmd_id": null,
  "created_at": 1725330000,
  "ended_at": null
}
```

`status` 可选值：

- `idle`
- `running`
- `waiting_approval`
- `ending`
- `ended`
- `failed`

## Command

```json
{
  "version": "v1",
  "username": "eame",
  "device_id": "dev_001",
  "session_id": "sess_001",
  "cmd_id": "cmd_001",
  "type": "run_shell",
  "payload": {
    "command": "ls -la"
  },
  "created_at": 1725330000,
  "timeout_ms": 600000,
  "requires_approval": false
}
```

`type` 初始可选值：

- `run_shell`
- `run_ai`
- `set_cwd`
- `create_session`
- `end_session`
- `send_media`

### Directory query

App 对 `u/<username>/fleet/<device_id>/directory` 发起 Zenoh Query：

```json
{"path":"."}
```

`path` 相对当前 session `cwd` 解析，可以使用 `..` 返回上级，但 agent 必须拒绝逃逸 `root` 的路径。

Agent 返回：

```json
{
  "version":"v1",
  "username":"eame",
  "device_id":"dev_001",
  "root":"/home/eame",
  "cwd":"/home/eame/project-a",
  "path":"/home/eame/project-a/src",
  "relative_path":"project-a/src",
  "entries":[
    {"name":"main.py","kind":"file","size":1234,"modified_at":1725330000,"relative_path":"project-a/src/main.py"}
  ]
}
```

### RunAI payload

```json
{
  "type": "run_ai",
  "payload": {
    "tool": "codex",
    "prompt": "分析这个仓库",
    "mode": "exec",
    "options": {
      "sandbox": "workspace-write",
      "approval": "never"
    }
  }
}
```

`tool` 初始可选值：

- `codex`
- `claude`

第一阶段只要求 adapter 支持非交互模式。完整 TUI slash command、长期会话和 approval 转发必须通过工具能力声明判断，不能默认所有工具都支持。

## Event

```json
{
  "version": "v1",
  "username": "eame",
  "device_id": "dev_001",
  "session_id": "sess_001",
  "cmd_id": "cmd_001",
  "event_id": "evt_001",
  "seq": 1,
  "kind": "stdout",
  "content": {
    "text": "total 12"
  },
  "timestamp": 1725330001
}
```

`kind` 初始可选值：

- `accepted`
- `message`
- `progress`
- `stdout`
- `stderr`
- `diff`
- `approval_request`
- `approval_result`
- `media_ref`
- `error`

## Media upload and AI attachment

手机发送的图片、音频、视频必须传输真实二进制内容，不能把手机本地路径直接发送给 agent。

上传流程：

1. App 为媒体生成 `asset_id`。
2. 真实手机和跨设备场景下，App 先通过 file-api/MinIO 上传真实字节，拿到 `TransferRef`。本地验证也可以继续使用 Zenoh chunk。
3. App 发送 manifest 到 `.../media/<asset_id>/manifest`，manifest 可携带 `transfer` 引用。
4. Agent 根据 manifest 拉取或拼装真实文件，校验原始文件 `size` 和 `sha256`，再写入本地媒体缓存。
5. `run_ai` 只引用 `asset_id`，并携带本轮用户描述。
6. Agent 根据工具能力解析 asset：图片可作为 Codex 图片输入；视频由 agent 决定是否抽帧；音频由对应转写 adapter 处理。

```json
{
  "type": "run_ai",
  "payload": {
    "tool": "codex",
    "prompt": "检查这张截图中的主要界面元素",
    "media": [
      {
        "asset_id": "asset_001",
        "description": "关注布局和按钮位置"
      }
    ]
  }
}
```

App 不应发送 `local_path`。agent 自己通过 `asset_id` 查找已校验的本地文件。

使用 file-api/MinIO 的媒体 manifest 示例：

```json
{
  "version": "v1",
  "username": "eame",
  "device_id": "dev_001",
  "session_id": "sess_001",
  "asset_id": "asset_001",
  "name": "screenshot.png",
  "media_type": "image/png",
  "size": 123456,
  "sha256": "raw-file-sha256",
  "chunk_count": 0,
  "transfer": {
    "version": "v1",
    "transfer_id": "transfer_001",
    "backend": "s3",
    "uri": "s3://zfc-transfers/.../screenshot.png",
    "name": "screenshot.png",
    "archive": "zip",
    "size": 654321,
    "sha256": "zip-sha256"
  },
  "description": "检查这个截图中的错误提示",
  "created_at": 1725330000
}
```

聊天 UI 不需要展示 `TransferRef`、bucket 或 object key。用户只看到附件和描述，底层传输由 App/agent 自动完成。

## File transfer

文件/目录传输使用后端引用，不直接绑定 Zenoh 分片。

### TransferRef

```json
{
  "version": "v1",
  "transfer_id": "transfer_001",
  "backend": "s3",
  "uri": "s3://zfc-transfers/u/eame/fleet/dev_001/sessions/sess_001/transfers/transfer_001/src.zip",
  "name": "src",
  "archive": "zip",
  "size": 123456,
  "sha256": "...",
  "bucket": "zfc-transfers",
  "object_key": "u/eame/fleet/dev_001/sessions/sess_001/transfers/transfer_001/src.zip",
  "download_url": "https://example.invalid/presigned-download",
  "expires_at": 1725330900,
  "created_at": 1725330000
}
```

字段约定：

- `backend=local_spool` 仅用于单机验证，`uri` 为 `file://...`。
- `backend=s3` / `minio` 用于真实手机和跨设备文件传输，`uri` 是稳定对象引用。
- `upload_url` 只由 file-api 返回给上传方，不通过 Zenoh 广播。
- `download_url` 是短期 URL，可以放在 `TransferRef` 中便于立即下载；如果缺失或过期，客户端用 `transfer_id/name/size/sha256` 向 file-api 刷新。

### Import transfer

App 上传文件或目录到当前 session cwd：

```json
{
  "type": "import_transfer",
  "payload": {
    "transfer": {"transfer_id": "transfer_001", "backend": "local_spool"},
    "target_path": "."
  }
}
```

Agent 校验 transfer 后端、大小、SHA-256 和解压路径，成功后发布 `transfer_imported` 和新的 `directory_listing`。

### Export transfer

App 从当前 session cwd 取回文件或目录：

```json
{
  "type": "export_transfer",
  "payload": {"path": "src"}
}
```

Agent 返回 `transfer_export_ready`，其中包含 `TransferRef`。App 根据后端下载或还原内容。

生产部署建议使用 `s3` / `minio` 后端，`local_spool` 只用于单机验证和协议开发。`tus` 可作为后续断点续传上传实现，但不改变 Zenoh 命令语义。


```json
{
  "version": "v1",
  "username": "eame",
  "device_id": "dev_001",
  "session_id": "sess_001",
  "cmd_id": "cmd_001",
  "status": "succeeded",
  "exit_code": 0,
  "summary": "command completed",
  "output": {
    "text": "..."
  },
  "completed_at": 1725330010
}
```

`status` 可选值：

- `succeeded`
- `failed`
- `cancelled`
- `timeout`

## Control

Control messages use the session control topic:

```text
u/<username>/fleet/<device_id>/sessions/<session_id>/control/<control_id>
```

### Cancel active task

```json
{
  "version": "v1",
  "username": "eame",
  "device_id": "dev_001",
  "session_id": "sess_001",
  "cmd_id": "cmd_running_001",
  "type": "cancel",
  "timestamp": 1725330008
}
```

### End session

`end_session` cancels the active tool process, discards pending follow-up messages, deletes the local tool-session mapping, and transitions the ZFC session to `ended`.

```json
{
  "version": "v1",
  "username": "eame",
  "device_id": "dev_001",
  "session_id": "sess_001",
  "cmd_id": "cmd_running_001",
  "type": "end_session",
  "timestamp": 1725330008
}
```

## Context resume and follow-up messages

A ZFC `session_id` is the stable outer session. The agent stores one native session ID per tool, for example a Codex `thread_id`.

- First `run_ai(tool=codex)` creates a Codex thread and stores its `thread_id`.
- Later `run_ai(tool=codex)` commands in the same ZFC session use that `thread_id` to resume context.
- When the tool is already running, a later `run_ai` command is accepted with `queued: true` and runs after the active turn completes.
- App UI must display `SessionState.status = running` and `active_cmd_id` while work is in progress.

## ApprovalRequest

审批请求作为 `Event.kind = approval_request` 发送：

```json
{
  "version": "v1",
  "username": "eame",
  "device_id": "dev_001",
  "session_id": "sess_001",
  "cmd_id": "cmd_001",
  "event_id": "evt_approve_001",
  "seq": 5,
  "kind": "approval_request",
  "content": {
    "approval_id": "apv_001",
    "reason": "command writes files",
    "action": "apply_patch",
    "risk": "medium",
    "details": {
      "files": ["src/main.py"]
    }
  },
  "timestamp": 1725330005
}
```

审批响应通过 control topic 发送：

```json
{
  "version": "v1",
  "username": "eame",
  "device_id": "dev_001",
  "session_id": "sess_001",
  "cmd_id": "cmd_001",
  "type": "approval_response",
  "payload": {
    "approval_id": "apv_001",
    "approved": true,
    "comment": "ok"
  },
  "timestamp": 1725330008
}
```

## MediaRef

```json
{
  "version": "v1",
  "username": "eame",
  "device_id": "dev_001",
  "asset_id": "asset_001",
  "media_type": "image/png",
  "name": "screenshot.png",
  "size": 123456,
  "sha256": "...",
  "uri": "zfc://media/asset_001",
  "created_at": 1725330000
}
```

## 错误格式

错误事件统一使用：

```json
{
  "kind": "error",
  "content": {
    "code": "cwd_not_found",
    "message": "working directory does not exist",
    "retryable": false
  }
}
```

## 兼容规则

- 新字段可以追加
- 已有字段语义不能随意改变
- App 遇到未知字段必须忽略
- App 遇到未知 `kind` 应显示为普通 message
- Agent 遇到未知 command type 应返回 `unsupported_command`
