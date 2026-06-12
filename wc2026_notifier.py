#!/usr/bin/env python3
"""
⚽ WC 2026 Telegram Notifier
Source: openfootball GitHub JSON (free, no API key)

Usage:
  python wc2026_notifier.py           # last5 + jadwal
  python wc2026_notifier.py --last5
  python wc2026_notifier.py --next5
  python wc2026_notifier.py --today
"""

import os, sys, requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT  = os.getenv("TELEGRAM_CHAT_ID")
WIB            = timezone(timedelta(hours=7))
DATA_URL       = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"

FLAGS = {
    "Argentina":"🇦🇷","Brazil":"🇧🇷","France":"🇫🇷","Germany":"🇩🇪",
    "Spain":"🇪🇸","Portugal":"🇵🇹","England":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","Italy":"🇮🇹",
    "Netherlands":"🇳🇱","Belgium":"🇧🇪","Croatia":"🇭🇷","Morocco":"🇲🇦",
    "Mexico":"🇲🇽","USA":"🇺🇸","United States":"🇺🇸","Canada":"🇨🇦",
    "Japan":"🇯🇵","South Korea":"🇰🇷","Korea Republic":"🇰🇷",
    "Australia":"🇦🇺","Senegal":"🇸🇳","Ghana":"🇬🇭","Nigeria":"🇳🇬",
    "Ecuador":"🇪🇨","Uruguay":"🇺🇾","Colombia":"🇨🇴","Chile":"🇨🇱",
    "Peru":"🇵🇪","Bolivia":"🇧🇴","Venezuela":"🇻🇪","Paraguay":"🇵🇾",
    "Poland":"🇵🇱","Switzerland":"🇨🇭","Serbia":"🇷🇸","Denmark":"🇩🇰",
    "Sweden":"🇸🇪","Norway":"🇳🇴","Turkey":"🇹🇷","Ukraine":"🇺🇦",
    "Romania":"🇷🇴","Hungary":"🇭🇺","Slovakia":"🇸🇰","Austria":"🇦🇹",
    "Wales":"🏴󠁧󠁢󠁷󠁬󠁳󠁿","Scotland":"🏴󠁧󠁢󠁳󠁣󠁴󠁿","Iran":"🇮🇷",
    "Saudi Arabia":"🇸🇦","Qatar":"🇶🇦","South Africa":"🇿🇦",
    "Cameroon":"🇨🇲","Tunisia":"🇹🇳","Ivory Coast":"🇨🇮",
    "Egypt":"🇪🇬","Algeria":"🇩🇿","Mali":"🇲🇱","DR Congo":"🇨🇩",
    "Cuba":"🇨🇺","Panama":"🇵🇦","Costa Rica":"🇨🇷","Honduras":"🇭🇳",
    "Jamaica":"🇯🇲","Iraq":"🇮🇶","Indonesia":"🇮🇩","New Zealand":"🇳🇿",
    "Slovenia":"🇸🇮","Greece":"🇬🇷","Czechia":"🇨🇿","Czech Republic":"🇨🇿",
    "Bosnia & Herzegovina":"🇧🇦","Bosnia and Herzegovina":"🇧🇦",
    "Israel":"🇮🇱","Guatemala":"🇬🇹","El Salvador":"🇸🇻",
    "Trinidad and Tobago":"🇹🇹","Kazakhstan":"🇰🇿","Finland":"🇫🇮",
    "Kenya":"🇰🇪","Uzbekistan":"🇺🇿","Haiti":"🇭🇹",
}

def f(name): return FLAGS.get(name, "🏳️")

def fetch_data():
    r = requests.get(DATA_URL, timeout=10)
    r.raise_for_status()
    return r.json()["matches"]

def parse_date(match):
    """Parse tanggal match, return datetime aware WIB"""
    raw = match.get("date", "")
    t   = match.get("time", "")
    if not raw:
        return None
    try:
        # time biasanya format "13:00 UTC-6"
        if t:
            tz_str = t.split()[-1] if "UTC" in t else "UTC+0"
            time_str = t.split()[0]
            offset_h = int(tz_str.replace("UTC", "") or 0)
            tz = timezone(timedelta(hours=offset_h))
            dt = datetime.strptime(f"{raw} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        else:
            dt = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt.astimezone(WIB)
    except:
        return None

def is_done(m):
    return bool(m.get("score") and m["score"].get("ft"))

def fmt_result(m):
    h, a = m["team1"], m["team2"]
    sc   = m["score"]["ft"]
    dt   = parse_date(m)
    dstr = dt.strftime("%d %b, %H:%M WIB") if dt else m.get("date","")
    rnd  = m.get("group", m.get("round",""))
    return f"  {f(h)} <b>{h} {sc[0]} - {sc[1]} {f(a)} {a}</b>\n  <i>📅 {dstr} · {rnd}</i>"

def fmt_fixture(m):
    h, a = m["team1"], m["team2"]
    dt   = parse_date(m)
    dstr = dt.strftime("%d %b, %H:%M WIB") if dt else m.get("date","")
    rnd  = m.get("group", m.get("round",""))
    return f"  {f(h)} <b>{h} vs {a} {f(a)}</b>\n  <i>📅 {dstr} · {rnd}</i>"

def send(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT, "text": text,
              "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=10
    )
    r.raise_for_status()

def main():
    mode     = sys.argv[1] if len(sys.argv) > 1 else "--all"
    matches  = fetch_data()
    now      = datetime.now(WIB)
    today    = now.date()

    done     = [m for m in matches if is_done(m)]
    upcoming = [m for m in matches if not is_done(m)]
    last5    = done[-5:]
    next5    = upcoming[:5]

    lines = [f"⚽ <b>FIFA WORLD CUP 2026</b>",
             f"<i>{now.strftime('%d %b %Y, %H:%M WIB')}</i>\n"]

    if mode in ("--all", "--last5"):
        lines.append("✅ <b>5 HASIL TERAKHIR</b>")
        if last5:
            for m in reversed(last5):
                lines += [fmt_result(m), ""]
        else:
            lines += ["  Belum ada hasil.", ""]

    if mode in ("--all", "--next5"):
        lines.append("📅 <b>JADWAL BERIKUTNYA</b>")
        if next5:
            for m in next5:
                lines += [fmt_fixture(m), ""]
        else:
            lines.append("  Tidak ada jadwal.")

    if mode == "--today":
        today_matches = [m for m in matches
                         if parse_date(m) and parse_date(m).date() == today]
        lines.append(f"📅 <b>HARI INI — {now.strftime('%d %b %Y')}</b>")
        if today_matches:
            for m in today_matches:
                lines += [(fmt_result(m) if is_done(m) else fmt_fixture(m)), ""]
        else:
            lines.append("  Tidak ada pertandingan hari ini.")

    msg = "\n".join(lines)
    print(msg)
    send(msg)
    print("✅ Sent!")

if __name__ == "__main__":
    main()
