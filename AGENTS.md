# AGENTS.md

## 目标
本项目用于 `NoneBot2 + OneBot v11 + NapCat` 联动。
当前实践采用：**NapCat 反向 WebSocket 连接 bot**（bot 监听 `127.0.0.1:8090`）。

## 启动顺序（已验证）
1. 先启动 NapCat（前台看日志）
2. 再启动 bot

命令：
```bash
/home/djj/stop_napcat.sh
/home/djj/start_napcat_env.sh

cd /home/djj/code/assignment/qbot
source .venv/bin/activate
python bot.py
```

## NapCat 配置（反向 WS）
配置文件：`/home/djj/napcat/config/onebot11.json`

关键项：
- `websocketClients[0].enable = true`
- `websocketClients[0].url = "ws://127.0.0.1:8090/onebot/v11/ws"`
- `websocketClients[0].reportSelfMessage = true`（需要 bot 接收自己发送的命令时必须开启）
- `websocketClients[0].token` 与 `.env` 中 `ONEBOT_V11_ACCESS_TOKEN` 保持一致

## bot 配置（反向 WS）
`.env` 使用反向模式：
```env
DRIVER=~fastapi
HOST=127.0.0.1
PORT=8090
ONEBOT_V11_ACCESS_TOKEN=
QBOT_ENABLED_GROUPS=1084141833
```

不要在反向模式下设置 `ONEBOT_V11_WS_URLS`（那是正向 WS 方案）。

## 日志判断标准
### 连接成功
- bot 日志出现：`OneBot V11 <self_id> | ... message.group...`
- NapCat 日志不再持续输出 `WebSocket Client 在 5 秒后尝试重新连接`

### 典型问题
- `address already in use`：端口占用
- `Connection refused`：目标端口无人监听或 URL 错误
- 能收到他人消息但自己发 `/rank` 无响应：`reportSelfMessage=false`

## 端口占用排查与释放
查占用：
```bash
ss -lntp | grep ':8090'
```

释放（替换 PID）：
```bash
kill <PID>
# 不行再强制
kill -9 <PID>
```

自动释放 8090：
```bash
kill $(ss -lntp | awk '/:8090/ {print $NF}' | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' | head -n1)
```

## 无图形服务器运行要点
- QQ/NapCat 需要图形环境登录，远程环境使用 `Xvfb + x11vnc`
- VNC 连接成功后完成扫码登录
- NapCat 前台启动可直接观察实时日志（便于排障）

## 版本经验（重要）
- 虽然 NapCat 为最新 release，也可能与当前 Linux QQ 版本存在兼容差异
- 遇到“进程在跑但 OneBot 不连/行为异常”时，优先检查：
  1. 是否已登录
  2. OneBot 配置是否生效
  3. NapCat 与 QQ 版本兼容情况

## 快速自检清单
```bash
# 1) bot 是否监听
ss -lntp | grep 8090

# 2) NapCat 是否已连接 bot
ss -tnp | grep 8090

# 3) QQ/NapCat 进程
ps -ef | grep -E 'qq --no-sandbox|python bot.py' | grep -v grep

# 4) 看 bot 日志是否收到群消息
# (按你的日志文件路径查看)
```
