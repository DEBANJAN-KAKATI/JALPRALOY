"""Reference places used by the live-data endpoints.

TOWNS: approximate town centres (±~2 km). Good enough for 0.1–0.25° weather data;
       do NOT use them for hexagon-level work.
GAUGES: Brahmaputra main-stem CWC stations, upstream -> downstream (mirror of
       data/static/gauges.csv). `glofas_*` is the GloFAS river cell with the highest
       mean discharge within ±0.15° of the station, i.e. the main stem rather than a
       tributary (regenerate with `python -m pipelines.ingest_river_levels snap`).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Town:
    name: str
    district: str
    lat: float
    lon: float


@dataclass(frozen=True)
class Gauge:
    name: str
    order: int
    lat: float
    lon: float
    glofas_lat: float
    glofas_lon: float


TOWNS = [
    Town("Guwahati", "Kamrup Metropolitan", 26.144, 91.736),
    Town("Nalbari", "Nalbari", 26.445, 91.434),
    Town("Barpeta", "Barpeta", 26.323, 91.006),
    Town("Mangaldoi", "Darrang", 26.443, 92.030),
    Town("Tezpur", "Sonitpur", 26.633, 92.800),
    Town("Nagaon", "Nagaon", 26.347, 92.684),
    Town("Golaghat", "Golaghat", 26.519, 93.960),
    Town("Jorhat", "Jorhat", 26.757, 94.203),
    Town("Majuli", "Majuli", 26.953, 94.164),
    Town("Sivasagar", "Sivasagar", 26.984, 94.637),
    Town("North Lakhimpur", "Lakhimpur", 27.236, 94.102),
    Town("Dhemaji", "Dhemaji", 27.482, 94.580),
    Town("Dibrugarh", "Dibrugarh", 27.472, 94.912),
    Town("Tinsukia", "Tinsukia", 27.489, 95.360),
    Town("Goalpara", "Goalpara", 26.173, 90.623),
    Town("Bongaigaon", "Bongaigaon", 26.477, 90.558),
    Town("Kokrajhar", "Kokrajhar", 26.401, 90.272),
    Town("Dhubri", "Dhubri", 26.020, 89.973),
    Town("Diphu", "Karbi Anglong", 25.843, 93.432),
    Town("Haflong", "Dima Hasao", 25.169, 93.016),
    Town("Silchar", "Cachar", 24.833, 92.779),
    Town("Karimganj", "Karimganj", 24.869, 92.355),
]

GAUGES = [
    Gauge("Dibrugarh", 1, 27.48, 94.91, 27.48, 94.76),
    Gauge("Neamatighat", 2, 26.99, 94.24, 26.89, 94.09),
    Gauge("Tezpur", 3, 26.62, 92.80, 26.57, 92.65),
    Gauge("Guwahati", 4, 26.19, 91.75, 26.19, 91.60),
    Gauge("Goalpara", 5, 26.17, 90.62, 26.22, 90.47),
    Gauge("Dhubri", 6, 26.02, 89.98, 25.87, 89.83),
]


def find_towns(q: str) -> list[Town]:
    q = q.strip().lower()
    if not q:
        return []
    hits = [t for t in TOWNS if q in t.name.lower() or q in t.district.lower()]
    return sorted(hits, key=lambda t: (not t.name.lower().startswith(q), t.name))  # prefix matches first
