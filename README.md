# qbot

QQ群分数统计机器人（NoneBot2 + NapCat + OneBot v11）。

## 功能

- 解析群成员名片中的 `分数-名字` / `分数—名字`
- 仅统计 350~500 分
- 按 5 分一档
- 统计上限：`min(500, 最高分 + 5)`
- 支持手动命令 `/stat`
- 每 20 分钟自动统计
- 发送：摘要 + 2 张图（当前分布柱状图、历史趋势图）

## 快速开始

1. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

2. 配置环境变量（可参考 `.env.example`）

3. 启动 NapCat 并配置 OneBot 正向 WS（让 NoneBot 主动连接）

4. 运行机器人

```bash
python bot.py
```

## 环境变量

- `ONEBOT_V11_WS_URLS`（JSON 列表格式，例如 `["ws://127.0.0.1:3001/onebot/v11/ws/"]`）
- `ONEBOT_V11_ACCESS_TOKEN`（可选）
- `QBOT_ENABLED_GROUPS`，如 `123456,789012`
- `QBOT_DB_PATH`（默认 `data/qbot.sqlite3`）
- `QBOT_HISTORY_WINDOW_HOURS`（默认 `24`）
- `QBOT_RETENTION_DAYS`（默认 `30`）
- `QBOT_FONT_PATH`（可选，解决中文字体问题）

## 命令

- `/h`：查看全部命令
- `/stat`：立即统计当前群
- `/stat help`：查看统计规则
- `/rank`：查询个人排名
- `/rank help`：查看个人排名规则
- `/rank-comp`：查询跨群排名（浙计按浙软同分换算）
- `/rank-comp help`：查看跨群排名规则
- `/set`：检测浙软与浙计考生 QQ 重合
- `/set help`：查看重合检测规则
