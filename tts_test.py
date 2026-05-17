import os
import subprocess
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

pcm_chunks = []
for i, (speaker, line) in enumerate(script):
    print(f"Generating turn {i+1}/{len(script)}: {speaker}...")
    audio_generator = client.text_to_speech.convert(
        voice_id=voice_map[speaker],
        text=line,
        model_id="eleven_turbo_v2_5",
        output_format="pcm_44100",
    )
    pcm_chunks.append(b"".join(audio_generator))

pcm_bytes = b"".join(pcm_chunks)

output_path = "audio_output/test_episode.ogg"
subprocess.run(
    [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "s16le", "-ar", "44100", "-ac", "1", "-i", "pipe:0",
        "-c:a", "libopus", "-b:a", "64k", "-application", "voip",
        output_path,
    ],
    input=pcm_bytes,
    check=True,
)

print(f"\n✅ Saved {os.path.getsize(output_path):,} bytes to {output_path}")