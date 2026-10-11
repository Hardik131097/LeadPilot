"""
Orchestrator: runs the five agents in sequence for every lead, passing each
agent's output to the next (shared state), and records an audit log.
"""
import time
from datetime import datetime

import pandas as pd

from agents import (OutreachAgent, QualificationAgent, ResearchAgent,
                    ReviewerAgent, SalesOpsAgent)
from config import MANUAL_MINUTES_PER_LEAD

REQUIRED_COLUMNS = ["lead_id", "contact_name", "title", "company", "industry", "employees", "city",
                    "current_hr_tool", "recent_signal", "lead_source", "budget_status", "timeline"]


def run_pipeline(df, llm=None, progress=None):
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Lead file is missing columns: {missing}")

    logs = []

    def logger(agent, lead_id, message):
        logs.append({"time": datetime.now().strftime("%H:%M:%S"), "agent": agent,
                     "lead_id": lead_id, "message": message})

    research_agent = ResearchAgent(llm, logger)
    qual_agent = QualificationAgent(llm, logger)
    writer_agent = OutreachAgent(llm, logger)
    reviewer_agent = ReviewerAgent(llm, logger)
    router_agent = SalesOpsAgent(llm, logger)

    start = time.time()
    records = []
    leads = df.fillna("").to_dict("records")
    for i, lead in enumerate(leads, 1):
        lead = {k: str(v).strip() for k, v in lead.items()}
        if progress:
            progress(i, len(leads), lead["company"])
        research = research_agent.run(lead)
        qual = qual_agent.run(lead, research)
        draft = writer_agent.run(lead, research, qual)
        review = reviewer_agent.run(lead, draft, research.get("flags"))
        route = router_agent.run(lead, qual, review)
        final = review["outreach"] or {}
        records.append({
            "lead_id": lead["lead_id"], "contact_name": lead["contact_name"], "title": lead["title"],
            "company": lead["company"], "industry": lead["industry"], "employees": lead["employees"],
            "city": lead["city"],
            "score": qual["score"], "tier": qual["tier"],
            **{f"score_{k.lower().replace(' & ', '_').replace(' ', '_')}": v for k, v in qual["breakdown"].items()},
            "justification": qual["justification"], "angle": qual["angle"],
            "account_summary": research["account_summary"],
            "case_study": research.get("case_study", ""),
            "research_flags": "; ".join(research.get("flags", [])),
            "pain_points": " | ".join(research["pain_points"]), "hook": research["hook"],
            "subject": final.get("subject", ""), "email_body": final.get("email_body", ""),
            "linkedin_note": final.get("linkedin_note", ""),
            "review_status": review["status"], "review_issues": "; ".join(review["issues"]),
            "revisions": review["revisions"],
            "priority": route["priority"], "owner": route["owner"], "territory": route["territory"], "next_action": route["next_action"],
            "follow_up_plan": route["follow_up_plan"],
            "mode": "AI (LLM)" if (llm and llm.calls) else "Demo (rules)",
        })

    for r in records:
        r["mode"] = "AI (LLM)" if (llm and llm.calls) else "Demo (rules)"
    summary = router_agent.summarize(records)
    elapsed = time.time() - start
    manual_min = sum(MANUAL_MINUTES_PER_LEAD.values()) * len(records)
    metrics = {
        "leads": len(records),
        "hot": sum(r["tier"] == "Hot" for r in records),
        "warm": sum(r["tier"] == "Warm" for r in records),
        "cold": sum(r["tier"] == "Cold" for r in records),
        "disqualified": sum(r["tier"] == "Disqualified" for r in records),
        "drafts": sum(bool(r["email_body"]) for r in records),
        "auto_approved": sum(r["review_status"].startswith("Approved") for r in records),
        "flagged": sum(r["review_status"] == "Flagged for human review" for r in records),
        "revisions": sum(r["revisions"] for r in records),
        "seconds": round(elapsed, 1),
        "manual_minutes": manual_min,
        "llm_calls": llm.calls if llm else 0,
        "llm_failed": bool(llm and llm.api_key and llm.calls == 0) or bool(llm and llm.disabled),
        "llm_error": llm.last_error if llm else "",
        "schema_repairs": getattr(llm, "repairs", 0) if llm else 0,
        "rag_retrievals": sum(m.startswith("RAG") for m in [l["message"] for l in logs]),
    }
    return {"results": pd.DataFrame(records), "logs": pd.DataFrame(logs), "summary": summary, "metrics": metrics}
