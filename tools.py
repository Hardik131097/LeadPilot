"""
Deterministic tools the agents call. Keeping scoring and compliance checks
rule-based makes them consistent, explainable and auditable; the LLM is used
for reasoning and writing on top of these tools.
"""
import re
from datetime import date, timedelta

from config import (BANNED_PHRASES, CITY_ALIASES, CITY_TERRITORY, ICP,
                    INDUSTRY_PAINS, INDUSTRY_SYNONYMS, MAX_EMAIL_WORDS,
                    MAX_LINKEDIN_CHARS, MAX_SUBJECT_CHARS, OPT_OUT_LINE, REPS,
                    VALUE_PROPS)

INJECTION_PATTERNS = [
    r"ignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|rules|prompts?)",
    r"disregard (all |any )?(the )?(previous|prior|above|earlier|your)", r"system prompt",
    r"you are now", r"new instructions", r"act as (an?|the) ", r"forget (all|your|the) (rules|instructions)",
    r"do not (follow|apply) (the )?(rules|policy)",
]


def detect_injection(lead):
    """Flag lead fields that read like instructions to the AI rather than data (prompt-injection guard)."""
    hits = []
    for key in ("recent_signal", "current_hr_tool", "company", "title", "contact_name"):
        text = str(lead.get(key, "")).lower()
        if any(re.search(p, text) for p in INJECTION_PATTERNS):
            hits.append(key)
    return hits


def normalize_industry(industry):
    """Map free-text industry labels from CRM exports onto the ICP's industry list."""
    raw = str(industry).strip()
    if raw in ICP["industry_scores"]:
        return raw
    low = raw.lower()
    for canonical, words in INDUSTRY_SYNONYMS.items():
        if any(w in low for w in words):
            return canonical
    return raw


def normalize_city(city):
    raw = str(city).strip()
    for alias, canonical in CITY_ALIASES.items():
        if raw.lower() == alias.lower():
            return canonical
    return raw

OPT_OUT_MARKERS = ["reply no", 'reply "no"', "reply 'no'", "not follow up", "unsubscribe", "opt out", "opt-out"]
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(text):
    return {n.replace(",", "") for n in NUM_RE.findall(str(text))}


def unverified_figures(lead, outreach, kb_text):
    """Hallucination guard: every number in the draft must exist in the knowledge base or the lead data."""
    allowed = _numbers(kb_text) | _numbers(" ".join(str(v) for v in lead.values())) | {"20", "15", "1"}
    found = _numbers(f"{outreach.get('subject', '')} {outreach.get('email_body', '')} {outreach.get('linkedin_note', '')}")
    return sorted(found - allowed)

SATISFIED_WORDS = ["happy with", "satisfied with", "content with", "no plans to change"]
GROWTH_WORDS = ["hiring", "expand", "opened", "opening", "launch", "new ", "plant",
                "warehouse", "stores", "campus", "unit", "funding", "raised",
                "transformation", "second"]
PAIN_WORDS = ["penalty", "error", "complain", "compliance", "renewal",
              "contract ends", "inspection", "disconnected"]


def _num(x, default=0):
    try:
        return int(float(str(x).replace(",", "")))
    except (ValueError, TypeError):
        return default


def _has(text, words):
    t = str(text).lower()
    return any(w in t for w in words)


# ---------- Tool 1: ICP lead scoring (used by Qualification Agent) ----------
def score_lead(lead):
    industry = normalize_industry(lead.get("industry", ""))
    industry_fit = ICP["industry_scores"].get(industry, 4)

    emp = _num(lead.get("employees"))
    if emp < 50:
        size_fit = 4
    elif emp < 100:
        size_fit = 10
    elif emp <= 2000:
        size_fit = 20
    elif emp <= 5000:
        size_fit = 15
    else:
        size_fit = 10

    title = str(lead.get("title", "")).lower()
    if _has(title, ["intern", "student"]):
        authority = 0
    elif _has(title, ["chro", "ceo", "cfo", "coo", "founder", "director", "vp", "head", "chief"]):
        authority = 20
    elif _has(title, ["manager", "lead"]):
        authority = 14
    elif _has(title, ["executive", "generalist", "specialist", "assistant"]):
        authority = 8
    else:
        authority = 6

    tool = str(lead.get("current_hr_tool", "")).lower()
    signal = str(lead.get("recent_signal", "")).lower()
    if _has(tool, ["manual", "excel", "spreadsheet", "register", "tally"]):
        need = 12
    elif _has(tool, ["legacy", "disconnected", "outsourced", "contract ends"]):
        need = 10
    elif _has(tool, ["basic"]):
        need = 8
    elif _has(tool, ["competitor"]):
        need = 3
    else:
        need = 0
    if _has(signal, GROWTH_WORDS):
        need += 8
    if _has(signal, PAIN_WORDS):
        need += 8
    if _has(signal, SATISFIED_WORDS):
        need -= 5
    if _has(signal, ["layoff", "restructuring"]):
        need -= 2
    need = max(0, min(20, need))

    budget_status = str(lead.get("budget_status", "")).strip().lower()
    budget = {"approved": 10, "exploring": 6, "unknown": 3, "no budget": 0}.get(budget_status, 3)
    timeline = {"0-3 months": 10, "3-6 months": 7, "6-12 months": 3}.get(
        str(lead.get("timeline", "")).strip().lower(), 0)
    readiness = budget + timeline

    total = industry_fit + size_fit + authority + need + readiness

    hard_disq = []
    if authority == 0:
        hard_disq.append("Contact is not a decision-maker or influencer")
    if str(lead.get("company", "")).strip().lower() in ("n/a", "na", "self", "none", ""):
        hard_disq.append("No valid company")
    if emp < 20:
        hard_disq.append("Company too small for ICP")
    soft_flags = []
    if budget_status == "no budget":
        soft_flags.append("No budget declared")
    if _has(signal, SATISFIED_WORDS):
        soft_flags.append("Satisfied with current vendor")
    if _has(signal, ["layoff", "restructuring"]):
        soft_flags.append("Company is restructuring")

    if hard_disq:
        tier = "Disqualified"
    elif total >= ICP["hot_threshold"] and not soft_flags:
        tier = "Hot"
    elif total >= ICP["warm_threshold"] and len(soft_flags) < 2:  # two warning signs together -> nurture, not chase
        tier = "Warm"
    else:
        tier = "Cold"

    return {
        "score": total,
        "tier": tier,
        "breakdown": {
            "Industry fit": industry_fit,
            "Company size": size_fit,
            "Decision authority": authority,
            "Need & trigger": need,
            "Budget & timeline": readiness,
        },
        "disqualifiers": hard_disq,
        "flags": soft_flags,
    }


# ---------- Tool 2: pain-point inference (used by Research Agent) ----------
def infer_pains(lead):
    pains = []
    industry = normalize_industry(lead.get("industry", ""))
    if industry in INDUSTRY_PAINS:
        pains.append(INDUSTRY_PAINS[industry])
    tool = str(lead.get("current_hr_tool", "")).lower()
    if _has(tool, ["manual", "excel", "spreadsheet", "register"]):
        pains.append("error-prone manual payroll with no single employee record")
    if _has(tool, ["tally"]):
        pains.append("payroll and attendance managed separately from accounts")
    if _has(tool, ["legacy"]):
        pains.append("a slow on-premise HR system with poor mobile access")
    if _has(tool, ["outsourced"]):
        pains.append("limited visibility and control over outsourced payroll")
    if _has(tool, ["disconnected", "multiple"]):
        pains.append("employee data scattered across disconnected tools")
    if _has(tool, ["competitor"]):
        pains.append("dissatisfaction with the current HR vendor")
    signal = str(lead.get("recent_signal", "")).lower()
    if _has(signal, ["penalty", "inspection", "compliance"]):
        pains.append("statutory compliance risk")
    if _has(signal, GROWTH_WORDS):
        pains.append("scaling HR operations quickly during growth")
    return pains[:3] or ["manual HR admin consuming management time"]


def pick_value_prop(lead):
    text = f"{lead.get('current_hr_tool', '')} {lead.get('recent_signal', '')} {lead.get('industry', '')}".lower()
    if _has(text, ["penalty", "compliance", "inspection", "contract workers"]):
        return VALUE_PROPS["compliance"]
    if _has(text, ["legacy"]):
        return VALUE_PROPS["legacy"]
    if _has(text, ["logistics", "healthcare", "shift", "stores", "warehouse"]):
        return VALUE_PROPS["shift"]
    if _has(text, GROWTH_WORDS):
        return VALUE_PROPS["growth"]
    if _has(text, ["manual", "excel", "spreadsheet", "tally", "register"]):
        return VALUE_PROPS["manual"]
    return VALUE_PROPS["default"]


# ---------- Tool 3: outreach compliance checker (used by Reviewer Agent) ----------
def check_outreach(lead, outreach, kb_text=""):
    issues = []
    subject = outreach.get("subject", "") or ""
    body = outreach.get("email_body", "") or ""
    note = outreach.get("linkedin_note", "") or ""
    full = f"{subject} {body} {note}".lower()

    for phrase in BANNED_PHRASES:
        if phrase in full:
            issues.append(f"Uses banned/spammy phrase: '{phrase}'")
    words = len(body.split())
    if words > MAX_EMAIL_WORDS:
        issues.append(f"Email too long ({words} words; max {MAX_EMAIL_WORDS})")
    if len(subject) > MAX_SUBJECT_CHARS:
        issues.append(f"Subject too long ({len(subject)} chars; max {MAX_SUBJECT_CHARS})")
    if len(note) > MAX_LINKEDIN_CHARS:
        issues.append(f"LinkedIn note too long ({len(note)} chars; max {MAX_LINKEDIN_CHARS})")
    first_name = str(lead.get("contact_name", "")).split(" ")[0]
    if first_name and first_name.lower() not in body.lower():
        issues.append("Email does not address the contact by name")
    company = str(lead.get("company", ""))
    if company and company.lower() not in body.lower():
        issues.append("Email does not mention the prospect's company")
    if "?" not in body:
        issues.append("No clear call-to-action question")
    if re.search(r"\[[^\]]+\]|\{[^}]+\}", body + subject):
        issues.append("Contains unfilled placeholders")
    if not any(m in body.lower() for m in OPT_OUT_MARKERS):
        issues.append("Missing opt-out line (policy: DPDP / anti-spam)")
    if kb_text:
        bad = unverified_figures(lead, outreach, kb_text)
        if bad:
            issues.append(f"Unverified figure(s) not in knowledge base: {', '.join(bad)}")
    return issues


def auto_fix(outreach):
    """Rule-based fixes when no LLM is available to rewrite."""
    fixed = dict(outreach)
    for key in ("subject", "email_body", "linkedin_note"):
        text = fixed.get(key, "") or ""
        for phrase in BANNED_PHRASES:
            text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)
        fixed[key] = re.sub(r"  +", " ", text).strip()
    body = fixed.get("email_body", "")
    if not any(m in body.lower() for m in OPT_OUT_MARKERS):
        parts = body.rsplit("\n\nBest regards", 1)
        fixed["email_body"] = (parts[0] + f"\n\n{OPT_OUT_LINE}" +
                               ("\n\nBest regards" + parts[1] if len(parts) == 2 else ""))
    if len(fixed.get("subject", "")) > MAX_SUBJECT_CHARS:
        fixed["subject"] = fixed["subject"][:MAX_SUBJECT_CHARS - 3].rstrip() + "..."
    if len(fixed.get("linkedin_note", "")) > MAX_LINKEDIN_CHARS:
        fixed["linkedin_note"] = fixed["linkedin_note"][:MAX_LINKEDIN_CHARS - 3].rstrip() + "..."
    return fixed


# ---------- Tool 4: CRM routing (used by Sales Ops Agent) ----------
def assign_rep(city):
    """Route by territory. An unknown city is NOT guessed: it goes to the sales manager to assign."""
    territory = CITY_TERRITORY.get(normalize_city(city))
    if territory is None:
        return "Sales manager (unassigned territory)", "Unassigned"
    return REPS[territory], territory


def follow_up_plan(tier, start=None):
    start = start or date.today()
    fmt = lambda d: (start + timedelta(days=d)).strftime("%d %b %Y")
    if tier == "Hot":
        return f"Email + call by {fmt(1)}; LinkedIn connect {fmt(1)}; follow-up call {fmt(3)}"
    if tier == "Warm":
        return f"Email {fmt(0)}; LinkedIn note {fmt(3)}; follow-up email {fmt(7)}"
    if tier == "Cold":
        return f"Monthly newsletter; re-score on {fmt(90)}"
    return "No outreach"
