# Fusion

**多模型共识管线** — Panel→Judge→Synth 三阶段对抗幻觉架构

## 为什么需要 Fusion？

单一LLM回答问题时，会"自信地编造"——你完全无法分辨真假。Fusion的核心思路：

1. **Panel**：让3个**不同厂商**的模型独立回答（防同源偏差）
2. **Judge**：用一个**独立模型**评审所有回答（防自审）
3. **Synth**：综合所有来源+评审结果，输出最终答案

这比单模型多次采样更有效——因为同一模型的系统性错误无法自我纠正。

## 快速开始

```bash
# 安装
pip install .

# 设置环境变量
export FUSION_LLM_BASE_URL=https://openrouter.ai/api/v1
export FUSION_LLM_API_KEY=sk-your-key

# 运行
fusion "量子计算2024最新进展" -u https://arxiv.org/abs/2401.12345

# 稳定性测试（3轮对比）
fusion "对比React和Vue" --stability 3
```

## 支持的API提供商

### OpenRouter（推荐起步）
```bash
export FUSION_LLM_BASE_URL=https://openrouter.ai/api/v1
export FUSION_LLM_API_KEY=sk-or-...
```

### 硅基流动
```bash
export FUSION_LLM_BASE_URL=https://api.siliconflow.cn/v1
export FUSION_LLM_API_KEY=sk-...
```

### 自建网关（如 CliProxyAPI）
```bash
export FUSION_LLM_BASE_URL=http://your-gateway:8317/v1
export FUSION_LLM_API_KEY=your-key
```

### 使用预设
```bash
fusion "问题" --preset openrouter --api-key sk-or-...
fusion "问题" --preset siliconflow --api-key sk-...
```

## 环境变量

| 变量 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `FUSION_LLM_BASE_URL` | ✅ | - | OpenAI兼容API地址 |
| `FUSION_LLM_API_KEY` | ✅ | - | API密钥 |
| `FUSION_PANEL_MODELS` | ❌ | qwen+gemma+minimax | Panel模型（逗号分隔） |
| `FUSION_JUDGE_MODEL` | ❌ | gpt-oss-120b | 评审模型 |
| `FUSION_SYNTH_MODEL` | ❌ | deepseek-v4-pro | 综合模型 |
| `FUSION_LLM_TIMEOUT` | ❌ | 90 | LLM超时（秒） |
| `FUSION_RPM_LIMIT` | ❌ | 20 | 每分钟请求限制 |
| `FUSION_AUTH_TOKEN` | ❌ | - | 自部署认证令牌 |
| `FUSION_TAVILY_KEY` | ❌ | - | Tavily搜索API密钥 |

## URL抓取支持

自动按域名路由到最佳抓取策略：

| 域名 | 方式 | 依赖 |
|------|------|------|
| arxiv.org | API提取 | 无 |
| youtube.com | yt-dlp字幕 | yt-dlp |
| mp.weixin.qq.com | curl+HTML提取 | curl |
| github.com | curl | curl |
| 其他 | Playwright→Crawl4AI→curl | 按需 |

可选依赖：`pip install fusion[all]`

## Docker

```bash
docker build -t fusion .
docker run -e FUSION_LLM_BASE_URL=... -e FUSION_LLM_API_KEY=... fusion "你的问题"
```

## 架构

```
query + URLs
    │
    ▼
┌──────────┐
│  Fetch    │  抓取来源内容（6种策略+降级链）
└──────────┘
    │
    ▼
┌──────────┐
│  Panel    │  3模型并行独立回答（不同厂商）
└──────────┘
    │
    ▼
┌──────────┐
│  Judge    │  独立模型评审打分（JSON结构化）
└──────────┘
    │
    ▼
┌──────────┐
│  Synth    │  综合所有来源+评审→最终回答
└──────────┘
```

## 安全

- **零硬编码密钥/IP** — 全部走环境变量
- **SSRF防护** — 自动拦截对内网/localhost的请求
- **速率限制** — 令牌桶算法，防止API滥用
- **认证** — 可选auth token保护自部署实例

## License

MIT
