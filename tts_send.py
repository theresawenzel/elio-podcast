import os
import uuid
import boto3
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

audio_path = "audio_output/test_episode.ogg"

# Upload to Cloudflare R2
print("Uploading audio to Cloudflare R2...")
s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["R2_ENDPOINT"],
    aws_access_key_id=os.environ["R2_ACCESS_KEY"],
    aws_secret_access_key=os.environ["R2_SECRET_KEY"],
    region_name="auto",
)

key = f"episodes/{uuid.uuid4()}.ogg"
with open(audio_path, "rb") as f:
    s3.put_object(
        Bucket=os.environ["R2_BUCKET"],
        Key=key,
        Body=f,
        ContentType="audio/ogg",
        ContentDisposition="inline",
    )
audio_url = f"{os.environ['R2_PUBLIC_URL']}/{key}"
print(f"Audio URL: {audio_url}")

# Send via Twilio to both phones
client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])

recipients = [
    os.environ["WHATSAPP_NUMBER_THERESA"],
    os.environ["WHATSAPP_NUMBER_HUSBAND"],
]

for recipient in recipients:
    print(f"Sending to {recipient}...")
    text_msg = client.messages.create(
        from_=os.environ["TWILIO_WHATSAPP_FROM"],
        to=recipient,
        body="🎧 Test episode — dump-and-fill phase",
    )
    print(f"  ✅ text SID={text_msg.sid}")
    audio_msg = client.messages.create(
        from_=os.environ["TWILIO_WHATSAPP_FROM"],
        to=recipient,
        media_url=[audio_url],
    )
    print(f"  ✅ audio SID={audio_msg.sid}")

print("\n🚀 Done! Check your phones.")