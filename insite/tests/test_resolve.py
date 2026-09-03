from insite.calc.resolve import rule_score, resolve_rule

ITEM = {"item_code": "GLZ-DGU-6MM", "item_group": "Glazing",
        "variant_of": None, "has_variants": 0, "attributes": {}}

def r(**kw):
    base = {"source": "?", "measure": "area", "formula": None, "apply_on": "Item Group",
            "item_code": None, "item_template": None, "item_group": None,
            "item_attribute": None, "attribute_value": None, "priority": 0}
    base.update(kw); return base

def test_group_match():
    assert rule_score(r(apply_on="Item Group", item_group="Glazing"), ITEM) == 100

def test_group_nomatch():
    assert rule_score(r(apply_on="Item Group", item_group="Aluminium"), ITEM) == -1

def test_item_code_match_beats_group():
    rules = [r(source="grp", apply_on="Item Group", item_group="Glazing", priority=99),
             r(source="code", apply_on="Item Code", item_code="GLZ-DGU-6MM", priority=0)]
    assert resolve_rule(ITEM, rules)["source"] == "code"

def test_attribute_match():
    item = dict(ITEM, attributes={"Thickness": "6mm"})
    rule = r(apply_on="Item Attribute Value", item_attribute="Thickness", attribute_value="6mm")
    assert rule_score(rule, item) == 200

def test_no_match_returns_none():
    assert resolve_rule(ITEM, [r(apply_on="Item Group", item_group="Wood")]) is None

if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__)
        except BaseException as e:  # noqa
            failed += 1; print("FAIL", fn.__name__, "->", repr(e))
    sys.exit(1 if failed else 0)
