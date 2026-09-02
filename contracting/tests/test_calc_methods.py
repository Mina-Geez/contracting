"""Pure unit tests for the calculation methods (no Frappe / no site required).

Run standalone from the repo root:
    python -m unittest contracting.tests.test_calc_methods
or under bench:
    bench --site <site> run-tests --app contracting
"""

import unittest

from contracting.calc import methods


class TestCalcMethods(unittest.TestCase):
	def test_area(self):
		# 1.2 x 2.4 x 3 panels = 8.64
		self.assertAlmostEqual(methods.compute("area", height=1.2, width=2.4, base_qty=3), 8.64)

	def test_area_defaults_base_qty_one(self):
		# base_qty defaults to 1.0 when not provided
		self.assertAlmostEqual(methods.compute("area", height=2, width=3), 6.0)

	def test_perimeter(self):
		# (1.2 + 2.4) * 2 * 3 = 21.6
		self.assertAlmostEqual(methods.compute("perimeter", height=1.2, width=2.4, base_qty=3), 21.6)

	def test_linear(self):
		self.assertAlmostEqual(methods.compute("linear", length=6, base_qty=2), 12.0)

	def test_piece_waste(self):
		self.assertAlmostEqual(methods.compute("piece_waste", base_qty=10, waste_factor=1.05), 10.5)

	def test_bom_driven(self):
		self.assertAlmostEqual(methods.compute("bom_driven", base_qty=5, waste_factor=1.1), 5.5)

	def test_manual_returns_none(self):
		self.assertIsNone(methods.compute("manual", base_qty=99))

	def test_unknown_method_raises(self):
		with self.assertRaises(ValueError):
			methods.compute("does_not_exist", base_qty=1)

	def test_coercion_of_none_and_blank(self):
		# None/"" dimensions coerce to 0.0 (not a crash)
		self.assertEqual(methods.compute("area", height=None, width="", base_qty=3), 0.0)

	def test_formula_requires_expression(self):
		# formula method with no expression raises before touching frappe
		with self.assertRaises(ValueError):
			methods.compute("formula", height=1, width=2, formula="")

	def test_standard_registry_keys(self):
		expected = {"area", "perimeter", "linear", "piece_waste", "bom_driven", "manual", "formula"}
		self.assertEqual(methods.STANDARD_METHOD_KEYS, expected)


if __name__ == "__main__":
	unittest.main()
