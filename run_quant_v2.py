#!/usr/bin/env python3
"""Run Fusion quant analysis - Round 2: let models use own knowledge."""
import os, sys

# Load env from fusion.env if not already set
if not os.environ.get("FUSION_LLM_BASE_URL"):
    env_file = os.path.join(os.path.dirname(__file__), "fusion.env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k, v)

os.environ.setdefault("FUSION_LLM_TIMEOUT", "300")

from fusion.config import Config
from fusion.pipeline import run
