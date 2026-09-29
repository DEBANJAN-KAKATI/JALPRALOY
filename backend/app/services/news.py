"""Flood / disaster news for the News tab.

Primary: Google News RSS search (per language edition). Fallback: GDELT DOC API.
Only headlines whose title or summary contain a flood/disaster keyword are kept,
and each item links to the publisher (via Google News) — we never copy article text.

Licence note: Google's RSS feed is offered "for personal, non-commercial use" in a feed
reader. That suits a hackathon prototype; for an operational service switch
NEWS_PROVIDER to a licensed API (GDELT, NewsData.io, a PIB/ASDMA feed…) — see
docs/12_LIVE_DATA_SYNC.md.
"""
from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import httpx

from app.services.live import cached, get_json

GOOGLE_RSS = "https://news.google.com/rss/search"
GDELT_API = "https://api.gdeltproject.org/api/v2/doc/doc"
TTL_S = 600  # every visitor within 10 min shares one fetch; then it refreshes

# The rule the user asked for: an item must mention FLOOD or DISASTER (in any supported language).
KEYWORDS = {
    "flood": ["flood", "বান", "বন্যা", "बाढ़"],
    "disaster": ["disaster", "দুৰ্যোগ", "দুর্যোগ", "आपदा"],
}
LOCAL_WORDS = ["assam", "guwahati", "brahmaputra", "barak", "অসম", "আসাম", "গুৱাহাটী", "গুয়াহাটি", "असम", "गुवाहाटी"]

EDITIONS = {  # UI language -> Google News edition
    "en": {"hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
    "hi": {"hl": "hi", "gl": "IN", "ceid": "IN:hi"},
    "bn": {"hl": "bn", "gl": "IN", "ceid": "IN:bn"},
}
QUERIES = {
    ("assam", "en"): "(flood OR floods OR disaster) (Assam OR Guwahati OR Brahmaputra) when:7d",
    ("india", "en"): "(flood OR floods OR disaster) India when:3d",
    ("assam", "hi"): "(बाढ़ OR आपदा) असम when:7d",
    ("india", "hi"): "(बाढ़ OR आपदा) when:3d",
    ("assam", "bn"): "(বন্যা OR দুর্যোগ) আসাম when:7d",
    ("india", "bn"): "(বন্যা OR দুর্যোগ) when:3d",
}
GDELT_QUERIES = {"assam": '(flood OR disaster) (Assam OR Guwahati)', "india": "(flood OR disaster) India sourcecountry:IN"}


# Figurative uses of "flood" that aren't about water ("a flood of complaints", "floods the market").
NOT_FLOOD = re.compile(r"flood(s|ed|ing)? (of|with)\b(?! \d)|floodlight|floods? (the )?(\w+ )?markets?|flooded (in)?box")


def matched_keywords(text: str) -> list[str]:
    t = NOT_FLOOD.sub(" ", text.lower())
    return [k for k, words in KEYWORDS.items() if any(w in t for w in words)]


def _item(title: str, url: str, source: str, published: datetime | None, summary: str = "") -> dict | None:
    kws = matched_keywords(f"{title} {summary}")
    if not kws:
        return None
    text = f"{title} {summary}".lower()
    return {
        "id": hashlib.sha1(url.encode()).hexdigest()[:16], "title": title, "url": url, "source": source,
        "published": published.isoformat() if published else None, "keywords": kws,
        "local": any(w in text for w in LOCAL_WORDS),
    }


def parse_google_rss(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    out = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        source = (it.findtext("source") or "").strip()
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]  # Google appends " - Publisher"
        summary = re.sub(r"<[^>]+>", " ", html.unescape(it.findtext("description") or ""))
        try:
            published = parsedate_to_datetime(it.findtext("pubDate") or "")
        except (TypeError, ValueError):
            published = None
        item = _item(title, (it.findtext("link") or "").strip(), source or "Google News", published, summary)
        if item:
            out.append(item)
    return out


def parse_gdelt(payload: dict) -> list[dict]:
    out = []
    for a in payload.get("articles", []):
        try:
            published = datetime.strptime(a.get("seendate", ""), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            published = None
        item = _item(a.get("title", ""), a.get("url", ""), a.get("domain", "GDELT"), published)
        if item:
            out.append(item)
    return out


def dedupe_sort(items: list[dict], limit: int = 40) -> list[dict]:
    seen, out = set(), []
    for it in sorted(items, key=lambda i: i["published"] or "", reverse=True):
        key = re.sub(r"\W+", " ", it["title"].lower()).strip()[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out[:limit]


async def _google(scope: str, lang: str) -> list[dict]:
    params = {"q": QUERIES[(scope, lang)], **EDITIONS[lang]}
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), follow_redirects=True,
                                 headers={"User-Agent": "Mozilla/5.0 (JalProloy flood news)"}) as client:
        r = await client.get(GOOGLE_RSS, params=params)
        r.raise_for_status()
        return parse_google_rss(r.text)


async def _gdelt(scope: str) -> list[dict]:
    payload = await get_json(GDELT_API, {"query": GDELT_QUERIES[scope], "mode": "artlist", "format": "json",
                                         "maxrecords": 60, "sort": "datedesc", "timespan": "7d"})
    return parse_gdelt(payload)


async def news(scope: str = "assam", lang: str = "en", force: bool = False) -> dict:
    lang = lang if lang in EDITIONS else "en"  # no Assamese edition on Google News -> English

    async def fetch():
        try:
            items, provider = await _google(scope, lang), "google-news"
        except Exception:
            items, provider = await _gdelt(scope), "gdelt"
        return {"items": dedupe_sort(items), "provider": provider,
                "fetched_at": datetime.now(timezone.utc).isoformat()}

    result = await cached(f"news:{scope}:{lang}", "news", TTL_S, fetch, force=force)
    return {**result, "scope": scope, "lang": lang}
