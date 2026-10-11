"""Sales Ops Router tools: territory routing and follow-up plans."""
from datetime import date

import pytest

import tools


@pytest.mark.parametrize("city,territory", [("Gurugram", "North"), ("Gurgaon", "North"), ("Bangalore", "South"),
                                            ("Bengaluru", "South"), ("Navi Mumbai", "West"), ("Pune", "West")])
def test_known_cities_route_to_territory(city, territory):
    assert tools.assign_rep(city)[1] == territory


def test_unknown_city_is_not_guessed():
    owner, territory = tools.assign_rep("Kolkata")
    assert territory == "Unassigned" and "Sales manager" in owner


@pytest.mark.parametrize("tier,needle", [("Hot", "call"), ("Warm", "follow-up email"),
                                         ("Cold", "newsletter"), ("Disqualified", "No outreach")])
def test_follow_up_plan_per_tier(tier, needle):
    assert needle in tools.follow_up_plan(tier, date(2026, 10, 10))
