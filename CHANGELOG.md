# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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
