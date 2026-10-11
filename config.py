"""
LeadPilot configuration: the seller's profile, Ideal Customer Profile (ICP),
sales team, and compliance rules. Change these to adapt the system to any
B2B company. NOTE: PayNest is a fictional company created for this project.
"""

SELLER = {
    "company": "PayNest",
    "product": "PayNest HR & Payroll Cloud",
    "one_liner": "cloud HR, payroll and statutory-compliance software for growing Indian companies",
    "pricing": "Rs 80-120 per employee per month",
    "sender_name": "Hardik Srivastava",
    "sender_title": "Business Development, PayNest",
}

# Value propositions mapped to the pain each one solves
VALUE_PROPS = {
    "manual": "automates payroll runs, payslips and PF/ESI/TDS filings from one dashboard",
    "compliance": "keeps PF, ESI, PT and labour-code compliance up to date automatically",
    "shift": "handles shift rosters and mobile attendance for large or distributed workforces",
    "growth": "lets HR onboard new hires in minutes, even across multiple locations",
    "legacy": "replaces slow on-premise systems with a mobile-first cloud platform",
    "default": "brings HR, attendance and payroll into one simple cloud platform",
}

# Industry pain points used by the Research Agent
INDUSTRY_PAINS = {
    "Logistics": "large shift-based workforces with high attrition",
    "Manufacturing": "contract-labour compliance (PF/ESI) and shift attendance",
    "Healthcare": "24x7 staff rosters and credential tracking",
    "Retail": "store-level attendance across many locations",
    "IT Services": "fast hiring and complex variable pay",
    "Fintech": "strict compliance and audit-trail requirements",
    "Education": "seasonal hiring and multi-campus payroll",
    "FMCG": "distributed field-sales teams across states",
}

# Ideal Customer Profile scoring rules (used by the Qualification Agent's tool)
ICP = {
    "industry_scores": {
        "Logistics": 20, "Manufacturing": 20, "Healthcare": 18, "Retail": 18,
        "IT Services": 16, "FMCG": 16, "Fintech": 14, "Education": 14,
        "Media": 8, "Real Estate": 8,
    },
    "hot_threshold": 90,
    "warm_threshold": 65,
}

# Sales team for routing (fictional)
REPS = {
    "North": "Aditi Rao",
    "South": "Karthik Subramanian",
    "West": "Rahul Desai",
}
CITY_TERRITORY = {
    "Delhi": "North", "Gurugram": "North", "Noida": "North", "Faridabad": "North",
    "Jaipur": "North", "Lucknow": "North", "Chandigarh": "North",
    "Bengaluru": "South", "Hyderabad": "South", "Chennai": "South",
    "Coimbatore": "South", "Kochi": "South",
    "Mumbai": "West", "Pune": "West", "Ahmedabad": "West", "Goa": "West",
}

# Alternative spellings seen in CRM exports (added after evaluation round 1)
CITY_ALIASES = {
    "Bangalore": "Bengaluru", "Gurgaon": "Gurugram", "Bombay": "Mumbai", "Navi Mumbai": "Mumbai",
    "Thane": "Mumbai", "Madras": "Chennai", "Greater Noida": "Noida", "New Delhi": "Delhi",
}
INDUSTRY_SYNONYMS = {
    "Logistics": ["logistic", "3pl", "courier", "warehousing", "supply chain", "freight", "transport"],
    "Manufacturing": ["manufactur", "factory", "textile", "auto component", "engineering", "plant"],
    "Healthcare": ["health", "hospital", "clinic", "diagnostic", "pharma", "nursing"],
    "Retail": ["retail", "grocery", "e-commerce", "ecommerce", "store chain", "quick commerce"],
    "IT Services": ["it services", "software", "saas", "technology services", "it consulting"],
    "FMCG": ["fmcg", "consumer goods", "cpg", "food products"],
    "Fintech": ["fintech", "payments", "nbfc", "lending"],
    "Education": ["education", "edtech", "school", "college", "university", "academy"],
    "Media": ["media", "advertising", "publishing", "studio"],
    "Real Estate": ["real estate", "coworking", "property", "realty"],
}

# Compliance rules for the Reviewer Agent
BANNED_PHRASES = [
    "guaranteed", "guarantee", "100%", "risk-free", "risk free", "act now",
    "limited time", "best in the world", "no.1", "number one", "cheapest",
    "free money", "click here", "urgent",
]
MAX_EMAIL_WORDS = 160
OPT_OUT_LINE = 'If this is not relevant, just reply "no" and I will not follow up.'
MAX_SUBJECT_CHARS = 60
MAX_LINKEDIN_CHARS = 300

# Assumption used for the time-saved metric (minutes a human SDR spends per lead)
MANUAL_MINUTES_PER_LEAD = {"research": 8, "qualification": 4, "writing": 8, "review_and_routing": 3}
