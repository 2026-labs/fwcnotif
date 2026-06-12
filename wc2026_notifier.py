#!/usr/bin/env python3
"""
⚽ WC 2026 Notifier — ESPN + state machine
Notif: pre-match → HT → FT → (AET) → (PEN)
State: state.json di repo (commit back tiap run)

Data source: ESPN unofficial API (free, no key, live)
"""

import os, sys, json, requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT  = os.getenv("TELEGRAM_CHAT_ID")

ESPN_URL   = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
STATE_FILE = Path("state.json")
UTC        = timezone.utc
WIB        = timezone(timedelta(hours=7))
HEADERS    = {"User-Agent": "Mozilla/5.0 (compatible; WC2026Bot/1.0)"}

FLAGS = {
    "Mexico":"🇲🇽","South Africa":"🇿🇦","South Korea":"🇰🇷","Czech Republic":"🇨🇿",
    "Czechia":"🇨🇿","Argentina":"🇦🇷","Brazil":"🇧🇷","France":"🇫🇷","Germany":"🇩🇪",
    "Spain":"🇪🇸","Portugal":"🇵🇹","England":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","Italy":"🇮🇹",
    "Netherlands":"🇳🇱","Belgium":"🇧🇪","Croatia":"🇭🇷","Morocco":"🇲🇦",
    "United States":"🇺🇸","USA":"🇺🇸","Canada":"🇨🇦","Japan":"🇯🇵",
    "Australia":"🇦🇺","Senegal":"🇸🇳","Ghana":"🇬🇭","Nigeria":"🇳🇬",
    "Ecuador":"🇪🇨","Uruguay":"🇺🇾","Colombia":"🇨🇴","Chile":"🇨🇱",
    "Peru":"🇵🇪","Bolivia":"🇧🇴","Venezuela":"🇻🇪","Paraguay":"🇵🇾",
    "Poland":"🇵🇱","Switzerland":"🇨🇭","Serbia":"🇷🇸","Denmark":"🇩🇰",
    "Turkey":"🇹🇷","Ukraine":"🇺🇦","Romania":"🇷🇴","Hungary":"🇭🇺",
    "Slovakia":"🇸🇰","Austria":"🇦🇹","Iran":"🇮🇷","Saudi Arabia":"🇸🇦",
    "Qatar":"🇶🇦","Cameroon":"🇨🇲","Tunisia":"🇹🇳","Egypt":"🇪🇬",
    "Algeria":"🇩🇿","Mali":"🇲🇱","Panama":"🇵🇦","Costa Rica":"🇨🇷",
    "Honduras":"🇭🇳","Jamaica":"🇯🇲","Iraq":"🇮🇶","Slovenia":"🇸🇮",
    "Greece":"🇬🇷","Indonesia":"🇮🇩","New Zealand":"🇳🇿","Wales":"🏴󠁧󠁢󠁷󠁬󠁳󠁿",
    "Scotland":"🏴󠁧󠁢󠁳󠁣󠁴󠁿","Bosnia & Herzegovina":"🇧🇦","Cuba":"🇨🇺",
    "Trinidad and Tobago":"🇹🇹","El Salvador":"🇸🇻","Guatemala":"🇬🇹",
    "Haiti":"🇭🇹","DR Congo":"🇨🇩","Israel":"🇮🇱",
}

def fl(name): return FLAGS.get(name, "🏳️")

# ─── STATE ────────────────────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}

def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))

def match_state(state, mid) -> dict:
    return state.setdefault(mid, {
        "prematch": False,
        "ht": False,
        "ft": False,
        "et_ht": False,
        "aet": False,
        "pen": False,
    })

# ─── ESPN DATA ────────────────────────────────────────────────────────────────
def fetch_espn() -> list:
    r = requests.get(ESPN_URL, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json().get("events", [])

def parse_event(event: dict) -> dict:
    """Extract relevant fields from ESPN event"""
    comp       = event["competitions"][0]
    status     = comp["status"]
    state      = status["type"]["state"]        # "pre", "in", "post"
    period     = status.get("period", 0)
    type_name  = status["type"]["name"]         # STATUS_HALFTIME, etc.
    detail     = status["type"].get("detail", "")
    short_det  = status["type"].get("shortDetail", "")
    clock      = status.get("displayClock", "")

    competitors = comp.get("competitors", [])
    home = next((c for c in competitors if c["homeAway"] == "home"), competitors[0])
    away = next((c for c in competitors if c["homeAway"] == "away"), competitors[1])

    # goal details
    def get_goals(team_id):
        goals = []
        for d in comp.get("details", []):
            if d.get("type", {}).get("text", "") in ("Goal", "Penalty Goal", "Own Goal"):
                if d.get("team", {}).get("id") == team_id:
                    scorer = d.get("athletesInvolved", [{}])[0].get("displayName", "?")
                    min_   = d.get("clock", {}).get("displayValue", "?")
                    own    = "OG" if "Own" in d.get("type", {}).get("text", "") else ""
                    goals.append(f"{scorer} {min_}'{own}")
        return goals

    home_id   = home["team"]["id"]
    away_id   = away["team"]["id"]
    home_name = home["team"].get("displayName", "?")
    away_name = away["team"].get("displayName", "?")
    home_sc   = home.get("score", "-")
    away_sc   = away.get("score", "-")

    # kickoff time
    ko_str    = comp.get("date", event.get("date", ""))
    try:
        ko_dt = datetime.fromisoformat(ko_str.replace("Z", "+00:00"))
    except:
        ko_dt = None

    # round/group info
    season_type = comp.get("type", {}).get("abbreviation", "")
    notes       = comp.get("notes", [])
    round_info  = notes[0].get("headline", "") if notes else season_type

    return {
        "id":        event["id"],
        "home":      home_name,
        "away":      away_name,
        "home_sc":   home_sc,
        "away_sc":   away_sc,
        "home_goals": get_goals(home_id),
        "away_goals": get_goals(away_id),
        "state":     state,         # pre, in, post
        "period":    period,        # 1=1H, 2=2H, 3=ET1, 4=ET2, 5=PEN
        "type_name": type_name,     # STATUS_HALFTIME, STATUS_FINAL, etc.
        "detail":    detail,
        "short_det": short_det,
        "clock":     clock,
        "ko_dt":     ko_dt,
        "round":     round_info,
        "is_knockout": is_knockout(round_info),
    }

def is_knockout(round_str: str) -> bool:
    ko_keywords = ["round of", "quarter", "semi", "final", "r32", "r16", "qf", "sf"]
    return any(k in round_str.lower() for k in ko_keywords)

# ─── FORMATTERS ───────────────────────────────────────────────────────────────
def scorers_str(home, away, home_goals, away_goals) -> str:
    lines = []
    if home_goals:
        lines.append(f"  ⚽ {fl(home)} " + ", ".join(home_goals))
    if away_goals:
        lines.append(f"  ⚽ {fl(away)} " + ", ".join(away_goals))
    return "\n".join(lines)

def notif_prematch(m: dict) -> str:
    ko_wib = m["ko_dt"].astimezone(WIB).strftime("%H:%M WIB") if m["ko_dt"] else "?"
    return (
        f"🔔 <b>KICK OFF SEBENTAR LAGI</b>\n\n"
        f"{fl(m['home'])} <b>{m['home']}</b>  vs  <b>{m['away']}</b> {fl(m['away'])}\n"
        f"⏰ {ko_wib} · {m['round']}"
    )

def notif_ht(m: dict) -> str:
    sc = scorers_str(m["home"], m["away"], m["home_goals"], m["away_goals"])
    return (
        f"⏸ <b>HALF TIME</b>\n\n"
        f"{fl(m['home'])} <b>{m['home']} {m['home_sc']} - {m['away_sc']} {m['away']}</b> {fl(m['away'])}\n"
        f"{sc}"
    )

def notif_ft(m: dict) -> str:
    sc = scorers_str(m["home"], m["away"], m["home_goals"], m["away_goals"])
    going_et = (
        m["is_knockout"]
        and m["home_sc"] == m["away_sc"]
        and m["home_sc"] not in ("-", "")
    )
    extra = "\n➡️ <i>Imbang → lanjut Extra Time</i>" if going_et else ""
    return (
        f"✅ <b>FULL TIME</b>\n\n"
        f"{fl(m['home'])} <b>{m['home']} {m['home_sc']} - {m['away_sc']} {m['away']}</b> {fl(m['away'])}\n"
        f"{sc}{extra}"
    )

def notif_et_ht(m: dict) -> str:
    return (
        f"⏸ <b>EXTRA TIME — HALF TIME</b>\n\n"
        f"{fl(m['home'])} <b>{m['home']} {m['home_sc']} - {m['away_sc']} {m['away']}</b> {fl(m['away'])}"
    )

def notif_aet(m: dict) -> str:
    sc = scorers_str(m["home"], m["away"], m["home_goals"], m["away_goals"])
    going_pen = m["home_sc"] == m["away_sc"]
    extra = "\n➡️ <i>Masih imbang → Adu Penalti!</i>" if going_pen else ""
    return (
        f"✅ <b>AFTER EXTRA TIME</b>\n\n"
        f"{fl(m['home'])} <b>{m['home']} {m['home_sc']} - {m['away_sc']} {m['away']}</b> {fl(m['away'])}\n"
        f"{sc}{extra}"
    )

def notif_pen(m: dict) -> str:
    sc = scorers_str(m["home"], m["away"], m["home_goals"], m["away_goals"])
    return (
        f"🏆 <b>PENALTY SHOOTOUT — FINAL</b>\n\n"
        f"{fl(m['home'])} <b>{m['home']} {m['home_sc']} - {m['away_sc']} {m['away']}</b> {fl(m['away'])}\n"
        f"{sc}"
    )

# ─── SEND TELEGRAM ────────────────────────────────────────────────────────────
def send(text: str):
    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT, "text": text,
              "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=10,
    )
    r.raise_for_status()
    print(f"✅ Sent: {text[:60]}...")

# ─── SCHEDULE NOTIF (jadwal hari ini) ─────────────────────────────────────────
def build_schedule_msg(events: list) -> str | None:
    today   = datetime.now(WIB).strftime("%Y-%m-%d")
    matches = []
    for ev in events:
        m  = parse_event(ev)
        ko = m["ko_dt"]
        if ko and ko.astimezone(WIB).strftime("%Y-%m-%d") == today:
            matches.append(m)
    if not matches:
        return None
    d = datetime.now(WIB).strftime("%d %b %Y")
    lines = [f"⚽ <b>WC 2026 — HARI INI {d}</b>\n"]
    for m in matches:
        ko_wib = m["ko_dt"].astimezone(WIB).strftime("%H:%M WIB")
        lines.append(
            f"{fl(m['home'])} <b>{m['home']} vs {m['away']}</b> {fl(m['away'])}\n"
            f"  🕐 {ko_wib} · {m['round']}\n"
        )
    return "\n".join(lines)

# ─── MAIN LOOP ────────────────────────────────────────────────────────────────
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--auto"
    state = load_state()
    now   = datetime.now(UTC)

    events = fetch_espn()
    print(f"Fetched {len(events)} events from ESPN")

    if mode == "--schedule":
        msg = build_schedule_msg(events)
        if msg:
            send(msg)
        else:
            print("No matches today")
        return

    for ev in events:
        m   = parse_event(ev)
        mid = m["id"]
        ms  = match_state(state, mid)

        print(f"  [{mid}] {m['home']} vs {m['away']} | state={m['state']} period={m['period']} type={m['type_name']}")

        # ── Pre-match: 60 min sebelum KO ─────────────────────────────────────
        if not ms["prematch"] and m["state"] == "pre" and m["ko_dt"]:
            diff_min = (m["ko_dt"] - now).total_seconds() / 60
            if 0 <= diff_min <= 65:
                send(notif_prematch(m))
                ms["prematch"] = True

        # ── Half Time ─────────────────────────────────────────────────────────
        if not ms["ht"] and m["state"] == "in" and m["period"] == 2:
            if "STATUS_HALFTIME" in m["type_name"] or "Half Time" in m["detail"]:
                send(notif_ht(m))
                ms["ht"] = True

        # ── Extra Time Half Time ──────────────────────────────────────────────
        if not ms["et_ht"] and m["state"] == "in" and m["period"] == 4:
            if "HALFTIME" in m["type_name"] or "Half" in m["detail"]:
                send(notif_et_ht(m))
                ms["et_ht"] = True

        # ── Full Time (90 min, no ET) ─────────────────────────────────────────
        if not ms["ft"] and m["state"] == "post" and m["period"] <= 2:
            send(notif_ft(m))
            ms["ft"] = True

        # ── After Extra Time ──────────────────────────────────────────────────
        if not ms["aet"] and m["state"] == "post" and m["period"] in (3, 4):
            send(notif_aet(m))
            ms["aet"] = True

        # ── Penalty Shootout Final ────────────────────────────────────────────
        if not ms["pen"] and m["state"] == "post" and m["period"] == 5:
            send(notif_pen(m))
            ms["pen"] = True

    save_state(state)
    print("State saved.")

if __name__ == "__main__":
    main()
