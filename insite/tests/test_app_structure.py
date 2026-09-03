"""Structural checks that catch install-time failures without a bench.

Frappe imports a Python module for EVERY DocType it syncs — child tables
included — via `load_doctype_module` in `DocType.on_update`. A DocType folder
with only a .json aborts `install-app` with "No module named ...". These tests
reproduce that requirement offline so the gate fails here, not on a live site.
"""

import glob
import json
import os
import re

DOCTYPE_GLOB = "insite/insite/doctype/*/"
REPORT_GLOB = "insite/insite/report/*/"


def _dirs(pattern):
	"""Real source folders under `pattern`, ignoring build artefacts."""
	found = [d.replace("\\", "/").rstrip("/") for d in glob.glob(pattern)]
	return [d for d in found if not os.path.basename(d).startswith("__")]


def _doctype_dirs():
	dirs = _dirs(DOCTYPE_GLOB)
	assert dirs, "no doctype folders found — run from the repo root"
	return dirs


def test_every_doctype_has_json_controller_and_init():
	for d in _doctype_dirs():
		slug = os.path.basename(d)
		for required in (f"{slug}.json", f"{slug}.py", "__init__.py"):
			assert os.path.isfile(f"{d}/{required}"), f"{d} is missing {required}"


def test_every_doctype_controller_defines_the_expected_class():
	"""Frappe looks for a class named after the DocType, spaces/hyphens removed."""
	for d in _doctype_dirs():
		slug = os.path.basename(d)
		with open(f"{d}/{slug}.json", encoding="utf-8") as fh:
			doctype_name = json.load(fh)["name"]
		expected = doctype_name.replace(" ", "").replace("-", "")
		source = open(f"{d}/{slug}.py", encoding="utf-8").read()
		assert re.search(rf"^class {expected}\(", source, re.MULTILINE), (
			f"{d}/{slug}.py must define `class {expected}(Document)` for DocType {doctype_name!r}"
		)


def test_doctype_folder_name_matches_doctype_name():
	for d in _doctype_dirs():
		slug = os.path.basename(d)
		with open(f"{d}/{slug}.json", encoding="utf-8") as fh:
			doctype_name = json.load(fh)["name"]
		expected_slug = doctype_name.lower().replace(" ", "_").replace("-", "_")
		assert slug == expected_slug, f"folder {slug!r} should be named {expected_slug!r}"


def test_every_doctype_field_order_matches_its_fields():
	for d in _doctype_dirs():
		slug = os.path.basename(d)
		with open(f"{d}/{slug}.json", encoding="utf-8") as fh:
			doc = json.load(fh)
		if "field_order" not in doc:  # child tables may omit it
			continue
		declared = set(doc["field_order"])
		actual = {f["fieldname"] for f in doc.get("fields", [])}
		assert declared == actual, (
			f"{d}/{slug}.json field_order mismatch: "
			f"only in field_order={sorted(declared - actual)}, only in fields={sorted(actual - declared)}"
		)


def test_preset_options_match_the_presets_in_code():
	"""The Select stores what the engine reads back, so the two must agree.

	A mismatch is invisible offline and fatal on a site: Frappe validates a
	Select against its options after the controller runs, so a value the code
	produces but the field does not offer makes the document unsaveable.
	"""
	from insite.calc.measures import PRESET_CHOICES

	with open("insite/insite/doctype/measurement_rule/measurement_rule.json", encoding="utf-8") as fh:
		doc = json.load(fh)
	field = next(f for f in doc["fields"] if f["fieldname"] == "preset")
	options = field["options"].split("\n")

	assert options == list(PRESET_CHOICES), (
		"measurement_rule.json 'preset' options must match PRESET_CHOICES exactly"
	)
	assert field["default"] in options, "the default must be one of the options"


def test_every_report_has_py_and_init():
	for d in _dirs(REPORT_GLOB):
		slug = os.path.basename(d)
		for required in (f"{slug}.json", f"{slug}.py", "__init__.py"):
			assert os.path.isfile(f"{d}/{required}"), f"{d} is missing {required}"
