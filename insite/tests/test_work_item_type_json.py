import glob
import json


def test_all_insite_doctype_json_parse():
	files = glob.glob("insite/insite/doctype/**/*.json", recursive=True)
	assert files, "no doctype json found"
	for f in files:
		with open(f, encoding="utf-8") as fh:
			d = json.load(fh)
		assert d.get("name"), f"{f} missing name"
