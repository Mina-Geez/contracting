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
PRINT_FORMAT_GLOB = "insite/insite/print_format/*/"

#: ERPNext reports the workspace points at rather than Insite rebuilding them.
#: Both work per scope because Insite registers the Scope as an accounting
#: dimension. `test_the_borrowed_reports_are_really_there` proves they exist.
BORROWED_REPORTS = {"Profitability Analysis", "Budget Variance Report"}


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
	for d in _doctype_dirs() + _dirs(REPORT_GLOB) + _dirs(PRINT_FORMAT_GLOB):
		slug = os.path.basename(d)
		with open(f"{d}/{slug}.json", encoding="utf-8") as fh:
			doc = json.load(fh)
		if "modified" not in doc:
			continue
		assert doc["modified"] > doc.get("creation", ""), (
			f"{d}/{slug}.json: bump 'modified' past 'creation' so migrate picks the change up"
		)


def test_print_formats_are_wired_up():
	"""Each print format points at a document Insite actually touches, and
	renders through the shared template rather than its own copy of it."""
	from insite.constants import MEASURED_DOCTYPES

	dirs = _dirs(PRINT_FORMAT_GLOB)
	assert dirs, "no print formats found"

	for d in dirs:
		slug = os.path.basename(d)
		assert os.path.isfile(f"{d}/__init__.py"), f"{d} is missing __init__.py"
		with open(f"{d}/{slug}.json", encoding="utf-8") as fh:
			fmt = json.load(fh)

		assert fmt["doctype"] == "Print Format"
		assert fmt["module"] == "Insite"
		assert fmt["standard"] == "Yes", "shipped with the app, not a site customisation"
		assert fmt["print_format_type"] == "Jinja"
		assert fmt["custom_format"] == 1, "without this Frappe ignores the html field"
		assert fmt["doc_type"] in MEASURED_DOCTYPES, (
			f"{slug} prints {fmt['doc_type']}, which Insite does not measure"
		)
		assert "measured_items.html" in fmt["html"], "the markup lives in one shared template"

	for template in ("measured_items.html", "measured_rows.html"):
		assert os.path.isfile(f"insite/templates/includes/{template}"), (
			f"the print formats include templates/includes/{template}"
		)


def test_the_print_templates_escape_what_they_print():
	"""Frappe renders print formats with Jinja autoescaping OFF.

	A format legitimately prints HTML fields — Terms is a Text Editor — so the
	whole template is unescaped by default, and every other interpolation has
	to escape itself. It did not: an item name of `<script>alert(1)</script>`
	reached the printed page and ran, as did a scope title of `<img src=x
	onerror=...>`. Both are plain text that lose nothing by being escaped.

	So: every `{{ ... }}` in these templates ends in `| e`, except the ones
	listed here, which are HTML on purpose.
	"""
	allowed_raw = {"doc.terms"}

	for template in ("measured_items.html", "measured_rows.html"):
		path = f"insite/templates/includes/{template}"
		body = open(path, encoding="utf-8").read()
		for expression in re.findall(r"\{\{(.*?)\}\}", body, re.DOTALL):
			printed = expression.strip()
			if printed in allowed_raw:
				continue
			assert printed.endswith("| e"), (
				f"{path} prints {printed!r} unescaped. Autoescaping is off in print "
				"formats, so add `| e` — or add it to allowed_raw if it is meant to be HTML."
			)


def test_every_table_the_report_filters_by_scope_is_indexed():
	"""Contract Progress reads these with `scope_item in (...)` on every run.

	Neither ERPNext's dimension machinery nor Insite's own custom fields index
	the column, so without this the report scans a table that grows a row per
	line of every document a contractor raises. The list of tables the report
	touches and the list Insite indexes have to stay the same list.
	"""
	from insite.constants import ITEM_DOCTYPES, QUALITY_INSPECTION

	dimension = open("insite/config/accounting_dimension.py", encoding="utf-8").read()
	report = open("insite/insite/report/contract_progress/contract_progress.py", encoding="utf-8").read()

	# Derived from the one list of places a Scope can live, so the two cannot
	# drift. A hand-kept copy did, and missed two of the nine line tables.
	assert "_INDEXED_TABLES = (*ITEM_DOCTYPES, QUALITY_INSPECTION)" in dimension
	indexed = set(ITEM_DOCTYPES) | {QUALITY_INSPECTION}

	for doctype in re.findall(r'_sum_by_scope\(\s*"([^"]+)"', report):
		assert doctype in indexed, f"the report filters {doctype} by scope but nothing indexes it"


#: Standard Frappe and ERPNext labels. Insite shows them but does not own them,
#: and Frappe's own Arabic already covers every one — checked on a bench.
#: Translating them again here would fight it.
_THEIRS_TO_TRANSLATE = {
	"Active",
	"Cancelled",
	"Company",
	"Completed",
	"Currency",
	"Customer",
	"Description",
	"Disabled",
	"Draft",
	"Item",
	"Item Group",
	"On Hold",
	"Priority",
	"Project",
	"Series",
	"Status",
	"Title",
	"UOM",
}

_TRANSLATABLE_CALL = re.compile(
	r"""(?<![A-Za-z0-9_])_{1,2}\(\s*((?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')"""
	r"""(?:\s*(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'))*)"""
)


def _strings_the_app_shows():
	"""Every `_()` and `__()` call, plus the labels and help on the forms."""
	shown = set()

	for path in glob.glob("insite/**/*.py", recursive=True) + glob.glob("insite/**/*.js", recursive=True):
		if "__pycache__" in path or "test_" in path:
			continue
		for match in _TRANSLATABLE_CALL.finditer(open(path, encoding="utf-8").read()):
			pieces = re.findall(r'"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'', match.group(1))
			text = "".join(a or b for a, b in pieces).replace('\\"', '"').replace("\\'", "'").strip()
			if len(text) > 1 and not text.isdigit():
				shown.add(text)

	for path in glob.glob("insite/insite/**/*.json", recursive=True):
		doc = json.load(open(path, encoding="utf-8"))
		if doc.get("doctype") == "DocType":
			shown.add(doc["name"])
		for field in doc.get("fields", []):
			for key in ("label", "description"):
				if field.get(key) and len(field[key]) > 1:
					shown.add(field[key].strip())
			if field.get("fieldtype") == "Select" and field.get("options"):
				shown.update(o.strip() for o in field["options"].split("\n") if len(o.strip()) > 1)
	return shown


def _arabic():
	body = open("insite/locale/ar.po", encoding="utf-8").read()
	return {
		m.group(1): m.group(2)
		for m in re.finditer(r'msgid "((?:[^"\\]|\\.)*)"\s*\nmsgstr "((?:[^"\\]|\\.)*)"', body)
		if m.group(1)
	}


def test_the_arabic_keeps_up_with_the_app():
	"""The product is bilingual, and a translation file rots silently.

	This one did: it still translated "Variation Order" and "Variation Lines"
	weeks after those doctypes were deleted, while a hundred and sixty strings
	the app had grown since were never translated at all. Nothing failed,
	because nothing was looking.
	"""
	shown = _strings_the_app_shows()
	arabic = _arabic()

	untranslated = sorted(
		text
		for text in shown - set(arabic) - _THEIRS_TO_TRANSLATE
		# naming series patterns are not prose
		if not re.fullmatch(r"[A-Z]{2,4}-[.#Y\-]*", text)
	)
	assert not untranslated, "no Arabic for: " + "; ".join(untranslated)

	dead = sorted(set(arabic) - shown)
	assert not dead, "ar.po translates strings the app no longer shows: " + "; ".join(dead)


def test_the_arabic_keeps_every_placeholder():
	"""A translation that drops a {0} formats into a message missing its number."""
	for english, arabic in _arabic().items():
		expected = sorted(re.findall(r"\{\d+\}", english))
		assert sorted(re.findall(r"\{\d+\}", arabic)) == expected, (
			f"placeholders differ between {english!r} and its Arabic"
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

	Only Insite's own records can be checked here — a shortcut to one of
	ERPNext's is fine and cannot be verified without a site. What this catches is
	the case that actually happened: a doctype deleted from the app while its
	shortcut stayed behind.

	The reports Insite borrows rather than builds are listed rather than waved
	through, so a typo in one is still caught here and the list itself says which
	ERPNext reports the product depends on. A bench test proves they exist.
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
			assert target in reports | BORROWED_REPORTS, (
				f"workspace points at a report that does not exist: {target}"
			)
		elif target.startswith(("Insite", "Measurement", "Work Item", "Scope")):
			assert target in insite_names, f"workspace points at a deleted doctype: {target}"


def test_every_report_has_py_and_init():
	for d in _dirs(REPORT_GLOB):
		slug = os.path.basename(d)
		for required in (f"{slug}.json", f"{slug}.py", "__init__.py"):
			assert os.path.isfile(f"{d}/{required}"), f"{d} is missing {required}"
