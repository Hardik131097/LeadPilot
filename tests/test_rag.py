"""Two knowledge bases in Chroma and the agents' retrieval."""
from agents import ResearchAgent
from rag import analyze, get_kbs


def test_two_knowledge_bases_are_built():
    sales, policy = get_kbs()
    assert len(sales.chunks) == 19 and len(policy.chunks) == 5


def test_industry_metadata_filter_returns_matching_case_study():
    sales, _ = get_kbs()
    hit = sales.search("payroll warehouse staff", k=1, industry="Logistics")[0]
    assert hit["industry"] == "Logistics"


def test_policy_retrieval_finds_opt_out_rule():
    _, policy = get_kbs()
    assert "opt-out" in policy.search("email must let the recipient opt out", k=1)[0]["section"].lower()


def test_vocabulary_links_cost_to_pricing():
    assert "price" in analyze("how much does it cost") and "price" in analyze("Pricing and implementation")


def test_no_case_study_invented_for_industry_without_one(lead, nolog):
    research = ResearchAgent(None, nolog).run({**lead, "industry": "FMCG"})
    assert research["case_study"] == ""


def test_research_uses_case_study_from_same_industry(lead, nolog):
    research = ResearchAgent(None, nolog).run(lead)
    assert "Logistics case study" in research["case_study"]
