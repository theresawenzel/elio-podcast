import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()

client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])

# Hardcoded test dialogue — feel free to edit
script = [
    ("ALEX", "Hey Lauren — quick question. Why do 11-month-olds suddenly become obsessed with putting things into containers and dumping them back out?"),
    ("LAUREN", "Oh, the dump-and-fill phase. It's actually one of my favorite milestones."),
    ("ALEX", "There's a name for it?"),
    ("LAUREN", "Yeah — developmental psychologists call it a 'container schema.' Babies are figuring out that objects can exist inside other objects, and they have to test it about four hundred times to be sure."),
    ("ALEX", "Four hundred times. So when Elio empties the laundry basket for the fifteenth time today..."),
    ("LAUREN", "He's doing developmental work. Annoying, sure, but developmental."),
]

voice_map = {
    "ALEX": os.environ["ELEVENLABS_VOICE_ALEX"],
    "LAUREN": os.environ["ELEVENLABS_VOICE_LAUREN"],
}

audio_chunks = []
for i, (speaker, line) in enumerate(script):
    print(f"Generating turn {i+1}/{len(script)}: {speaker}...")
    audio_generator = client.text_to_speech.convert(
        voice_id=voice_map[speaker],
        text=line,
        model_id="eleven_turbo_v2_5",
        output_format="mp3_44100_128",
    )
    audio_bytes = b"".join(audio_generator)
    audio_chunks.append(audio_bytes)

final_audio = b"".join(audio_chunks)

output_path = "audio_output/test_episode.mp3"
with open(output_path, "wb") as f:
    f.write(final_audio)

print(f"\n✅ Saved {len(final_audio):,} bytes to {output_path}")