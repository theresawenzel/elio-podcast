"""
Configuration for the Elio podcast agent.
Edit this file to update Elio's age math, pillars, or host names.
"""

from datetime import date

# ───── Elio ─────
ELIO_BIRTHDATE = date(2025, 6, 13)
ELIO_NAME = "Elio"
# ───── Family & language context ─────
# This is passed to Claude on every episode so the dialogue reflects
# the actual family Elio is growing up in — not a generic baby's family.

FAMILY_CONTEXT = """
Elio's parents:
- Theresa (mother): German native speaker, speaks German with Elio.
- Husband (father): Portuguese native speaker, speaks English with Elio. 
  Portuguese has not yet been introduced as a third language by either parent.

Elio's extended family:
- Maternal grandmother and aunts/uncles (Theresa's side): speak German with Elio.
- Paternal grandmother and aunt (husband's side): speak Portuguese with Elio.

Language exposure pattern at this stage:
- Daily: German (from Theresa) and English (from husband).
- Periodic (when extended family visits or via video calls): German (Theresa's family) and Portuguese (husband's family).
- Theresa and husband speak English to each other.
- This is a OPOL-with-overlap pattern: Mom-German, Dad-English, with Portuguese 
  arriving from paternal grandmother/aunt rather than from a parent.
"""

def elio_age_months(today: date | None = None) -> int:
    """
    Returns Elio's current age in whole months.
    Used to pass age-specific context to Claude on every run.
    """
    today = today or date.today()
    months = (today.year - ELIO_BIRTHDATE.year) * 12 + (today.month - ELIO_BIRTHDATE.month)
    if today.day < ELIO_BIRTHDATE.day:
        months -= 1
    return months

def elio_age_description(today: date | None = None) -> str:
    """
    Human-friendly age description for use in prompts.
    e.g. "11 months old" or "13 months old (just past his first birthday)"
    """
    months = elio_age_months(today)
    if months < 12:
        return f"{months} months old"
    elif months == 12:
        return "12 months old (just turned 1)"
    else:
        years = months // 12
        extra_months = months % 12
        if extra_months == 0:
            return f"{years} years old"
        return f"{years} years and {extra_months} months old ({months} months total)"

# ───── Hosts ─────
HOSTS = {
    "ALEX": {
        "persona": "research-leaning. Cites studies, frames the 'why' behind behaviors. "
                   "Slightly skeptical of pop-parenting trends, grounded in developmental science.",
    },
    "LAUREN": {
        "persona": "practical and warm. Translates research into 'what does this look like at "
                   "6pm with a tired baby.' Asks the questions the listener would ask. "
                   "Often pushes back on Alex when something doesn't match real-world parenting.",
    },
}

# ───── Topic pillars ─────
PILLARS = [
    {
        "name": "developmental_milestones",
        "description": "Motor, language, cognitive, and social milestones relevant to Elio's "
                       "current age window — what's happening NOW plus what to watch for in "
                       "the next 2-3 months.",
    },
    {
        "name": "bilingual_trilingual",
        "description": "Raising a child with English, German, and Italian. OPOL (One Parent One "
                       "Language) strategies, code-switching research, milestone differences in "
                       "multilingual kids, building vocabulary in non-dominant languages.",
    },
    {
        "name": "sleep_feeding_routines",
        "description": "Age-appropriate sleep patterns, feeding transitions, daily routine "
                       "design. At 11-14 months: night weaning, dropping bottles, finger foods, "
                       "transitioning to toddler eating.",
    },
    {
        "name": "working_parent_logistics",
        "description": "Mental load, time management, partnership dynamics, daycare/childcare "
                       "transitions, balancing career and parenting. Especially relevant for "
                       "dual-career households.",
    },
    {
        "name": "behavioral_emotional",
        "description": "Attachment, emotional regulation, early social development, separation "
                       "anxiety, tantrum precursors, what babies understand about feelings.",
    },
    {
        "name": "research_news",
        "description": "Wildcard pillar — only used when web search surfaces genuinely new "
                       "parenting research, AAP guidance updates, or studies relevant to "
                       "Elio's age. Otherwise the rotation skips this.",
    },
]

# ───── Episode constraints ─────
TARGET_WORD_COUNT = 1500  # ~10 min spoken at conversational pace
MIN_WORD_COUNT = 1200
MAX_WORD_COUNT = 1800