import pytest

from insite.calc.measures import compute, evaluate_formula, validate_formula

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

# --- resource guards: a valid formula must not be able to hang a worker ------

def test_validate_rejects_huge_exponent():
    # Planted by a manager, triggered by every user who saves a document.
    with pytest.raises(ValueError):
        validate_formula("2 ** 999999999")

def test_validate_rejects_stacked_exponents():
    with pytest.raises(ValueError):
        validate_formula("9 ** 9 ** 9")

def test_evaluate_rejects_huge_exponent():
    with pytest.raises(ValueError):
        evaluate_formula("count ** 9999", {"count": 9.0})

def test_reasonable_powers_still_work():
    assert evaluate_formula("width ** 2", {"width": 3.0}) == pytest.approx(9.0)

def test_validate_rejects_an_over_long_formula():
    with pytest.raises(ValueError):
        validate_formula(" + ".join(["height"] * 300))

# --- arity: catch a miscalled function at save time, not on an invoice -------

def test_validate_rejects_wrong_argument_count():
    for bad in ("abs()", "abs(1, 2)", "sqrt()", "pow(1)", "round(1.5, 2, 3)"):
        with pytest.raises(ValueError):
            validate_formula(bad)

def test_correct_argument_counts_are_accepted():
    for good in ("abs(height)", "round(height, 2)", "pow(height, 2)", "min(height, width)"):
        validate_formula(good)

def test_non_finite_result_is_rejected():
    with pytest.raises(ValueError):
        evaluate_formula("1e308 * 10", T)
