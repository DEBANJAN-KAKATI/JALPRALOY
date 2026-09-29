import numpy as np

from ml.common.imd import Color, enforce_monotone, flood_color, rain_category, rain_color
from ml.evaluation.metrics import brier_skill_score, categorical_scores, nse


def test_rain_category_boundaries():
    assert rain_category(0.0) == "no_rain"
    assert rain_category(64.4) == "moderate"
    assert rain_category(64.5) == "heavy"
    assert rain_category(115.6) == "very_heavy"
    assert rain_category(204.5) == "extremely_heavy"


def test_monotone_probabilities():
    p_h, p_vh, p_x = enforce_monotone([0.3], [0.5], [0.6])
    assert p_h[0] >= p_vh[0] >= p_x[0]


def test_colors():
    assert rain_color(0.1, 0.0, 0.0) == Color.GREEN
    assert rain_color(0.8, 0.2, 0.0) == Color.ORANGE
    assert rain_color(0.9, 0.8, 0.1) == Color.RED
    assert flood_color(0.75) == Color.RED


def test_categorical_scores():
    obs = np.array([1, 1, 0, 0, 1])
    fc = np.array([1, 0, 1, 0, 1])
    s = categorical_scores(obs, fc)
    assert (s["hits"], s["misses"], s["false_alarms"]) == (2, 1, 1)
    assert np.isclose(s["csi"], 0.5)
    assert np.isclose(s["pod"], 2 / 3)


def test_skill_scores():
    o = np.array([0, 0, 1, 1])
    assert brier_skill_score(o.astype(float), o) == 1.0
    assert nse(o, o) == 1.0
