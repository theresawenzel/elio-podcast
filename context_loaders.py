"""
Reads context from Google Doc + Google Calendar for the day's episode.

Public functions:
    read_topic_notes() -> TopicNotes
        Reads the structured topic notes doc and returns parsed sections.
    
    get_calendar_today() -> list[dict]
        Returns today's events from Google Calendar. Empty list if unavailable.
"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]

CREDENTIALS_PATH = Path("credentials.json")
TOKEN_PATH = Path("token.json")


@dataclass
class TopicNotes:
    """Parsed sections from the topic notes doc."""
    state_of_elio: str = ""
    topic_requests: list[str] = field(default_factory=list)
    agent_notes: list[str] = field(default_factory=list)
    last_updated: str = ""
    raw_text: str = ""
    
    @property
    def has_topic_request(self) -> bool:
        return any(
            r.strip() and r.strip().lower() not in ("(empty)", "empty", "-")
            for r in self.topic_requests
        )
    
    @property
    def wants_skip(self) -> bool:
        return any(
            "skip" in r.lower() and "today" in r.lower()
            for r in self.topic_requests
        )


def _get_creds():
    creds = None
    if env_token := os.environ.get("GOOGLE_TOKEN_JSON"):
        try:
            creds = Credentials.from_authorized_user_info(json.loads(env_token), SCOPES)
        except Exception as e:
            print(f"   Failed to load GOOGLE_TOKEN_JSON: {e}")
    if not creds and TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except Exception as e:
            print(f"   Failed to load token.json: {e}")
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json())
        except Exception as e:
            print(f"   Failed to refresh token: {e}")
            creds = None
    if not creds:
        if not CREDENTIALS_PATH.exists():
            print(f"   No credentials.json - Google integration disabled")
            return None
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
        creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
    return creds


def _doc_to_text(doc):
    parts = []
    for elem in doc.get("body", {}).get("content", []):
        para = elem.get("paragraph")
        if not para:
            continue
        for run in para.get("elements", []):
            text_run = run.get("textRun")
            if text_run:
                parts.append(text_run.get("content", ""))
    return "".join(parts)


def _parse_topic_notes(raw: str) -> TopicNotes:
    """Parses doc by section titles (Google Docs strips markdown headers)."""
    notes = TopicNotes(raw_text=raw)
    
    if m := re.search(r"Last updated:\s*(\d{4}-\d{2}-\d{2})", raw):
        notes.last_updated = m.group(1)
    
    section_titles = ["State of Elio", "Topic Requests", "Notes for the agent"]
    
    positions = {}
    for title in section_titles:
        pattern = rf"(?im)^\s*{re.escape(title)}\s*$"
        m = re.search(pattern, raw)
        if m:
            positions[title] = m.end()
    
    sorted_sections = sorted(positions.items(), key=lambda x: x[1])
    
    for i, (title, start_pos) in enumerate(sorted_sections):
        if i + 1 < len(sorted_sections):
            next_title = sorted_sections[i + 1][0]
            next_match = re.search(rf"(?im)^\s*{re.escape(next_title)}\s*$", raw[start_pos:])
            end_pos = start_pos + next_match.start() if next_match else len(raw)
        else:
            end_pos = len(raw)
        
        body = raw[start_pos:end_pos].strip()
        body = re.sub(r"^\s*\(.*?\)\s*\n+", "", body, flags=re.DOTALL, count=1)
        body = re.sub(r"^\s*Last updated:.*\n+", "", body, flags=re.MULTILINE)
        body = body.strip()
        
        if title == "State of Elio":
            notes.state_of_elio = body
        elif title == "Topic Requests":
            notes.topic_requests = _extract_lines(body)
        elif title == "Notes for the agent":
            notes.agent_notes = _extract_lines(body)
    
    return notes


def _extract_lines(text: str) -> list[str]:
    """Extracts meaningful lines from a section block."""
    items = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        stripped = re.sub(r"^[\*\-]\s+", "", stripped)
        if stripped.lower() in ("(empty)", "empty", "-", "(none)"):
            continue
        items.append(stripped)
    return items


def read_topic_notes() -> TopicNotes:
    doc_id = os.environ.get("GOOGLE_DOC_ID")
    if not doc_id:
        print("   GOOGLE_DOC_ID not set in .env - skipping topic notes")
        return TopicNotes()
    creds = _get_creds()
    if not creds:
        return TopicNotes()
    try:
        service = build("docs", "v1", credentials=creds)
        doc = service.documents().get(documentId=doc_id).execute()
        raw = _doc_to_text(doc)
        return _parse_topic_notes(raw)
    except Exception as e:
        print(f"   Failed to read Google Doc: {e}")
        return TopicNotes()


def get_calendar_today() -> list[dict]:
    creds = _get_creds()
    if not creds:
        return []
    try:
        service = build("calendar", "v3", credentials=creds)
        now = datetime.now().astimezone()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        events_result = service.events().list(
            calendarId="primary",
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = []
        for e in events_result.get("items", []):
            start = e.get("start", {})
            end = e.get("end", {})
            events.append({
                "summary": e.get("summary", "(no title)"),
                "start_time": start.get("dateTime") or start.get("date"),
                "end_time": end.get("dateTime") or end.get("date"),
                "all_day": "date" in start and "dateTime" not in start,
            })
        return events
    except Exception as e:
        print(f"   Failed to read Google Calendar: {e}")
        return []
