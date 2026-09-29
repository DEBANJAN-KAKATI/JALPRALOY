"""Live-data logic with fake payloads — no network needed."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.imd import Color
from app.main import app
from app.services import live

client = TestClient(app)


def _series(today: date, base: float, today_value: float):
    """10 years of flat `base` flow, then `today_value` today and a 7-day forecast bump."""
    start = date(today.year - 10, 1, 1)
    times, values = [], []
    d = start
    while d <= today + timedelta(days=7):
        v = base
        if d == today:
            v = today_value
        elif d > today:
            v = today_value * (1.2 if d == today + timedelta(days=3) else 1.0)
        times.append(d.isoformat())
        values.append(v)
        d += timedelta(days=1)
    return times, values


def test_river_normal_vs_very_high():
    today = date(2026, 7, 10)
    s = live.analyse_station(*_series(today, 10000, 9000), today)
    assert s["status"] == "Normal" and s["color"] == Color.GREEN
    s = live.analyse_station(*_series(today, 10000, 30000), today)
    assert s["status"] == "Very high" and s["color"] == Color.RED
    assert s["trend"] == "rising"
    assert s["peak_date"] == (today + timedelta(days=3)).isoformat()
    assert any(p["forecast"] for p in s["series"]) and s["series"][0]["forecast"] is False


def test_rain_days_use_imd_colours():
    days = live.parse_rain_days({"time": ["d1", "d2", "d3"], "precipitation_sum": [10, 70, 210],
                                 "precipitation_probability_max": [20, 80, 95]})
    assert [d["color"] for d in days] == [Color.GREEN, Color.YELLOW, Color.RED]


def test_gdacs_region_filter():
    def feat(lon, lat, iso3, level="Orange", current="true"):
        return {"geometry": {"coordinates": [lon, lat]},
                "properties": {"eventid": 1, "episodeid": 1, "name": "Flood", "alertlevel": level, "iso3": iso3,
                               "iscurrent": current, "todate": "2026-09-01", "affectedcountries": [{"iso3": iso3}]}}
    out = live.filter_gdacs([feat(91.7, 26.1, "IND"), feat(72.8, 19.0, "IND"), feat(-8.8, 8.4, "GIN")])
    assert len(out["region"]) == 1 and out["region"][0]["color"] == Color.ORANGE
    assert len(out["india_other"]) == 1


def test_endpoints_degrade_gracefully(monkeypatch):
    async def boom(*_a, **_k):
        raise RuntimeError("network down")

    live._CACHE.clear()
    monkeypatch.setattr(live, "get_json", boom)
    assert client.get("/api/rivers").status_code == 503
    status = {s["id"]: s for s in client.get("/api/status").json()}
    assert status["glofas"]["status"] == "offline"
    assert status["flood-model"]["status"] == "demo"


@pytest.mark.parametrize("q,level", [("dibru", "town"), ("guwahati", "district")])
def test_search_includes_towns(q, level):
    hits = client.get("/api/areas/search", params={"q": q}).json()
    assert hits[0]["level"] == level


def test_locate():
    inside = client.get("/api/areas/locate", params={"lat": 26.15, "lon": 91.74}).json()
    assert inside["covered"] and inside["area"] == "Guwahati"
    outside = client.get("/api/areas/locate", params={"lat": 27.47, "lon": 94.91}).json()
    assert not outside["covered"] and outside["nearest_town"] == "Dibrugarh"


# --- News --------------------------------------------------------------------
from app.services import geocode, news  # noqa: E402

RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Flood situation worsens in Assam, 2 lakh affected - The Sentinel</title>
  <link>https://news.google.com/rss/articles/a1</link><pubDate>Mon, 28 Sep 2026 10:00:00 GMT</pubDate>
  <source url="https://www.sentinelassam.com">The Sentinel</source><description>Brahmaputra above danger level</description></item>
<item><title>Cricket: India win series - Sports Daily</title>
  <link>https://news.google.com/rss/articles/a2</link><pubDate>Mon, 28 Sep 2026 11:00:00 GMT</pubDate>
  <source url="https://x">Sports Daily</source><description>no match here</description></item>
<item><title>NDRF teams deployed after landslide disaster in Kerala - PTI</title>
  <link>https://news.google.com/rss/articles/a3</link><pubDate>Mon, 28 Sep 2026 12:00:00 GMT</pubDate>
  <source url="https://ptinews.com">PTI</source><description></description></item>
</channel></rss>"""


def test_news_keeps_only_flood_or_disaster():
    items = news.dedupe_sort(news.parse_google_rss(RSS))
    assert [i["title"] for i in items] == ["NDRF teams deployed after landslide disaster in Kerala",
                                            "Flood situation worsens in Assam, 2 lakh affected"]
    assert items[1]["local"] is True and items[1]["keywords"] == ["flood"]
    assert items[0]["local"] is False and items[0]["keywords"] == ["disaster"]


def test_news_localised_keywords():
    assert news.matched_keywords("असम में बाढ़ से हालात गंभीर") == ["flood"]
    assert news.matched_keywords("আসামে বন্যা পরিস্থিতি") == ["flood"]


def test_news_endpoint_falls_back_to_gdelt(monkeypatch):
    async def google_down(*_a):
        raise RuntimeError("blocked")

    async def gdelt(*_a, **_k):
        return {"articles": [{"title": "Flood alert in Guwahati", "url": "https://e.x/1",
                              "domain": "e.x", "seendate": "20260928T100000Z"}]}

    live._CACHE.clear()
    monkeypatch.setattr(news, "_google", google_down)
    monkeypatch.setattr(news, "get_json", gdelt)
    body = client.get("/api/news", params={"scope": "assam"}).json()
    assert body["provider"] == "gdelt" and body["items"][0]["local"] is True


# --- Search suggestions -------------------------------------------------------
def test_suggest_combines_local_and_osm(monkeypatch):
    async def photon(*_a, **_k):
        return {"features": [
            {"properties": {"name": "Anil Nagar", "osm_key": "place", "osm_value": "suburb", "city": "Dispur",
                            "state": "Assam"}, "geometry": {"coordinates": [91.7731, 26.1673]}},
            {"properties": {"name": "Anil Nagar", "osm_key": "place", "osm_value": "suburb", "city": "Dispur",
                            "state": "Assam"}, "geometry": {"coordinates": [91.7731, 26.1673]}},
        ]}

    live._CACHE.clear()
    monkeypatch.setattr(geocode, "get_json", photon)
    rows = client.get("/api/areas/suggest", params={"q": "anil nagar"}).json()
    assert len(rows) == 1 and rows[0]["kind"] == "Locality" and rows[0]["subtitle"] == "Dispur, Assam"
    assert rows[0]["covered"] is True and rows[0]["area"] == "Guwahati"


def test_suggest_survives_geocoder_outage(monkeypatch):
    async def down(*_a, **_k):
        raise RuntimeError("down")

    live._CACHE.clear()
    monkeypatch.setattr(geocode, "get_json", down)
    rows = client.get("/api/areas/suggest", params={"q": "dibru"}).json()
    assert rows and rows[0]["name"] == "Dibrugarh"


@pytest.mark.parametrize("title,expected", [
    ("Single-Use Plastic Still Floods Guwahati Markets", []),
    ("A flood of complaints after power cut", []),
    ("Stadium floodlights fail", []),
    ("Flash floods hit Dhemaji; 12 villages submerged", ["flood"]),
    ("Floods of 2022 revisited: lessons for Assam", ["flood"]),  # plain "floods of <year>" still counts
])
def test_news_ignores_figurative_flood(title, expected):
    assert news.matched_keywords(title) == expected
