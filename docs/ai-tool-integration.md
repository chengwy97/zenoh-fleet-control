# AI 工具接入设计

## 结论

Codex、Claude 这类工具不能假设完全等价于在 bash 中启动后的完整交互式 TUI。

它们通常同时存在两类入口：

- 非交互执行模式：适合 agent 调用、JSON/JSONL 流式解析、结果回传
- 交互式 TUI/服务模式：更接近真实终端体验，但依赖 PTY、会话服务、权限确认和工具私有协议

因此本项目第一阶段只承诺支持非交互执行模式，完整交互和 slash command 能力通过 adapter capabilities 显式暴露。

## 前端选择模型

前端展示 AI 工具选择器：

- `shell`
- `codex`
- `claude`

实际下发统一命令：

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

## Agent 适配层

```text
CommandHandler
  -> ToolAdapterRegistry
      -> ShellAdapter
      -> CodexExecAdapter
      -> ClaudePrintAdapter
      -> future adapters
```

统一接口：

```python
class ToolAdapter:
    name: str
    capabilities: list[str]

    async def run(self, request, context):
        yield ToolEvent(...)
```

## Codex 能力边界

当前第一阶段使用：

```bash
codex -a never exec --json --cd <cwd> --sandbox workspace-write <prompt>
```

已验证：

- 可以输出 JSONL 事件
- 可以指定工作目录
- 可以作为非交互任务执行

暂不承诺：

- TUI 中所有 slash command 都可用
- `/goal` 等交互命令在 `exec` 模式下等价
- 人工 approval 可完整转发

后续要完整支持交互，应研究：

- `codex queue`
- `codex app-server`
- `codex remote-control`

## Claude 能力边界

Claude Code 后续建议使用非交互 print/JSON 模式接入。

暂不在第一阶段实现真实 Claude 调用，原因是需要单独确认本机 CLI、认证状态、输出格式和权限模式。

## Capability 上报

agent 不应该让前端猜能力，而应上报：

```json
{
  "tool": "codex",
  "capabilities": [
    "non_interactive_run",
    "json_stream",
    "cwd"
  ]
}
```

前端根据 capabilities 决定是否显示继续会话、approval、slash command 等按钮。
