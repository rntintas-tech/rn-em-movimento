#!/usr/bin/env python3
"""
Atualiza data/weeks.json com os leaderboards semanais do clube no Strava.

Uso:
  1) primeira vez (gera o refresh token):  python scripts/update_leaderboard.py --auth
  2) atualizar dados:                      python scripts/update_leaderboard.py

Credenciais lidas de scripts/.env (ou variáveis de ambiente):
  STRAVA_CLIENT_ID=...
  STRAVA_CLIENT_SECRET=...
  STRAVA_REFRESH_TOKEN=...   (gravado automaticamente pelo --auth)
"""

import argparse
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request

CLUB_ID = 2297640
CHALLENGE_START = dt.date(2026, 8, 17)   # segunda-feira, início do desafio
CHALLENGE_END = dt.date(2026, 9, 17)
BASE = "https://www.strava.com"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT, "scripts", ".env")
DATA_PATH = os.path.join(ROOT, "data", "weeks.json")


# ---------------- .env ----------------
def load_env():
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())


def save_env_var(key, value):
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, encoding="utf-8") as f:
            lines = [l.rstrip("\n") for l in f]
    lines = [l for l in lines if not l.startswith(key + "=")]
    lines.append(f"{key}={value}")
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------- HTTP ----------------
def http_json(url, data=None, headers=None, method=None):
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


# ---------------- OAuth ----------------
def do_auth(client_id, client_secret):
    redirect = "http://localhost/exchange_token"
    url = (
        f"{BASE}/oauth/authorize?client_id={client_id}"
        f"&response_type=code&redirect_uri={urllib.parse.quote(redirect)}"
        f"&approval_prompt=force&scope=read"
    )
    print("\n1) Abra esta URL no navegador, faça login no Strava e clique em 'Autorizar':\n")
    print(url)
    print(
        "\n2) Você será redirecionado para uma página que NÃO abre (localhost)."
        "\n   Copie da barra de endereços o valor do parâmetro `code=` (entre code= e &)."
    )
    code = input("\nCole o code aqui: ").strip()

    tok = http_json(
        f"{BASE}/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
    )
    save_env_var("STRAVA_REFRESH_TOKEN", tok["refresh_token"])
    print(f"\nOK! Autorizado como: {tok.get('athlete', {}).get('firstname', '?')} "
          f"{tok.get('athlete', {}).get('lastname', '')}")
    print(f"Refresh token salvo em {ENV_PATH}")
    return tok["access_token"]


def get_access_token(client_id, client_secret, refresh_token):
    tok = http_json(
        f"{BASE}/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    # o Strava pode rotacionar o refresh token
    if tok.get("refresh_token") and tok["refresh_token"] != refresh_token:
        save_env_var("STRAVA_REFRESH_TOKEN", tok["refresh_token"])
    return tok["access_token"]


# ---------------- Leaderboard ----------------
def fetch_week(access_token, week_offset):
    """Busca o leaderboard do clube. week_offset: 0=semana atual, 1=anterior."""
    url = f"{BASE}/api/v3/clubs/{CLUB_ID}/leaderboard?per_page=200&week_offset={week_offset}"
    raw = http_json(url, headers={"Authorization": f"Bearer {access_token}"})
    entries = raw.get("data", raw) if isinstance(raw, dict) else raw
    athletes = []
    for e in entries:
        athletes.append(
            {
                "name": f"{e.get('athlete_firstname', '').strip()} {e.get('athlete_lastname', '').strip()}".strip(),
                "distance": float(e.get("distance", 0) or 0),
                "activities": int(e.get("num_activities", 0) or 0),
                "elevation": float(e.get("elev_gain", 0) or 0),
                "time": int(e.get("moving_time", 0) or 0),
                "velocity": float(e.get("velocity", 0) or 0),
            }
        )
    return athletes


def strava_week_start(today=None):
    """Segunda-feira da semana Strava corrente."""
    today = today or dt.date.today()
    return today - dt.timedelta(days=today.weekday())


def week_meta(start):
    end = start + dt.timedelta(days=6)
    n = ((start - CHALLENGE_START).days // 7) + 1
    return {
        "id": start.isoformat(),
        "label": f"Semana {n}",
        "start": start.isoformat(),
        "end": end.isoformat(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--auth", action="store_true", help="fluxo OAuth inicial")
    args = parser.parse_args()

    load_env()
    client_id = os.environ.get("STRAVA_CLIENT_ID")
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit(f"Defina STRAVA_CLIENT_ID e STRAVA_CLIENT_SECRET em {ENV_PATH}")

    if args.auth:
        access = do_auth(client_id, client_secret)
    else:
        refresh = os.environ.get("STRAVA_REFRESH_TOKEN")
        if not refresh:
            sys.exit("Sem STRAVA_REFRESH_TOKEN. Rode primeiro: python scripts/update_leaderboard.py --auth")
        access = get_access_token(client_id, client_secret, refresh)

    # carrega snapshots existentes
    store = {"updated_at": None, "weeks": []}
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, encoding="utf-8") as f:
            store = json.load(f)
    by_id = {w["id"]: w for w in store.get("weeks", [])}

    this_monday = strava_week_start()

    # captura semana atual (offset 0) e anterior (offset 1)
    for offset in (1, 0):
        start = this_monday - dt.timedelta(weeks=offset)
        if start + dt.timedelta(days=6) < CHALLENGE_START or start > CHALLENGE_END:
            continue  # fora do desafio
        meta = week_meta(start)
        try:
            athletes = fetch_week(access, offset)
        except Exception as exc:
            print(f"[ERRO] semana {meta['id']} (offset {offset}): {exc}")
            continue
        meta["athletes"] = athletes
        by_id[meta["id"]] = meta  # sobrescreve snapshot da semana
        print(f"[OK] {meta['label']} ({meta['start']} a {meta['end']}): {len(athletes)} atletas")

    store["weeks"] = sorted(by_id.values(), key=lambda w: w["start"])
    store["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()

    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print(f"\nSalvo em {DATA_PATH}")


if __name__ == "__main__":
    main()
