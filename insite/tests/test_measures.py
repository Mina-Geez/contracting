import pytest

from insite.calc.measures import compute


def test_area():
    assert compute("area", height=1.5, width=2.8, count=40) == pytest.approx(168.0)

def test_perimeter():
    assert compute("perimeter", height=1.5, width=2.8, count=40) == 344.0

def test_linear():
    assert compute("linear", length=3.0, count=60) == 180.0

def test_count_only():
    assert compute("count", count=12) == 12.0

def test_piece_waste():
    assert compute("piece_waste", count=500, wastage=1.1) == 550.0

def test_manual_returns_none():
    assert compute("manual", count=5) is None

def test_defaults_count_and_wastage_default_to_one():
    assert compute("area", height=2, width=3) == 6.0          # count defaults 1
    assert compute("piece_waste", count=10) == 10.0           # wastage defaults 1

def test_blank_inputs_coerced_to_zero():
    assert compute("area", height="", width=None, count=40) == 0.0

def test_unknown_measure_raises():
    with pytest.raises(ValueError):
        compute("nope", count=1)

# --- a zero count is a real zero where the count IS the quantity -------------

def test_count_of_zero_stays_zero():
    # A blank Float reads as 0. For `count` and `piece_waste` the count is the
    # quantity, so inventing 1 would bill a unit nobody ordered.
    assert compute("count", count=0) == 0.0
    assert compute("piece_waste", count=0, wastage=1.1) == 0.0

def test_zero_count_still_falls_back_where_it_is_only_a_multiplier():
    assert compute("area", height=2, width=3, count=0) == 6.0
    assert compute("linear", length=4, count=0) == 4.0

# --- measures are stored and shown by label, resolved by key ----------------

def test_labels_resolve_to_the_same_measure():
    from insite.calc.measures import MEASURE_LABELS, normalize_measure
    assert normalize_measure(MEASURE_LABELS["area"]) == "area"
    assert compute(MEASURE_LABELS["area"], height=1.5, width=2.8, count=40) == pytest.approx(168.0)

def test_every_measure_has_a_label():
    from insite.calc.measures import MEASURE_KEYS, MEASURE_LABELS
    assert set(MEASURE_LABELS) == MEASURE_KEYS
    assert len(set(MEASURE_LABELS.values())) == len(MEASURE_KEYS)  # labels are unique
