"""Pure most-specific-wins rule resolution (framework-free, offline-testable).

The ladder follows the one ERPNext already teaches on the Item: a default set
on the item beats one set on its brand, which beats one set on its item group.
Nobody has to learn a second ordering.

    Item Code             this exact item
    Item Template         every variant of a template
    Item Attribute Value  every item with an attribute, e.g. 6mm
    Brand                 every item of a make
    Item Group            every item in a group, and in the groups beneath it

**Item Group is a tree, and a rule on a parent reaches everything under it** —
the way an Item Default does. A rule on `Products` covers `Products > Glazing`
until a rule is written on `Glazing` itself, which is nearer and wins. The
nearness bonus is bounded so the whole Item Group band still sits below Brand:
the deepest group in the world never outranks a brand.

The caller passes the group ancestry, nearest first and including the item's own
group, so this module stays free of the framework and testable without a site.
"""

from __future__ import annotations

SPECIFICITY = {
	"Item Code": 500,
	"Item Template": 400,
	"Item Attribute Value": 300,
	"Brand": 200,
	"Item Group": 100,
}

#: How much a nearer item group is worth, and the ceiling on it. 99 keeps the
#: Item Group band at 100-199, under Brand at 200.
NEAREST_GROUP_BONUS = 99


def rule_score(rule, item):
	a = rule.get("apply_on")
	if a == "Item Code":
		return SPECIFICITY[a] if rule.get("item_code") and rule["item_code"] == item.get("item_code") else -1
	if a == "Item Template":
		template = item.get("variant_of") or (item.get("item_code") if item.get("has_variants") else None)
		return SPECIFICITY[a] if rule.get("item_template") and rule["item_template"] == template else -1
	if a == "Item Attribute Value":
		if not rule.get("item_attribute"):
			return -1
		val = (item.get("attributes") or {}).get(rule["item_attribute"])
		return SPECIFICITY[a] if val is not None and str(val) == str(rule.get("attribute_value")) else -1
	if a == "Brand":
		return SPECIFICITY[a] if rule.get("brand") and rule["brand"] == item.get("brand") else -1
	if a == "Item Group":
		return _item_group_score(rule.get("item_group"), item)
	return -1


def _item_group_score(wanted, item):
	"""Higher the nearer the rule's group is to the item's own."""
	if not wanted:
		return -1
	for distance, group in enumerate(_ancestry(item)):
		if group == wanted:
			return SPECIFICITY["Item Group"] + max(0, NEAREST_GROUP_BONUS - distance)
	return -1


def _ancestry(item):
	"""The item's group, then its parents, nearest first.

	Falls back to the item's own group alone, so a caller that knows nothing
	about the tree still gets the exact match it used to get.
	"""
	ancestry = item.get("item_group_ancestry")
	if ancestry:
		return ancestry
	group = item.get("item_group")
	return [group] if group else []


def resolve_rule(item, rules):
	best, best_score = None, -1
	for rule in rules:  # pre-sorted priority desc, recency desc
		s = rule_score(rule, item)
		if s > best_score:
			best, best_score = rule, s
	return best
