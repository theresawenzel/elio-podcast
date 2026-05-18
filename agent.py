"""
Main orchestrator. Generates one podcast episode and delivers it.

Run:
    python agent.py

For Phase 3: hardcoded topic + pillar.
For Phase 4: pillar rotation, research loop, memory.
"""

import os
import uuid
from dotenv import load_dotenv

load_dotenv()

from script_writer import write_episode
from tts import synthesize
from delivery import send_episode
from config import PILLARS, elio_age_description


def main():
    # ───── For Phase 3: hardcode a topic ─────
    # Picking the bilingual pillar since it's likely under-covered in mainstream content
    pillar = next(p for p in PILLARS if p["name"] == "bilingual_trilingual")
    topic = (
        "Whether code-switching between languages within a single sentence "
        "helps or harms vocabulary development in babies under 18 months — "
        "what the research actually says vs. what most parents are told."
    )
    
    print(f"📅 Elio is {elio_age_description()}")
    print(f"🎯 Pillar: {pillar['name']}")
    print(f"📝 Topic: {topic[:80]}...")
    print()
    
    # ───── 1. Generate script ─────
    print("✍️  Writing episode with Claude...")
    script = write_episode(topic, pillar["description"])
    print(f"   Script: {len(script.split())} words")
    
    # Save the script locally for debugging / review
    script_path = "audio_output/last_script.txt"
    os.makedirs("audio_output", exist_ok=True)
    with open(script_path, "w") as f:
        f.write(script)
    print(f"   Saved transcript: {script_path}")
    
    # ───── 2. Synthesize audio ─────
    print("\n🎙️  Generating audio with ElevenLabs...")
    audio_path = f"audio_output/episode_{uuid.uuid4().hex[:8]}.ogg"
    synthesize(script, audio_path)
    print(f"   Saved audio: {audio_path}")
    
    # ───── 3. Deliver to WhatsApp ─────
    print("\n📲 Sending to WhatsApp...")
    body = f"🎧 Today's episode: {topic}"
    send_episode(audio_path, body)
    
    print("\n✅ Done! Episode delivered.")


if __name__ == "__main__":
    main()