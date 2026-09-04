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


def test_input_source_options_match_the_code():
	"""The engine compares against these strings; the field offers them."""
	from insite.constants import INPUT_SOURCES

	with open("insite/insite/doctype/measurement_input/measurement_input.json", encoding="utf-8") as fh:
		doc = json.load(fh)
	field = next(f for f in doc["fields"] if f["fieldname"] == "source")
	assert field["options"].splitlines() == list(INPUT_SOURCES)
	assert field["default"] in INPUT_SOURCES


def test_source_files_hold_no_stray_control_characters():
	"""A control character in the source is invisible in every editor and fatal.

	This caught a real one: the word boundaries in the Measurement Rule summary
	had been written as actual backspace bytes (0x08) instead of the two
	characters backslash and b. The regex then looked for a backspace either
	side of the token, matched nothing, and 'Worked out as' quietly showed
	`height * width * count` instead of `Height × Width × Count`. Nothing
	failed; it was found by reading a rule on the site.

	Tabs, newlines and carriage returns are the only control bytes source may
	contain.
	"""
	allowed = {9, 10, 13}
	for path in glob.glob("insite/**/*.py", recursive=True) + glob.glob("insite/**/*.js", recursive=True):
		data = open(path, "rb").read()
		found = sorted({byte for byte in data if byte < 0x20 and byte not in allowed})
		assert not found, f"{path} holds control character(s) {[hex(b) for b in found]}"


def test_insite_owns_no_doctype_erpnext_already_ships():
	"""Insite adds fields to standard doctypes; it does not clone them.

	Rejected work was briefly a doctype of Insite's own before anyone checked
	that ERPNext's Quality Inspection already carried the status, the inspector,
	the verifier, the remarks and the readings, and that both Delivery Note Item
	and Sales Invoice Item already linked to one.
	"""
	own = {os.path.basename(d) for d in _doctype_dirs()}
	assert "rejection" not in own, "rejected work is a Quality Inspection, not a doctype of ours"

	# And the fields that replaced it are the two ERPNext genuinely lacks. Read
	# as source, because config/custom_fields.py imports Frappe and this suite
	# runs without it.
	source = open("insite/config/custom_fields.py", encoding="utf-8").read()
	assert '"Quality Inspection"' in source
	for fieldname in ("scope_item", "custom_rejected_qty", "custom_rejected_amount"):
		assert f'"{fieldname}"' in source, f"{fieldname} should be added to Quality Inspection"


def test_a_quotation_line_can_carry_a_scope():
	"""ERPNext will never put the Scope there, so Insite has to.

	Accounting Dimensions only reach doctypes that post to the ledger, and a
	Quotation does not. Without this field a quote cannot carry a scope, Frappe
	drops the value silently, and the Sales Order made from it is refused by
	Insite's own Scope check — the journey the whole app is built around.
	"""
	source = open("insite/config/custom_fields.py", encoding="utf-8").read()
	assert '"Quotation Item"' in source, "Quotation Item needs its own scope_item field"

	# Read as source: both modules import Frappe, and this suite runs without it.
	dimension = open("insite/config/accounting_dimension.py", encoding="utf-8").read()
	assert 'DIMENSION_FIELDNAME = "scope_item"' in dimension, (
		"the Quotation field must share the dimension's fieldname, or get_mapped_doc "
		"will not carry it into the Sales Order"
	)


def test_doctype_timestamps_have_been_bumped():
	"""Frappe skips a DocType whose file is not newer than the database row.

	Every JSON here is written by hand, so the timestamp has to be bumped by
	hand too. Leaving it equal to `creation` means the scaffolded value was
	never touched, and every change after the first install is silently
	ignored by `bench migrate` — the field is simply never updated on the site.
	"""
	for d in _doctype_dirs() + _dirs(REPORT_GLOB):
		slug = os.path.basename(d)
		with open(f"{d}/{slug}.json", encoding="utf-8") as fh:
			doc = json.load(fh)
		if "modified" not in doc:
			continue
		assert doc["modified"] > doc.get("creation", ""), (
			f"{d}/{slug}.json: bump 'modified' past 'creation' so migrate picks the change up"
		)


def test_the_workspace_agrees_with_itself():
	"""The two lists in a Workspace are edited by hand and drift apart.

	`shortcuts` holds the definitions and `content` holds the layout that
	references them by name. A shortcut missing from either side is a dead tile
	or a tile that never appears, and neither shows up until someone opens the
	app.
	"""
	with open("insite/insite/workspace/insite/insite.json", encoding="utf-8") as fh:
		workspace = json.load(fh)

	defined = [s["label"] for s in workspace["shortcuts"]]
	laid_out = [
		block["data"]["shortcut_name"]
		for block in json.loads(workspace["content"])
		if block["type"] == "shortcut"
	]
	assert defined == laid_out, (
		f"workspace shortcuts and layout disagree: defined={defined}, laid out={laid_out}"
	)


def test_the_workspace_only_points_at_records_that_exist():
	"""A shortcut to a deleted doctype is a dead link in the app's own sidebar.

	Only Insite's own doctypes can be checked here — a shortcut to one of
	ERPNext's (Quality Inspection) is fine and cannot be verified without a
	site. What this catches is the case that actually happened: a doctype
	deleted from the app while its shortcut stayed behind.
	"""
	with open("insite/insite/workspace/insite/insite.json", encoding="utf-8") as fh:
		workspace = json.load(fh)

	own = set()
	for d in _doctype_dirs():
		slug = os.path.basename(d)
		with open(f"{d}/{slug}.json", encoding="utf-8") as fh:
			own.add(json.load(fh)["name"])
	reports = set()
	for d in _dirs(REPORT_GLOB):
		slug = os.path.basename(d)
		with open(f"{d}/{slug}.json", encoding="utf-8") as fh:
			reports.add(json.load(fh)["name"])

	# Anything named like one of ours must actually be one of ours.
	insite_names = {name for name in own | reports}
	for shortcut in workspace["shortcuts"]:
		target = shortcut["link_to"]
		if shortcut["type"] == "Report":
			assert target in reports, f"workspace points at a report that does not exist: {target}"
		elif target.startswith(("Insite", "Measurement", "Work Item", "Scope")):
			assert target in insite_names, f"workspace points at a deleted doctype: {target}"


def test_every_report_has_py_and_init():
	for d in _dirs(REPORT_GLOB):
		slug = os.path.basename(d)
		for required in (f"{slug}.json", f"{slug}.py", "__init__.py"):
			assert os.path.isfile(f"{d}/{required}"), f"{d} is missing {required}"
