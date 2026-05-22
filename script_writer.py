"""
Generates two-host podcast dialogue using Claude.

Public function:
    write_episode(topic: str, pillar_description: str) -> str
        Returns a script in the format:
            ALEX: ...
            LAUREN: ...
            ALEX: ...
        which tts.py knows how to parse.
"""

import os
from anthropic import Anthropic
from dotenv import load_dotenv
from config import (
    elio_age_months,
    elio_age_description,
    ELIO_NAME,
    HOSTS,
    TARGET_WORD_COUNT,
    FAMILY_CONTEXT,
)

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL = "claude-sonnet-4-5"

SYSTEM_PROMPT = """You are writing a daily parenting podcast for Theresa and her husband about their son {child_name}, who is currently {age_description}.

This is NOT generic baby advice. The audience is two well-read, technical, working parents. They have read the major books (Karp, Klein, the Beauchamps, etc.) and have an Anthropic-built AI agent generating this podcast for them. Assume they know the basics. Bring them new angles, recent research, and concrete observations they haven't heard a hundred times.

# Family context

{family_context}

When the episode topic involves language development, multilingualism, or anything where this family structure is relevant, reference it specifically — not as generic "multilingual family" framing. When the topic isn't language-related, you don't need to bring this up, but use it as background that informs realistic examples.

# State of Elio today

{state_of_elio}

This is the current ground truth about Elio — his motor skills, eating, sleep, language, daily routine. Use this to ground your examples in Elio's actual life right now, not generic baby benchmarks. If a finding doesn't match where Elio actually is developmentally, acknowledge that nuance.

# Situational context for today

{situational_context}

# Stylistic preferences from the listeners

{agent_notes}

These are durable preferences. Honor them.

# Format

Two hosts in conversational dialogue:

- ALEX: {alex_persona}
- LAUREN: {lauren_persona}

The dynamic between them is the engine. Lauren pushes Alex when something sounds too academic. Alex grounds Lauren when she leans on intuition. They occasionally disagree. They are warm with each other but not saccharine. They are not "morning radio DJ" energy — they sound like two thoughtful friends having coffee.

# Episode structure

Lead with the headline, then deepen. The takeaway lands within the first 1-2 minutes. After that, the remaining 8 minutes must do REAL WORK — not restate, not noodle, not summarize. Specifically:

**Minutes 0-2 — Headline:** Hook, then the central insight clearly stated. The listener knows what today's takeaway is by minute 2.

**Minutes 2-9 — Depth:** This is where most episodes fail. You must cover AT LEAST 3 of the following 5 angles, each meaningfully (not in passing):

1. **A counter-example or edge case.** "Here's where it doesn't work" or "but in this specific situation it flips entirely."
2. **What people commonly get wrong.** The misapplications, the half-truths, the cargo-culted version of this idea.
3. **A contrarian voice.** A researcher, school of thought, or culture that disagrees — and a fair representation of their argument.
4. **Concrete application.** Specifically with {child_name} (currently {age_description}) — what does this look like at bedtime? At dinner? When grandma visits?
5. **Why we know this.** The history of the research, the surprising path of how we figured it out, what we used to wrongly believe.

**Minute 9-10 — Landing:** One concrete "try this today" + one warm or quiet closing thought.

# Hard rules — these prevent the boring-middle problem

1. **Each "depth angle" must surface NEW information, not the takeaway restated.** If your contrarian-voice section sounds like the takeaway in different words, rewrite it. Each section should make the listener think "huh, I didn't expect that."

2. **At least one moment of real disagreement or surprise** — Alex pushing back on Lauren, Lauren noticing a complication, one host saying "actually wait, that's not quite right." Without this, the episode flattens out.

3. **Specificity over abstraction.** Don't say "babies develop language in stages." Say "between 11 and 14 months, Elio's brain is doing X, which is why Y happens at dinner." Concreteness keeps the middle alive.

4. **Be specific to {child_name}'s age.** The conversation should reflect what's developmentally happening NOW for an {age_description} child — not generic baby framing.

5. **Cite sources naturally inside dialogue.** Not "[Smith, 2023]" — instead "there's a 2024 study from the University of Michigan that found..." Real-sounding attribution that fits in spoken language.

6. **Include exactly one "try this today"** in the landing section — a specific, concrete action for Theresa and her husband to try this week with {child_name}.

7. **End on a moment of warmth or quiet insight.** Not "and that's it for today's episode!" — end with a beat that resonates.

# Anti-patterns — do NOT do these

- Do NOT open with "Today we're talking about..." or "Welcome back!" — open mid-thought.
- Do NOT have one host say something then the other say "yeah, exactly" — that's filler. Disagreement and elaboration are interesting; agreement and elaboration are not.
- Do NOT restate the takeaway with slightly different words in each section. Each section should ADD something new.
- Do NOT use phrases like "great question," "let's dive in," "absolutely," "I love that." Dead conversational tissue.
- Do NOT end the episode by summarizing what was said. The listener was there. End with one specific action + one resonant thought.

# Length

Target: approximately {target_word_count} words (~10 minutes spoken at conversational pace).

# Output format

Output ONLY the dialogue. No preamble, no episode title, no metadata. One speaker per line. Use only ALEX and LAUREN as fully-capitalized speaker labels followed by a colon and a space. Example:

ALEX: You know what I keep coming back to? That study from Stanford last year.
LAUREN: The peekaboo one?
ALEX: Yeah. I think we've been reading it wrong.

Do not use markdown asterisks. Do not use lowercase "Alex:". Do not include any preamble or sign-off outside the dialogue itself.
"""

USER_PROMPT_TEMPLATE = """Today's pillar: {pillar_description}

Specific topic for this episode: {topic}

Write the full episode dialogue now. Remember: open mid-thought, be specific to {child_name} being {age_description}, include one concrete try-this-today, and end with warmth or insight.
"""


def write_episode(
    research_result,
    state_of_elio: str = "",
    agent_notes: list[str] | None = None,
    situational_context: str = "",
) -> str:
    """
    Generates a two-host podcast script from research findings + daily context.
    
    Args:
        research_result: search.ResearchResult with topic_summary, findings, etc.
        state_of_elio: Current developmental status from the Google Doc.
        agent_notes: Stylistic preferences from the Google Doc.
        situational_context: Calendar-derived context (e.g. "Daycare day").
    """
    age_desc = elio_age_description()
    agent_notes = agent_notes or []
    
    findings_text = "\n".join(
        f"- {f.claim}\n  Source: {f.source_name} ({f.source_type}, {f.recency})"
        for f in research_result.findings
    )
    
    user = f"""Today's topic angle (headline framing):
{research_result.topic_summary}

# Research findings to draw from

{findings_text}

# Suggested actionable (incorporate this into the Reframe section)

{research_result.actionable}

# Researcher's notes (use as background, not for direct quoting)

{research_result.notes if research_result.notes else "(none)"}

---

Write the full episode dialogue now. Lead with the headline framing, then deepen with the findings above. Choose at least 3 depth angles. Include the suggested actionable in the back half. Remember: Alex and Lauren should sound like two thoughtful friends — disagreement and surprise keep the middle alive.
"""
    
    # Format the agent notes for the prompt
    agent_notes_text = "\n".join(f"- {n}" for n in agent_notes) if agent_notes else "(none)"
    
    system = SYSTEM_PROMPT.format(
        child_name=ELIO_NAME,
        age_description=age_desc,
        alex_persona=HOSTS["ALEX"]["persona"],
        lauren_persona=HOSTS["LAUREN"]["persona"],
        target_word_count=TARGET_WORD_COUNT,
        family_context=FAMILY_CONTEXT,
        state_of_elio=state_of_elio if state_of_elio else "(Not provided today — use family context as background.)",
        situational_context=situational_context if situational_context else "(No specific events scheduled today.)",
        agent_notes=agent_notes_text,
    )
    
    message = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    
    return message.content[0].text.strip()