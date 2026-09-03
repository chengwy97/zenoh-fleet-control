# 状态机设计

## 目标

状态机用于约束 session、command 和 approval 的生命周期，避免手机切换终端、断线重连、重复命令导致状态混乱。

## Session 状态

```text
idle -> running -> idle
idle -> waiting_approval -> running -> idle
running -> waiting_approval -> running
idle -> ending -> ended
running -> ending -> ended
waiting_approval -> ending -> ended
any -> failed
```

### `idle`

含义：

- session 已创建
- 没有正在运行的 command
- 可以切换 cwd
- 可以接收新 command

### `running`

含义：

- 有 command 正在执行
- 不建议切换 cwd
- 可以接收 control 命令，例如 cancel

### `waiting_approval`

含义：

- command 暂停等待用户确认
- session 不应接收新的普通执行命令
- 可以接收 approval_response 或 cancel

### `ending`

含义：

- 用户请求结束 session
- agent 正在处理运行中的 command
- 不再接收新 command

### `ended`

含义：

- session 已关闭
- 不再接收 command
- 只允许查看历史

### `failed`

含义：

- session 进入异常状态
- 需要由用户重新创建 session 或执行恢复流程

## Command 状态

```text
queued -> accepted -> running -> succeeded
queued -> accepted -> running -> failed
queued -> accepted -> running -> waiting_approval -> running -> succeeded
queued -> accepted -> running -> cancelled
queued -> accepted -> running -> timeout
```

### `queued`

命令已经发送，但 agent 尚未确认。

### `accepted`

agent 已收到命令，并确认会处理。

### `running`

命令正在执行。

### `waiting_approval`

命令需要用户确认才能继续。

### `succeeded`

命令成功完成。

### `failed`

命令执行失败。

### `cancelled`

命令被用户或系统取消。

### `timeout`

命令超过超时时间。

## cwd 切换规则

`set_cwd` 只能在 session 处于以下状态时执行：

- `idle`

如果 session 正在运行任务，agent 应返回错误：

```json
{
  "code": "session_busy",
  "message": "cannot change cwd while command is running",
  "retryable": true
}
```

切换成功后：

- 更新 session 的 `cwd`
- 发布新的 `SessionState`
- 发送 `cwd_changed` event

## 结束会话规则

用户请求结束 session 时：

### session 为 `idle`

- 直接进入 `ending`
- 归档状态
- 进入 `ended`

### session 为 `running`

需要选择结束模式：

- `wait`：等待当前 command 完成后结束
- `cancel`：取消当前 command 后结束
- `force`：强制终止当前 command 后结束

### session 为 `waiting_approval`

默认推荐：

- 先取消等待中的 command
- 再结束 session

结束后：

- 不允许新的 command
- 保留历史 events 和 results
- App 只能只读查看

## 终端切换规则

手机切换终端时：

- 不改变 agent 端 session 状态
- 不取消当前 command
- 当前终端事件继续进入缓存
- 切回时按 `after_seq` 补拉遗漏事件
- 补拉完成后再接实时订阅

## 断线重连规则

App 重连后：

1. 拉取 device status
2. 拉取 session list
3. 对当前 session 拉取最新 state
4. 使用最后已读 `seq` 补拉 events
5. 重新订阅实时 events

Agent 重连后：

1. 重新发布 presence
2. 重新发布 status
3. 重新发布 active session state
4. 恢复可恢复任务或标记任务失败

## 幂等规则

Agent 必须记录已处理的 `cmd_id`。

如果重复收到同一个 command：

- 如果还在运行，返回当前状态
- 如果已完成，重新发布 result 引用
- 不重复执行副作用命令

## Approval 规则

approval request 必须包含：

- `approval_id`
- `cmd_id`
- `reason`
- `risk`
- `action`

approval response 必须匹配同一个：

- `username`
- `device_id`
- `session_id`
- `cmd_id`
- `approval_id`

如果 approval 超时：

- command 进入 `failed` 或 `cancelled`
- session 回到 `idle`
- 发布 result

## 第一阶段简化

验证阶段可以先支持：

- 一个 session 同时只运行一个 command
- `set_cwd` 只允许 idle 时执行
- `end_session` 默认 cancel 当前 command
- event 只使用内存缓存或本地文件缓存
- approval 先只支持 allow / deny


## 补充消息和上下文恢复

同一个 ZFC `session_id` 可以绑定多个工具原生会话 ID。第一阶段对 Codex 保存 `thread_id`：

- 第一次 AI 请求创建 Codex thread 并持久化 ID。
- 后续 AI 请求使用 `codex exec resume <thread_id> <prompt>`。
- 因此 App 中“补充内容”不是创建新的 ZFC session，而是在同一个 session 下发送新的 `run_ai` command。

如果当前 turn 正在执行：

- agent 接收补充消息后发布 `accepted`，并标记 `queued: true`。
- session 保持 `running`，`active_cmd_id` 保持当前任务 ID。
- 当前 turn 完成后，agent 从队列取出补充消息，并继续同一个 tool native session。

第一阶段队列只保存在内存；agent 重启后未执行的补充消息不会恢复。

## 取消和结束会话

- `cancel`：终止当前工具子进程，session 回到 `idle`，保留 Codex thread 映射，可继续对话。
- `end_session`：终止当前工具子进程，清空待执行补充消息，删除本地 tool-session 映射，并进入 `ended`。
- `ended` session 不再接受新的 command；用户必须创建新的 ZFC session。

## App 状态展示

App 只依赖 `SessionState`：

- `idle`：可发送消息、可切换 cwd、可结束会话。
- `running`：显示正在工作和 `active_cmd_id`；可以发送补充消息，也可以取消或结束会话。
- `ending`：显示正在中断；禁用新消息。
- `ended`：只读历史；显示“新建会话”。
