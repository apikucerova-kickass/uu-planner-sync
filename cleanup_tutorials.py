import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/calendar.events"
]

# Načtení ID kalendáře z .env
CALENDAR_ID = None
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("CALENDAR_ID="):
                CALENDAR_ID = line.split("=", 1)[1].strip().strip("'\"")

creds = None
if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None

    if not creds:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        
    with open("token.json", "w") as token:
        token.write(creds.to_json())

tasks_svc = build("tasks", "v1", credentials=creds)
cal_svc = build("calendar", "v3", credentials=creds)

print("Hledám a mažu tutoriály z Google Tasks...")
tasks_res = tasks_svc.tasks().list(tasklist="@default", maxResults=100).execute()
deleted_tasks = 0
for t in tasks_res.get("items", []):
    title = t.get("title", "")
    if any(w in title.lower() for w in ["tutoriál", "tutorial"]):
        tasks_svc.tasks().delete(tasklist="@default", task=t["id"]).execute()
        print(f"🗑️ Smazán úkol: {title}")
        deleted_tasks += 1

deleted_events = 0
if CALENDAR_ID:
    print(f"\nHledám a mažu tutoriály z Google Kalendáře...")
    events_res = cal_svc.events().list(calendarId=CALENDAR_ID, maxResults=250).execute()
    for e in events_res.get("items", []):
        summary = e.get("summary", "")
        if any(w in summary.lower() for w in ["tutoriál", "tutorial"]):
            cal_svc.events().delete(calendarId=CALENDAR_ID, eventId=e["id"]).execute()
            print(f"🗑️ Smazána událost: {summary}")
            deleted_events += 1

print(f"\n Hotovo! Smazáno {deleted_tasks} úkolů a {deleted_events} událostí.")