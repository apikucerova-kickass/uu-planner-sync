import json
import os
from datetime import datetime, timedelta, timezone

# --- Automatické načtení souboru .env na Macu ---
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env")

if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip("'\"")
# ------------------------------------------------

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import requests

# ================= KONFIGURACE =================
SCOPES = [
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/calendar.events"
]
CACHE_FILE = "sync_cache.json"
LOOKBACK_DAYS = 21  # Ignorovat neodevzdané starší než 3 týdny

# Načtení z prostředí (.env nebo GitHub Secrets)
CALENDAR_ID = os.getenv("CALENDAR_ID")
UU_ENDPOINT = os.getenv("UU_ENDPOINT")
UU_AUTH_HEADER = os.getenv("UU_AUTH_HEADER")

if not UU_ENDPOINT or not UU_AUTH_HEADER:
    raise ValueError("Chybí přihlašovací údaje k Plus4U! Zkontrolujte soubor .env nebo GitHub Secrets.")

# Vytvoření token.json v cloudu GitHub Actions
if os.getenv("GOOGLE_CREDENTIALS") and not os.path.exists("token.json"):
    with open("token.json", "w", encoding="utf-8") as f:
        f.write(os.getenv("GOOGLE_CREDENTIALS"))

# Klíčová slova pro události do kalendáře
BIG_TASK_KEYWORDS = [
    "semestrální", "projekt", "zkouška", "test", "milestone", 
    "esej", "prezentace", "zápočet", "termín", "úkol", "cvičení"
]
# ===============================================

def parse_iso_datetime(dt_str):
    if not dt_str:
        return None
    dt_str = dt_str.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None

def get_google_services():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
            
    tasks_svc = build("tasks", "v1", credentials=creds)
    cal_svc = build("calendar", "v3", credentials=creds)
    return tasks_svc, cal_svc

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

def is_major_task(title: str) -> bool:
    return any(w in title.lower() for w in BIG_TASK_KEYWORDS)

def run_sync():
    print("Načítám Google služby...")
    tasks_svc, cal_svc = get_google_services()
    cache = load_cache()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=LOOKBACK_DAYS)

    print("Stahuji data z Plus4U...")
    headers = {
        "Authorization": UU_AUTH_HEADER,
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "Origin": "https://uuapp.plus4u.net",
        "Referer": "https://uuapp.plus4u.net/"
    }
    payload = {
        "uri": UU_ENDPOINT,
        "pageInfo": {"pageSize": 4000}
    }
    resp = requests.post(UU_ENDPOINT, headers=headers, json=payload)
    resp.raise_for_status()
    
    data = resp.json()
    items = data.get("uuDwRecordList", [])
    print(f"Nalezeno celkem {len(items)} položek.")

    synced_tasks_count = 0
    synced_cal_count = 0

    for item in items:
        uu_id = str(item.get("id"))
        title = item.get("name", "Bez názvu")
        due_str = item.get("endTime") or item.get("expirationTime")
        if not due_str:
            continue

        due_dt = parse_iso_datetime(due_str)
        if not due_dt:
            continue

        state = str(item.get("state", "active")).lower()
        is_completed = state in ["closed", "resolved", "done", "completed", "finished"]

        if due_dt < cutoff and not is_completed:
            continue

        rec = cache.get(uu_id, {})
        last_synced_due = rec.get("last_synced_due")

        source_name = item.get("sourceArtifactName") or item.get("sourceAwidName") or "Neznámý předmět"
        url = item.get("routeUri") or ""
        notes = f"Předmět: {source_name}\nStav: {state}\nOdkaz: {url}\nPlus4U ID: {uu_id}"
        tasks_due_format = due_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        # --- GOOGLE TASKS ---
        if is_completed:
            if "google_task_id" in rec and rec.get("task_status") != "completed":
                tasks_svc.tasks().patch(
                    tasklist="@default",
                    task=rec["google_task_id"],
                    body={"status": "completed"}
                ).execute()
                rec["task_status"] = "completed"
        else:
            if "google_task_id" not in rec:
                created_task = tasks_svc.tasks().insert(
                    tasklist="@default",
                    body={"title": title, "due": tasks_due_format, "notes": notes}
                ).execute()
                rec["google_task_id"] = created_task["id"]
                rec["task_status"] = "needsAction"
                synced_tasks_count += 1
            elif last_synced_due != due_str:
                tasks_svc.tasks().patch(
                    tasklist="@default",
                    task=rec["google_task_id"],
                    body={"due": tasks_due_format, "title": title}
                ).execute()

        # --- GOOGLE KALENDÁŘ ---
        if is_major_task(title) and CALENDAR_ID:
            if "google_cal_id" not in rec:
                event_start = due_dt - timedelta(hours=2)
                event_body = {
                    "summary": f"📌 {title}",
                    "description": notes,
                    "start": {"dateTime": event_start.isoformat()},
                    "end": {"dateTime": due_dt.isoformat()},
                    "colorId": "11",
                    "reminders": {
                        "useDefault": False,
                        "overrides": [
                            {"method": "popup", "minutes": 7 * 24 * 60},
                            {"method": "popup", "minutes": 3 * 24 * 60},
                            {"method": "popup", "minutes": 24 * 60}
                        ]
                    }
                }
                event = cal_svc.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
                rec["google_cal_id"] = event["id"]
                synced_cal_count += 1
            else:
                cal_id = rec["google_cal_id"]
                if is_completed and not rec.get("cal_marked_done"):
                    cal_svc.events().patch(
                        calendarId=CALENDAR_ID,
                        eventId=cal_id,
                        body={
                            "summary": f"✅ [HOTOVO] {title}",
                            "colorId": "8",
                            "reminders": {"useDefault": False, "overrides": []}
                        }
                    ).execute()
                    rec["cal_marked_done"] = True
                elif not is_completed and last_synced_due and last_synced_due != due_str:
                    cal_svc.events().patch(
                        calendarId=CALENDAR_ID,
                        eventId=cal_id,
                        body={
                            "start": {"dateTime": (due_dt - timedelta(hours=2)).isoformat()},
                            "end": {"dateTime": due_dt.isoformat()},
                            "description": f"{notes}\nAktualizovaný deadline: {due_str}"
                        }
                    ).execute()

        rec["last_synced_due"] = due_str
        cache[uu_id] = rec

    save_cache(cache)
    print(f"Synchronizace hotova. Nové úkoly: {synced_tasks_count}, kalendář: {synced_cal_count}.")

if __name__ == "__main__":
    run_sync()