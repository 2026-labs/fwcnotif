import os
import sys
import json
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

# ─── CONFIG ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT   = os.getenv("TELEGRAM_CHAT_ID")
APIFOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")   # dari api-football.com

# api-football.com endpoint
API_BASE  = "https://v3.football.api-sports.io"
WC_LEAGUE = 1       # FIFA World Cup di api-football
WC_SEASON = 2026

# openfootball fallback (no key, update harian)
OPENFOOTBALL_URL = (
    "https://raw.githubusercontent.com/openfootball/"
    "worldcup.json/master/2026/worldcup.json"
)

# WIB = UTC+7
WIB = timezone(timedelta(hours=7))

# ─── FLAG EMOJIS ───────────────────────────────────────────────────────────────
FLAGS: dict[str, str] = {
    "Argentina": "🇦🇷", "Brazil": "🇧🇷", "France": "🇫🇷", "Germany": "🇩🇪",
    "Spain": "🇪🇸", "Portugal": "🇵🇹", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Italy": "🇮🇹",
    "Netherlands": "🇳🇱", "Belgium": "🇧🇪", "Croatia": "🇭🇷", "Morocco": "🇲🇦",
    "Mexico": "🇲🇽", "USA": "🇺🇸", "United States": "🇺🇸", "Canada": "🇨🇦",
    "Japan": "🇯🇵", "South Korea": "🇰🇷", "Korea Republic": "🇰🇷",
    "Australia": "🇦🇺", "Senegal": "🇸🇳", "Ghana": "🇬🇭", "Nigeria": "🇳🇬",
    "Ecuador": "🇪🇨", "Uruguay": "🇺🇾", "Colombia": "🇨🇴", "Chile": "🇨🇱",
    "Peru": "🇵🇪", "Bolivia": "🇧🇴", "Venezuela": "🇻🇪", "Paraguay": "🇵🇾",
    "Poland": "🇵🇱", "Switzerland": "🇨🇭", "Serbia": "🇷🇸", "Denmark": "🇩🇰",
    "Sweden": "🇸🇪", "Norway": "🇳🇴", "Turkey": "🇹🇷", "Ukraine": "🇺🇦",
    "Romania": "🇷🇴", "Hungary": "🇭🇺", "Slovakia": "🇸🇰", "Austria": "🇦🇹",
    "Wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "Iran": "🇮🇷",
    "Saudi Arabia": "🇸🇦", "Qatar": "🇶🇦", "South Africa": "🇿🇦",
    "Cameroon": "🇨🇲", "Tunisia": "🇹🇳", "Ivory Coast": "🇨🇮",
    "Egypt": "🇪🇬", "Algeria": "🇩🇿", "Mali": "🇲🇱", "DR Congo": "🇨🇩",
    "Cuba": "🇨🇺", "Panama": "🇵🇦", "Costa Rica": "🇨🇷", "Honduras": "🇭🇳",
    "Jamaica": "🇯🇲", "Iraq": "🇮🇶", "Indonesia": "🇮🇩",
    "New Zealand": "🇳🇿", "Slovenia": "🇸🇮", "Greece": "🇬🇷",
    "Czechia": "🇨🇿", "Czech Republic": "🇨🇿",
    "Israel": "🇮🇱", "Guatemala": "🇬🇹", "El Salvador": "🇸🇻",
    "Trinidad and Tobago": "🇹🇹", "Kazakhstan": "🇰🇿", "Finland": "🇫🇮",
}


def flag(name: str) -> str:
    return FLAGS.get(name, "🏳️")


# ─── API FOOTBALL ──────────────────────────────────────────────────────────────
def _api_get(endpoint: str, params: dict) -> dict | None:
    try:
        r = requests.get(
            f"{API_BASE}/{endpoint}",
            headers={"x-apisports-key": APIFOOTBALL_KEY},
            params=params,
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        errors = data.get("errors")
        if errors and (isinstance(errors, dict) and errors) or (isinstance(errors, list) and errors):
            print(f"[API] Error: {errors}")
            return None
        return data
    except Exception as e:
        print(f"[API] Request failed: {e}")
        return None


def get_live() -> list:
    """Live matches WC 2026"""
    d = _api_get("fixtures", {"league": WC_LEAGUE, "season": WC_SEASON, "live": "all"})
    return d.get("response", []) if d else []


def get_last5() -> list:
    """5 match terakhir yang sudah selesai"""
    d = _api_get("fixtures", {
        "league": WC_LEAGUE, "season": WC_SEASON, "last": 5
    })
    return d.get("response", []) if d else []


def get_next5() -> list:
    """5 match berikutnya"""
    d = _api_get("fixtures", {
        "league": WC_LEAGUE, "season": WC_SEASON, "next": 5
    })
    return d.get("response", []) if d else []


def get_today() -> list:
    """Match hari ini (WIB → UTC)"""
    today = datetime.now(WIB).strftime("%Y-%m-%d")
    d = _api_get("fixtures", {
        "league": WC_LEAGUE, "season": WC_SEASON, "date": today
    })
    return d.get("response", []) if d else []


# ─── FORMATTERS ────────────────────────────────────────────────────────────────
def fmt_result(f: dict) -> str:
    """Completed match → formatted string"""
    home = f["teams"]["home"]["name"]
    away = f["teams"]["away"]["name"]
    hg   = f["goals"]["home"]
    ag   = f["goals"]["away"]
    dt   = datetime.fromisoformat(f["fixture"]["date"].replace("Z", "+00:00"))
    dstr = dt.astimezone(WIB).strftime("%d %b")
    rnd  = f["league"]["round"].replace("Group Stage - ", "Grup ").replace("Round of ", "R16/" if "16" in f["league"]["round"] else "R")

    # penalty shootout
    pen = f.get("score", {}).get("penalty", {})
    pen_str = ""
    if pen and pen.get("home") is not None:
        pen_str = f" (PEN {pen['home']}-{pen['away']})"

    status = f["fixture"]["status"]["short"]
    status_tag = {"FT": "FT", "AET": "AET (ET)", "PEN": "PEN"}.get(status, status)

    return (
        f"  {flag(home)} <b>{home} {hg} - {ag} {flag(away)} {away}</b>{pen_str}\n"
        f"  <i>{dstr} · {rnd} · {status_tag}</i>"
    )


def fmt_fixture(f: dict) -> str:
    """Upcoming match → formatted string"""
    home = f["teams"]["home"]["name"]
    away = f["teams"]["away"]["name"]
    dt   = datetime.fromisoformat(f["fixture"]["date"].replace("Z", "+00:00"))
    twib = dt.astimezone(WIB).strftime("%d %b %H:%M")
    rnd  = f["league"]["round"].replace("Group Stage - ", "Grup ")

    return (
        f"  {flag(home)} <b>{home} vs {away} {flag(away)}</b>\n"
        f"  <i>{twib} WIB · {rnd}</i>"
    )


def fmt_live(f: dict) -> str:
    """Live match → formatted string"""
    home    = f["teams"]["home"]["name"]
    away    = f["teams"]["away"]["name"]
    hg      = f["goals"]["home"] or 0
    ag      = f["goals"]["away"] or 0
    elapsed = f["fixture"]["status"].get("elapsed", "?")

    return (
        f"  🔴 {elapsed}' | {flag(home)} <b>{home} {hg} - {ag} {away} {flag(away)}</b>"
    )


# ─── OPENFOOTBALL FALLBACK ────────────────────────────────────────────────────
def get_openfootball() -> dict | None:
    """Fetch openfootball worldcup.json (no API key, update harian)"""
    try:
        r = requests.get(OPENFOOTBALL_URL, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[openfootball] Failed: {e}")
        return None


def build_fallback_message() -> str:
    """Build message dari openfootball.json (schedule + results, no live)"""
    data = get_openfootball()
    if not data:
        return "❌ Gagal ambil data dari openfootball."

    matches = data.get("matches", [])
    now     = datetime.now(WIB)
    today   = now.date()

    finished   = [m for m in matches if m.get("score") and m["score"].get("ft")]
    upcoming   = [m for m in matches if not m.get("score") or not m["score"].get("ft")]

    last5      = finished[-5:]
    next5      = upcoming[:5]

    lines = [
        f"⚽ <b>FIFA WORLD CUP 2026</b>",
        f"<i>via openfootball · {now.strftime('%d %b %Y %H:%M WIB')}</i>\n",
    ]

    lines.append("✅ <b>LAST MATCH</b>")
    if last5:
        for m in reversed(last5):
            h, a = m["team1"], m["team2"]
            sc   = m["score"]["ft"]
            dt   = m.get("date", "")
            lines.append(
                f"  {flag(h)} <b>{h} {sc[0]} - {sc[1]} {flag(a)} {a}</b>\n"
                f"  <i>{dt} · {m.get('group', m.get('round', ''))}</i>"
            )
    else:
        lines.append(" NO DATA.")

    lines.append("")
    lines.append("📅 <b>NEXT</b>")
    if next5:
        for m in next5:
            h, a = m["team1"], m["team2"]
            dt   = m.get("date", "")
            t    = m.get("time", "")
            lines.append(
                f"  {flag(h)} <b>{h} vs {a} {flag(a)}</b>\n"
                f"  <i>{dt} {t} UTC · {m.get('group', m.get('round', ''))}</i>"
            )
    else:
        lines.append("  Tidak ada jadwal.")

    lines.append("\n⚠️ <i>Data via openfootball, update ~1x/hari. Gunakan API key untuk live score.</i>")
    return "\n".join(lines)


# ─── MAIN MESSAGE BUILDER ─────────────────────────────────────────────────────
def build_all_message() -> str:
    now   = datetime.now(WIB)
    lines = [
        f"⚽ <b>FIFA WORLD CUP 2026</b>",
        f"<i>Update: {now.strftime('%d %b %Y %H:%M WIB')}</i>\n",
    ]

    # Live
    live = get_live()
    if live:
        lines.append("🔴 <b>RUNNING</b>")
        for f in live:
            lines.append(fmt_live(f))
        lines.append("")

    # Last 5 results
    results = get_last5()
    lines.append("✅ <b>LAST MATCH</b>")
    if results:
        for f in results:   # api returns newest first
            lines.append(fmt_result(f))
            lines.append("")
    else:
        lines.append(" NO DATA.\n")

    # Next 5 upcoming
    upcoming = get_next5()
    lines.append("📅 <b>NEXT</b>")
    if upcoming:
        for f in upcoming:
            lines.append(fmt_fixture(f))
            lines.append("")
    else:
        lines.append("NO DATA.")

    return "\n".join(lines)


def build_live_message() -> str:
    live = get_live()
    if not live:
        return "⚽ <b>WC 2026</b>\n\nSLEEP."
    lines = [f"⚽ <b>WORLD CUP 2026 — LIVE</b> 🔴\n"]
    for f in live:
        lines.append(fmt_live(f))
    return "\n".join(lines)


def build_last5_message() -> str:
    results = get_last5()
    if not results:
        return "⚽ <b>WC 2026</b>\n\nNO DATA."
    lines = [f"⚽ <b>WORLD CUP 2026 — LAST RESULT</b>\n"]
    for f in results:
        lines.append(fmt_result(f))
        lines.append("")
    return "\n".join(lines)


def build_next5_message() -> str:
    upcoming = get_next5()
    if not upcoming:
        return "⚽ <b>WC 2026</b>\n\nNO DATA."
    lines = [f"⚽ <b>WORLD CUP 2026 — SCHEDULE</b>\n"]
    for f in upcoming:
        lines.append(fmt_fixture(f))
        lines.append("")
    return "\n".join(lines)


def build_today_message() -> str:
    today = get_today()
    now   = datetime.now(WIB).strftime("%d %b %Y")
    if not today:
        return f"⚽ <b>WC 2026 — {now}</b>\n\nNO DATA."
    lines = [f"⚽ <b>WORLD CUP 2026 — {now}</b>\n"]
    for f in today:
        status = f["fixture"]["status"]["short"]
        if status in ("FT", "AET", "PEN"):
            lines.append(fmt_result(f))
        elif status in ("1H", "2H", "ET", "BT", "P", "LIVE"):
            lines.append(fmt_live(f))
        else:
            lines.append(fmt_fixture(f))
        lines.append("")
    return "\n".join(lines)


# ─── TELEGRAM SEND ────────────────────────────────────────────────────────────
def send_tele(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[Telegram] Send failed: {e}")
        return False


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--all"

    MODE_MAP = {
        "--all":      build_all_message,
        "--live":     build_live_message,
        "--last5":    build_last5_message,
        "--next5":    build_next5_message,
        "--today":    build_today_message,
        "--fallback": build_fallback_message,
    }

    builder = MODE_MAP.get(mode)
    if not builder:
        print(f"Unknown mode: {mode}")
        print(f"Available: {list(MODE_MAP.keys())}")
        sys.exit(1)

    msg = builder()

    # Print ke console (buat debug)
    print(msg)
    print("\n" + "─" * 50)
    print("Sending to Telegram...")

    ok = send_tele(msg)
    print("✅ Sent!" if ok else "❌ Failed to send!")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
