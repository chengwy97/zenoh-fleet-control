# zenoh-fleet-control

## 定位

这是一个基于 Zenoh 的多终端控制面实现仓库。它只记录本仓库自身的设计、协议、模块和落地方式，不再重复放外部仓库对比。

## 目标

- 手机 App 作为统一控制台
- 浏览器作为同源 HTTPS 控制台
- 多终端在线状态管理
- 会话切换和工作目录切换
- 命令下发与执行反馈
- 富媒体与附件传输
- 离线缓存、补发、回放
- 会话结束和重新开始

## 设计输入

实现思路参考了这些已有项目的功能边界：

- 远程 Codex 控制台
- Android 远控桥接
- 多远端 session/thread 管理
- 流式输出和 approval 转发
- `/cd`、`/sessions`、历史回放、附件传输

这些外部项目的细节和对比已经移到父目录说明里，本仓库只保留可执行的实现方案。

文档入口：

- [CHANGELOG.md](CHANGELOG.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SECURITY.md](SECURITY.md)
- [docs/development-versions.md](docs/development-versions.md)
- [docs/deployment.md](docs/deployment.md)
- [file-api/README.md](file-api/README.md)
- [docs/file-transfer-architecture.md](docs/file-transfer-architecture.md)

## 快速验证入口

本地完整模拟栈可以用脚本启动：

```bash
./scripts/start-android-sim-backend.sh
```

启动后：

- Android 模拟器使用 `https://10.0.2.2:8443`
- 本机浏览器使用 `https://127.0.0.1:8443/`
- 真机使用 `https://<部署机器局域网 IP>:8443`，并需要手动导入脚本生成的 CA

浏览器控制台由 `zfc-bridge-api` 同源托管；手机 App 和浏览器都只接 HTTPS bridge，不直接接 Zenoh。

## 语言选型

### Android App

- 推荐 `Kotlin`
- 原因是 Android 生态完整、UI 和权限模型更自然

### Linux / Windows Agent

- 验证阶段优先 `Python`
- 原因是上手快、开发周期短、便于快速打通命令、状态和回传链路

### 后续可选方案

- 如果后面需要更高稳定性和更强的长期运行能力，可以再迁移到 `Rust`
- 如果团队更熟 JVM，也可用 `Java` / `Kotlin` 作为 agent 实现语言

### 选型原则

- App 和 Agent 分离
- 先以 Python 打通协议和功能验证
- 协议层保持和实现语言解耦
- 后续可无痛替换 agent 实现语言

## 访问层架构

手机 App 和浏览器客户端不直接依赖 Zenoh。推荐的对外接入方式是：

- `App / Browser -> HTTPS bridge -> Zenoh -> Agent`

这样可以把账号密码、TLS 证书导入、会话管理和 UI 适配放在 HTTP 层，同时保留 Zenoh 作为内部事件总线和多终端控制面。

### 为什么要加桥接层

- Android 和浏览器都更容易接 HTTPs
- 私有 CA 证书可以手动导入，不依赖系统自动识别
- 后续可以同时给手机 App 和网页端复用同一套接口
- Zenoh 继续负责状态广播、命令分发、事件流和回放

### 对外协议

- 登录、设备列表、会话状态、目录查询、命令下发、控制消息都走 HTTPS
- 浏览器控制台由 `zfc-bridge-api` 直接托管，避免浏览器直接接 Zenoh
- 终端 agent 继续只连 Zenoh
- 文件上传仍然走 `zfc-file-api + MinIO`，桥接层只处理会话控制面

## 云端安全模型

如果 `zenohd` 部署到云端，必须默认按受控接入处理，避免误接入和匿名终端混入。

### 基本要求

- 只允许 TLS 连接
- 优先使用 mTLS
- 每个终端单独签发证书
- 禁止匿名接入
- 证书过期自动失效
- 服务端按证书主体识别设备身份

### 访问控制

- 按用户和设备做 ACL
- 只允许访问自身命名空间下的 topic
- 手机端和 agent 端的权限应分开
- 管理端可以跨设备，但普通终端只能看自己相关的数据

### 防误接入

建议增加入网流程：

- 新设备先拿到一次性 pairing token
- 设备用 token 申请注册
- 服务端下发证书或绑定证书指纹
- 绑定后才允许进入正式 topic 空间

示例配置见：

- [agent-python/config.example.json](agent-python/config.example.json)
- [router/zenohd-security.example.json5](router/zenohd-security.example.json5)

### 推荐策略

- 不暴露裸露的公网明文端口
- 不允许无证书终端直连生产 router
- 对证书和 token 做定期轮换

## 多用户命名空间

话题建议再加一级用户名作为顶层命名空间。这样后续接入多用户时，不需要重构 keyspace，只要在用户维度下再挂设备和会话即可。

### 推荐结构

- `u/<username>/fleet/<device_id>/presence`
- `u/<username>/fleet/<device_id>/status`
- `u/<username>/fleet/<device_id>/sessions/<session_id>/state`
- `u/<username>/fleet/<device_id>/sessions/<session_id>/commands/<cmd_id>`
- `u/<username>/fleet/<device_id>/sessions/<session_id>/events/<event_id>`
- `u/<username>/fleet/<device_id>/sessions/<session_id>/results/<cmd_id>`
- `u/<username>/fleet/<device_id>/media/<asset_id>`

### 设计原则

- 用户是一级隔离边界
- 终端只订阅和处理与当前用户相关的命名空间
- 管理端可以枚举多个用户，但普通终端只关心自己的用户前缀
- 所有命令、事件和状态都必须带 `username`

### 消息字段补充

每条消息建议额外带：

- `username`
- `device_id`
- `session_id`
- `cmd_id`
- `scope`

这样在路由、鉴权、缓存和回放时都能直接按用户切分。

## 工具接入层

这个仓库不把 Codex、Claude 之类工具当成固定实现，而是当成可插拔的能力源。  
agent 侧应该提供统一的 `Tool Adapter`，把不同工具的输入输出收敛成同一种内部协议。

### 设计原则

- 工具接入和会话控制分离
- 工具输出统一转成 `event`
- 工具调用统一转成 `command`
- 工具状态统一转成 `session` 或 `task` 状态
- 不把某个工具的私有格式直接暴露给手机端

### Codex 特点

适合的场景：

- 代码编辑
- 仓库级任务
- 终端命令执行
- 文件修改和补丁回传
- 按工作目录组织的任务流

接入建议：

- 把 Codex 视为“代码工作流执行器”
- 让它接收结构化任务，而不是自由散发的自然语言
- 输出统一映射成 `progress`、`diff`、`result`、`error`
- 对仓库、分支、cwd、patch 一类对象做显式建模

### Claude 特点

适合的场景：

- 通用对话和推理
- 复杂任务分解
- 长上下文解释
- 工具调用编排
- 人机交互式审批

接入建议：

- 把 Claude 视为“控制面上的规划器或对话层”
- 让它负责任务拆解、澄清问题、生成执行计划
- 再把计划转成具体 command 下发给终端 agent
- 输出统一映射成 `message`、`plan`、`approval_request`、`result`

### 统一抽象

建议在本仓库中定义一层通用接口：

- `Planner`
- `Executor`
- `Reviewer`
- `Notifier`

其中：

- `Planner` 负责生成执行步骤
- `Executor` 负责落地执行
- `Reviewer` 负责确认高风险动作
- `Notifier` 负责把反馈推送到手机端

这样未来接入更多工具时，只需要实现适配器，不需要改整体协议。

## 目录结构

目录结构设计见：

- [docs/directory-structure.md](docs/directory-structure.md)
- [docs/ai-tool-integration.md](docs/ai-tool-integration.md)

## 架构分层

### 1. Mobile Console

负责：

- 设备列表
- 会话列表
- 当前 session 状态
- 工作目录切换
- 命令编辑与提交
- 执行反馈展示
- 媒体查看

### 2. Device Agent

部署在终端上，负责：

- 连接 Zenoh
- 注册 presence
- 接收命令
- 执行本地动作
- 上报日志、进度、结果
- 维护 session 状态和 cwd

### 3. Router / Transport

负责：

- 路由和转发
- 在线状态传播
- 消息补发
- 终端和手机间的连接中继

### 4. Persistence

负责：

- session 事件归档
- 离线消息缓存
- command/result 持久化
- 媒体元数据与引用

### 5. File Data Plane

负责：

- 通过 `zfc-file-api` 鉴权
- 通过 MinIO/S3 存储真实文件字节
- 给 App 和 Agent 生成短期上传/下载 URL
- 只在 Zenoh 控制面传递 `TransferRef`

## 核心对象

### Device

```text
device_id, name, platform, last_seen, status, capabilities
```

### Session

```text
session_id, device_id, cwd, status, created_at, ended_at, active_task_id
```

### Command

```text
cmd_id, session_id, device_id, type, payload, status, created_at, updated_at
```

### Event

```text
event_id, cmd_id, session_id, device_id, kind, content, seq, timestamp
```

## 协议框架

### Presence

- `fleet/<device_id>/presence`
- `fleet/<device_id>/status`

### Session state

- `fleet/<device_id>/sessions/<session_id>/state`

### Commands

- `fleet/<device_id>/sessions/<session_id>/commands/<cmd_id>`

### Events

- `fleet/<device_id>/sessions/<session_id>/events/<event_id>`

### Results

- `fleet/<device_id>/sessions/<session_id>/results/<cmd_id>`

### Media

- `fleet/<device_id>/media/<asset_id>`

## 消息格式

### Command

```json
{
  "cmd_id": "cmd_001",
  "session_id": "sess_001",
  "device_id": "dev_001",
  "type": "run",
  "payload": {
    "text": "ls -la"
  }
}
```

### Event

```json
{
  "event_id": "evt_001",
  "cmd_id": "cmd_001",
  "session_id": "sess_001",
  "device_id": "dev_001",
  "kind": "progress",
  "seq": 12,
  "content": "running...",
  "timestamp": 1725330000
}
```

### Result

```json
{
  "cmd_id": "cmd_001",
  "session_id": "sess_001",
  "device_id": "dev_001",
  "status": "succeeded",
  "output": {
    "text": "..."
  }
}
```

## 状态机

### Session

- `idle`
- `running`
- `waiting_approval`
- `ending`
- `ended`
- `failed`

### Command

- `queued`
- `accepted`
- `running`
- `waiting_approval`
- `succeeded`
- `failed`
- `cancelled`

## 工作目录

`root` 是 agent 允许访问的根目录，`cwd` 属于 session，不属于 device。

切换目录的指令必须是结构化命令，不直接发送 shell `cd`。

校验项：

- 路径存在
- 是目录
- 用户有权限
- 在允许访问范围内
- 当前没有不允许中断的任务

## 会话结束

结束会话后：

- 不再接受新命令
- 归档事件流
- 保留历史查询
- 新建会话需要新的 `session_id`

## 离线缓存

策略：

- 实时流继续推送到当前前台会话
- 非当前终端的消息进入缓存
- 切回时先补拉缓存，再接实时流
- 关键命令和结果持久化
- 普通日志按 TTL 清理

## 实现顺序

1. Device / Session / Command / Event 数据模型
2. Presence 和在线状态
3. Command / Result 基础链路
4. cwd 切换和 session 结束
5. 离线缓存和补发
6. 富媒体和附件传输
7. 权限、审批和审计

## 借鉴点

实现时建议重点吸收外部仓库中的这些思路：

- session 恢复
- 流式输出
- approval 转发
- 多会话切换
- 目录级上下文
- 附件和媒体回传

本仓库最终要形成的是一套可落地的协议和 agent 实现，而不是单纯的前端壳。
