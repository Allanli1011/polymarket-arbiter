# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed
- **cross_market 套利检测逻辑修复** (2026-02-24)
  - 修复分组逻辑：添加核心事件匹配检查（去除时间限定词后比较）
  - 修复配对逻辑：要求互补市场（Yes/No 价格之和偏离 100%）
  - 修复收益率计算：按无风险套利公式 `profit = 1 - (yes_price + no_price)` 计算
  - 解决误报问题：不再把任意两个 Yes/No 市场价格差当作套利机会

### Added
- 初始版本：Polymarket 套利监控系统
- API 客户端：支持 Gamma API 和 CLOB API
- 套利检测引擎：支持概率和异常、跨市场、价差三种检测
- 通知系统：支持 Telegram 和 Console 两种方式
- Cron 定时任务：每10分钟自动扫描

### Features
- 异步架构 (asyncio + aiohttp)
- 结构性日志 (structlog)
- 可配置阈值和过滤条件

## [0.1.0] - 2026-02-23

### Added
- `src/config.py` - 配置管理
- `src/models.py` - 数据模型
- `src/api_client.py` - Polymarket API 客户端
- `src/arbitrage_detector.py` - 套利检测引擎
- `src/notifier.py` - Telegram 通知
- `scan.py` - 主扫描脚本
- `README.md` - 项目文档
