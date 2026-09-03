# Keyspace 规范

## 目标

Keyspace 用于统一描述手机 App、终端 agent、router 和缓存层之间的 Zenoh topic 命名。

设计目标：

- 支持多用户隔离
- 支持多终端
- 支持多会话
- 支持命令、事件、结果、媒体分离
- 便于 ACL 授权
- 便于离线缓存和补拉

## 顶层结构

所有业务 topic 必须挂在用户命名空间下：

```text
u/<username>/fleet/<device_id>/...
```

其中：

- `username`：用户标识，作为一级隔离边界
- `device_id`：终端设备标识

## 设备级 Topic

### Presence

```text
u/<username>/fleet/<device_id>/presence
```

用途：

- 表示终端是否在线
- 由终端 agent 发布
- 手机 App 订阅用户下所有设备的 presence

### Status

```text
u/<username>/fleet/<device_id>/status
```

用途：

- 发布设备状态
- 包括系统信息、agent 版本、当前活动 session、负载信息等

## 会话级 Topic

### Session List

```text
u/<username>/fleet/<device_id>/sessions
```

用途：

- 记录当前设备上的 session 摘要列表
- App 用于展示活跃会话和历史会话

### Session State

```text
u/<username>/fleet/<device_id>/sessions/<session_id>/state
```

用途：

- 发布某个 session 的当前状态
- 包括 `cwd`、状态、活动任务、创建/结束时间

### Directory Queryable

```text
u/<username>/fleet/<device_id>/directory
```

用途：

- App 使用 Zenoh Query 查询 agent 当前允许访问范围内的真实目录
- 查询路径相对当前 session `cwd` 解析，但必须限制在 agent `root` 内
- 返回当前 `root`、`cwd`、查询目录、目录项类型、大小、修改时间和相对 root 的路径
- App 不得猜测终端目录结构，也不应信任自己缓存的路径作为事实

## 命令 Topic

### Commands

```text
u/<username>/fleet/<device_id>/sessions/<session_id>/commands/<cmd_id>
```

用途：

- App 向指定 session 下发命令
- Agent 只订阅自己所属用户和设备下的 commands

约束：

- `cmd_id` 必须全局唯一或在 session 内唯一
- 同一个 `cmd_id` 重复到达时，agent 必须按幂等规则处理

## 事件 Topic

### Events

```text
u/<username>/fleet/<device_id>/sessions/<session_id>/events/<event_id>
```

用途：

- Agent 回传执行过程中的流式事件
- 包括 stdout、stderr、progress、approval_request、diff、message 等

约束：

- 每条 event 必须带 `seq`
- App 通过 `seq` 去重和补拉

## 结果 Topic

### Results

```text
u/<username>/fleet/<device_id>/sessions/<session_id>/results/<cmd_id>
```

用途：

- 发布命令最终结果
- 一个 command 最多有一个最终 result

## 控制 Topic

### Control

```text
u/<username>/fleet/<device_id>/sessions/<session_id>/control/<cmd_id>
```

用途：

- 取消任务
- 暂停任务
- 继续任务
- 回应 approval_request

## 媒体 Topic

### Media Metadata

```text
u/<username>/fleet/<device_id>/media/<asset_id>
```

用途：

- 传输图片、文件、富媒体的元数据和引用
- 大文件不建议直接放在控制 topic 里

## 文件传输 Topic

### Transfer Control

第一版不把大文件直接设计成 Zenoh 自定义分片协议。Zenoh 负责传输 `TransferRef`、状态和结果；真实文件内容由后端处理。

后端可以是：

- `local_spool`：本地验证用，文件或目录打包为 zip 并通过受控路径引用
- `tus`：后续用于断点续传上传
- `s3` / `minio`：后续用于云端对象存储和预签名 URL

命令仍发送到 session command topic：

```text
u/<username>/fleet/<device_id>/sessions/<session_id>/commands/<cmd_id>
```

App 上传到当前目录使用 `import_transfer`。
App 从当前目录取回内容使用 `export_transfer`。


后续可以为 App 补拉历史数据预留 query 入口：

```text
u/<username>/fleet/<device_id>/sessions/<session_id>/history
```

用途：

- 根据 `after_seq` 补拉事件
- 根据时间范围查询历史
- 查询 session 摘要

## ACL 建议

### 手机 App

允许：

```text
u/<username>/**
```

### 终端 Agent

允许：

```text
u/<username>/fleet/<device_id>/**
```

### 管理端

允许范围由部署策略决定，可以跨用户或只读全局状态。

## 命名规则

- `username` 只允许小写字母、数字、下划线和中划线
- `device_id` 建议使用稳定 ID，不使用主机名作为唯一身份
- `session_id` 建议使用时间前缀加随机后缀
- `cmd_id` 和 `event_id` 建议使用 UUID 或 ULID
- topic 中不放空格和中文

## 最小可实现集合

第一阶段只需要实现：

```text
u/<username>/fleet/<device_id>/presence
u/<username>/fleet/<device_id>/status
u/<username>/fleet/<device_id>/sessions/<session_id>/state
u/<username>/fleet/<device_id>/sessions/<session_id>/commands/<cmd_id>
u/<username>/fleet/<device_id>/sessions/<session_id>/events/<event_id>
u/<username>/fleet/<device_id>/sessions/<session_id>/results/<cmd_id>
```
