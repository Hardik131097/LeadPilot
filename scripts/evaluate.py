"""
LeadPilot evaluation script.

Runs the real agent pipeline (demo mode, no language model) on test sets whose
expected outcomes were written in advance, plus a red-team test of the
Compliance Reviewer and a retrieval test of both knowledge bases.

Usage:  python scripts/evaluate.py [round_label]
Writes: docs/evaluation_results.json and docs/EVALUATION.md
"""
import json
import os
import sys
import time
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import pandas as pd

import tools
from agents import ReviewerAgent
from config import MAX_EMAIL_WORDS
from orchestrator import run_pipeline
from rag import get_kbs

EVAL = os.path.join(BASE, "data", "eval")
NOLOG = lambda *a: None


def load(name):
    path = os.path.join(EVAL, name)
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None


def check_rows(res, expected):
    rows = []
    for _, r in res.iterrows():
        exp = expected[r["lead_id"]]
        has_draft = bool(r["email_body"])
        should_draft = r["tier"] in ("Hot", "Warm")
        rows.append({
            "id": r["lead_id"], "desc": exp.get("desc", r["company"]),
            "tier": r["tier"], "score": int(r["score"]), "expected_tiers": exp["tiers"],
            "tier_ok": r["tier"] in exp["tiers"],
            "territory": r["territory"], "expected_territory": exp["territory"],
            "route_ok": r["territory"] == exp["territory"],
            "draft_rule_ok": has_draft == should_draft,
            "review_status": r["review_status"],
        })
    return rows


def run_set(df, expected):
    out = run_pipeline(df, None)
    return out, check_rows(out["results"], expected)


def variants_df(sample, cases):
    rows, expected = [], {}
    by_id = sample.set_index("lead_id")
    for c in cases:
        row = by_id.loc[c["base"]].to_dict()
        row.update(c["change"])
        row["lead_id"] = c["id"]
        rows.append(row)
        expected[c["id"]] = {"tiers": c["tiers"], "territory": c["territory"], "desc": c["desc"]}
    return pd.DataFrame(rows), expected


# ---------------------------------------------------------------- red team
FAULTS = {
    "Banned phrase in subject": lambda l, d: {**d, "subject": "Guaranteed savings for " + l["company"]},
    "Banned phrase in body": lambda l, d: {**d, "email_body": d["email_body"].replace("\n\n", "\n\nThis is completely risk-free. ", 1)},
    "Invented statistic": lambda l, d: {**d, "email_body": d["email_body"].replace("\n\n", "\n\nClients cut payroll costs by 47 percent. ", 1)},
    "Opt-out line removed": lambda l, d: {**d, "email_body": "\n\n".join(p for p in d["email_body"].split("\n\n") if "not follow up" not in p)},
    "Contact name removed": lambda l, d: {**d, "email_body": d["email_body"].replace(l["contact_name"].split()[0], "there")},
    "Company name removed": lambda l, d: {**d, "email_body": d["email_body"].replace(l["company"], "your company")},
    "Call-to-action removed": lambda l, d: {**d, "email_body": d["email_body"].replace("?", ".")},
    "Unfilled placeholder": lambda l, d: {**d, "email_body": d["email_body"].replace("\n\n", "\n\nAs [CUSTOMER NAME] found, ", 1)},
    "Email far too long": lambda l, d: {**d, "email_body": d["email_body"] + "\n\n" + " ".join(["Our platform helps teams."] * 40)},
    "Subject too long": lambda l, d: {**d, "subject": d["subject"] + " - a detailed note on payroll, attendance and compliance"},
}
FAULT_SIGNATURE = {
    "Banned phrase in subject": "banned", "Banned phrase in body": "banned", "Invented statistic": "Unverified figure",
    "Opt-out line removed": "opt-out", "Contact name removed": "by name", "Company name removed": "company",
    "Call-to-action removed": "call-to-action", "Unfilled placeholder": "placeholder",
    "Email far too long": "too long", "Subject too long": "Subject too long",
}


def red_team(sample_res, sample_df):
    sales_kb, _ = get_kbs()
    kb_text = sales_kb.all_text()
    leads = {r["lead_id"]: {k: str(v) for k, v in r.items()} for r in sample_df.fillna("").to_dict("records")}
    per_fault = {f: {"planted": 0, "detected": 0, "fixed_by_rules": 0, "flagged_for_human": 0, "escaped": 0} for f in FAULTS}
    baseline_clean = 0
    drafts = sample_res[sample_res["email_body"] != ""]
    for _, r in drafts.iterrows():
        lead = leads[r["lead_id"]]
        clean = {"subject": r["subject"], "email_body": r["email_body"], "linkedin_note": r["linkedin_note"]}
        if not tools.check_outreach(lead, clean, kb_text):
            baseline_clean += 1
        for name, plant in FAULTS.items():
            bad = plant(lead, clean)
            stat = per_fault[name]
            stat["planted"] += 1
            issues = tools.check_outreach(lead, bad, kb_text)
            if any(FAULT_SIGNATURE[name].lower() in i.lower() for i in issues):
                stat["detected"] += 1
            review = ReviewerAgent(None, NOLOG).run(lead, bad)
            if review["status"].startswith("Approved"):
                still = tools.check_outreach(lead, review["outreach"], kb_text)
                # approved = no issues left; check the fault text itself is gone
                gone = name not in ("Invented statistic",) or "47" not in review["outreach"]["email_body"]
                if gone and not still:
                    stat["fixed_by_rules"] += 1
                else:
                    stat["escaped"] += 1
            else:
                stat["flagged_for_human"] += 1
    return {"drafts": len(drafts), "baseline_clean": baseline_clean, "per_fault": per_fault}


# ---------------------------------------------------------------- retrieval
def retrieval_eval():
    sales_kb, policy_kb = get_kbs()
    q = load("rag_queries.json")
    out = {}
    for kb_name in [k for k in q if not k.startswith("_")]:
        kb = policy_kb if "policy" in kb_name else sales_kb
        rows = []
        for item in q[kb_name]:
            hits = kb.search(item["q"], k=3)
            sections = [h["section"] for h in hits]
            rank = next((i + 1 for i, s in enumerate(sections) if s.lower().startswith(item["expect"].lower())), None)
            rows.append({"query": item["q"], "expect": item["expect"], "top3": sections, "rank": rank})
        out[kb_name] = rows
    return out


def pct(a, b):
    return f"{a}/{b} ({round(100 * a / b) if b else 0}%)"


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "final"
    t0 = time.time()
    sample = pd.read_csv(os.path.join(BASE, "data", "sample_leads.csv"))
    expected = {k: v for k, v in load("expected_sample.json").items() if not k.startswith("_")}

    sample_out, sample_rows = run_set(sample, expected)
    second = run_pipeline(sample, None)["results"]
    deterministic = (sample_out["results"]["score"].tolist() == second["score"].tolist())

    sets = {"sample": sample_rows}
    for fname, key in (("variants_round1.json", "variants_round1"), ("heldout.json", "heldout")):
        spec = load(fname)
        if spec:
            df, exp = variants_df(sample, spec["cases"]) if "base" in spec["cases"][0] else (
                pd.DataFrame([c["lead"] for c in spec["cases"]]),
                {c["lead"]["lead_id"]: {"tiers": c["tiers"], "territory": c["territory"], "desc": c["desc"]} for c in spec["cases"]})
            out, rows = run_set(df, exp)
            if key == "heldout":
                for c, r in zip(spec["cases"], rows):
                    if c.get("check") == "injection":
                        res = out["results"].set_index("lead_id").loc[c["lead"]["lead_id"]]
                        text = f"{res['subject']} {res['email_body']} {res['linkedin_note']}".lower()
                        r["injection_contained"] = ("ignore" not in text and "guarantee" not in text
                                                    and "100%" not in text)
                        r["injection_flagged"] = "injection" in str(res.get("research_flags", "")).lower() or \
                                                 "injection" in str(res.get("justification", "")).lower()
            sets[key] = rows

    sales_kb, _ = get_kbs()
    kb_text = sales_kb.all_text()
    leads = {r["lead_id"]: {k: str(v) for k, v in r.items()} for r in sample.fillna("").to_dict("records")}
    drafts = sample_out["results"][sample_out["results"]["email_body"] != ""]
    grounding = {"drafts": len(drafts), "unverified_figures": 0, "opt_out_present": 0, "banned_phrases": 0,
                 "within_length": 0, "approved": 0}
    for _, r in drafts.iterrows():
        d = {"subject": r["subject"], "email_body": r["email_body"], "linkedin_note": r["linkedin_note"]}
        lead = leads[r["lead_id"]]
        if tools.unverified_figures(lead, d, kb_text):
            grounding["unverified_figures"] += 1
        if "not follow up" in d["email_body"]:
            grounding["opt_out_present"] += 1
        if any(p in (d["subject"] + d["email_body"]).lower() for p in tools.BANNED_PHRASES):
            grounding["banned_phrases"] += 1
        if len(d["email_body"].split()) <= MAX_EMAIL_WORDS:
            grounding["within_length"] += 1
        if r["review_status"].startswith("Approved"):
            grounding["approved"] += 1

    rt = red_team(sample_out["results"], sample)
    retr = retrieval_eval()
    results = {"label": label, "run_at": datetime.now().strftime("%d %B %Y %H:%M"), "mode": "demo (rule-based, no LLM)",
               "sets": sets, "deterministic_scores": deterministic, "grounding": grounding, "red_team": rt,
               "retrieval": retr, "pipeline_seconds_20_leads": sample_out["metrics"]["seconds"],
               "eval_seconds": round(time.time() - t0, 1)}
    os.makedirs(os.path.join(BASE, "docs"), exist_ok=True)
    json.dump(results, open(os.path.join(BASE, "docs", f"evaluation_results_{label}.json"), "w"), indent=1)
    write_md(results, label)
    print(summary(results))


def summary(r):
    lines = [f"EVALUATION ({r['label']}, {r['run_at']}, {r['mode']})"]
    for k, rows in r["sets"].items():
        lines.append(f"  {k:16s} tier {pct(sum(x['tier_ok'] for x in rows), len(rows))} | "
                     f"route {pct(sum(x['route_ok'] for x in rows), len(rows))} | "
                     f"draft rule {pct(sum(x['draft_rule_ok'] for x in rows), len(rows))}")
        for x in rows:
            if not (x["tier_ok"] and x["route_ok"] and x["draft_rule_ok"]) or "injection_contained" in x:
                lines.append(f"     MISS {x['id']} {x['desc']}: got {x['tier']} ({x['score']}) / {x['territory']}; "
                             f"expected {x['expected_tiers']} / {x['expected_territory']}"
                             + (f"; injection contained={x.get('injection_contained')} flagged={x.get('injection_flagged')}" if "injection_contained" in x else ""))
    g = r["grounding"]
    lines.append(f"  grounding: {g}")
    lines.append(f"  deterministic: {r['deterministic_scores']}")
    rt = r["red_team"]
    tot = {k: sum(v[k] for v in rt["per_fault"].values()) for k in ("planted", "detected", "fixed_by_rules", "flagged_for_human", "escaped")}
    lines.append(f"  red team: {tot} baseline clean {rt['baseline_clean']}/{rt['drafts']}")
    for f, v in rt["per_fault"].items():
        lines.append(f"     {f:26s} {v}")
    for kb, rows in r["retrieval"].items():
        h1 = sum(x["rank"] == 1 for x in rows); h3 = sum(x["rank"] is not None for x in rows)
        lines.append(f"  retrieval {kb}: top1 {pct(h1, len(rows))} top3 {pct(h3, len(rows))}")
        for x in rows:
            if x["rank"] != 1:
                lines.append(f"     rank={x['rank']} '{x['query']}' expect '{x['expect']}' got {x['top3']}")
    return "\n".join(lines)


def write_md(r, label):
    md = [f"# LeadPilot evaluation results ({label})", "",
          f"Run: {r['run_at']} · Mode: {r['mode']} · Generated by `scripts/evaluate.py`. Nothing here was typed by hand.", "",
          "```", summary(r), "```"]
    open(os.path.join(BASE, "docs", f"EVALUATION_{label}.md"), "w").write("\n".join(md))


if __name__ == "__main__":
    main()
