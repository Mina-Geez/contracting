"""Pure most-specific-wins rule resolution (framework-free, offline-testable)."""

from __future__ import annotations

SPECIFICITY = {"Item Code": 400, "Item Template": 300, "Item Attribute Value": 200, "Item Group": 100}


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
	if a == "Item Group":
		return (
			SPECIFICITY[a] if rule.get("item_group") and rule["item_group"] == item.get("item_group") else -1
		)
	return -1


def resolve_rule(item, rules):
	best, best_score = None, -1
	for rule in rules:  # pre-sorted priority desc, recency desc
		s = rule_score(rule, item)
		if s > best_score:
			best, best_score = rule, s
	return best
