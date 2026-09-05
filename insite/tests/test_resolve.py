from insite.calc.resolve import SPECIFICITY, resolve_rule, rule_score

ITEM = {
	"item_code": "GLZ-DGU-6MM",
	"item_group": "Glazing",
	"brand": None,
	"variant_of": None,
	"has_variants": 0,
	"attributes": {},
}


def r(**kw):
	base = {
		"source": "?",
		"measure": "area",
		"formula": None,
		"apply_on": "Item Group",
		"item_code": None,
		"item_template": None,
		"item_group": None,
		"brand": None,
		"item_attribute": None,
		"attribute_value": None,
		"priority": 0,
	}
	base.update(kw)
	return base


def test_group_match():
	assert rule_score(r(apply_on="Item Group", item_group="Glazing"), ITEM) >= SPECIFICITY["Item Group"]


def test_group_nomatch():
	assert rule_score(r(apply_on="Item Group", item_group="Aluminium"), ITEM) == -1


def test_item_code_match_beats_group():
	rules = [
		r(source="grp", apply_on="Item Group", item_group="Glazing", priority=99),
		r(source="code", apply_on="Item Code", item_code="GLZ-DGU-6MM", priority=0),
	]
	assert resolve_rule(ITEM, rules)["source"] == "code"


def test_attribute_match():
	item = dict(ITEM, attributes={"Thickness": "6mm"})
	rule = r(apply_on="Item Attribute Value", item_attribute="Thickness", attribute_value="6mm")
	assert rule_score(rule, item) == SPECIFICITY["Item Attribute Value"]


def test_no_match_returns_none():
	assert resolve_rule(ITEM, [r(apply_on="Item Group", item_group="Wood")]) is None


# --- Item Template: both ways an item can belong to a template --------------


def test_template_matches_a_variant():
	variant = dict(ITEM, variant_of="GLZ-DGU")
	assert (
		rule_score(r(apply_on="Item Template", item_template="GLZ-DGU"), variant)
		== SPECIFICITY["Item Template"]
	)


def test_template_matches_the_template_item_itself():
	template = dict(ITEM, item_code="GLZ-DGU", has_variants=1)
	assert (
		rule_score(r(apply_on="Item Template", item_template="GLZ-DGU"), template)
		== SPECIFICITY["Item Template"]
	)


def test_template_does_not_match_an_unrelated_item():
	assert rule_score(r(apply_on="Item Template", item_template="GLZ-DGU"), ITEM) == -1


# --- ties are broken by the caller's ordering, so pin that contract ---------


def test_first_rule_wins_when_specificity_is_equal():
	rules = [
		r(source="first", apply_on="Item Group", item_group="Glazing"),
		r(source="second", apply_on="Item Group", item_group="Glazing"),
	]
	assert resolve_rule(ITEM, rules)["source"] == "first"


def test_specificity_beats_priority():
	# A high-priority group rule must still lose to an item rule.
	rules = [
		r(source="group", apply_on="Item Group", item_group="Glazing", priority=999),
		r(source="item", apply_on="Item Code", item_code="GLZ-DGU-6MM", priority=0),
	]
	assert resolve_rule(ITEM, rules)["source"] == "item"


def test_attribute_values_compare_as_text():
	item = dict(ITEM, attributes={"Panes": 2})
	assert (
		rule_score(r(apply_on="Item Attribute Value", item_attribute="Panes", attribute_value="2"), item)
		== SPECIFICITY["Item Attribute Value"]
	)


# --- the ladder, in the order the Item already teaches -----------------------


def test_the_ladder_reads_item_then_brand_then_group():
	"""ERPNext's own ordering on the Item: the narrower default wins.

	Asserted as an ordering rather than as numbers, because the numbers are an
	implementation detail and the ordering is the promise.
	"""
	assert (
		SPECIFICITY["Item Code"]
		> SPECIFICITY["Item Template"]
		> SPECIFICITY["Item Attribute Value"]
		> SPECIFICITY["Brand"]
		> SPECIFICITY["Item Group"]
	)


def test_a_brand_rule_beats_a_group_rule_and_loses_to_the_item():
	item = dict(ITEM, brand="Guardian")
	rules = [
		r(source="group", apply_on="Item Group", item_group="Glazing", priority=999),
		r(source="brand", apply_on="Brand", brand="Guardian"),
	]
	assert resolve_rule(item, rules)["source"] == "brand"

	rules.append(r(source="item", apply_on="Item Code", item_code="GLZ-DGU-6MM"))
	assert resolve_rule(item, rules)["source"] == "item"


def test_a_brand_rule_ignores_an_item_of_another_make():
	assert rule_score(r(apply_on="Brand", brand="Guardian"), dict(ITEM, brand="Saint-Gobain")) == -1
	assert rule_score(r(apply_on="Brand", brand="Guardian"), ITEM) == -1


# --- item groups are a tree, the way Item Defaults are ----------------------


def test_a_rule_on_a_parent_group_reaches_the_items_beneath_it():
	"""A rule on Products covers Products > Glazing until Glazing has its own."""
	item = dict(ITEM, item_group_ancestry=["Glazing", "Products", "All Item Groups"])
	assert rule_score(r(apply_on="Item Group", item_group="Products"), item) > 0
	assert rule_score(r(apply_on="Item Group", item_group="All Item Groups"), item) > 0


def test_the_nearer_group_wins():
	item = dict(ITEM, item_group_ancestry=["Glazing", "Products", "All Item Groups"])
	rules = [
		r(source="root", apply_on="Item Group", item_group="All Item Groups", priority=999),
		r(source="parent", apply_on="Item Group", item_group="Products"),
		r(source="own", apply_on="Item Group", item_group="Glazing"),
	]
	assert resolve_rule(item, rules)["source"] == "own"
	assert resolve_rule(item, rules[:2])["source"] == "parent"


def test_even_the_nearest_group_loses_to_a_brand():
	"""The nearness bonus must not let a deep group climb out of its band."""
	item = dict(ITEM, brand="Guardian", item_group_ancestry=["Glazing", "Products", "All Item Groups"])
	rules = [
		r(source="own group", apply_on="Item Group", item_group="Glazing"),
		r(source="brand", apply_on="Brand", brand="Guardian"),
	]
	assert resolve_rule(item, rules)["source"] == "brand"


def test_a_group_outside_the_line_of_descent_still_does_not_match():
	item = dict(ITEM, item_group_ancestry=["Glazing", "Products", "All Item Groups"])
	assert rule_score(r(apply_on="Item Group", item_group="Aluminium"), item) == -1


def test_without_an_ancestry_it_matches_the_item_s_own_group_as_before():
	"""A caller that knows nothing of the tree keeps the old exact match."""
	assert rule_score(r(apply_on="Item Group", item_group="Glazing"), ITEM) > 0
	assert rule_score(r(apply_on="Item Group", item_group="Products"), ITEM) == -1
