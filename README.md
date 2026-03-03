# MoneyRobot (Feishu 投研机器人)

可对接飞书应用机器人，支持：

- 飞书消息对话
- 定时推送（组合收益 + 热点 + AI分析）
- 工作日 09:30、14:30 热点摘要推送
- 工作日每 5 分钟自选异动告警（单次变化阈值默认 2%）
- 股票盯盘（实时行情）
- 单只股票/基金查询 + AI分析
- 热点获取与 AI 解读
- 基金推荐与定投计划
- 自选管理
- 模拟买卖与收益跟踪

## 1. 安装

```bash
pip install -r requirements.txt
```

复制配置文件并填写：

```bash
cp .env.example .env
```

必须配置：

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_VERIFICATION_TOKEN`（飞书事件订阅里的 verification token）

可选配置：

- `AI_PROVIDER` / `AI_PROVIDERS`（AI提供商列表与默认provider）
- `DEEPSEEK_*`（你当前用这个）
- `OPENAI_*`、`QWEN_*`（后续可开）
- `FEISHU_DEFAULT_OPEN_ID` 或 `FEISHU_DEFAULT_CHAT_ID`（用于主动推送）
- `REPORT_CRON`（可选，配置后额外开启日报任务）
- `HOT_PUSH_TIMES`（默认 `09:30,14:30`）
- `PRICE_ALERT_CRON`（默认 `*/5 * * * 1-5`）
- `PRICE_ALERT_THRESHOLD_PCT`（默认 `2`）

## 2. 飞书后台配置

1. 创建企业自建应用并启用机器人能力。  
2. 事件订阅中添加请求地址：`https://你的域名/feishu/events`。  
如果先用你的公网IP联调（`8.130.50.145`），可先用：`http://8.130.50.145:8000/feishu/events`。  
生产建议务必配 HTTPS（可用 Nginx + 证书，再反代到 8000 端口）。  
3. 订阅事件：`im.message.receive_v1`。  
4. 给应用开通接口权限：消息发送相关权限（`im:message` 相关）。  
5. 将应用发布到企业并对目标用户可用。  

## 3. 启动

```bash
python run.py
```

健康检查：

```bash
GET /health
```

手动触发推送（可用于联调）：

```bash
POST /admin/push
```

## 4. 飞书命令

- `help`
- `quote 600519`
- `fund 161725`
- `analyze stock 600519`
- `analyze fund 161725`
- `hot`
- `ai list`
- `ai use deepseek`
- `funds 5`
- `plan 12000 12`
- `add stock 600519 贵州茅台`
- `add fund 161725 招商中证白酒`
- `watch`
- `buy stock 600519 100 1500 5`
- `sell stock 600519 50 1600 5`
- `portfolio`

## 5. 数据来源与说明

- 股票行情：东方财富公开行情接口
- 基金估值：天天基金估值接口
- 热点：优先 `akshare` 热榜，失败回退到板块热度
- AI：OpenAI 兼容协议（默认 DeepSeek，可扩展 OpenAI/Qwen）

## 6. 需要的 API 清单

- 飞书开放平台
- `tenant_access_token` 获取
- `im/v1/messages` 发送消息
- `im/v1/messages/{message_id}/reply` 回复消息
- 事件订阅：`im.message.receive_v1`

- 行情/热点数据
- 东方财富股票行情接口（公开）
- 天天基金估值接口（公开）
- akshare 热门榜（可选增强）

- AI 推理
- DeepSeek Chat Completions（当前）
- 其他 OpenAI 兼容接口（后续可增删）

## 7. 数据库说明

- 当前使用 `SQLite`（文件：`money_robot.db`）
- 原因：单机部署简单、零运维、足够支撑你当前机器人场景
- 如果后续多实例或并发提升，建议迁移到 `MySQL` 或 `PostgreSQL`

本项目仅用于研究与模拟，不构成投资建议。
