"""
Uploads audio to Cloudflare R2 and sends via Twilio WhatsApp to both recipients.
"""

import os
import uuid
import boto3
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

# R2 (S3-compatible) client
s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["R2_ENDPOINT"],
    aws_access_key_id=os.environ["R2_ACCESS_KEY"],
    aws_secret_access_key=os.environ["R2_SECRET_KEY"],
    region_name="auto",
)

twilio_client = Client(
    os.environ["TWILIO_ACCOUNT_SID"],
    os.environ["TWILIO_AUTH_TOKEN"],
)

# Determine audio file extension (mp3 vs ogg) for proper Content-Type
def _content_type_for(path: str) -> str:
    ext = path.lower().rsplit(".", 1)[-1]
    return {
        "mp3": "audio/mpeg",
        "ogg": "audio/ogg",
        "m4a": "audio/mp4",
    }.get(ext, "audio/mpeg")


def upload_audio(audio_path: str) -> str:
    """Uploads to R2 and returns a public URL."""
    ext = audio_path.rsplit(".", 1)[-1]
    key = f"episodes/{uuid.uuid4()}.{ext}"
    
    with open(audio_path, "rb") as f:
        s3.put_object(
            Bucket=os.environ["R2_BUCKET"],
            Key=key,
            Body=f,
            ContentType=_content_type_for(audio_path),
            ContentDisposition="inline",
        )
    
    return f"{os.environ['R2_PUBLIC_URL']}/{key}"


def send_episode(audio_path: str, body_text: str) -> None:
    """
    Uploads audio and sends to both recipients on WhatsApp.
    Each recipient gets one text + one audio message.
    """
    audio_url = upload_audio(audio_path)
    print(f"   Uploaded: {audio_url}")
    
    recipients = [
        os.environ["WHATSAPP_NUMBER_THERESA"],
        os.environ["WHATSAPP_NUMBER_HUSBAND"],
    ]
    
    for recipient in recipients:
        # Send body text
        text_msg = twilio_client.messages.create(
            from_=os.environ["TWILIO_WHATSAPP_FROM"],
            to=recipient,
            body=body_text,
        )
        # Send audio attachment
        audio_msg = twilio_client.messages.create(
            from_=os.environ["TWILIO_WHATSAPP_FROM"],
            to=recipient,
            media_url=[audio_url],
        )
        print(f"   Sent to {recipient}: text={text_msg.sid}, audio={audio_msg.sid}")