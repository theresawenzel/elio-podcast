"""
ElevenLabs two-host TTS. Parses ALEX:/LAUREN: scripts and synthesizes audio.
"""

import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()

client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])

VOICE_MAP = {
    "ALEX": os.environ["ELEVENLABS_VOICE_ALEX"],
    "LAUREN": os.environ["ELEVENLABS_VOICE_LAUREN"],
}


def parse_script(script_text: str) -> list[tuple[str, str]]:
    """
    Parses 'ALEX: ...\nLAUREN: ...' into [(speaker, line), ...].
    Forgiving about extra whitespace and blank lines.
    """
    turns = []
    for raw_line in script_text.strip().split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("ALEX:"):
            turns.append(("ALEX", line[len("ALEX:"):].strip()))
        elif line.startswith("LAUREN:"):
            turns.append(("LAUREN", line[len("LAUREN:"):].strip()))
        # Lines that don't match either prefix are silently skipped
        # (handles stray blank lines, occasional preamble Claude slips in, etc.)
    return turns


def synthesize(script_text: str, output_path: str) -> str:
    """
    Generates an MP3 from a two-host script.
    Returns the output path.
    """
    turns = parse_script(script_text)
    if not turns:
        raise ValueError("Script had no parseable ALEX/LAUREN lines")
    
    chunks = []
    for i, (speaker, line) in enumerate(turns):
        print(f"   Turn {i+1}/{len(turns)} ({speaker}, {len(line)} chars)")
        audio_generator = client.text_to_speech.convert(
            voice_id=VOICE_MAP[speaker],
            text=line,
            model_id="eleven_turbo_v2_5",
            output_format="opus_48000_64",
        )
        chunks.append(b"".join(audio_generator))
    
    audio_bytes = b"".join(chunks)
    with open(output_path, "wb") as f:
        f.write(audio_bytes)
    
    return output_path