import pytest

from insite.calc.measures import evaluate_formula, formula_tokens, validate_formula

#: The names a rule's inputs provide in these tests.
TOKENS = {"height", "width", "length", "count", "wastage"}

T = {"height": 1.5, "width": 2.8, "length": 3.0, "count": 40.0, "wastage": 1.1}


def test_basic_arithmetic():
	assert evaluate_formula("height * width * count", T) == pytest.approx(168.0)


def test_with_wastage_and_constant():
	assert evaluate_formula("height * width * count * 1.1", T) == pytest.approx(184.8)


def test_whitelisted_function():
	assert evaluate_formula("round(height * width, 2)", T) == 4.2


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


# --- validate_formula: the save-time check against a rule's own inputs -------


def test_validate_accepts_a_formula_over_the_rules_inputs():
	validate_formula("height * width * count * 1.1", TOKENS)


def test_validate_accepts_a_formula_that_would_divide_by_zero_on_samples():
	# Regression: validation must not evaluate the maths. This formula is legal
	# but blows up when width equals height.
	validate_formula("count / (width - height)", TOKENS)


def test_validate_rejects_a_name_the_rule_does_not_provide():
	with pytest.raises(ValueError) as excinfo:
		validate_formula("height * panels", TOKENS)
	assert "panels" in str(excinfo.value)


def test_validate_accepts_a_site_specific_input_name():
	validate_formula("height * width * panels", {"height", "width", "panels"})


def test_validate_rejects_empty():
	with pytest.raises(ValueError):
		validate_formula("", TOKENS)


def test_validate_rejects_attribute_access():
	with pytest.raises(ValueError):
		validate_formula("height.__class__", TOKENS)


def test_validate_rejects_non_whitelisted_call():
	with pytest.raises(ValueError):
		validate_formula("__import__('os')", TOKENS)


def test_validate_rejects_bad_syntax():
	with pytest.raises(ValueError):
		validate_formula("height *", TOKENS)


# --- resource guards: a valid formula must not be able to hang a worker ------


def test_validate_rejects_huge_exponent():
	# Planted by a manager, triggered by every user who saves a document.
	with pytest.raises(ValueError):
		validate_formula("2 ** 999999999", TOKENS)


def test_validate_rejects_stacked_exponents():
	with pytest.raises(ValueError):
		validate_formula("9 ** 9 ** 9", TOKENS)


def test_validate_rejects_a_called_power_that_is_too_large():
	with pytest.raises(ValueError):
		validate_formula("pow(9, 9 ** 9)", TOKENS)


def test_evaluate_rejects_huge_exponent():
	with pytest.raises(ValueError):
		evaluate_formula("count ** 9999", {"count": 9.0})


def test_reasonable_powers_still_work():
	assert evaluate_formula("width ** 2", {"width": 3.0}) == pytest.approx(9.0)


def test_validate_rejects_an_over_long_formula():
	with pytest.raises(ValueError):
		validate_formula(" + ".join(["height"] * 300), TOKENS)


# --- arity: catch a miscalled function at save time, not on an invoice -------


def test_validate_rejects_wrong_argument_count():
	for bad in ("abs()", "abs(1, 2)", "sqrt()", "pow(1)", "round(1.5, 2, 3)"):
		with pytest.raises(ValueError):
			validate_formula(bad, TOKENS)


def test_correct_argument_counts_are_accepted():
	for good in ("abs(height)", "round(height, 2)", "pow(height, 2)", "min(height, width)"):
		validate_formula(good, TOKENS)


def test_non_finite_result_is_rejected():
	with pytest.raises(ValueError):
		evaluate_formula("1e308 * 10", T)


# --- formula_tokens: what a rule must supply --------------------------------


def test_formula_tokens_lists_the_names_used():
	assert formula_tokens("height * width * count") == {"height", "width", "count"}


def test_formula_tokens_ignores_functions_and_constants():
	assert formula_tokens("round(height * pi, 2)") == {"height"}


def test_formula_tokens_of_nonsense_is_empty():
	assert formula_tokens("height *") == set()
