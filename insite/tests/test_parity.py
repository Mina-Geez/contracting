from insite.calc.measures import PRESETS, evaluate_formula

# Oracle: values verified against the legacy `contracting` engine and its unit
# tests. The presets must keep producing the numbers the old app produced.
CASES = [
	("Area", {"height": 1.5, "width": 2.8, "count": 40}, 168.0),
	("Area", {"height": 1.2, "width": 2.4, "count": 3}, 8.64),
	("Perimeter", {"height": 1.5, "width": 2.8, "count": 40}, 344.0),
	("Linear", {"length": 3.0, "count": 60}, 180.0),
	("Piece × Wastage", {"count": 500, "wastage": 1.1}, 550.0),
	("Count", {"count": 25}, 25.0),
]


def test_parity_matches_oracle():
	for preset_name, values, expected in CASES:
		got = evaluate_formula(PRESETS[preset_name]["formula"], values)
		assert abs(got - expected) < 1e-9, f"{preset_name} {values}: {got} != {expected}"
