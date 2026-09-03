import json, glob, os

def test_all_insite_doctype_json_parse():
    files = glob.glob("insite/insite/doctype/**/*.json", recursive=True)
    assert files, "no doctype json found"
    for f in files:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        assert d.get("name"), f"{f} missing name"

if __name__ == "__main__":
    import sys
    try:
        test_all_insite_doctype_json_parse(); print("PASS json"); sys.exit(0)
    except BaseException as e:  # noqa
        print("FAIL ->", repr(e)); sys.exit(1)
