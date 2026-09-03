import pytest
from insite.calc.measures import evaluate_formula, compute, validate_formula

T = {"height": 1.5, "width": 2.8, "length": 3.0, "count": 40.0, "wastage": 1.1}

def test_basic_arithmetic():
    assert evaluate_formula("height * width * count", T) == pytest.approx(168.0)

def test_with_wastage_and_constant():
    assert evaluate_formula("height * width * count * 1.1", T) == pytest.approx(184.8)

def test_whitelisted_function():
    assert evaluate_formula("round(height * width, 2)", T) == 4.2

def test_via_compute_formula():
    assert compute("formula", height=1.5, width=2.8, count=40,
                   formula="height * width * count") == pytest.approx(168.0)

def test_empty_formula_raises():
    with pytest.raises(ValueError):
        evaluate_formula("", T)

def test_unknown_name_raises():
    with pytest.raises(ValueError):
        evaluate_formula("height * price", T)

def test_attribute_access_blocked():
    with pytest.raises(ValueError):
        evaluate_formula("height.__class__", T)

def test_call_of_non_whitelisted_blocked():
    with pytest.raises(ValueError):
        evaluate_formula("__import__('os')", T)

# --- validate_formula: save-time structural check ----------------------------

def test_validate_accepts_good_formula():
    validate_formula("height * width * count * 1.1")  # must not raise

def test_validate_accepts_formula_that_would_divide_by_zero_on_samples():
    # Regression: validation must not evaluate the maths. This formula is legal
    # but blows up against all-ones sample values.
    validate_formula("count / (width - height)")

def test_validate_rejects_empty():
    with pytest.raises(ValueError):
        validate_formula("")

def test_validate_rejects_unknown_name():
    with pytest.raises(ValueError):
        validate_formula("height * price")

def test_validate_rejects_attribute_access():
    with pytest.raises(ValueError):
        validate_formula("height.__class__")

def test_validate_rejects_non_whitelisted_call():
    with pytest.raises(ValueError):
        validate_formula("__import__('os')")

def test_validate_rejects_bad_syntax():
    with pytest.raises(ValueError):
        validate_formula("height *")

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
