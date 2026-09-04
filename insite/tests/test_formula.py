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


# --- a formula that saves must be a formula that runs ------------------------
#
# The module promises validation and evaluation share one walker, so anything
# accepted at save time can be worked out on a real document. These are the
# ways that promise was broken: each of them saved cleanly and then raised an
# unhandled TypeError on every document the rule matched.


def test_min_and_max_need_two_numbers():
	"""Over a single float Python wants something to iterate, and raises."""
	for bad in ("min(height)", "max(height)"):
		with pytest.raises(ValueError):
			validate_formula(bad, TOKENS)


def test_round_needs_a_plain_whole_number_of_places():
	# A measurement arrives as a float, and float places is a TypeError.
	with pytest.raises(ValueError):
		validate_formula("round(height, width)", TOKENS)
	with pytest.raises(ValueError):
		validate_formula("round(height, 2.5)", TOKENS)


def test_round_still_takes_a_literal_number_of_places():
	assert evaluate_formula("round(height, 2)", {"height": 1.23456}) == 1.23
	assert evaluate_formula("round(height)", {"height": 1.6}) == 2


def test_nothing_the_validator_accepts_raises_an_unhandled_error():
	"""The guarantee, stated as a test.

	ValueError and ArithmeticError are the two the engine turns into a message
	naming the row. Anything else reaches the user as a traceback.
	"""
	saveable = [
		"height * width * count",
		"min(height, width)",
		"max(height, width, 3)",
		"round(height * width, 2)",
		"sqrt(height)",
		"height / width",
		"height % width",
		"height ** width",
		"abs(height - width)",
		"ceil(height) + floor(width)",
		"pow(height, 2)",
		"height * pi",
	]
	hostile = [
		{"height": 0, "width": 0, "count": 0},
		{"height": -1, "width": 0, "count": -1},
		{"height": 1e300, "width": 1e300, "count": 1e300},
		{"height": 1.5, "width": 2.8, "count": 40},
	]
	for formula in saveable:
		validate_formula(formula, TOKENS)
		for values in hostile:
			try:
				evaluate_formula(formula, values)
			except (ValueError, ArithmeticError):
				pass  # handled: the engine reports these against the row
			except Exception as e:
				raise AssertionError(
					f"{formula!r} on {values!r} raised {type(e).__name__}, "
					"which nothing catches and the user sees as a traceback"
				) from e


# --- formula_tokens: what a rule must supply --------------------------------


def test_formula_tokens_lists_the_names_used():
	assert formula_tokens("height * width * count") == {"height", "width", "count"}


def test_formula_tokens_ignores_functions_and_constants():
	assert formula_tokens("round(height * pi, 2)") == {"height"}


def test_formula_tokens_of_nonsense_is_empty():
	assert formula_tokens("height *") == set()


# --- hostile formulas, not just hostile values ------------------------------


def test_a_formula_too_long_to_parse_is_refused_not_crashed():
	"""`ast.parse` recurses, and a few thousand terms exhaust the stack.

	That is a RecursionError raised inside the parser, before the node count can
	reject anything. Nothing catches it: the engine and the preview endpoints
	both catch ValueError and ArithmeticError, and RecursionError is neither, so
	it reached the user as a 500 from a whitelisted method.
	"""
	monstrous = "+".join(["1"] * 5000)
	with pytest.raises(ValueError, match="too long"):
		validate_formula(monstrous, TOKENS)
	with pytest.raises(ValueError, match="too long"):
		evaluate_formula(monstrous, {})


def test_a_formula_nested_too_deeply_is_refused_not_crashed():
	with pytest.raises(ValueError):
		validate_formula("(" * 400 + "1" + ")" * 400, TOKENS)


def test_listing_the_tokens_of_a_monstrous_formula_never_raises():
	"""`formula_tokens` promises never to raise. It is how a bad rule is described."""
	assert formula_tokens("+".join(["height"] * 5000)) == set()
	assert formula_tokens("(" * 400 + "height" + ")" * 400) == set()


@pytest.mark.parametrize(
	"formula",
	[
		"height.__class__",
		"__import__",
		"height[0]",
		"height()",
		"(lambda: 1)()",
		"[x for x in (1, 2)][0]",
		"(h := 5)",
		"'abc'",
		'f"{height}"',
		"b'ab'",
		"(1, 2)",
		"height > 1",
		"height and width",
		"1 if height else 2",
		"max(*[1, 2])",
		"round(height, ndigits=2)",
		"import os",
		"1; 2",
		"height × width",
		"height\x00* width",
	],
)
def test_nothing_but_arithmetic_gets_through(formula):
	"""The evaluator is the one place a user's text becomes code."""
	with pytest.raises(ValueError):
		validate_formula(formula, TOKENS)
