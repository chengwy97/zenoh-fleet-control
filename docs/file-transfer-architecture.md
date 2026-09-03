# 文件传输架构

## 目标

文件传输采用控制面和数据面分离：

```text
App / Agent -- Zenoh --> zenohd
App / Agent -- HTTPS --> zfc-file-api -- S3 API --> MinIO
```

- `zenohd` 只负责命令、状态、事件和 `TransferRef`。
- `zfc-file-api` 负责身份认证、授权、对象命名和短期 URL。
- `MinIO` 负责实际文件字节和持久化。
- App 和 Agent 不通过 Zenoh 自定义大文件分片传输。

## 为什么这样拆分

- Zenoh 消息保持小而可缓存，避免大文件挤占控制面。
- MinIO/S3 自带成熟的对象存储、分段上传、校验和生命周期能力。
- 预签名 URL 允许 App/Agent 直接传输文件，file-api 不需要代理所有字节。
- 后续从 MinIO 迁移到 AWS S3、其他 S3 兼容存储时，控制协议不变。

## TransferRef 生命周期

### App 上传到 Agent

1. App 选择文件或目录。目录在 App 端打包为 zip；大目录也可以交给 file-api 或 Agent 侧打包。
2. App 请求 `zfc-file-api` 创建上传对象。
3. file-api 校验身份和目标命名空间，返回短期 `upload_url` 与 `TransferRef`。
4. App 使用 `upload_url` 直接 PUT 文件到 MinIO。
5. App 通过 Zenoh 向目标 session 发送 `import_transfer` 和 `TransferRef`。
6. Agent 使用短期下载能力取得对象，校验大小、SHA-256 和归档内容。
7. Agent 解压到当前 cwd 或指定的安全相对目录，并回传 `transfer_imported`。

### Agent 下载到 App

1. App 通过 Zenoh 发送 `export_transfer`，只包含当前 cwd 内的相对路径。
2. Agent 校验路径，打包文件或目录并上传到 MinIO。
3. Agent 通过 Zenoh 回传 `transfer_export_ready` 和 `TransferRef`。
4. App 向 file-api 请求短期 `download_url`，或使用受控的现有 URL。
5. App 下载对象，校验 SHA-256，目录归档则解压到用户选择的位置。

## 对象命名

对象 key 必须包含用户、设备、会话和 transfer：

```text
u/<username>/fleet/<device_id>/sessions/<session_id>/transfers/<transfer_id>/<name>
```

客户端提交的 `username`、`device_id` 和 `session_id` 不能单独作为信任依据。生产 file-api 应从认证 token、mTLS 身份或服务端会话中确定调用者身份，再与请求目标做授权校验。

## 认证与授权

开发环境可以使用 Bearer Token。生产环境建议：

- App 使用用户登录 token 或 OIDC/JWT。
- Agent 使用设备证书、mTLS 或设备专用 token。
- file-api 校验 token 中的用户、设备和权限。
- 普通 App 只能访问自己用户命名空间下的对象。
- Agent 只能访问被授权的目标设备和会话对象。
- 预签名 URL 只允许一个对象、一个动作和短时间窗口。
- MinIO 不直接暴露给公网，公网只暴露 HTTPS file-api 或受控对象网关。

## 校验与安全边界

- 上传完成后必须校验对象存在、大小和 SHA-256。
- Agent 解压前必须检查 zip entry，拒绝 `..`、绝对路径和符号链接逃逸。
- cwd 和文件操作必须限制在 agent `root` 内。
- 文件名只作为对象名的一部分，不能用于构造本地任意路径。
- 传输记录应保存创建者、目标 namespace、大小、摘要、状态和过期时间。
- 未完成或过期对象应由 MinIO lifecycle 定期清理。

## 传输状态

建议统一使用：

```text
created -> uploading -> uploaded -> queued -> processing -> completed
                                          \-> failed
                                          \-> cancelled
```

控制面应回传进度和最终状态；App 切换终端或短暂断线后，通过 `transfer_id` 查询状态，不重新猜测文件是否存在。

## 后端演进

当前 Python 原型同时支持 `local_spool` 和基于 `zfc-file-api` 的 `s3`/`minio` 后端：

- `local_spool`：同机共享路径，不适用于真实手机。
- `s3`/`minio`：跨设备、云端和多用户部署。agent 和开发 CLI 通过 file-api 获取短期 URL，不直接保存 MinIO 密钥。
- `tus`：如果需要专门的断点续传上传，可作为 file-api 的上传实现，但不改变 Zenoh 命令语义。

App 和 Agent 应依赖抽象的 `TransferRef`，不要依赖具体存储 URL 格式。

## 当前实现状态

`agent-python` 已实现 file-api 传输后端：

- `stage_upload`：本地文件或目录打包为 zip，向 file-api 申请上传 URL，PUT 到 MinIO，返回去掉 `upload_url` 的 `TransferRef`。
- `import_to_cwd`：根据 `TransferRef.download_url` 下载 zip，校验 `size/sha256`，安全解压到当前 cwd 下的目标目录。
- `export_from_cwd`：agent 打包 cwd 内文件或目录，上传到 MinIO，并通过 Zenoh 回传 `transfer_export_ready`。
- `materialize`：App/开发 CLI 根据 `TransferRef` 下载并解包到本地输出目录。

本地闭环验证脚本：

```bash
./scripts/verify-file-api-minio.sh
```

该脚本会启动 MinIO、file-api、zenohd 和 Python agent，验证 app 侧上传到 agent cwd、agent 侧导出回 app 侧并比较文件内容。
