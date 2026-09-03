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
    import pytest
    with pytest.raises(ValueError):
        compute("nope", count=1)

if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__)
        except BaseException as e:  # noqa
            failed += 1; print("FAIL", fn.__name__, "->", repr(e))
    sys.exit(1 if failed else 0)
