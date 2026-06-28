# Fusion

**多模型共识管线（Multi-model Consensus Pipeline）** — Panel→Judge→Synth 三阶段对抗幻觉架构

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://opensource.org/licenses/MIT)

---

## 问题是什么？

大模型（LLM）有个致命缺陷：**自信地编造**。它给你一个看起来很靠谱的答案，但你完全无法分辨真假。

单模型多次采样？没用——同一个模型的系统性偏差无法自我纠正。问5次同一个模型，错的地方5次都错。

**Fusion 的解法**：让3个**不同厂商**的模型独立回答，再用一个独立模型评审，最后综合输出。不同厂商的模型犯的错不一样——交叉验证就能筛掉大部分幻觉。

---

## 架构

```
你的问题 + 参考URL（可选）
        │
        ▼
  ┌──────────┐
  │  Fetch    │  抓取参考页面内容（6种策略 + 降级链）
  └──────────┘
        │
        ▼
  ┌──────────┐
  │  Panel    │  3个不同厂商的模型并行独立回答
  │           │  例：Qwen + Gemma + Minimax
  └──────────┘
        │
        ▼
  ┌──────────┐
  │  Judge    │  第4个独立模型评审所有回答
  │           │  输出：每条回答的评分 + 理由（JSON）
  └──────────┘
        │
        ▼
  ┌──────────┐
  │  Synth    │  综合所有来源 + 评审结果
  │           │  输出：最终答案（标注来源）
  └──────────┘
```

**为什么是3+1+1？**
- Panel 用3个**不同厂商**模型：同一厂商的不同模型共享训练数据，偏差相同
- Judge 用独立模型：不能让Panel模型自己评自己（"自审"会偏袒）
- Synth 用另一个独立模型：综合时避免偏见

---

## 安装

### 前置条件

- Python 3.10 或更高版本
- pip（Python 包管理器）
- 一个 OpenAI 兼容的 API 服务（见下方支持的提供商）

### 基础安装

```bash
git clone https://github.com/guanyafei00/fusion.git
cd fusion
pip install .
```

### 包含所有抓取能力

```bash
pip install ".[all]"
```

这会安装 Crawl4AI、Playwright、yt-dlp、DuckDuckGo 搜索等全部可选依赖。

### 仅安装特定能力

```bash
pip install ".[yt]"          # 仅 YouTube 字幕抓取
pip install ".[crawl4ai]"    # 仅 Crawl4AI 抓取
pip install ".[playwright]"  # 仅 Playwright 抓取
pip install ".[ddg]"         # 仅 DuckDuckGo 搜索
```

---

## 快速开始

### 1. 设置 API 密钥

```bash
# 方法一：环境变量（推荐）
export FUSION_LLM_BASE_URL=https://openrouter.ai/api/v1
export FUSION_LLM_API_KEY=sk-or-vv-xxxxx

# 方法二：.env 文件（在项目目录下创建 .env）
cat > .env << 'EOF'
FUSION_LLM_BASE_URL=https://openrouter.ai/api/v1
FUSION_LLM_API_KEY=sk-or-vv-xxxxx
EOF
```

### 2. 运行

```bash
# 最简单：纯问题
fusion "量子计算2024年有哪些突破性进展？"

# 带参考来源
fusion "这篇论文的核心贡献是什么？" -u https://arxiv.org/abs/2401.12345

# 多个参考来源
fusion "对比这些文章的观点" -u https://a.com -u https://b.com

# 稳定性测试（跑3轮，对比结果一致性）
fusion "对比React和Vue" --stability 3

# 显示中间步骤（Panel/Judge的详细输出）
fusion "为什么GPU比CPU快？" --verbose
```

### 3. 输出格式

最终输出为 Markdown 格式，包含：
- **综合答案**：综合所有模型回答的最终结论
- **来源标注**：每个关键结论标注来源模型/文献
- **评审摘要**：Judge对各模型回答的评分和理由

运行 `--verbose` 还会额外输出：
- 每个Panel模型的独立回答
- Judge的完整评审JSON（评分 + 理由）

---

## CLI 完整参数

```
fusion [OPTIONS] QUERY

QUERY                    要回答的问题

选项：
  -u, --url TEXT         参考URL（可多次指定）
  -s, --stability INT    稳定性测试轮数（默认: 1）
  --panel-models TEXT    Panel模型ID，逗号分隔
  --judge-model TEXT     Judge模型ID
  --synth-model TEXT     Synth模型ID
  --preset TEXT          API提供商预设（openrouter / siliconflow）
  --api-key TEXT         API密钥（或设置 FUSION_LLM_API_KEY）
  -v, --verbose          显示中间步骤详情
  --help                 显示帮助信息
```

---

## 支持的 API 提供商

### OpenRouter（推荐起步）

[OpenRouter](https://openrouter.ai/) 聚合了数百个模型，一个 API Key 就能调用所有主流模型。

```bash
export FUSION_LLM_BASE_URL=https://openrouter.ai/api/v1
export FUSION_LLM_API_KEY=sk-or-vv-xxxxx

# 或使用预设
fusion "问题" --preset openrouter --api-key sk-or-vv-xxxxx
```

### 硅基流动（SiliconFlow）

国内用户推荐，访问速度快、价格低。

```bash
export FUSION_LLM_BASE_URL=https://api.siliconflow.cn/v1
export FUSION_LLM_API_KEY=sk-xxxxx

# 或使用预设
fusion "问题" --preset siliconflow --api-key sk-xxxxx
```

### 自建网关

任何 OpenAI 兼容的 API 网关都可以用，比如 CliProxyAPI、One API 等。

```bash
export FUSION_LLM_BASE_URL=http://your-gateway:8317/v1
export FUSION_LLM_API_KEY=your-key

fusion "问题" --panel-models qwen3-80b,gemma3-27b,minimax-m2.5 \
              --judge-model gpt-oss-120b \
              --synth-model deepseek-v4-pro
```

---

## 模型选择指南

Fusion 有三个阶段，每个阶段对模型的要求不同：

### Panel（独立回答）

- **要求**：3个模型必须来自**不同厂商**，避免同源偏差
- **推荐**：1个中文强模型 + 1个英文强模型 + 1个中立模型
- **示例**：`qwen3-next-80b,gemma3-27b,minimax-m2.5`
- **为什么**：Qwen中文好、Gemma英文好、Minimax中立不偏

### Judge（评审）

- **要求**：必须与Panel模型不同厂商
- **推荐**：推理能力强、能输出结构化JSON的模型
- **示例**：`gpt-oss-120b` 或 `deepseek-v4-pro`
- **为什么**：评审需要理解多个回答的差异，推理能力比知识面更重要

### Synth（综合）

- **要求**：必须与Panel/Judge不同厂商
- **推荐**：写作能力好、能综合多种信息源的模型
- **示例**：`deepseek-v4-pro` 或 `qwen3-coder-480b`
- **为什么**：综合需要权衡不同来源的信息，写出有依据的结论

> **核心原则**：4个模型（3 Panel + 1 Judge）+ 1 Synth = 5个插槽，尽量覆盖5个不同厂商。厂商越多，交叉验证效果越好。

---

## 环境变量

| 变量 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `FUSION_LLM_BASE_URL` | ✅ | — | OpenAI兼容API地址 |
| `FUSION_LLM_API_KEY` | ✅ | — | API密钥 |
| `FUSION_PANEL_MODELS` | ❌ | `qwen3-next-80b-a3b-instruct,gemma-3-27b-it,minimax-m2.5` | Panel模型（逗号分隔） |
| `FUSION_JUDGE_MODEL` | ❌ | `openai/gpt-oss-120b` | 评审模型 |
| `FUSION_SYNTH_MODEL` | ❌ | `deepseek-ai/deepseek-v4-pro/flash` | 综合模型 |
| `FUSION_LLM_TIMEOUT` | ❌ | 90 | 单次LLM调用超时（秒） |
| `FUSION_RPM_LIMIT` | ❌ | 20 | 每分钟请求限制（令牌桶） |
| `FUSION_AUTH_TOKEN` | ❌ | — | 自部署认证令牌 |
| `FUSION_TAVILY_KEY` | ❌ | — | Tavily搜索API密钥 |

---

## URL 抓取支持

Fusion 自动按域名路由到最佳抓取策略，失败时逐级降级：

| 域名 | 抓取方式 | 需要安装 | 备注 |
|------|---------|---------|------|
| arxiv.org | API提取 | 无 | 直接取摘要+正文 |
| youtube.com | yt-dlp字幕 | `pip install ".[yt]"` | 自动取字幕 |
| mp.weixin.qq.com | curl + HTML解析 | 无 | 微信公众号文章 |
| github.com | curl | 无 | README + 目录树 |
| b23.tv / bilibili | curl + 重定向 | 无 | B站视频描述 |
| 其他 | Playwright → Crawl4AI → curl | `pip install ".[all]"` | 三级降级链 |

降级链：优先用 Playwright（最完整）→ 失败用 Crawl4AI → 再失败用 curl（最基础）。

---

## Docker

```bash
# 构建
docker build -t fusion .

# 运行（单次查询）
docker run --rm \
  -e FUSION_LLM_BASE_URL=https://openrouter.ai/api/v1 \
  -e FUSION_LLM_API_KEY=sk-or-vv-xxxxx \
  fusion "量子计算最新进展"

# 运行（带参考URL）
docker run --rm \
  -e FUSION_LLM_BASE_URL=https://openrouter.ai/api/v1 \
  -e FUSION_LLM_API_KEY=sk-or-vv-xxxxx \
  fusion "这篇论文讲了什么" -u https://arxiv.org/abs/2401.12345
```

---

## 安全

- **零硬编码密钥/IP** — 全部走环境变量，代码中无任何密钥或内网地址
- **SSRF 防护** — 自动拦截对内网（10.x / 172.16-31.x / 192.168.x）、localhost、链路本地地址的请求
- **速率限制** — 令牌桶算法，默认 20 RPM，防止API调用失控
- **超时保护** — 单次 LLM 调用默认 90 秒超时，防止无限等待
- **可选认证** — 设置 `FUSION_AUTH_TOKEN` 后，API 请求必须带 token

---

## 常见问题

### 429 Too Many Requests

API 限流了。降低请求频率：
```bash
export FUSION_RPM_LIMIT=10  # 降低每分钟请求限制
```

### 超时

大模型响应慢。增加超时时间：
```bash
export FUSION_LLM_TIMEOUT=180  # 3分钟
```

### 抓取失败

某些网页需要 JS 渲染。安装 Playwright：
```bash
pip install ".[playwright]"
playwright install chromium
```

### 模型不可用

确认你的 API 提供商支持你指定的模型。用 `--verbose` 查看每一步的详细输出。

### Panel 模型都返回相似答案

说明3个模型可能来自同一厂商或共享训练数据。更换为**不同厂商**的模型。

---

## 开发

```bash
# 安装开发依赖
pip install ".[dev]"

# 运行测试
pytest

# 代码结构
fusion/
├── cli.py          # 命令行入口
├── config.py       # 配置管理
├── fetchers.py     # URL 抓取（6种策略 + 降级链）
├── llm.py          # LLM 调用封装
├── pipeline.py     # Panel→Judge→Synth 管线
└── security.py     # SSRF防护 + 速率限制
```

---

## 与单模型的区别

| 对比项 | 单模型多次采样 | Fusion 多模型共识 |
|--------|---------------|-------------------|
| 系统性偏差 | 无法消除（同源） | 交叉验证筛除 |
| 幻觉检测 | 无法做到 | Judge 阶段评分筛除 |
| 准确率提升 | 边际递减 | 不同厂商越多越好 |
| API 成本 | 低 | 约单模型5倍（3 Panel + 1 Judge + 1 Synth） |
| 适用场景 | 简单问题 | 重要决策、事实核查、争议话题 |

---

## 致谢

本项目由 **guanyafei00** 提供产品思路与方向指导，**Hermes Agent** 完成全部代码编写。

初次版本由 **Qwen 3.5** 生成，后续重构与完善由 **GLM-5** 完成。

## License

MIT License

Copyright (c) 2026 guanyafei00
