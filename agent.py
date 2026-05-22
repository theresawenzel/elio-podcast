"""
Main orchestrator. Picks a pillar, researches it, writes the episode, delivers it.

Run:
    python agent.py
"""

import os
import uuid
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
    
    # ───── 1. Pick today's pillar ─────
    pillar = pick_pillar(PILLARS)
    print(f"📅 Elio is {age_desc}")
    print(f"🎯 Pillar: {pillar['name']}")
    print(f"   ({pillar['description'][:100]}...)")
    print()
    
# ───── 2. Research the pillar ─────
    print("🔬 Researching...")
    recent_topic_list = recent_topics(days=30)
    if recent_topic_list:
        print(f"   Avoiding {len(recent_topic_list)} recent topics from memory")
    result = research(
        pillar=pillar,
        recent_topics=recent_topic_list,
        age_description=age_desc,
    )
    
    if result is None:
        # ───── Escalation path: couldn't find fresh material ─────
        print("\n⚠️  Research failed. Sending escalation to WhatsApp.")
        send_escalation(pillar_name=pillar["name"])
        return
    
    print(f"\n📋 Topic: {result.topic_summary}")
    print(f"   {len(result.findings)} findings | actionable: {result.actionable[:60]}...")
    
    # ───── 3. Write the script ─────
    print("\n✍️  Writing episode with Claude...")
    script = write_episode(result)
    print(f"   Script: {len(script.split())} words")
    
    # Save the transcript for debugging / review
    os.makedirs("audio_output", exist_ok=True)
    script_path = "audio_output/last_script.txt"
    with open(script_path, "w") as f:
        f.write(script)
    print(f"   Saved transcript: {script_path}")
    
    # ───── 4. Synthesize audio ─────
    print("\n🎙️  Generating audio with ElevenLabs...")
    audio_path = f"audio_output/episode_{uuid.uuid4().hex[:8]}.ogg"
    synthesize(script, audio_path)
    print(f"   Saved audio: {audio_path}")
    
    # ───── 5. Deliver to WhatsApp ─────
    print("\n📲 Sending to WhatsApp...")
    body = f"🎧 Today's episode: {result.topic_summary}"
    send_episode(audio_path, body)
    
    # ───── 6. Save the episode to memory ─────
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


if __name__ == "__main__":
    main()