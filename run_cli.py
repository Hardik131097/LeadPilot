"""Run the agent team from the terminal: python run_cli.py [path/to/leads.csv]"""
import os
import sys

import pandas as pd

from llm import LLM
from orchestrator import run_pipeline

BASE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "data", "sample_leads.csv")
    llm = LLM(os.getenv("LLM_PROVIDER", "groq"))
    print(f"Mode: {'AI - ' + llm.model if llm.available else 'Demo (rule-based, no API key)'}")
    out = run_pipeline(pd.read_csv(path), llm,
                       lambda i, n, c: print(f"[{i}/{n}] {c}"))
    os.makedirs(os.path.join(BASE, "outputs"), exist_ok=True)
    out["results"].to_csv(os.path.join(BASE, "outputs", "results.csv"), index=False)
    out["logs"].to_csv(os.path.join(BASE, "outputs", "agent_log.csv"), index=False)
    with open(os.path.join(BASE, "outputs", "manager_summary.md"), "w", encoding="utf-8") as f:
        f.write(out["summary"])
    print("\n" + out["summary"])
    print("\nMetrics:", out["metrics"])
    print("Saved to outputs/")
