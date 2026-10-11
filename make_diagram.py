"""Generates docs/architecture.png (used in the report and PPT)."""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

fig, ax = plt.subplots(figsize=(14, 7.2), dpi=200)
ax.set_xlim(0, 14); ax.set_ylim(0, 7.2); ax.axis("off")

def box(x, y, w, h, title, sub, color, tc="white", fs=11):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.15",
                                fc=color, ec="none"))
    ax.text(x + w/2, y + (h*0.66 if sub else h/2), title, ha="center", va="center", fontsize=fs, weight="bold", color=tc)
    ax.text(x + w/2, y + h*0.3, sub, ha="center", va="center", fontsize=8.2, color=tc, wrap=True)

def arrow(x1, y1, x2, y2, label=""):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", lw=1.6, color="#444"))
    if label:
        ax.text((x1+x2)/2, (y1+y2)/2 + 0.17, label, ha="center", fontsize=7.5, color="#444")

ax.text(7, 6.85, "LeadPilot: Multi-Agent B2B Lead Qualification & Outreach (Sequential Orchestration)",
        ha="center", fontsize=13.5, weight="bold", color="#1F2A44")

box(0.2, 3.3, 1.9, 1.3, "Lead Inbox", "CSV / CRM export\n(webinar, forms,\nLinkedIn, events)", "#5B6B82")
agents = [("1. Research", "profile, pains, hook\n+ case study (RAG)", "#1E6FD9"),
          ("2. Qualification", "ICP score 0-100\nHot/Warm/Cold/DQ", "#0E9F8E"),
          ("3. Outreach\nWriter", "email + LinkedIn\ngrounded in KB (RAG)", "#7B4DD6"),
          ("4. Compliance\nReviewer", "policy + fact-check\nrevise loop (RAG)", "#D9822B"),
          ("5. Sales Ops\nRouter", "owner, priority,\nfollow-up, briefing", "#C2410C")]
xs = [2.6, 4.85, 7.1, 9.35, 11.6]
for (t, s, c), x in zip(agents, xs):
    box(x, 3.3, 2.0, 1.3, t, s, c)
arrow(2.15, 3.95, 2.58, 3.95)
for a, b in zip(xs[:-1], xs[1:]):
    arrow(a + 2.02, 3.95, b - 0.02, 3.95)

# Tools layer
tools_ = [("infer_pains()", 2.6), ("score_lead()\nICP rules", 4.85), ("pick_value_prop()", 7.1),
          ("check_outreach()\nauto_fix()", 9.35), ("assign_rep()\nfollow_up_plan()", 11.6)]
for t, x in tools_:
    box(x + 0.1, 1.75, 1.8, 0.85, t, "", "#E8EDF5", "#1F2A44", fs=8.5)
    arrow(x + 1.0, 3.28, x + 1.0, 2.64)
ax.text(0.25, 2.15, "Deterministic\ntools", fontsize=9, weight="bold", color="#1F2A44")

# LLM layer
ax.add_patch(FancyBboxPatch((2.6, 5.45), 11.0, 0.7, boxstyle="round,pad=0.05,rounding_size=0.15",
                            fc="#FFF4D6", ec="#E0B84A"))
ax.text(8.1, 5.8, "LLM layer: Groq GPT-OSS / Gemini / OpenAI / local Ollama · Pydantic-schema structured output · rule-based fallback",
        ha="center", va="center", fontsize=9, color="#6B4E00")
for x in xs:
    ax.plot([x + 1.0, x + 1.0], [4.62, 5.43], ls=":", color="#C9A227", lw=1.2)

# Outputs
box(0.2, 0.25, 3.2, 1.0, "Chroma: sales_kb", "product facts, case studies,\nobjection playbook", "#334155")
box(3.6, 0.25, 3.2, 1.0, "Chroma: policy_kb", "brand voice, claims rules,\nDPDP opt-out policy", "#475569")
box(7.0, 0.25, 3.2, 1.0, "Human-in-the-loop", "rep edits & approves in\nStreamlit UI · audit log", "#15803D")
box(10.4, 0.25, 3.4, 1.0, "n8n: Webhook → SMTP", "sends approved emails;\nbriefing + CSV outputs", "#1F2A44")
arrow(10.22, 0.75, 10.38, 0.75)
plt.savefig("docs/architecture.png", bbox_inches="tight", facecolor="white")
print("saved")
