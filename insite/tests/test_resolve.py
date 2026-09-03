from insite.calc.resolve import resolve_rule, rule_score

ITEM = {"item_code": "GLZ-DGU-6MM", "item_group": "Glazing",
        "variant_of": None, "has_variants": 0, "attributes": {}}

def r(**kw):
    base = {"source": "?", "measure": "area", "formula": None, "apply_on": "Item Group",
            "item_code": None, "item_template": None, "item_group": None,
            "item_attribute": None, "attribute_value": None, "priority": 0}
    base.update(kw)
    return base

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

# --- Item Template: both ways an item can belong to a template --------------

def test_template_matches_a_variant():
    variant = dict(ITEM, variant_of="GLZ-DGU")
    assert rule_score(r(apply_on="Item Template", item_template="GLZ-DGU"), variant) == 300

def test_template_matches_the_template_item_itself():
    template = dict(ITEM, item_code="GLZ-DGU", has_variants=1)
    assert rule_score(r(apply_on="Item Template", item_template="GLZ-DGU"), template) == 300

def test_template_does_not_match_an_unrelated_item():
    assert rule_score(r(apply_on="Item Template", item_template="GLZ-DGU"), ITEM) == -1

# --- ties are broken by the caller's ordering, so pin that contract ---------

def test_first_rule_wins_when_specificity_is_equal():
    rules = [r(source="first", apply_on="Item Group", item_group="Glazing"),
             r(source="second", apply_on="Item Group", item_group="Glazing")]
    assert resolve_rule(ITEM, rules)["source"] == "first"

def test_specificity_beats_priority():
    # A high-priority group rule must still lose to an item rule.
    rules = [r(source="group", apply_on="Item Group", item_group="Glazing", priority=999),
             r(source="item", apply_on="Item Code", item_code="GLZ-DGU-6MM", priority=0)]
    assert resolve_rule(ITEM, rules)["source"] == "item"

def test_attribute_values_compare_as_text():
    item = dict(ITEM, attributes={"Panes": 2})
    assert rule_score(r(apply_on="Item Attribute Value", item_attribute="Panes",
                        attribute_value="2"), item) == 200
