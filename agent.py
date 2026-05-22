"""
Main orchestrator. Picks a pillar, researches it, writes the episode, delivers it.

Run:
    python agent.py
"""

import os
import uuid
from context_loaders import read_topic_notes, get_calendar_today
from datetime import date
from dotenv import load_dotenv

load_dotenv()

from script_writer import write_episode
from tts import synthesize
from delivery import send_episode, send_escalation
from search import research, extract_keywords
from memory import save_episode, recent_topics
from pillar_history import pick_pillar
from config import PILLARS, elio_age_description


def main():
    age_desc = elio_age_description()
    
    # ───── 1. Read context: Google Doc + Calendar ─────
    print("📄 Reading topic notes from Google Doc...")
    notes = read_topic_notes()
    if notes.last_updated:
        print(f"   Doc last updated: {notes.last_updated}")
    if notes.state_of_elio:
        print(f"   State of Elio: {len(notes.state_of_elio)} chars loaded")
    
    print("\n📅 Checking calendar...")
    events = get_calendar_today()
    if events:
        print(f"   {len(events)} events today:")
        for e in events:
            time_str = "all-day" if e["all_day"] else (e["start_time"] or "?")[:16]
            print(f"     - {e['summary']} ({time_str})")
    
    # ───── 2. Handle skip-today request ─────
    if notes.wants_skip:
        print("\n⏭️  User requested 'skip today' in topic notes. Exiting.")
        from delivery import twilio_client
        try:
            twilio_client.messages.create(
                from_=os.environ["TWILIO_WHATSAPP_FROM"],
                to=os.environ["WHATSAPP_NUMBER_THERESA"],
                body="🤖 Skipping today's episode per your topic notes. See you tomorrow!",
            )
        except Exception as e:
            print(f"   Couldn't send skip notification: {e}")
        return
    
    # ───── 3. Pick today's pillar (or use topic override) ─────
    if notes.has_topic_request:
        # User wrote a specific topic in the doc — use the first one
        override_topic = notes.topic_requests[0]
        print(f"\n📌 Topic override from doc: {override_topic[:100]}")
        # We still need a pillar for memory tracking — use research_news as 
        # a catch-all when topic is user-specified
        pillar = next(p for p in PILLARS if p["name"] == "research_news")
        forced_topic_hint = override_topic
    else:
        pillar = pick_pillar(PILLARS)
        forced_topic_hint = ""
        print(f"\n🎯 Pillar: {pillar['name']}")
        print(f"   ({pillar['description'][:100]}...)")
    
    # ───── 4. Build situational context from calendar ─────
    situational_context = _build_situational_context(events) if events else ""
    if situational_context:
        print(f"\n🗓️  Situational context: {situational_context}")
    
    # ───── 5. Research the pillar (or the override topic) ─────
    print("\n🔬 Researching...")
    recent_topic_list = recent_topics(days=30)
    if recent_topic_list:
        print(f"   Avoiding {len(recent_topic_list)} recent topics from memory")
    
    if forced_topic_hint:
        # When the user has specified a topic, augment the pillar description
        # so the research module focuses on what they asked for
        custom_pillar = {
            "name": pillar["name"],
            "description": f"{pillar['description']}\n\nUSER REQUEST: {forced_topic_hint}",
        }
        result = research(
            pillar=custom_pillar,
            recent_topics=recent_topic_list,
            age_description=age_desc,
        )
    else:
        result = research(
            pillar=pillar,
            recent_topics=recent_topic_list,
            age_description=age_desc,
        )
    
    if result is None:
        print("\n⚠️  Research failed. Sending escalation to WhatsApp.")
        send_escalation(pillar_name=pillar["name"])
        return
    
    print(f"\n📋 Topic: {result.topic_summary}")
    print(f"   {len(result.findings)} findings | actionable: {result.actionable[:60]}...")
    
    # ───── 6. Write the script with full context ─────
    print("\n✍️  Writing episode with Claude...")
    script = write_episode(
        result,
        state_of_elio=notes.state_of_elio,
        agent_notes=notes.agent_notes,
        situational_context=situational_context,
    )
    print(f"   Script: {len(script.split())} words")
    
    os.makedirs("audio_output", exist_ok=True)
    script_path = "audio_output/last_script.txt"
    with open(script_path, "w") as f:
        f.write(script)
    print(f"   Saved transcript: {script_path}")
    
    # ───── 7. Synthesize audio ─────
    print("\n🎙️  Generating audio with ElevenLabs...")
    audio_path = f"audio_output/episode_{uuid.uuid4().hex[:8]}.ogg"
    synthesize(script, audio_path)
    print(f"   Saved audio: {audio_path}")
    
    # ───── 8. Deliver to WhatsApp ─────
    print("\n📲 Sending to WhatsApp...")
    body = f"🎧 Today's episode: {result.topic_summary}"
    send_episode(audio_path, body)
    
    # ───── 9. Save to memory ─────
    print("\n💾 Saving to memory...")
    findings_text = "\n".join(
        f"- {f.claim} (Source: {f.source_name})" for f in result.findings
    )
    keywords = extract_keywords(result.topic_summary, findings_text)
    print(f"   Keywords: {keywords}")
    
    episode_id = save_episode(
        pillar=pillar["name"],
        topic_summary=result.topic_summary,
        transcript=script,
        sources=result.findings,
        keywords=keywords,
        word_count=len(script.split()),
    )
    
    print(f"\n✅ Done! Episode {episode_id} for {date.today()} ({pillar['name']}).")


def _build_situational_context(events: list[dict]) -> str:
    """Builds a short natural-language description of today's calendar events."""
    if not events:
        return ""
    
    summaries = []
    for e in events:
        if e["all_day"]:
            summaries.append(f"{e['summary']} (all day)")
        else:
            # Extract just HH:MM from ISO timestamp
            time_str = (e["start_time"] or "")[11:16]
            summaries.append(f"{e['summary']} at {time_str}")
    
    return "Today's calendar: " + "; ".join(summaries)

if __name__ == "__main__":
    main()
