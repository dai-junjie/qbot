# qbot 从分数统计迁移为执行型 Agent：仓库与安全边界审计

## 1. 范围、基线与结论

- 审计日期：2026-11-03。精确仓库基线：`dfd441ffe8ce70111831d43db39b2e0a7dd490c3`；开始审计时工作树干净。
- 本篇属于仅文档调研，不启动 QQ/NapCat/bot，不连接生产，不读取应用实际环境文件、数据库或凭据。运行时选型见[运行时研究](<agent-runtime-options.md>)，整体建议见[总报告](<qbot-agent-feasibility.md>)。
- **结论：可以复用 QQ 消息接入，但不能把现有统计 handler 换成“调用模型并执行命令”。** 当前是白名单群内任意成员可调用的短事务统计器，不是带用户隔离、持久任务、审批和执行沙箱的控制平面。[入口](<../../src/qbot/plugin.py#L119-L120>)、[群过滤](<../../src/qbot/plugin.py#L198-L229>)。
- 推荐首期：一个试验群、固定 QQ 身份 allowlist、显式命令、独立持久任务库、每任务隔离工作区；只开放经授权仓库的只读研究和结构化状态控制。执行能力后置，先在无生产凭据的独立 worker 中开放有限文件修改/测试；不开放宿主任意 shell、部署、自动提交、跨群广播或账号管理。

## 2. 仓库实际结构：复用与退出边界

| 层 | 当前事实与证据 | 迁移处置 |
| --- | --- | --- |
| 启动 | [bot.py](<../../bot.py#L1-L12>) 初始化 NoneBot，注册 OneBot v11，加载插件 | 保留框架/适配器；Agent 与统计插件分离 |
| 消息/发送 | [plugin.py](<../../src/qbot/plugin.py#L198-L249>) 读群消息纯文本；[回复](<../../src/qbot/plugin.py#L280-L283>)；[图片](<../../src/qbot/plugin.py#L56-L59>) 读本地 bytes 发 base64 | 提取窄消息接口，模型不能获得 Bot、任意 call_api 或任意文件路径 |
| 群过滤 | [config.py](<../../src/qbot/config.py#L10-L37>) 群列表默认空；[过滤](<../../src/qbot/plugin.py#L62-L63>) 只查群号 | 保留默认拒绝，增加用户、所有者、工具/仓库权限；群准入不是执行授权 |
| 命令 | [解析器](<../../src/qbot/plugin.py#L252-L277>) NFKC、去不可见字符、接受无斜杠命令 | 新入口要求显式 `/agent ...`，避免普通聊天误触 |
| 调度/并发 | [锁](<../../src/qbot/plugin.py#L44-L53>) 是进程内按群锁；[cron](<../../src/qbot/plugin.py#L168-L195>) 北京时间 08:00—22:00 每两小时、选第一个在线 bot；[冷却](<../../src/qbot/plugin.py#L349-L358>) 仅统计触发 8 秒 | 都不是持久任务队列；旧 cron 默认停用，不能让它自动启动 Agent |
| 编排/采集 | [service.py](<../../src/qbot/service.py#L116-L193>) 拉全量群成员、解析、写快照、清理、绘图；[collector.py](<../../src/qbot/collector.py#L9-L13>) 包装群成员接口 | 属于旧业务，不进入 Agent 默认工具；身份查询另做最小接口，错误不能当空名单忽略 |
| 算法/模型 | [parser.py](<../../src/qbot/parser.py>)、[bucketizer.py](<../../src/qbot/bucketizer.py>)、[ranker.py](<../../src/qbot/ranker.py>)、[analyzer.py](<../../src/qbot/analyzer.py>)、[models.py](<../../src/qbot/models.py>) 都是统计；[setops.py](<../../src/qbot/setops.py#L60-L84>) 输出跨群成员资料 | 保留历史代码/测试用于回滚，不作为模型上下文或默认工具 |
| 存储 | [repository.py](<../../src/qbot/repository.py#L15-L54>) 只有统计快照、桶、命令日志 | 可借鉴参数化 SQL/UTC；不能充当任务/审批账本 |
| 产物 | [service.py](<../../src/qbot/service.py#L180-L193>) 相对目录写按群图表；[plotter.py](<../../src/qbot/plotter.py#L1-L25>) 用全局 Matplotlib 状态 | 退出关键链路；新产物按租户/任务/attempt 隔离、限额、鉴权 |

### 2.1 当前重试不可迁移为执行重试

[统计重试](<../../src/qbot/plugin.py#L72-L116>) 对整个 run_once 最多执行三次；[service.py](<../../src/qbot/service.py#L144-L152>) 先写快照再清理/绘图，绘图失败重试可重复插入。摘要成功但图片失败仍可返回成功。这不提供工具 exactly-once、重启恢复或成功回执语义，禁止直接复制该循环包 shell/提交/部署。

### 2.2 测试资产与缺口

发现 25 个测试函数，覆盖分数解析、分桶、摘要、跨群集合、排名/追分、环境群名单、命令计数：[解析](<../../tests/test_parser.py>)、[分桶](<../../tests/test_bucketizer.py>)、[摘要](<../../tests/test_analyzer.py>)、[集合](<../../tests/test_setops.py>)、[排名](<../../tests/test_service_rank.py>)、[环境](<../../tests/test_env_and_log_match.py>)、[仓储](<../../tests/test_repository_command_usage.py>)。“模拟日志匹配白名单”只测试正则/设置，不是 handler 授权测试；仓储只测计数。未发现 OneBot/NapCat 联调、自消息、持久任务、取消、附件或沙箱测试。

## 3. 依赖、配置、部署假设

1. [pyproject.toml](<../../pyproject.toml#L6-L21>) 为开放依赖下限，无锁文件。迁移前需精确版本清单和可复现依赖集，不能把本次上游源码等同部署版本。
2. 声明 Python >=3.10，但 [repository.py](<../../src/qbot/repository.py#L3>)、[service.py](<../../src/qbot/service.py#L4>) 使用 Python 3.11 才有的 datetime.UTC。另 [config.py](<../../src/qbot/config.py#L7>) 使用 NoDecode，须核实 pydantic-settings 实际最低版本兼容性。
3. [AGENTS.md](<../../AGENTS.md#L3-L40>)、[.env.example](<../../.env.example#L1-L9>) 为反向 WS、loopback 监听；[README.md](<../../README.md#L11-L38>) 仍写正向 WS、20 分钟、两张图，与实际 cron/单张 dashboard 不符。部署以实际版本/配置验收，不按旧说明猜测。
4. [start.sh](<../../start.sh#L1-L2>) 先 bot 后 NapCat，与 [AGENTS.md](<../../AGENTS.md#L7-L9>) 顺序相反；无 supervisor、单实例保证、任务 drain 或重启恢复契约。研究中不执行该脚本。
5. [.env.example](<../../.env.example#L8-L9>) 的 token 可选/空值不能用于执行型 Agent。loopback 不抵御同机进程，不等于跨容器隔离；跨主机需 TLS/ACL，不将 WS/WebUI/VNC 暴露公网。
6. [AGENTS.md](<../../AGENTS.md#L70-L80>) 记录图形登录和版本兼容依赖，本次未验证机器配置。worker 不得访问 QQ 登录态、显示服务、桌面控制和 NapCat 管理凭据。

## 4. 官方一手证据

一手证据来自官方仓库，调研时上游基线：NoneBot2 `8ea99f1849466e0ac8085deb045a0f198b9ed1d0`；adapter-onebot `2f5930d4f6c7fb3a82cf3201639e8f0b0a6c124e`；OneBot v11 `d4456ee706f9ada9c2dfde56a2bcfc69752600e4`；NapCatQQ `98d781d19815d1625b24d717ce280ecf0a4f6d0c`。不代表生产安装版本。

- **NoneBot Permission 是事件筛选，不是工具沙箱。** [官方权限文档](https://github.com/nonebot/nonebot2/blob/8ea99f1849466e0ac8085deb045a0f198b9ed1d0/website/docs/appendices/permission.mdx) 说明：检查先于 Rule，多个 checker 任一通过即放行；连续会话 Permission 持续检查而 Rule 只初次检查。群、用户、工具授权须按 AND 明确组合，不可误用 `Permission(a) | Permission(b)` 扩权；执行前仍须重新授权。
- **会话互斥不是持久任务。** [single_session](https://github.com/nonebot/nonebot2/blob/8ea99f1849466e0ac8085deb045a0f198b9ed1d0/nonebot/plugins/single_session.py) 用进程内字典，不提供重启恢复/分布式租约。
- **群角色是尽力提供的缓存信息。** [群消息规范](https://github.com/botuniverse/onebot-11/blob/d4456ee706f9ada9c2dfde56a2bcfc69752600e4/event/message.md) 定义 self_id/group_id/user_id/message_id 和 sender.role，但明确 sender 可缺失/过期、匿名消息尤其不可参考；[适配器权限源码](https://github.com/nonebot/adapter-onebot/blob/2f5930d4f6c7fb3a82cf3201639e8f0b0a6c124e/nonebot/adapters/onebot/v11/permission.py) 直接比较 role。群主/管理员不是宿主执行授权。
- **反向 WS 认证不是群用户授权。** [鉴权](https://github.com/botuniverse/onebot-11/blob/d4456ee706f9ada9c2dfde56a2bcfc69752600e4/communication/authorization.md) 用 bearer token 建连；[反向 WS](https://github.com/botuniverse/onebot-11/blob/d4456ee706f9ada9c2dfde56a2bcfc69752600e4/communication/ws-reverse.md) 定义重连/X-Self-ID，但不提供应用任务持久重放、用户签名或恰好一次执行契约。
- **仅配 WS token 不保护所有路由。** [adapter.py](https://github.com/nonebot/adapter-onebot/blob/2f5930d4f6c7fb3a82cf3201639e8f0b0a6c124e/nonebot/adapters/onebot/v11/adapter.py) 在 ASGI 注册 HTTP POST 和 WS；WS 仅在非空 token 时校验，HTTP 使用独立 onebot_secret 签名且仅在非空 secret 时校验。关闭不需要的 HTTP 上报路径，或配置独立强签名并测试，网络入口默认拒绝；还须对实际版本回归。
- **NapCat 自发事件/重连可配置，不是任务恢复。** [配置源码](https://github.com/NapNeko/NapCatQQ/blob/98d781d19815d1625b24d717ce280ecf0a4f6d0c/packages/napcat-onebot/config/config.ts) 中 WS client 默认 reportSelfMessage=false、重连 5000ms、空 token，位于 network.websocketClients，旧手册字段不能直接套新版。[WS client](https://github.com/NapNeko/NapCatQQ/blob/98d781d19815d1625b24d717ce280ecf0a4f6d0c/packages/napcat-onebot/network/websocket-client.ts) 发 bearer、重连，onEvent 只在 OPEN 时发送，不能承诺离线重放。
- **消息段跨文件/网络边界。** [消息段规范](https://github.com/botuniverse/onebot-11/blob/d4456ee706f9ada9c2dfde56a2bcfc69752600e4/message/segment.md) 的媒体支持 URL/file URI/base64；合并转发可自定义 user_id/nickname。这些身份和路径不是授权来源，模型输出不能直接作 CQ/消息段。
- [NapCat SECURITY.md](https://github.com/NapNeko/NapCatQQ/blob/98d781d19815d1625b24d717ce280ecf0a4f6d0c/SECURITY.md) 只给支持版本/漏洞报告方式，不是执行沙箱或安全认证。

## 5. 最小安全迁移设计（非现有能力）

### 5.1 群内多用户与薄入口

采用 `QQ event → ingress/policy → durable task service → isolated worker → controlled outbound`。handler 只校验、去重、落库、短回执，不等待整次执行。

- 默认拒绝未知 bot、群、用户、匿名、私聊/临时会话、未知 post_type；身份来自已认证接入事件，不取模型、昵称或转发作者。拒绝 message_sent 和 user_id==self_id；现有 [自发 handler](<../../src/qbot/plugin.py#L454-L495>) 不进入 Agent 通路。
- principal 至少 `(adapter,self_id,group_id,user_id)`，上下文再加 task_id。同群不自动共享运行时历史、工作区、受限文件和控制权；首期个人任务，协作需显式参与者/可见性。**群消息中的输入、回执和交付对群成员可见，运行时隔离不等于群消息保密。首期不接机密任务；以后如支持私有产物，群里只发脱敏状态，产物走独立身份鉴权的私有渠道。**
- 授权用户创建/查自己的任务；所有者取消/重试/补充输入；审核者只获得明确审批职责；受信运维可紧急停机但不自动继承所有数据。群角色仅附加信号，不替代可信 QQ allowlist。
- 引用回执只定位候选任务，须重新查所有者/群/状态。换群、转发、猜 task_id 不得接管其他成员任务。
- 入站唯一键含 bot/group/message_id/post_type，并保留去重记录；处理 ID 复用和冲突，不能假定跨账号全局唯一。重复事件不得重复建任务。

### 5.2 持久任务、重启、取消、重试

独立任务库记录任务/租户/所有者、触发事件、允许仓库、状态版本、attempt/父任务、权限快照、审批、预算、worker 租约/心跳、步骤事件、产物和发送 outbox；不存整群聊天。

状态建议 queued → running → waiting_approval/needs_input → succeeded/failed/cancelled，补 cancel_requested、interrupted/unknown；事务/CAS 解决竞争，每步有 operation ID 和副作用类别。

- 重启后租约失效的 running 转 interrupted；纯读/可证明幂等才自动恢复。写成功但回执丢失为 unknown，不盲目重跑。
- 取消需复核身份、持久化请求、废止待审批、阻断后续工具、终止 worker 整个进程树/隔离单元，先优雅停止后限时强制回收。取消不是撤销既成副作用。
- 重试建新 attempt、留旧审计、重验权限/审批；外部写默认不自动重试。模型结束、退出码、工具成功、群消息送达是不同事实。
- outbox 将执行和发送解耦，限频/分片/脱敏；发送超时不能重跑任务，回执不确定允许可识别重复通知但不能重复执行。
- 按任务/仓库锁、按用户/群配额、全局 worker 并发、时间/token/输出/磁盘预算；多进程用持久租约而非 asyncio.Lock。

### 5.3 工具与审批

模型仅提出结构化调用，服务器 policy 决定允许/拒绝/审批；每次查 principal、仓库/路径、参数、预算、有效授权。不能靠提示词保证安全。

首期只读授权仓库/状态；后续只在独立副本编辑/测试。禁宿主环境文件、旧 DB、QQ 登录态、SSH/云凭据、容器管理 socket、任意网络及任意 OneBot API。shell 不可靠黑名单防护；测试脚本/构建钩子同样会执行代码，需非特权 worker、最小挂载、无宿主凭据、默认断网、进程/资源限额。

外发、push、部署、删除、依赖安装、联网、新工具分别授权，首期禁用。审批绑定准确参数/diff 或输入 hash、task/attempt、审批人、过期时间；改参数、重试、撤权则失效。模型不能自批，群里孤立的“同意”不算审批。

### 5.4 提示注入、自消息环、出站

群消息、引用/转发、仓库说明、网页、附件和工具输出都是不可信数据，不能修改系统策略或工具权限；“忽略上文/替管理员同意/发凭据”无控制效力。只取任务明确授权材料，不默认把整群聊天送模型，并说明第三方模型数据流。

输出按纯文本发送，禁止动态 CQ、@all、任意路径/URL 图片段。产物只通过经鉴权 artifact ID 发出；记录 bot-origin 消息 ID，入口仍独立拒绝自发，即使输出含 `/agent run ...` 也不触发。限流只是兜底。

### 5.5 附件/数据隔离

首期禁附件和自动下载。后续主动授权后下载至当前任务隔离区，绑定来源/所有者、大小/数量/MIME/hash；服务端生成文件名，检查规范化路径、symlink、归档穿越/炸弹。不自动执行宏/脚本，解析器也限资源。

下载器隔离于 QQ/worker；拒 file URI、loopback/内网/链路本地/元数据地址和非 HTTP(S)，每次重定向/DNS 复核，设超时/大小上限，不把 NapCat 返回的本机路径直接交 worker。artifact 访问/转发复核任务权限，不能仅靠难猜 URL。

## 6. 旧数据库、保留与回退

[存储](<../../src/qbot/repository.py#L20-L51>) 的快照/桶为聚合，但命令日志含用户/群 ID、动作和时间，仍属用户相关数据。[cleanup_old](<../../src/qbot/repository.py#L131-L151>) 删三类记录，只由成功进入采集的 [run_once](<../../src/qbot/service.py#L144-L152>) 调用；停统计后不再自动清理，图表也不在该清理范围。

新旧库物理分离；先备份验证恢复，旧库只读、受信运维可访问，Agent 不挂载、不索引、不作记忆。明确旧图表、日志、备份的保留/销毁政策；独立维护流程执行，不复制旧 cleanup 到任务库误删未完成任务审计。正文、审批、工具日志、产物分别设保留策略。

灰度前保留旧配置/发布包，插件互斥开关，先影子接入无执行再小群授权。回退先停新任务/撤权，drain 或标 interrupted，再恢复旧统计；不用杀端口代替任务取消，不清旧库、不用新库覆盖旧库。

## 7. 必须实现的威胁测试（尚未通过）

| 场景 | 验收结果 |
| --- | --- |
| 空/错 token、假 self_id、未授权群/用户、匿名/私聊、无签名 HTTP POST | 模型/工具前拒绝，其他注册路由无旁路 |
| B 引用 A 回执/猜 task_id，A 换群补充 | 不能读/取消/重试/审批/污染 A 任务 |
| role 缺失/过期、未授权管理员、运行中撤权 | 高权限默认拒绝，每步重验 |
| 重复事件、message+message_sent、重连上报 | 最多一任务，自发消息绝不建任务 |
| 输出命令/CQ/@all，转发伪造管理员同意 | 普通文本/材料，不执行扩权 |
| kill worker、重启、租约失效、写成功回执丢失 | interrupted/unknown，不盲目重放副作用 |
| 改参数/重放/跨任务/跨 attempt 使用审批 | 无效，要求新授权 |
| cancel 与启动/完成竞争、长进程/孙进程 | 状态一致，阻后续工具，隔离单元回收 |
| 测试脚本读宿主凭据/跨任务文件/联网 | 实际策略拒绝，不靠模型自律 |
| URL 跳内网、file URI、巨量下载、穿越/symlink/炸弹 | 拒绝/受限，无目录逃逸/泄漏 |
| 仓库/附件/网页诱导读旧 DB、泄密、跨群发送 | 拒绝，无凭据日志/外发 |
| 队列淹没、超时、磁盘满、发送失败/断线 | 有预算/告警，不重复执行或全局阻塞 |

### 本次命令与证据强度

`git rev-parse HEAD` 验证基线；`git status --short` 初始为空；官方 GitHub 操作均用 `gh api`。默认 Python 3.9.6 的测试尝试因未安装 pytest 且低于项目支持版本失败，不是仓库回归证据。随后使用独立 Python 3.12.14 环境安装 `.[dev]`，执行 `python -m pytest -q`：**25 passed in 4.45s**。pytest-asyncio 提示未显式设置异步 fixture loop scope 的弃用警告，不影响本次结果；未修改配置消除该警告。该结果仅验证现有统计单元测试，不覆盖 Agent 能力、QQ 联调或线上环境。复现：在受支持的隔离 Python 环境安装 `.[dev]` 后运行 `python -m pytest -q`。

## 8. Go / No-Go

可进入离线设计/原型：保留传输栈，薄入口+持久任务+独立 worker，默认只读，明确身份/数据/预算/回执。

不可直接上线：沿用任意群成员权限、自发命令、空 token、未审计 HTTP 路由、进程内锁/整流程重试，或让模型持宿主 shell/Bot 对象。上线须完成上述跨用户、重启取消、注入附件、沙箱测试，并由人确认真实版本、账号网络边界和旧数据保留政策。
