"""End-to-end orchestration in demo mode."""
import os

import pandas as pd
import pytest

from conftest import ROOT
from orchestrator import run_pipeline


@pytest.fixture(scope="module")
def out():
    return run_pipeline(pd.read_csv(os.path.join(ROOT, "data", "sample_leads.csv")), None)


def test_all_twenty_leads_processed(out):
    assert out["metrics"]["leads"] == 20 and len(out["results"]) == 20


def test_only_hot_and_warm_get_drafts(out):
    res = out["results"]
    assert (res[res["tier"].isin(["Cold", "Disqualified"])]["email_body"] == "").all()
    assert (res[res["tier"].isin(["Hot", "Warm"])]["email_body"] != "").all()


def test_every_lead_has_owner_and_next_action(out):
    assert (out["results"]["owner"] != "").all() and (out["results"]["next_action"] != "").all()


def test_every_agent_leaves_an_audit_trail(out):
    agents = set(out["logs"]["agent"])
    assert {"Research Agent", "Qualification Agent", "Outreach Writer Agent",
            "Compliance Reviewer Agent", "Sales Ops Router Agent"} <= agents


def test_knowledge_bases_were_used(out):
    assert out["metrics"]["rag_retrievals"] > 0


def test_manager_briefing_written(out):
    assert "Pipeline briefing" in out["summary"] and "Hot" in out["summary"]


def test_missing_columns_rejected():
    with pytest.raises(ValueError):
        run_pipeline(pd.DataFrame([{"company": "X"}]), None)
