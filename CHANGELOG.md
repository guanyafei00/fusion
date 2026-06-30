# Changelog

All notable changes to this project will be documented in this file.

## [v1.1.0] - 2026-06-30

### Added — Auto Model Quality Probe (模型质量自动检测)

- **`fusion/probe.py`** — 全新模块，每次运行fusion时自动探测API可用模型质量：
  - 从API网关拉取模型列表
  - 过滤非聊天模型（embed/vision/tts/image等）
  - 并发探测每个候选模型：发送简单测试问题，测量响应延迟+回答质量
  - 按 **质量(是否正常回答) × 速度(延迟)** 排名
  - 自动选出最优N个**不同家族**模型做panel（避免3个同一家族模型联hallucination）
  - Judge和Synth也同步更新为探测最优模型
  - 全部不可用时自动回退到预设fallback模型列表
- **`fusion/config.py`** — 新增环境变量：
  - `FUSION_AUTO_PROBE` (默认true): 是否启动时自动探测模型质量
  - `FUSION_PROBE_PANEL_SIZE` (默认3): 探测选出几个panel模型
- **`fusion/cli.py`** — 新增 `--no-probe` 选项：手动跳过探测，用环境变量指定的模型直接跑
- **Pipeline Step 0** — `run()` 新增 `auto_probe` 参数，探测→替换模型→再跑原有Fetch→Panel→Judge→Synth

### Fixed

- 修复硬编码内网IP和密钥文件路径的问题，所有脚本改为从 `fusion.env` 加载环境变量
- `.gitignore` 添加 `fusion.env`，防止密钥泄露

## [v1.0.0] - 2026-06-28

### Added

- Panel→Judge→Synth 三阶段多模型防幻觉共识管线
- SSRF 防护（自动拦截内网/localhost/链路本地URL）
- 令牌桶限流器（rpm_limit可配置）
- 6种URL抓取策略（httpx/浏览器/Reddit/HackerNews/Twitter/通用）
- OpenRouter 和 硅基流动 两个预设presets
- 可选认证（FUSION_AUTH_TOKEN）
- Dockerfile + docker-compose.yml
- 稳定性测试（--stability N 多轮输出一致性检验）
