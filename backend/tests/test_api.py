from xml.etree import ElementTree as ET

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
NS = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_area_summary_is_labelled_synthetic():
    r = client.get("/api/risk/area", params={"name": "Guwahati", "horizon": "24h"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "synthetic-demo"
    assert body["most_affected"] and body["least_affected"]
    assert all(a["name"].startswith("Demo zone") for a in body["most_affected"])


def test_unknown_area_404():
    assert client.get("/api/risk/area", params={"name": "Atlantis"}).status_code == 404


def test_cells_and_cell_detail():
    cells = client.get("/api/risk/area/cells", params={"name": "Guwahati", "horizon": "6h"}).json()["cells"]
    assert len(cells) > 100
    detail = client.get(f"/api/risk/cell/{cells[0]['h3']}", params={"horizon": "6h"}).json()
    assert detail["h3"] == cells[0]["h3"] and detail["drivers"]


def test_search_direct_latlon():
    hits = client.get("/api/areas/search", params={"q": "26.14, 91.73"}).json()
    assert hits and hits[0]["level"] == "point" and hits[0]["covered"] is True


def test_cap_xml_is_valid_shape():
    alerts = client.get("/api/alerts").json()
    if not alerts:
        return
    r = client.get(f"/api/alerts/{alerts[0]['id']}/cap")
    assert r.status_code == 200
    root = ET.fromstring(r.content)
    assert root.find("cap:status", NS).text == "Exercise"
    info = root.find("cap:info", NS)
    assert info.find("cap:severity", NS).text in {"Extreme", "Severe", "Moderate", "Minor"}
    poly = info.find("cap:area/cap:polygon", NS).text.split()
    assert poly[0] == poly[-1]
