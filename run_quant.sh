#!/bin/bash
set -e
cd "$(dirname "$0")"

# 加载fusion.env
if [ -f fusion.env ]; then
    set -a
    source fusion.env
    set +a
fi
export FUSION_LLM_TIMEOUT=300

fusion "分析近一年涨多跌少总体涨幅较好的股票从5个维度美股信号A股关联新闻催化AI技术方向资金面给出A股港股美股每类3到5只具体股票代码推荐逻辑和风险点只买低价股必须给具体代码" \
  -u "https://finance.yahoo.com/quote/NVDA/" \
  -u "https://finance.yahoo.com/quote/AMD/" \
  -v
