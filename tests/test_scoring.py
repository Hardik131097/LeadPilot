"""Qualification Agent's scoring tool: ICP rules, tiers, disqualifiers, wording variants."""
import pytest

import tools


def test_ideal_lead_is_hot(lead):
    assert tools.score_lead(lead)["tier"] == "Hot"


def test_score_equals_sum_of_five_factors(lead):
    s = tools.score_lead(lead)
    assert s["score"] == sum(s["breakdown"].values())
    assert all(0 <= v <= 20 for v in s["breakdown"].values())


@pytest.mark.parametrize("title", ["Marketing Intern", "Intern - Marketing", "Student"])
def test_non_decision_makers_are_disqualified(lead, title):
    assert tools.score_lead({**lead, "title": title})["tier"] == "Disqualified"


def test_tiny_company_disqualified(lead):
    assert tools.score_lead({**lead, "employees": "12"})["tier"] == "Disqualified"


def test_no_company_disqualified(lead):
    assert tools.score_lead({**lead, "company": "Self"})["tier"] == "Disqualified"


def test_one_warning_sign_blocks_hot(lead):
    s = tools.score_lead({**lead, "budget_status": "No budget"})
    assert s["tier"] != "Hot" and "No budget declared" in s["flags"]


def test_two_warning_signs_mean_cold(lead):
    s = tools.score_lead({**lead, "budget_status": "No budget", "recent_signal": "Recent layoffs and restructuring"})
    assert s["tier"] == "Cold"


@pytest.mark.parametrize("signal", ["Happy with current vendor", "Very happy with our current vendor",
                                    "Satisfied with existing HRMS"])
def test_satisfied_customer_flagged(lead, signal):
    assert "Satisfied with current vendor" in tools.score_lead({**lead, "recent_signal": signal})["flags"]


@pytest.mark.parametrize("raw,canonical", [("Hospital", "Healthcare"), ("3PL / Logistics", "Logistics"),
                                           ("Warehousing", "Logistics"), ("Pharmaceuticals", "Healthcare"),
                                           ("Jute manufacturing", "Manufacturing"), ("EdTech", "Education")])
def test_industry_wording_normalised(raw, canonical):
    assert tools.normalize_industry(raw) == canonical


def test_headcount_with_comma(lead):
    assert tools.score_lead({**lead, "employees": "1,500"})["breakdown"]["Company size"] == 20


def test_scoring_is_deterministic(lead):
    assert tools.score_lead(lead) == tools.score_lead(lead)
