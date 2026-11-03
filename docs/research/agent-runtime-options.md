# qbot 执行型 Agent 的运行时选项研究

- **评估日期：2026-11-03（Asia/Shanghai）**。
- **范围：仅研究，不实现、不部署、不运行模型。**面向把现有 QQ 计分/统计用途替换为可读文件、改文件、运行受控命令、等待审批、汇报结果的助手；不把“接入一个聊天模型”等同于具备执行能力。
- **证据标记**：**已核实**＝读取官方源码、官方仓库文档或官方站点；**建议**＝本研究判断；**待验证**＝没有实际执行验证，不能作为已具备能力承诺。
- **重要边界**：公开运行时 SDK、当前交互助手的系统策略、多代理调度以及 QQ 产品层是不同对象。复用运行时不等于复制当前助手所有工具、审批策略、托管服务或编排行为。

## 一、结论先行

**建议：保留现有 NoneBot2 / OneBot 通道，退役统计用途，把执行 Agent 放在独立工作进程；优先验证 DeepSeek Harness 官方 Python SDK，保留可替换运行时边界。**已找到官方 SDK、独立运行时、stdio JSON-RPC、会话恢复和审批桥接。[D1](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/README.md)[D2](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/python/sdk/README.md)[D3](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/sdk/server/README.md) 对执行型助手的目标，这比从通用循环框架重新组装文件工具、shell、会话和权限更贴近需求；但这是适配度判断，不是速度、稳定性或安全优越性的实测结论。

**此推荐附带两个硬条件**：

1. 接受 developer preview 的破坏性升级风险，固定经过验证的 SDK/运行时版本；官方明确尚未安全审计，不能作为不可信群消息执行的唯一安全边界。[D1](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/README.md)[D5](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/SAFETY.md)
2. 先解决取消与隔离：当前核实的 SDK 协议表**没有 `session/cancel` 或 `session/interrupt` 方法**；`shutdown` 是整个运行时关闭。不能设计一个不存在的“每会话取消 API”。[D3](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/sdk/server/README.md)[D4](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/sdk/protocol/README.md) 建议任务级独立 worker，加受控关停和进程树清理验收；如果必须在单个共享运行时内可靠、独立地中断任意任务，DSH 尚不能凭现有证据过选型门槛。

**替代路线**：

- 若优先选择现成 coding 工具与原生异步 Python 客户端，并接受 Claude Code/Anthropic 产品依赖：验证 **Claude Agent SDK**。[C1](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/README.md)[C2](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/src/claude_agent_sdk/client.py)
- 若优先跨模型、应用自行控制工具，并希望有明确的流式取消和可持久化审批状态：验证 **OpenAI Agents SDK**。不能沿用“它只有 function calling、没有 coding/sandbox”这一过时概括：当前官方源码已包含 `SandboxAgent` 与 Docker 等 sandbox client。[O1](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/README.md)[O4](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/sandbox/clients.md)
- 若核心难点是跨重启的审批流程、状态机和可恢复多步骤任务：考虑 **LangGraph 作为编排层**，不是把它当现成 coding assistant 或 OS 沙箱。[L1](https://github.com/langchain-ai/langgraph/blob/3c916d750575b22c464790e9774494d810ccd322/README.md)[L2](https://docs.langchain.com/oss/python/langgraph/persistence)[L3](https://docs.langchain.com/oss/python/langgraph/interrupts)
- **AstrBot** 适合作为直接相关的 QQ/OneBot、多通道、插件、执行环境参考；本次不建议为了获得 Agent 把现有 qbot 整体迁移。是否迁移属于产品替换决策，且须评估 AGPL。[A1](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/README.md)[A2](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/docs/zh/use/astrbot-agent-sandbox.md)[A3](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/LICENSE)

## 二、先纠正仓库身份与证据版本

### 2.1 DeepSeek Harness 的真实官方仓库

**已核实**：DeepSeek Harness 官方仓库是 **`deepseek-ai/deepseek-harness`**；README 自述由 DeepSeek AI 开发，许可证 MIT，并提供 SDK 文档。[D1](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/README.md)[D2](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/python/sdk/README.md)[D6](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/apps/cli/package.json)

下述 GitHub 证据是评估日默认分支快照，不代表所有 API 都已进入选定的 PyPI/npm 发布包；上线前仍需固定发布版本并验证兼容性。

### 2.2 固定的源码快照

所有 GitHub 读取均经 `gh`，未通过网页抓取 GitHub；以下是本次记录的默认分支提交。正文引用尽量指向这些不可变版本，避免“当前 main/master”变化造成难以复核。

| 项目 | 记录的提交 | 本次读取的许可证信息 |
|---|---|---|
| DeepSeek Harness | `ce7073d51254c26cd63b22a60835b8f948deb447` | MIT；官方另有安全告知与第三方许可清单。[D1](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/README.md)[D5](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/SAFETY.md) |
| Claude Agent SDK Python | `8abce1165075a20f5fe0e257b2306b4037bae37e` | SDK LICENSE 为 MIT，但 README 同时指向 Anthropic Commercial Terms；不能推导为 Claude Code 和服务均可任意再分发。[C1](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/README.md)[C4](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/LICENSE) |
| OpenAI Agents SDK Python | `e355d69152d4f4730dfb03b63dbce53e8d9f5d8c` | MIT。[O5](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/LICENSE) |
| LangGraph | `3c916d750575b22c464790e9774494d810ccd322` | MIT，指开源库而非所有托管产品条款。[L1](https://github.com/langchain-ai/langgraph/blob/3c916d750575b22c464790e9774494d810ccd322/README.md)[L4](https://github.com/langchain-ai/langgraph/blob/3c916d750575b22c464790e9774494d810ccd322/LICENSE) |
| AstrBot | `6c942855cb06b6d43854e8b841859d60a5c6043e` | AGPL-3.0；具体改造、组合与对外提供网络服务的合规义务须另行审查。[A3](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/LICENSE) |

## 三、横向比较：到底复用哪一层

| 维度 | DSH | Claude Agent SDK | OpenAI Agents SDK | LangGraph | AstrBot |
|---|---|---|---|---|---|
| 无 GUI 接入 | Python 子进程 SDK + stdio JSON-RPC；另有 one-shot headless。[D2](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/python/sdk/README.md)[D3](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/sdk/server/README.md)[D7](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/bundle/headless/README.md) | `query()`、`ClaudeSDKClient`，CLI 随包提供。[C1](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/README.md) | `Runner.run/run_sync/run_streamed`；存在 `SandboxAgent`。[O1](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/README.md)[O2](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/running_agents.md) | 本地 graph invoke/stream；无需购买托管部署才能用库。[L1](https://github.com/langchain-ai/langgraph/blob/3c916d750575b22c464790e9774494d810ccd322/README.md)[L2](https://docs.langchain.com/oss/python/langgraph/persistence) | 独立聊天机器人平台，插件与 Runner，不等同于小型嵌入 SDK。[A1](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/README.md)[A4](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/docs/zh/use/agent-runner.md) |
| coding 工具现成度 | full SDK 的工具/插件组合与 minimal profile 有明确差异。[D2](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/python/sdk/README.md) | 默认 Claude Code Read/Write/Edit/Bash 等工具。[C1](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/README.md) | SandboxAgent、Shell/ApplyPatch 等；仍需选具体执行后端。[O1](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/README.md)[O3](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/human_in_the_loop.md)[O4](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/sandbox/clients.md) | 低层编排，执行工具和执行环境另配。[L1](https://github.com/langchain-ai/langgraph/blob/3c916d750575b22c464790e9774494d810ccd322/README.md) | 内建 Agent 循环、电脑能力、MCP/Skills 和沙箱配置。[A1](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/README.md)[A2](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/docs/zh/use/astrbot-agent-sandbox.md)[A4](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/docs/zh/use/agent-runner.md) |
| 会话持久化 | JSONL/配置归 home，显式 resume；不恢复外部进程。[D2](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/python/sdk/README.md) | session id + `resume`/`continue_conversation`；不是任务队列承诺。[C3](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/src/claude_agent_sdk/types.py) | Sessions 管理历史；RunState 保存暂停执行状态，两者不同。[O2](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/running_agents.md)[O3](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/human_in_the_loop.md) | checkpointer + thread id；选持久后端才跨重启。[L2](https://docs.langchain.com/oss/python/langgraph/persistence)[L3](https://docs.langchain.com/oss/python/langgraph/interrupts) | 平台会话与 sandbox session；耐久任务重投/崩溃恢复语义本次未核实。[A2](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/docs/zh/use/astrbot-agent-sandbox.md) |
| 人类审批 | SDK 双向 `approval/request`；headless 无实时审批返回通道。[D2](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/python/sdk/README.md)[D3](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/sdk/server/README.md)[D7](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/bundle/headless/README.md) | 权限模式、`can_use_tool`、hooks。[C1](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/README.md)[C3](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/src/claude_agent_sdk/types.py) | `needs_approval` → interruptions → RunState approve/reject → resume。[O3](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/human_in_the_loop.md) | `interrupt()` + `Command(resume=...)`，应用自行鉴权。[L3](https://docs.langchain.com/oss/python/langgraph/interrupts) | 文档包含普通成员/管理员权限矩阵；逐次外部审批协议待验证。[A2](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/docs/zh/use/astrbot-agent-sandbox.md) |
| 取消 | 未见单会话取消方法；shutdown 全运行时；goal pause 不是通用强制终止。[D3](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/sdk/server/README.md)[D4](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/sdk/protocol/README.md) | `await client.interrupt()`，源码限定 streaming mode。[C2](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/src/claude_agent_sdk/client.py) | 流式结果 `cancel(immediate/after_turn)`；after_turn 会执行当前待处理工具。[O6](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/src/agents/result.py#L941-L965) | interrupt 是检查点暂停，不能等同于杀死外部命令。[L3](https://docs.langchain.com/oss/python/langgraph/interrupts) | Runner 终止与外部命令清理的端到端保障待验证。[A4](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/docs/zh/use/agent-runner.md) |
| 沙箱边界 | 平台相关文件效果约束；不自带网络隔离保证。[D8](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/subsystems/sandbox.md) | 有 sandbox 配置；权限允许不是 OS 隔离。[C3](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/src/claude_agent_sdk/types.py) | UnixLocal、Docker、托管后端差异很大；Linux UnixLocal 无 OS confinement。[O4](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/sandbox/clients.md) | 图状态持久化不隔离 OS。[L1](https://github.com/langchain-ai/langgraph/blob/3c916d750575b22c464790e9774494d810ccd322/README.md)[L2](https://docs.langchain.com/oss/python/langgraph/persistence) | 本机隔离或第三方独立环境，能力依赖平台和容器配置。[A2](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/docs/zh/use/astrbot-agent-sandbox.md) |
| 主要绑定 | DSH profile/Cordis、事件和会话格式；可插件化适配模型但需配置。[D1](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/README.md)[D2](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/python/sdk/README.md) | Claude Code CLI 与服务生态；不是任意模型通用执行器。[C1](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/README.md)[C3](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/src/claude_agent_sdk/types.py) | 开源多 provider；Hosted tools、Responses 特性和 trace 服务需单独评估。[O1](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/README.md)[O2](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/running_agents.md) | 图/检查点模型；可独立用库，LangSmith 部署另计。[L1](https://github.com/langchain-ai/langgraph/blob/3c916d750575b22c464790e9774494d810ccd322/README.md)[L2](https://docs.langchain.com/oss/python/langgraph/persistence) | AstrBot 插件/事件/平台管理方式及 AGPL。[A1](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/README.md)[A3](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/LICENSE) |

> **建议**：将“历史可恢复”“暂停审批可恢复”“进程崩溃后任务自动继续”“shell 进程继续存在”“外部副作用恰好一次”分开验收。任何一格有“持久化”都不意味着后四项自动成立。

## 四、逐项核实与接入含义

### 4.1 DeepSeek Harness：最贴近目标，但必须约束预览版风险

**真实入口**：[D2](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/python/sdk/README.md) 文档给出安装包 `deepseek-harness-sdk`，依赖同版本 runtime wheel；`DeepSeekHarness(...)` 延迟启动并复用运行时，`harness.run(...)` / `session.run(...)` 返回 `RunResult`。其背后启动 `dsh --profile sdk`，使用换行分隔 JSON-RPC。SDK 要求显式指定 Harness home，不能默认借用操作者已有个人配置。`cwd` 是工作区，`runtime_cwd` 是子进程工作目录，两者独立。

**流与结果**：`on_notification` 接收根会话及已知后代活动；`RunResult.events` 只含根会话事件，`final_response` 不应被子任务文本覆盖。低层 `session_prompt()` 返回的是入队消息 ID，不是最终结果。[D2](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/python/sdk/README.md)[D3](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/sdk/server/README.md) 因高层 API 为同步调用，**建议**不要直接放在 NoneBot 异步事件处理函数里阻塞执行，应交给 worker/专用线程；审批读取必须能与运行等待并行。

**恢复**：`resume_session(saved_session_id)` 使用原 home/工作区恢复，缺失、不可读、不兼容或已占用会话失败，而不是悄悄新建。`start_session()` 不等价于恢复。官方明确不会复活 shell、浏览器等外部进程。[D2](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/python/sdk/README.md) `/goal` 可跨自动轮次运行，但恢复后已激活 goal 会保持 disarmed，需显式 resume；这与“机器人重启就自动执行上次剩余命令”不是同一语义。[D2](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/python/sdk/README.md)[D3](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/sdk/server/README.md)

**审批**：显式开启 `approval_requests=True` 后，宿主处理 `approval/request`，一次性结果为 `allowed-once` / `rejected` / `cancelled`。断链、非法响应与晚到响应不能授权已放弃的调用。[D2](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/python/sdk/README.md)[D3](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/sdk/server/README.md)[D4](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/sdk/protocol/README.md) **建议**将 QQ 身份验证、授权人列表、任务归属、过期时间、单次消费放在 bot 服务端；不允许把模型生成的“用户已同意”当审批证据。

**headless 的适用边界**：`dsh --profile headless` 一次任务后退出；`--json` 给 NDJSON，`--session-id` 可恢复，且有目录/所有权/preset 校验。headless 没有 live approval-response channel；无交互执行可使用 `--approval-policy never` 拒绝需要审批的调用。[D7](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/bundle/headless/README.md) 因此：只做管理员只读报告时可考虑 headless；需要 QQ 内审批/追问时应选 SDK，而不是解析 GUI 或猜 HTTP 路由。JSON 的 text/thinking 来自已提交消息，不是逐 token 输出；除最终结果外事件存在截断，不能当无损审计日志。[D7](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/bundle/headless/README.md)

**取消与隔离**：公开 SDK 方法表没有单会话取消接口；`shutdown` 关闭全运行时，`/goal pause` 只表达 goal 控制。[D3](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/sdk/server/README.md)[D4](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/sdk/protocol/README.md) **待验证**：中断正在执行的 shell 时，后代进程、临时文件、外部请求如何收束；不可承诺关进程即回滚已发生写入。sandbox 的 read-only/workspace-write 是文件效果策略，network/process visibility 在词汇范围之外；Linux bwrap/Landlock、macOS Seatbelt、Windows ACL 后端还存在 full/partial enforcement 区别。[D8](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/subsystems/sandbox.md) **建议**独立容器/VM、非特权账户、最小挂载、外联限制与凭据隔离，不与聊天登录环境共用信任边界。官方自身也推荐一次性或专用环境，禁止把 DSH 当唯一安全控制。[D5](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/SAFETY.md)

### 4.2 Claude Agent SDK：现成执行体验，依赖范围要写清

**真实入口**：Python `query()` 返回异步消息迭代器，`ClaudeSDKClient` 支持双向交互、自定义工具与 hooks，SDK 包含 CLI。[C1](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/README.md) `allowed_tools` 是自动批准名单，**不是“未列出的工具彻底不可见/不可用”**；禁用要看 `disallowed_tools`。使用 acceptEdits、bypassPermissions 等模式会改变授权边界，不应为了无人值守而一律绕过。[C1](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/README.md)[C3](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/src/claude_agent_sdk/types.py)

**持续与取消**：`ClaudeAgentOptions.resume` 按 session id 恢复历史，`continue_conversation` 延续当前目录最近会话；应以任务持久化保存准确 ID，不靠“最近一次”关联群消息。[C3](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/src/claude_agent_sdk/types.py) `await client.interrupt()` 真实存在，源码说明仅 streaming mode。[C2](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/src/claude_agent_sdk/client.py) 但这不是外部副作用回滚、所有第三方工具进程均立即退出或任务跨重启恰好一次的证据。

**权限与沙箱**：具备工具决策回调、hooks、sandbox 配置；SDK 权限策略与执行环境隔离应分别审计。[C1](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/README.md)[C3](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/src/claude_agent_sdk/types.py) **建议**对 QQ 群输入不启用 bypassPermissions，不依赖字符串命令黑名单作为完整安全边界；工具函数、MCP 与 shell 必须纳入同一任务授权模型。

**许可/锁定**：仓库 SDK LICENSE 为 MIT，但 README 明确使用受 Anthropic Commercial Terms 约束，并包含面向自身最终用户提供产品的情形。[C1](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/README.md)[C4](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/LICENSE) SDK bundling CLI 不等于 Claude Code 二进制与服务条款也都变成 MIT。**建议**评估组织 API 身份、Claude Code 再分发、企业/第三方平台接入规则后再选；本次未完成法律审查，也未验证任意非 Claude 模型可替换性，不能把它推荐为 vendor-neutral 框架。

### 4.3 OpenAI Agents SDK：不只聊天循环，需防止选错 sandbox

**真实入口**：`Runner.run()` 异步、`run_sync()` 同步、`run_streamed()` 返回流式结果；可设置 max_turns、模型/provider、工具和 tracing。[O1](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/README.md)[O2](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/running_agents.md) 当前官方 README 明确支持 `SandboxAgent` 检查文件、运行命令、打补丁与工作区持续状态，存在 `UnixLocalSandboxClient`、`DockerSandboxClient` 和托管扩展。[O1](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/README.md)[O4](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/sandbox/clients.md) 这是源码快照事实，不是本次已验证发布包支持。

**持久化**：SQLiteSession 等 Sessions 保存对话历史；审批中断后 `result.to_state()` → `RunState` 序列化 → `RunState.from_json/from_string` → approve/reject → Runner 恢复。[O2](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/running_agents.md)[O3](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/human_in_the_loop.md) 官方强调恢复反序列化**不会验证状态提交者身份**，快照必须放可信服务端，授权和防重放由应用完成。官方也明确审批不保证 exactly-once：外部操作已完成但状态未落盘时，重放可能重复执行，应使用目标端幂等键或权威对账。[O3](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/human_in_the_loop.md)

**取消**：流式结果 `cancel()` 默认 immediate，另有 `cancel(mode="after_turn")`；后者允许当前模型答复完成、执行 pending tool calls，再停在下一轮前；调用后仍应继续消费 stream 使取消完成。[O6](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/src/agents/result.py#L941-L965) **建议**QQ 的“立即停止”不能映射成 after_turn，否则用户以为停了但危险调用还可能执行；即使 immediate，也要为不响应 asyncio cancellation 的阻塞工具和外部进程另做终止机制与验收。

**沙箱**：官方 client 文档警告 UnixLocal 在 Linux **不增加 OS 级隔离**，cwd/HOME 不是访问控制；macOS 文件限制也不提供网络隔离。Docker 可选 `network_mode="none"`，但挂载、凭据与容器权限仍应显式审查。[O4](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/sandbox/clients.md) 因此不能仅看到类名有 Sandbox 就宣称适合接收不可信 QQ 命令。

**绑定与隐私**：框架支持其他 provider，但 Responses/hosted tools 的可移植性与函数工具不是同一回事。RunConfig 提供 tracing_disabled、trace_include_sensitive_data 等设置。[O1](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/README.md)[O2](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/running_agents.md) **建议**先明确禁用或脱敏外发 trace，再评估模型与执行后端；可替换 provider 不等于所有高级能力零成本迁移。

### 4.4 LangGraph：用于耐久编排，不替代 execution harness

**已核实**：官方定位低层、长时间、状态化工作流框架，可脱离 LangChain 使用；本地库与 LangSmith 托管部署分开。[L1](https://github.com/langchain-ai/langgraph/blob/3c916d750575b22c464790e9774494d810ccd322/README.md) 编译 graph 时配置 checkpointer，运行使用 `configurable.thread_id`；InMemorySaver 跨进程不持久，应选择持久后端。[L2](https://docs.langchain.com/oss/python/langgraph/persistence)

`interrupt()` 可保存状态等待外部输入，使用同一 thread id 和 `Command(resume=...)` 恢复。**恢复会从所在 node 开头重跑，不是从 Python 指令行原位置继续**；因此 interrupt 前的副作用必须幂等或拆分节点，不能把“已经发出的 QQ 消息/已写的文件”再发/再写一次。[L3](https://docs.langchain.com/oss/python/langgraph/interrupts)

**建议**：当任务包含“计划→等待管理员→执行→人工复核→发布”、需要清晰持久状态转换时，它的价值高于一次简单 shell 工具循环。若主要目标是迅速获得成熟编码工具，用 LangGraph 从零组装执行器并不自然减少工作量。图 checkpoint 不会隔离进程、收回凭据或取消已发出的外部请求；审批暂停也不等同运行中取消。**待验证**：本地运行取消传播、部署 server 的 run cancel 行为、被调用工具的超时和清理；本次未以某个未读取的 server API 作为保证。

### 4.5 AstrBot：直接相关的 QQ/OneBot 平台参考

**已核实**：官方 README 列出 QQ、OneBot v11、多平台、工具/MCP/Skills 和 Agent Sandbox。[A1](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/README.md) Agent Runner 文档把执行描述为理解→计划→工具→观察的循环。[A4](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/docs/zh/use/agent-runner.md) 沙箱文档区分“本机环境”与“第三方独立环境”；本机 Linux/macOS 隔离依赖 bwrap/Seatbelt 等，Docker 内部再启 bwrap 受到宿主命名空间/seccomp 等限制，默认容器部署不一定可用；成员/管理员有不同权限矩阵。[A2](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/docs/zh/use/astrbot-agent-sandbox.md)

**建议**参考它的通道隔离、会话与执行环境映射、工具权限和诊断，而不是重复发明每个 QQ 接入细节。**不建议直接搬代码进 qbot** 而忽略 AGPL；如果决定整体替换现有 bot，应另评估统计功能退役、现有协议行为、插件兼容、许可证义务与运维成本。[A3](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/LICENSE)

**待验证**：其对“运行数小时任务”的断电恢复、任务级取消、挂起审批跨重启、每用户工作区实际隔离及第三方 sandbox 生命周期保证。当前证据证明平台有相关模块，不能自动证明这些端到端产品保证。

## 五、选型门槛与后续验证（建议，未执行）

以下是研究结论转入后续原型前的检查表，不是本次新增产品功能：

1. **固定版本**：记录运行时、SDK、模型 adapter、工具 schema、sandbox 后端；验证默认分支 API 是否进入所选发布包。升级时先跑兼容性测试，再恢复旧任务。
2. **headless 接入**：不用 GUI、不猜内部 HTTP 接口，能启动 worker、接收结构化事件、区分入队/运行/工具结束/任务结束，且不能把“shell 工具已返回”误报为“命令 exit code=0”。DSH headless 文档已明确这一差异。[D7](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/bundle/headless/README.md)
3. **恢复语义**：持久保存 task id→会话 id→工作区→身份；分别测试等待审批时重启、模型流断线、shell 中途退出、结果落盘前崩溃。不得因请求超时就自动重放执行。
4. **取消验收**：模型调用、长 shell、后台子进程、MCP、等待审批五种状态分别取消；确认进程树、文件句柄、容器、晚到审批和结果发送均收束。DSH 先验证任务级 worker shutdown，不假设独立会话取消。
5. **权限验收**：非授权群/用户不可执行；审批绑定真实用户、任务、原始工具参数、过期时间及单次决策；恢复后不得继承别的用户批准。即使机器人能接收自己发的消息，也必须防止自触发重入。
6. **隔离验收**：逃逸到工作区外、软链接、共享仓库元数据、环境变量、宿主凭据、出网、磁盘/内存/CPU/进程数。read-only 通常不是“不可读秘密”，cwd 更不是 jail。
7. **副作用审计**：发消息、修改外部数据、写文件、对外 API 调用分开看幂等性。未知结果标为 unknown 并人工核对，不把取消/重试当回滚。[O3](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/human_in_the_loop.md)[L3](https://docs.langchain.com/oss/python/langgraph/interrupts)
8. **成本与隐私**：设应用级时长/轮次/预算/并发边界；验收日志脱敏、工具输出和 trace 的流向。没有做性能基准，不能承诺更快、更省或支持某一并发量。
9. **许可/服务条款**：开源库、CLI/runtime 二进制、第三方插件/模型服务、sandbox 服务逐层审查；尤其 Claude 的额外条款和 AstrBot 的 AGPL，必要时咨询合规人员。[C1](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/README.md)[C4](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/LICENSE)[A3](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/LICENSE)

## 六、证据限制与未解决问题

- 本次基于官方文档、源码与只读安装包元信息，**没有安装/升级候选包、调用付费模型、启动 bot/QQ、执行 shell agent 任务或做基准测试**。示例接口经来源核实，不是运行通过声明。
- 上游分支可能先于包发布；记录的不可变源码是复核依据。官方站点 LangGraph 文档是评估日读取的动态页面，与指定源码提交不一定同一发布版本。
- 未完成 DSH 任务级取消、发布 wheel 平台覆盖、生产隔离、权限继承及长期任务故障注入；不能把 SDK 真实存在误写成接入已经零风险。
- 没有证明 Claude SDK 能任意切换模型厂商；没有证明 OpenAI 各 provider 对全部 hosted/sandbox/stream 特性等价；没有证明 AstrBot 已满足 qbot 的持久任务保障。
- 没有进行法律意见、QQ 平台规则或账号风控审查；AGPL 与商业服务条款仅提示须审查，不作合规结论。

## 七、一手资料索引

### DeepSeek Harness

- [D1：官方 README：身份、developer preview、MIT](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/README.md)
- [D2：Python SDK：真实入口、恢复、审批、profiles、provider、通知语义](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/python/sdk/README.md)
- [D3：SDK server：初始化、归属、审批、恢复、goal 与 shutdown](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/sdk/server/README.md)
- [D4：SDK protocol：完整方法表与审批 wire contract](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/sdk/protocol/README.md)
- [D5：官方 SAFETY：未经审计与唯一安全边界警告](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/SAFETY.md)
- [D6：官方 CLI 包元信息](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/apps/cli/package.json)
- [D7：headless：CLI、JSON、恢复、退出、权限和已知限制](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/bundle/headless/README.md)
- [D8：sandbox 子系统：文件效果、平台、partial enforcement](https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/subsystems/sandbox.md)

### Claude Agent SDK

- [C1：官方 Python SDK README：工具权限、CLI、hooks、商业条款](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/README.md)
- [C2：客户端源码：interrupt 和双向客户端](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/src/claude_agent_sdk/client.py)
- [C3：选项/类型源码：resume、权限、sandbox](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/src/claude_agent_sdk/types.py)
- [C4：SDK MIT LICENSE](https://github.com/anthropics/claude-agent-sdk-python/blob/8abce1165075a20f5fe0e257b2306b4037bae37e/LICENSE)

### OpenAI Agents SDK

- [O1：官方 README：Runner 与 SandboxAgent](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/README.md)
- [O2：运行指南：入口、配置、Sessions、tracing、durable integrations](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/running_agents.md)
- [O3：HITL：RunState、安全恢复、防重放与外部副作用幂等](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/human_in_the_loop.md)
- [O4：sandbox clients：UnixLocal 限制、Docker 与网络](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/sandbox/clients.md)
- [O5：MIT LICENSE](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/LICENSE)
- [O6：流式结果源码：cancel 的真实语义](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/src/agents/result.py#L941-L965)

### LangGraph

- [L1：官方 README：低层编排定位、可独立使用、产品分层](https://github.com/langchain-ai/langgraph/blob/3c916d750575b22c464790e9774494d810ccd322/README.md)
- [L2：官方 persistence 文档](https://docs.langchain.com/oss/python/langgraph/persistence)
- [L3：官方 interrupts 文档：恢复与重执行规则](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [L4：MIT LICENSE](https://github.com/langchain-ai/langgraph/blob/3c916d750575b22c464790e9774494d810ccd322/LICENSE)

### AstrBot

- [A1：官方 README：QQ、OneBot、多通道与 Agent 能力](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/README.md)
- [A2：官方 Agent Sandbox 文档：本机/第三方与权限/平台限制](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/docs/zh/use/astrbot-agent-sandbox.md)
- [A3：AGPL LICENSE](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/LICENSE)
- [A4：Agent Runner 概念与执行循环](https://github.com/AstrBotDevs/AstrBot/blob/6c942855cb06b6d43854e8b841859d60a5c6043e/docs/zh/use/agent-runner.md)
