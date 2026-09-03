import pytest

from insite.calc.measures import (
	CUSTOM,
	MANUAL,
	PRESET_CHOICES,
	PRESETS,
	evaluate_formula,
	is_valid_token,
	suggest_token,
)

# --- the presets are just a starting pair of inputs and formula --------------


def test_every_preset_formula_uses_exactly_its_own_inputs():
	from insite.calc.measures import formula_tokens

	for name, preset in PRESETS.items():
		tokens = {token for token, _field in preset["inputs"]}
		assert formula_tokens(preset["formula"]) == tokens, f"{name} names an input it does not declare"


def test_preset_choices_cover_the_presets_plus_manual_and_custom():
	assert set(PRESET_CHOICES) == set(PRESETS) | {MANUAL, CUSTOM}


def test_area_preset_computes_the_expected_quantity():
	preset = PRESETS["Area"]
	assert evaluate_formula(preset["formula"], {"height": 1.5, "width": 2.8, "count": 40}) == pytest.approx(
		168.0
	)


def test_perimeter_preset():
	preset = PRESETS["Perimeter"]
	assert evaluate_formula(preset["formula"], {"height": 1.5, "width": 2.8, "count": 40}) == 344.0


def test_linear_preset():
	assert evaluate_formula(PRESETS["Linear"]["formula"], {"length": 3.0, "count": 60}) == 180.0


def test_count_preset_keeps_a_zero():
	# The count IS the quantity here, so a zero must stay a zero rather than
	# become one and invent a unit nobody ordered.
	assert evaluate_formula(PRESETS["Count"]["formula"], {"count": 0}) == 0.0
	assert evaluate_formula(PRESETS["Count"]["formula"], {"count": 25}) == 25.0


def test_piece_waste_preset():
	formula = PRESETS["Piece × Wastage"]["formula"]
	assert evaluate_formula(formula, {"count": 500, "wastage": 1.1}) == pytest.approx(550.0)


def test_volume_preset():
	formula = PRESETS["Volume"]["formula"]
	assert evaluate_formula(formula, {"height": 2, "width": 3, "length": 4, "count": 2}) == 48.0


# --- a rule may name its inputs whatever the site calls them -----------------


def test_a_formula_can_use_a_sites_own_field_name():
	assert evaluate_formula(
		"height * width * panels", {"height": 1.2, "width": 2.4, "panels": 3}
	) == pytest.approx(8.64)


def test_blank_values_are_treated_as_zero():
	assert evaluate_formula("height * width", {"height": "", "width": None}) == 0.0


# --- tokens ------------------------------------------------------------------


def test_suggest_token_from_a_label():
	assert suggest_token("Number of Panels") == "number_of_panels"
	assert suggest_token("Height") == "height"
	assert suggest_token("  ") == "field"
	assert suggest_token("2nd Layer") == "f_2nd_layer"


def test_valid_tokens():
	assert is_valid_token("height")
	assert is_valid_token("number_of_panels")
	assert not is_valid_token("Number of Panels")
	assert not is_valid_token("2panels")
	assert not is_valid_token("")
