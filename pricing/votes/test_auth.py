import os, sys, requests

def leggi_cookie():
    raw = os.environ.get("FC_COOKIE", "")
    if not raw and os.path.exists("cookie.txt"):
        with open("cookie.txt", encoding="utf-8-sig") as f:
            raw = f.read()
    c = "".join(raw.replace("\ufeff", "").split())
    return c.encode("latin-1", "ignore").decode("latin-1")

c = leggi_cookie()
if not c:
    sys.exit("cookie vuoto")

print(f"lunghezza cookie: {len(c)}")
print("contiene token di sessione:", "fantacalcio.it=" in c)

s = requests.Session()
s.headers.update({
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Accept": ("application/vnd.openxmlformats-officedocument."
               "spreadsheetml.sheet,application/octet-stream,*/*"),
    "Accept-Language": "it-IT,it;q=0.9",
    "Referer": "https://www.fantacalcio.it/voti-fantacalcio-serie-a",
    "Cookie": c,
})

for sid, g in [(20, 4), (10, 1)]:
    r = s.get(f"https://www.fantacalcio.it/api/v1/Excel/votes/{sid}/{g}", timeout=30)
    ok = r.content.startswith(b"PK")
    print(f"stagione_id={sid} g={g} -> HTTP {r.status_code}, "
          f"{len(r.content)} byte, xlsx valido: {ok}")