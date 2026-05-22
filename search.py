"""
Research module. Uses Claude with web search to find fresh material
on today's pillar, then critiques its own findings.

Public functions:
    research(pillar, recent_topics, elio_age) -> ResearchResult | None
        Runs the full research-and-critique loop. Returns synthesized findings
        if a sufficient set was found within max_attempts, otherwise None.
"""

import os
import json
import re
from dataclasses import dataclass, field
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL = "claude-sonnet-4-5"
MAX_RESEARCH_ATTEMPTS = 3
WEB_SEARCH_MAX_USES = 5   # Per attempt — caps cost per episode


@dataclass
class Finding:
    claim: str
    source_name: str
    source_url: str = ""
    source_type: str = "unknown"   # peer_reviewed | guideline | popular_press | forum | unknown
    recency: str = "unknown"        # last_12mo | last_5yr | older | unknown


@dataclass
class ResearchResult:
    topic_summary: str       # 1-2 sentence framing of the day's angle
    findings: list[Finding]  # The substantive claims to inform the episode
    actionable: str          # Concrete thing the parents can try this week
    pillar_name: str
    notes: str = ""          # Optional notes from Claude (e.g. caveats, related areas)


# ───── Prompts ─────

RESEARCH_SYSTEM = """You are a researcher for a daily parenting podcast. The audience is two well-read, technical, working parents (Theresa and her husband) raising their son Elio, currently {age_description}. They have an Anthropic-built AI agent producing this podcast. They've read the major parenting books. They are NOT looking for "Baby Sleep 101" — they want fresh angles, recent research, contrarian findings, and source-backed insights.

Your job: use the web_search tool to find compelling, source-backed material for today's episode on the following pillar:

PILLAR: {pillar_name}
PILLAR DESCRIPTION: {pillar_description}

# Research priorities

You should be EXPLORATORY in your selection — surface emerging findings, contested debates, or counter-intuitive results when they exist. Don't default to safest-mainstream framings.

Weight sources roughly in this order:
1. **Peer-reviewed research** (PubMed, journal articles, university research) — highest authority
2. **Major professional guidelines** (AAP, ZERO TO THREE, WHO, ACOG)
3. **Reputable popular press** (NYT parenting coverage, Atlantic, Vox, well-cited science journalists)
4. **Practitioner pieces** (developmental psychologists, pediatricians with credentials)
5. Avoid: parenting blogs, anecdotal forums, Pinterest-style content

When sources conflict, that's INTERESTING — surface the disagreement.

# What to look for

A great episode needs:
- A central angle that can be stated as a headline ("Here's what we know about X")
- 3-5 specific findings/studies/claims with attribution
- At least one counter-intuitive or surprising element (a finding that complicates the obvious view, an edge case, a contrarian voice)
- Specificity to {child_name}'s age window ({age_description})
- One concrete actionable parents can try this week

# Topics already covered recently — AVOID repeating these

{recent_topics_str}

# What to return

After your research is complete, output a single JSON object inside <output> tags with this exact shape (no other text outside the tags):

<output>
{{
  "topic_summary": "1-2 sentence headline framing of today's angle",
  "findings": [
    {{
      "claim": "Specific claim or finding in 1-2 sentences",
      "source_name": "e.g. 'Pediatrics 2024 study by University of Michigan' or 'AAP guidelines (2023)'",
      "source_url": "https://...",
      "source_type": "peer_reviewed | guideline | popular_press | practitioner | unknown",
      "recency": "last_12mo | last_5yr | older | unknown"
    }}
  ],
  "actionable": "One concrete thing Theresa and her husband can try this week with {child_name}",
  "notes": "Any caveats, related areas, or things you couldn't find good sources for"
}}
</output>

Make sure the JSON is valid (no trailing commas, properly escaped quotes inside strings).
"""


CRITIQUE_SYSTEM = """You are critiquing research findings for a parenting podcast. Decide whether the findings are sufficient to support a compelling 10-minute episode, or whether more research is needed.

Use this rubric — answer YES or NO for each:

1. Does the research have at least 3 distinct findings with attribution?
2. At least one source from a peer-reviewed journal, major guideline body, or credible practitioner?
3. At least one piece of evidence that complicates or counters the obvious view? (i.e. it's not just "X is good, do more X")
4. Specific to the child's age window, not generic across all infancy?
5. The "actionable" is concrete (a specific thing to try this week), not abstract ("be present with your child")?
6. The findings collectively support an INTERESTING episode, not a boring one?

Return a single JSON object inside <output> tags:

<output>
{{
  "is_sufficient": true | false,
  "rubric": {{
    "has_3_findings": true | false,
    "has_authoritative_source": true | false,
    "has_complicating_evidence": true | false,
    "age_specific": true | false,
    "actionable_concrete": true | false,
    "compelling_overall": true | false
  }},
  "reason": "1-2 sentence summary of strengths and weaknesses",
  "what_to_improve": "If insufficient: specific guidance for the next research attempt (e.g. 'search for X angle' or 'find counter-evidence on Y')"
}}
</output>
"""


# ───── Helpers ─────

def _extract_json(text: str) -> dict:
    """Pulls a JSON object out of <output>...</output> tags, falling back to first {...} block."""
    match = re.search(r"<output>\s*(\{.*?\})\s*</output>", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    # Fallback: find any JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON found in Claude response")
    return json.loads(match.group(0))


def _format_recent_topics(recent_topics: list[str]) -> str:
    if not recent_topics:
        return "(None yet — this is one of the first episodes.)"
    return "\n".join(f"- {t}" for t in recent_topics)


# ───── Single research attempt ─────

def _single_research(
    pillar: dict,
    recent_topics: list[str],
    age_description: str,
    child_name: str,
    refinement_hint: str = "",
) -> ResearchResult | None:
    """One research call. Returns ResearchResult or None if parsing fails."""
    system = RESEARCH_SYSTEM.format(
        pillar_name=pillar["name"],
        pillar_description=pillar["description"],
        age_description=age_description,
        child_name=child_name,
        recent_topics_str=_format_recent_topics(recent_topics),
    )
    user_msg = f"Research and return findings."
    if refinement_hint:
        user_msg += f"\n\nGuidance for this attempt based on previous critique:\n{refinement_hint}"
    
    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": WEB_SEARCH_MAX_USES,
        }],
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    
    # Concatenate all text blocks from the response
    text = "".join(
        block.text for block in response.content if hasattr(block, "text")
    )
    
    try:
        data = _extract_json(text)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"   ⚠️ Failed to parse research JSON: {e}")
        return None
    
    findings = [
        Finding(
            claim=f.get("claim", ""),
            source_name=f.get("source_name", ""),
            source_url=f.get("source_url", ""),
            source_type=f.get("source_type", "unknown"),
            recency=f.get("recency", "unknown"),
        )
        for f in data.get("findings", [])
    ]
    
    return ResearchResult(
        topic_summary=data.get("topic_summary", ""),
        findings=findings,
        actionable=data.get("actionable", ""),
        pillar_name=pillar["name"],
        notes=data.get("notes", ""),
    )


# ───── Critique ─────

def _critique(result: ResearchResult) -> dict:
    """Evaluates whether the research is sufficient. Returns dict with is_sufficient + reason."""
    findings_summary = "\n".join(
        f"- {f.claim} [{f.source_name}, {f.source_type}, {f.recency}]"
        for f in result.findings
    )
    user_msg = f"""Topic summary: {result.topic_summary}

Findings:
{findings_summary}

Actionable: {result.actionable}

Notes: {result.notes}

Evaluate this research against the rubric."""
    
    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=CRITIQUE_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = "".join(b.text for b in response.content if hasattr(b, "text"))
    
    try:
        return _extract_json(text)
    except (ValueError, json.JSONDecodeError):
        # If critique fails to parse, be conservative — assume insufficient
        return {
            "is_sufficient": False,
            "reason": "Critique response failed to parse",
            "what_to_improve": "Re-run research with broader scope",
        }


# ───── Public entry point ─────

def research(
    pillar: dict,
    recent_topics: list[str],
    age_description: str,
    child_name: str = "Elio",
) -> ResearchResult | None:
    """
    Runs the research-and-critique loop. Returns a sufficient ResearchResult,
    or None if no sufficient result could be found within MAX_RESEARCH_ATTEMPTS.
    """
    refinement_hint = ""
    
    for attempt in range(1, MAX_RESEARCH_ATTEMPTS + 1):
        print(f"   🔍 Research attempt {attempt}/{MAX_RESEARCH_ATTEMPTS}...")
        result = _single_research(
            pillar=pillar,
            recent_topics=recent_topics,
            age_description=age_description,
            child_name=child_name,
            refinement_hint=refinement_hint,
        )
        
        if result is None:
            print(f"      ⚠️ Attempt {attempt} produced unparseable output")
            refinement_hint = "Previous attempt produced invalid JSON. Be careful with formatting."
            continue
        
        verdict = _critique(result)
        print(f"      Critique: {verdict.get('reason', '(no reason given)')}")
        
        if verdict.get("is_sufficient"):
            print(f"   ✅ Research sufficient on attempt {attempt}")
            return result
        
        refinement_hint = verdict.get("what_to_improve", "Find more compelling material.")
    
    print(f"   ❌ Could not find sufficient research after {MAX_RESEARCH_ATTEMPTS} attempts")
    return None

KEYWORD_EXTRACTION_SYSTEM = """You are extracting topic keywords from a podcast episode for future deduplication.

Return a JSON array of 3-7 short topic keywords (lowercase, underscored, specific). 
Keywords should be specific enough that they wouldn't accidentally match unrelated future episodes.

Good keywords: "object_permanence", "german_opol_strategy", "night_weaning_11_months", "stranger_anxiety_peak", "code_switching_research"
Bad keywords: "babies", "language", "sleep" (too generic), "parenting" (too broad)

Return ONLY a JSON array inside <output> tags, like:
<output>["keyword_one", "keyword_two", "keyword_three"]</output>
"""


def extract_keywords(topic_summary: str, findings_text: str) -> list[str]:
    """Pulls 3-7 topic keywords from a research result. Used for memory storage."""
    user_msg = f"Topic: {topic_summary}\n\nFindings:\n{findings_text}\n\nExtract keywords."
    response = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system=KEYWORD_EXTRACTION_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = "".join(b.text for b in response.content if hasattr(b, "text"))
    try:
        match = re.search(r"<output>\s*(\[.*?\])\s*</output>", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        # Fallback
        match = re.search(r"\[.*?\]", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except (ValueError, json.JSONDecodeError):
        pass
    return []   # Return empty list rather than crashing — keywords are nice-to-have, not critical