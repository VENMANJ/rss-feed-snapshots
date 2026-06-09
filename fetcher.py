#!/usr/bin/env python3
"""Weekly RSS/Atom snapshot fetcher.

Reads sources.json, fetches each public feed, keeps entries from the last
WINDOW_DAYS days and writes one JSON snapshot per ISO week plus a stable
output/latest.json. Per source it also records the most recent publication
date seen on the feed (proof for "genuinely no items this week") and a
status (ok / empty / error) so dead feeds surface immediately.
"""
import json, datetime, time, html, re, sys, urllib.request, gzip, io
from pathlib import Path

import feedparser

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
WINDOW_DAYS = 9
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def clean(text, limit=300):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    return text[:limit]


def entry_date(e):
    for key in ("published_parsed", "updated_parsed"):
        t = e.get(key)
        if t:
            return datetime.date(t.tm_year, t.tm_mon, t.tm_mday)
    return None


HEADERS = {
    "User-Agent": UA,
    "Accept": ("application/rss+xml, application/atom+xml, application/xml;q=0.9, "
               "text/xml;q=0.8, */*;q=0.7"),
    "Accept-Language": "en,nl;q=0.8",
    "Accept-Encoding": "gzip",
}


def _download(url, pogingen=2):
    """Feed-bytes ophalen met browser-achtige headers; 1 retry bij netwerkfouten."""
    laatste = None
    for _ in range(pogingen):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
                    raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
                return raw
        except Exception as ex:  # noqa: BLE001
            laatste = ex
            time.sleep(3)
    raise laatste


def fetch_source(src, cutoff):
    rec = {"id": src["id"], "url": src["url"], "status": "ok",
           "laatste_pubdate_gezien": None, "n_in_window": 0, "items": [], "fout": None}
    try:
        d = feedparser.parse(_download(src["url"]))
        if d.bozo and not d.entries:
            rec["status"] = "error"
            rec["fout"] = f"bozo: {getattr(d, 'bozo_exception', 'parse error')}"[:200]
            return rec
        dates = []
        for e in d.entries:
            dt = entry_date(e)
            if dt:
                dates.append(dt)
            if dt and dt >= cutoff:
                rec["items"].append({
                    "titel": clean(e.get("title"), 250),
                    "url": e.get("link"),
                    "datum": dt.isoformat(),
                    "samenvatting": clean(e.get("summary") or e.get("description"), 300),
                })
        if dates:
            rec["laatste_pubdate_gezien"] = max(dates).isoformat()
        rec["n_in_window"] = len(rec["items"])
        if not d.entries:
            rec["status"] = "empty"
            rec["fout"] = "feed parseert maar bevat 0 entries"
    except Exception as ex:  # noqa: BLE001 - report, never crash the batch
        rec["status"] = "error"
        rec["fout"] = str(ex)[:200]
    return rec


def main():
    cfg = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=WINDOW_DAYS)
    week = f"{today.isocalendar()[0]}-W{today.isocalendar()[1]:02d}"
    sources = [fetch_source(s, cutoff) for s in cfg["feeds"]]
    ok = sum(1 for s in sources if s["status"] == "ok")
    snapshot = {
        "week": week,
        "gegenereerd_op": datetime.datetime.now(datetime.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "venster_dagen": WINDOW_DAYS,
        "cutoff": cutoff.isoformat(),
        "n_feeds": len(sources),
        "n_ok": ok,
        "n_error": sum(1 for s in sources if s["status"] == "error"),
        "n_items_totaal": sum(s["n_in_window"] for s in sources),
        "bronnen": sources,
    }
    OUT.mkdir(exist_ok=True)
    blob = json.dumps(snapshot, ensure_ascii=False, indent=1)
    (OUT / f"{week}.json").write_text(blob, encoding="utf-8")
    (OUT / "latest.json").write_text(blob, encoding="utf-8")
    print(f"{week}: {ok}/{len(sources)} feeds ok, "
          f"{snapshot['n_items_totaal']} items in venster")
    errs = [s for s in sources if s["status"] != "ok"]
    for s in errs:
        print(f"  {s['status'].upper():6s} {s['id']}: {s['fout']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
