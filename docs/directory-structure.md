# 目录结构设计

## 设计原则

- 先支持 Python agent 原型验证
- 协议定义独立于具体语言
- Android App、Agent、Router 配置分离
- 文档和实现分离
- 后续迁移 Rust agent 时不影响协议和 App

## 顶层结构

```text
zenoh-fleet-control/
├── README.md
├── docs/
├── protocol/
├── agent-python/
├── app-android/
├── web/
├── bridge-api/
├── router/
├── examples/
├── scripts/
└── tests/
```

## 目录说明

### `docs/`

放设计文档和决策记录。

建议内容：

- 架构设计
- 协议说明
- 状态机
- 安全模型
- 目录结构说明
- 后续路线图

### `protocol/`

放跨端共享的协议定义。

建议内容：

- message schema
- command 类型定义
- event 类型定义
- keyspace 规范
- versioning 规则

这个目录不绑定 Python、Kotlin 或 Rust。所有端都应该以这里为准。

### `agent-python/`

放验证阶段的终端 agent。

职责：

- 连接 Zenoh
- 注册设备 presence
- 订阅用户命名空间下的 commands
- 管理 session 和 cwd
- 执行本地任务
- 回传 events 和 results
- 接入 Codex / Claude 等工具 adapter

建议后续结构：

```text
agent-python/
├── pyproject.toml
├── README.md
├── src/
│   └── zfc_agent/
│       ├── main.py
│       ├── config.py
│       ├── zenoh_client.py
│       ├── device.py
│       ├── sessions.py
│       ├── commands.py
│       ├── events.py
│       ├── storage.py
│       └── adapters/
│           ├── base.py
│           ├── shell.py
│           ├── codex.py
│           └── claude.py
└── tests/
```

### `app-android/`

放 Android App。

职责：

- 设备列表
- 会话列表
- 工作目录切换
- 命令输入
- 实时事件流展示
- approval 操作
- 媒体发送和查看

验证阶段可以先放设计文档，后续再创建 Android Studio 工程。

### `bridge-api/`

放给手机 App 和浏览器用的 HTTPS 入口层。

职责：

- 用户名密码登录
- bearer token 颁发
- 设备列表和会话状态查询
- 命令和控制消息下发
- 跟 Zenoh 做后端桥接
- 对外统一 HTTPS，便于后续浏览器复用

### `web/`

放浏览器控制台静态资源。

职责：

- 登录 bridge
- 设备和 session 切换
- 通过 bridge 发送 Codex / shell 命令
- 轮询 session events/results
- 浏览 agent 工作目录

浏览器端不直接连接 Zenoh，由 `bridge-api` 同源托管。

### `router/`

放 `zenohd` 相关配置。

职责：

- 本地开发配置
- 云端 TLS / mTLS 配置
- ACL 配置
- 用户命名空间隔离规则
- pairing / enrollment 示例配置

### `examples/`

放端到端演示用例。

建议内容：

- 单用户单终端
- 单用户多终端
- 切换 session
- 切换 cwd
- 离线后补拉事件
- approval 流程

### `scripts/`

放开发辅助脚本。

建议内容：

- 启动本地 zenohd
- 启动测试 agent
- 生成开发证书
- 清理本地测试数据

### `tests/`

放跨组件测试。

建议内容：

- 协议 schema 测试
- keyspace 测试
- session 状态机测试
- 离线缓存和补拉测试
- agent 与 router 的集成测试

## 推荐演进顺序

1. `protocol/` 先定义 keyspace 和消息 schema。
2. `agent-python/` 打通 presence、command、event、result。
3. `router/` 加本地 zenohd 配置。
4. `examples/` 放最小可跑通场景。
5. `app-android/` 再开始接真实移动端 UI。
6. `tests/` 随协议稳定后补集成测试。

## 命名约定

- 项目简称可以使用 `zfc`。
- Python 包名建议为 `zfc_agent`。
- Zenoh key 前缀建议为 `u/<username>/fleet/...`。
- 文档优先使用小写文件名和中划线。
