#!/usr/bin/env python3
"""思路1：skill脚本抓数据 → 灌进Fusion跑量化分析"""
import json
import subprocess
import sys
import os

SKILL_DIR = "/root/.hermes/skills"
FUSION_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = "/tmp/fusion_quant_data"
os.makedirs(DATA_DIR, exist_ok=True)

# ── Step 1: 用skill脚本抓数据 ──
print("=" * 60)
print("Step 1: 用china-stock-deep-analysis抓A股数据")
print("=" * 60)

# A股权重股（Fusion Round 2推荐的）
a_codes = ["600519", "002475", "300750"]  # 茅台/立讯/宁德
a_results = {}

for code in a_codes:
    out_file = f"{DATA_DIR}/a_{code}.json"
    script = f"{SKILL_DIR}/china-stock-deep-analysis/scripts/fetch_a_share.py"
    cmd = [sys.executable, script, "--code", code, "--out", out_file, "--market", "a"]
    print(f"  抓 {code} ...")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            with open(out_file) as f:
                a_results[code] = json.load(f)
            print(f"  ✅ {code} OK")
        else:
            print(f"  ❌ {code} 失败: {r.stderr[:200]}")
            a_results[code] = {"error": r.stderr[:200]}
    except Exception as e:
        print(f"  ❌ {code} 超时: {e}")
        a_results[code] = {"error": str(e)}

# 美股（Yahoo Finance via stocks skill）
print("\n" + "=" * 60)
print("Step 1b: 用stocks skill抓美股数据")
print("=" * 60)

us_symbols = ["NVDA", "MSFT", "AAPL"]
us_results = {}

for sym in us_symbols:
    script = f"{SKILL_DIR}/finance/stocks/scripts/stocks_client.py"
    cmd = [sys.executable, script, "quote", sym]
    print(f"  抓 {sym} ...")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout.strip():
            try:
                us_results[sym] = json.loads(r.stdout)
                print(f"  ✅ {sym} OK")
            except json.JSONDecodeError:
                us_results[sym] = {"raw": r.stdout[:500]}
                print(f"  ⚠️ {sym} 非JSON，存原文")
        else:
            print(f"  ❌ {sym} 失败: {r.stderr[:200]}")
            us_results[sym] = {"error": r.stderr[:200] if r.stderr else "empty response"}
    except Exception as e:
        print(f"  ❌ {sym} 超时: {e}")
        us_results[sym] = {"error": str(e)}

# ── Step 2: 把数据整理成Fusion的输入文本 ──
print("\n" + "=" * 60)
print("Step 2: 整理数据为Fusion输入")
print("=" * 60)

data_summary = []
data_summary.append("=== 实时行情数据（由本地skill脚本抓取） ===\n")

for code, d in a_results.items():
    if "error" in d:
        data_summary.append(f"[A股 {code}] 获取失败: {d['error']}")
        continue
    q = d.get("quote_sina") or d.get("quote_tencent") or {}
    name = q.get("name", code)
    price = q.get("price", "?")
    pct = q.get("pct", "?")
    pe = None
    # 从腾讯行情取PE
    tq = d.get("quote_tencent", {})
    if tq:
        pe = tq.get("pe")
    kline = d.get("kline", [])
    # 取最近5日K线
    recent_k = kline[-5:] if kline else []
    k_summary = ""
    for k in recent_k:
        k_summary += f"  {k.get('date','?')}: 收{k.get('close','?')} 涨跌{k.get('pct','?')}%\n"
    # 净利润/营收（东方财富）
    fin = d.get("finance", [])
    fin_summary = ""
    for f_item in fin[:2]:
        fin_summary += f"  {f_item.get('REPORT_DATE','?')[:10]}: 净利润{f_item.get('PARENT_NETPROFIT','?')}亿, 营收{f_item.get('TOTAL_OPERATE_INCOME','?')}亿\n"

    data_summary.append(
        f"[A股 {code} {name}] 现价{price} 涨跌{pct}% PE={pe}\n"
        f"近5日K线:\n{k_summary}"
        f"财务数据:\n{fin_summary}"
    )

for sym, d in us_results.items():
    if "error" in d:
        data_summary.append(f"[美股 {sym}] 获取失败: {d['error']}")
        continue
    # stocks_client输出格式
    if isinstance(d, dict) and "price" in d:
        data_summary.append(
            f"[美股 {sym}] {d.get('name', sym)} 现价{d.get('price','?')} "
            f"涨跌{d.get('change_pct', d.get('pct','?'))}% "
            f"PE={d.get('pe','?')} 市值{d.get('market_cap','?')}"
        )
    elif "raw" in d:
        data_summary.append(f"[美股 {sym}] 原始数据: {d['raw'][:300]}")
    else:
        # 可能是quote嵌套
        q = d.get("quote", d)
        price = q.get("regularMarketPrice") or q.get("price", "?")
        pct = q.get("regularMarketChangePercent") or q.get("change_pct", "?")
        data_summary.append(f"[美股 {sym}] 现价{price} 涨跌{pct}%")

full_data = "\n".join(data_summary)

# 保存数据摘要
data_file = f"{DATA_DIR}/skill_data_summary.txt"
with open(data_file, "w") as f:
    f.write(full_data)
print(f"数据摘要已保存: {data_file}")
print(f"数据长度: {len(full_data)} 字符")

# ── Step 3: 构造Fusion查询 ──
print("\n" + "=" * 60)
print("Step 3: 构造Fusion查询并跑")
print("=" * 60)

fusion_query = f"""基于以下skill脚本抓取的实时行情数据，结合你对市场的了解，分析：

{full_data}

请分析：
1. 这9只股票近一年涨多跌少、总体涨幅的依据
2. 1000元本金散户应该买哪个ETF（给出具体代码和理由）
3. 当前市场风险信号

分析要求：简明扼要，直接给结论，不要废话。"""

# 保存query
query_file = f"{DATA_DIR}/fusion_query.txt"
with open(query_file, "w") as f:
    f.write(fusion_query)

# 跑Fusion — 从fusion.env加载环境变量
_script_dir = os.path.dirname(os.path.abspath(__file__))
_env_file = os.path.join(_script_dir, "fusion.env")
if os.path.exists(_env_file) and not os.environ.get("FUSION_LLM_BASE_URL"):
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)

fusion_cmd = [
    sys.executable, "-m", "fusion.cli",
    fusion_query,
    "--panel-models", "glm-4.7-flash,qwen3-next-80b-a3b-instruct,stepfun-ai/step-3.7-flash",
    "--judge-model", "qwen3-next-80b-a3b-instruct",
    "--synth-model", "qwen3-next-80b-a3b-instruct",
    "-v",
]

print(f"运行: fusion \"查询({len(fusion_query)}字)\" --panel-models 3模型")
print("等待Fusion输出...")

try:
    r = subprocess.run(
        fusion_cmd,
        capture_output=True,
        text=True,
        timeout=300,
        cwd=FUSION_DIR,
    )
    print("\n" + "=" * 60)
    print("Fusion 输出:")
    print("=" * 60)
    if r.stdout:
        print(r.stdout[-3000:] if len(r.stdout) > 3000 else r.stdout)
    if r.stderr:
        print("\n[stderr]:", r.stderr[-500:])
    if r.returncode != 0:
        print(f"\n退出码: {r.returncode}")
except subprocess.TimeoutExpired:
    print("❌ Fusion超时（300秒）")
except Exception as e:
    print(f"❌ Fusion执行失败: {e}")
