#!/usr/bin/env python3
"""Skill data → Fusion analysis pipeline."""
import json
import os
import sys
import subprocess

DATA_DIR = os.environ.get("FUSION_DATA_DIR", "/tmp/fusion_quant_data")
FUSION_DIR = os.path.dirname(os.path.abspath(__file__))

# 读取skill抓取的数据摘要
with open(f"{DATA_DIR}/skill_data_summary.txt") as f:
    skill_data = f.read()

# 追加港股（用新浪港股代替，因为Yahoo超时）
print("补充港股数据...")
try:
    import requests
    H = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"}
    hk_codes = {"00700": "腾讯", "01810": "小米", "03690": "美团"}
    hk_data = []
    for code, name in hk_codes.items():
        try:
            r = requests.get(f"https://hq.sinajs.cn/list=hk{code}", headers=H, timeout=10)
            r.encoding = "utf-8"
            import re
            m = re.search(r'="([^"]*)"', r.text)
            if m:
                fields = m.group(1).split(",")
                hk_data.append(f"[港股 {code} {name}] 现价: {fields[6] if len(fields)>6 else '?'}")
        except:
            hk_data.append(f"[港股 {code} {name}] 获取失败")
    skill_data += "\n\n" + "\n".join(hk_data)
    print("港股数据OK")
except Exception as e:
    print(f"港股数据跳过: {e}")

# 构造Fusion查询
query = f"""你是量化分析专家。以下数据由本地skill脚本实时抓取（新浪+腾讯+东方财源F10），请基于这些真实数据分析：

{skill_data}

分析要求：
1. 涨多跌少判断：这9只股票中，哪些近120日涨多跌少、总体上涨？给出具体涨幅数据
2. 散户建议：小本金，只买ETF，给出3只具体ETF代码+配比+理由
3. 风险信号：当前最大风险是什么？一句话说清
4. 结论：直接给操作建议，不要废话"""

# 环境变量：从fusion.env加载
env = os.environ.copy()
env_file = os.path.join(FUSION_DIR, "fusion.env")
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k, v)

# 跑Fusion（auto-probe自动选模型）
cmd = [
    sys.executable, "-m", "fusion.cli",
    query,
    "-v",
]

print(f"\n{'='*60}")
print(f"Fusion查询（{len(query)}字）: skill真数据+自动探测模型")
print(f"{'='*60}\n")

try:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=FUSION_DIR, env=env)
    if r.stdout:
        print(r.stdout)
    if r.stderr:
        for line in r.stderr.split("\n"):
            if "Error" in line or "error" in line or "502" in line:
                print(f"[ERR] {line.strip()}")
    if r.returncode != 0:
        print(f"退出码: {r.returncode}")
except subprocess.TimeoutExpired:
    print("❌ 300秒超时")
except Exception as e:
    print(f"❌ 执行失败: {e}")
