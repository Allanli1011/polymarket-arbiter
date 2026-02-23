# Polymarket Arbitrage Monitor

Polymarket 预测市场套利机会监控系统。

## 目标

自动扫描 Polymarket 高流动性市场，检测套利机会并推送通知。

## 技术栈

- Python 3.14 (asyncio)
- aiohttp (异步 HTTP)
- structlog (日志)
- Cron (定时任务)

## 项目结构

```
polymarket-arbiter/
├── src/
│   ├── config.py        # 配置
│   ├── models.py        # 数据模型
│   ├── api_client.py    # Polymarket API
│   ├── arbitrage_detector.py  # 套利检测
│   └── notifier.py     # Telegram 通知
├── scan.py              # 主扫描脚本
├── requirements.txt     # 依赖
└── venv/               # 虚拟环境
```

## 使用方法

### 安装依赖

```bash
cd projects/polymarket-arbiter
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 手动扫描

```bash
source venv/bin/activate
python3 scan.py
```

### 配置 Telegram 通知（可选）

```bash
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"
```

## 套利检测类型

1. **概率和异常** - outcomes 概率和 ≠ 1.0
2. **跨市场** - 同一事件在不同市场
3. **价差套利** - 宽买卖价差

## Cron 任务

- 任务名: `polymarket-scan`
- 频率: 每 10 分钟
- 目标群: `-5165526014`

## API

- Gamma API: `https://gamma-api.polymarket.com`
- CLOB API: `https://clob.polymarket.com`
