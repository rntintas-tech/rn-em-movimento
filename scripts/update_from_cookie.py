#!/usr/bin/env python3
"""
Captura o leaderboard do clube via cookie de sessão do Strava (env STRAVA_COOKIE)
e mescla em data/weeks.json. Feito para rodar no GitHub Actions a cada hora.

Env:
  STRAVA_COOKIE  ex.: "_strava4_session=abc123"
"""

import datetime as dt
import json
import os
import subprocess
import sys
import zoneinfo

CLUB_ID = 2297640
CHALLENGE_START = dt.date(2026, 8, 17)
CHALLENGE_END = dt.date(2026, 9, 17)
TZ = zoneinfo.ZoneInfo("America/Sao_Paulo")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "data", "weeks.json")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36")


def fetch_week(cookie, week_offset):
    url = f"https://www.strava.com/clubs/{CLUB_ID}/leaderboard?week_offset={week_offset}"
    cmd = [
        "curl", "-sS", "--fail-with-body", "--compressed", "-m", "40", url,
        "-H", f"Cookie: {cookie}",
        "-H", "Accept: text/javascript, application/javascript, application/json, */*; q=0.01",
        "-H", "X-Requested-With: XMLHttpRequest",
        "-H", f"User-Agent: {UA}",
        "-H", f"Referer: https://www.strava.com/clubs/{CLUB_ID}/leaderboard",
        "-H", "Accept-Language: pt-BR,pt;q=0.9,en;q=0.8",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"curl rc={proc.returncode}: {proc.stderr[:200]} body={proc.stdout[:200]}")
    body = proc.stdout.strip()
    if not body.startswith("{"):
        raise RuntimeError(f"resposta não-JSON (cookie expirado?): {body[:200]}")
    entries = json.loads(body).get("data", [])
    return [
        {
            "name": f"{e.get('athlete_firstname', '').strip()} {e.get('athlete_lastname', '').strip()}".strip(),
            "athlete_id": e.get("athlete_id"),
            "distance": float(e.get("distance", 0) or 0),
            "activities": int(e.get("num_activities", 0) or 0),
            "elevation": float(e.get("elev_gain", 0) or 0),
            "time": int(e.get("moving_time", 0) or 0),
        }
        for e in entries
    ]


def week_meta(start):
    end = start + dt.timedelta(days=6)
    n = ((start - CHALLENGE_START).days // 7) + 1
    return {"id": start.isoformat(), "label": f"Semana {n}",
            "start": start.isoformat(), "end": end.isoformat()}


def main():
    cookie = os.environ.get("STRAVA_COOKIE", "").strip()
    if not cookie:
        sys.exit("STRAVA_COOKIE não definido")

    today = dt.datetime.now(TZ).date()
    this_monday = today - dt.timedelta(days=today.weekday())

    store = {"updated_at": None, "weeks": []}
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, encoding="utf-8") as f:
            store = json.load(f)
    by_id = {w["id"]: w for w in store.get("weeks", [])}

    errors = []
    for offset in (1, 0):
        start = this_monday - dt.timedelta(weeks=offset)
        if start + dt.timedelta(days=6) < CHALLENGE_START or start > CHALLENGE_END:
            continue
        meta = week_meta(start)
        try:
            athletes = fetch_week(cookie, offset)
        except Exception as exc:
            errors.append(f"{meta['id']}: {exc}")
            continue
        if not athletes and by_id.get(meta["id"], {}).get("athletes"):
            # não sobrescreve snapshot bom com resposta vazia
            print(f"[SKIP] {meta['label']}: resposta vazia, mantendo snapshot existente")
            continue
        meta["athletes"] = athletes
        by_id[meta["id"]] = meta
        print(f"[OK] {meta['label']} ({meta['start']}..{meta['end']}): {len(athletes)} atletas")

    if errors and len(errors) == 2:
        sys.exit("Nenhuma semana capturada: " + " | ".join(errors))

    store["weeks"] = sorted(by_id.values(), key=lambda w: w["start"])
    store["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Salvo: {DATA_PATH}")
    if errors:
        print("Avisos:", " | ".join(errors))


if __name__ == "__main__":
    main()
