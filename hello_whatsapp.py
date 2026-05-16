import os
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])

recipients = [
    os.environ["WHATSAPP_NUMBER_THERESA"],
    os.environ["WHATSAPP_NUMBER_HUSBAND"],
]

for recipient in recipients:
    message = client.messages.create(
        from_=os.environ["TWILIO_WHATSAPP_FROM"],
        to=recipient,
        body="Hello from the Elio podcast agent 👋"
    )
    print(f"Sent to {recipient}: SID={message.sid}")

print("Done!")