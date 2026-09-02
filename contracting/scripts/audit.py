"""Contracting vertical — READ-ONLY live-site audit tool (Task A / Phase 0).

SAFETY CONTRACT
---------------
This module performs **only reads**: ``frappe.get_all`` and ``frappe.db.sql``
with ``SELECT`` statements. It never writes, never calls ``db_set`` /
``db.set_value``, never inserts, submits, or deletes anything. It is therefore
safe to run against production through a read-only, permission-checked connector
— but it is *intended* to be run against the STAGING CLONE, which is where all
Phase-2 parity work happens.

USAGE (inside a bench context)
------------------------------
    bench --site <clone> execute contracting.scripts.audit.run

or in a console::

    bench --site <clone> console
    >>> from contracting.scripts import audit
    >>> data = audit.run()          # returns dict, also writes dump files

OUTPUT
------
``run(to_file=True)`` returns the assembled dict and writes two files into the
site path (falling back to the current working directory):

* ``audit_dump.json`` — the complete machine-readable capture.
* ``audit_dump.md``   — a human-readable summary incl. full script bodies.

Each capture section is isolated in try/except so a single failing query (e.g. a
doctype absent on this version) never aborts the whole run; failures are recorded
under the ``errors`` key.
"""

import json
import os

import frappe


def _safe(section, fn, errors):
    """Run one capture closure, recording any exception instead of raising."""
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 - an audit must never abort mid-run
        errors[section] = f"{type(e).__name__}: {e}"
        return None


def collect():
    """Execute every Batch A0-A5 read-only query and return the assembled dict."""
    errors = {}
    out = {"errors": errors}

    # ------------------------------------------------------------------ A0
    # Identity & platform versions (Task A #1).
    out["platform"] = _safe(
        "platform",
        lambda: {
            "site": frappe.local.site,
            "company": frappe.db.get_single_value("Global Defaults", "default_company"),
            "installed_apps": frappe.get_installed_apps(),
            "installed_application": frappe.db.sql(
                "SELECT app_name, app_version, git_branch FROM `tabInstalled Application`",
                as_dict=True,
            ),
        },
        errors,
    )

    # ------------------------------------------------------------------ A1
    # Full customization inventory (Task A #2) + permlevel access rows.
    out["custom_fields"] = _safe(
        "custom_fields",
        lambda: frappe.get_all(
            "Custom Field",
            fields=[
                "name", "dt", "fieldname", "label", "fieldtype", "options",
                "insert_after", "permlevel", "depends_on", "read_only", "reqd",
                "hidden", "fetch_from", "module",
            ],
            order_by="dt, idx",
            limit_page_length=0,
        ),
        errors,
    )
    out["property_setters"] = _safe(
        "property_setters",
        lambda: frappe.get_all(
            "Property Setter",
            fields=["name", "doc_type", "field_name", "property", "property_type", "value", "module"],
            order_by="doc_type, field_name",
            limit_page_length=0,
        ),
        errors,
    )
    # Permlevel access on STANDARD doctypes lives here (role-based price visibility).
    out["permlevel_custom_docperms"] = _safe(
        "permlevel_custom_docperms",
        lambda: frappe.get_all(
            "Custom DocPerm",
            fields=["parent", "role", "permlevel", "read", "write", "create", "submit", "cancel", "amend"],
            filters={"permlevel": [">", 0]},
            order_by="parent, permlevel",
            limit_page_length=0,
        ),
        errors,
    )

    # ------------------------------------------------------------------ A2
    # Script bodies — full text (Task A #2, #4, #8).
    out["client_scripts"] = _safe(
        "client_scripts",
        lambda: frappe.get_all(
            "Client Script",
            fields=["name", "dt", "view", "enabled", "script"],
            limit_page_length=0,
        ),
        errors,
    )
    out["server_scripts"] = _safe(
        "server_scripts",
        lambda: frappe.get_all(
            "Server Script",
            fields=[
                "name", "script_type", "reference_doctype", "doctype_event",
                "api_method", "event_frequency", "disabled", "script",
            ],
            limit_page_length=0,
        ),
        errors,
    )

    # ------------------------------------------------------------------ A3
    # Trade templates / calc keying (Task A #3).
    out["item_templates"] = _safe(
        "item_templates",
        lambda: frappe.get_all(
            "Item",
            filters={"has_variants": 1},
            fields=["name", "item_code", "item_name", "item_group", "stock_uom", "variant_based_on"],
            limit_page_length=0,
        ),
        errors,
    )
    out["item_groups"] = _safe(
        "item_groups",
        lambda: frappe.get_all(
            "Item Group",
            fields=["name", "parent_item_group", "is_group"],
            limit_page_length=0,
        ),
        errors,
    )
    out["item_attributes"] = _safe(
        "item_attributes",
        lambda: frappe.get_all(
            "Item Attribute",
            fields=["name", "numeric_values", "from_range", "to_range", "increment"],
            limit_page_length=0,
        ),
        errors,
    )
    out["variant_attributes_sample"] = _safe(
        "variant_attributes_sample",
        lambda: frappe.get_all(
            "Item Variant Attribute",
            fields=["parent", "attribute", "attribute_value"],
            limit_page_length=500,
        ),
        errors,
    )

    # ------------------------------------------------------------------ A4
    # Clause subsystem, Accounting Dimension, workflows, tolerance (Task A #4, #6, #10).
    out["custom_doctypes"] = _safe(
        "custom_doctypes",
        lambda: frappe.get_all(
            "DocType",
            filters={"custom": 1},
            fields=["name", "module", "istable", "is_submittable", "autoname", "track_changes"],
            limit_page_length=0,
        ),
        errors,
    )
    out["accounting_dimensions"] = _safe(
        "accounting_dimensions",
        lambda: frappe.get_all(
            "Accounting Dimension",
            fields=["name", "document_type", "label", "fieldname", "disabled"],
            limit_page_length=0,
        ),
        errors,
    )
    out["workflows"] = _safe(
        "workflows",
        lambda: frappe.get_all(
            "Workflow",
            fields=["name", "document_type", "is_active", "workflow_state_field"],
            limit_page_length=0,
        ),
        errors,
    )
    out["workflow_states"] = _safe(
        "workflow_states",
        lambda: frappe.get_all(
            "Workflow Document State",
            fields=["parent", "state", "doc_status", "allow_edit"],
            limit_page_length=0,
        ),
        errors,
    )
    out["workflow_transitions"] = _safe(
        "workflow_transitions",
        lambda: frappe.get_all(
            "Workflow Transition",
            fields=["parent", "state", "action", "next_state", "allowed"],
            limit_page_length=0,
        ),
        errors,
    )
    out["tolerance_custom_fields"] = _safe(
        "tolerance_custom_fields",
        lambda: frappe.get_all(
            "Custom Field",
            filters={"fieldname": ["like", "%toler%"]},
            fields=["dt", "fieldname", "label", "fieldtype", "default"],
            limit_page_length=0,
        ),
        errors,
    )

    # ------------------------------------------------------------------ A5
    # Reports, print formats, ETA / cut-optimization detection, CoA (Task A #5, #7, #9, #11, #12).
    out["nonstandard_reports"] = _safe(
        "nonstandard_reports",
        lambda: frappe.get_all(
            "Report",
            filters={"is_standard": "No"},
            fields=[
                "name", "ref_doctype", "report_type", "module", "disabled",
                "query", "report_script", "javascript",
            ],
            limit_page_length=0,
        ),
        errors,
    )
    out["print_formats"] = _safe(
        "print_formats",
        lambda: frappe.get_all(
            "Print Format",
            filters={"standard": "No"},
            fields=["name", "doc_type", "print_format_type", "module", "disabled"],
            limit_page_length=0,
        ),
        errors,
    )
    out["eta_doctype_hits"] = _safe(
        "eta_doctype_hits",
        lambda: frappe.get_all(
            "DocType",
            filters={"name": ["like", "%ETA%"]},
            fields=["name", "module", "custom"],
            limit_page_length=0,
        ),
        errors,
    )
    out["scheduled_jobs"] = _safe(
        "scheduled_jobs",
        lambda: frappe.get_all(
            "Scheduled Job Type",
            fields=["name", "method", "frequency", "stopped"],
            limit_page_length=0,
        ),
        errors,
    )
    out["leaf_accounts"] = _safe(
        "leaf_accounts",
        lambda: frappe.get_all(
            "Account",
            filters={"is_group": 0},
            fields=["name", "account_number", "account_type", "root_type", "company"],
            limit_page_length=0,
        ),
        errors,
    )

    return out


def _md(data):
    """Render a human-readable markdown summary of the capture."""
    lines = ["# Live-site Audit Dump", ""]

    def h(title):
        lines.append("")
        lines.append(f"## {title}")
        lines.append("")

    p = data.get("platform") or {}
    h("Platform")
    lines.append(f"- Site: `{p.get('site')}`")
    lines.append(f"- Default company: `{p.get('company')}`")
    lines.append(f"- Installed apps: {', '.join(p.get('installed_apps') or []) or 'ERROR/None'}")
    for row in (p.get("installed_application") or []):
        lines.append(f"  - {row.get('app_name')} {row.get('app_version')} ({row.get('git_branch')})")

    h("Inventory counts")
    for key in [
        "custom_fields", "property_setters", "permlevel_custom_docperms",
        "client_scripts", "server_scripts", "item_templates", "item_groups",
        "custom_doctypes", "accounting_dimensions", "workflows",
        "nonstandard_reports", "print_formats", "leaf_accounts",
    ]:
        v = data.get(key)
        n = len(v) if isinstance(v, list) else "ERROR/None"
        lines.append(f"- {key}: {n}")

    h("Server Scripts (full bodies)")
    for s in (data.get("server_scripts") or []):
        ev = s.get("doctype_event") or s.get("script_type")
        lines.append(f"### {s.get('name')} — {s.get('reference_doctype')} / {ev} (disabled={s.get('disabled')})")
        lines.append("```python")
        lines.append(s.get("script") or "")
        lines.append("```")

    h("Client Scripts (full bodies)")
    for s in (data.get("client_scripts") or []):
        lines.append(f"### {s.get('name')} — {s.get('dt')} (enabled={s.get('enabled')})")
        lines.append("```javascript")
        lines.append(s.get("script") or "")
        lines.append("```")

    h("Accounting Dimensions")
    for d in (data.get("accounting_dimensions") or []):
        lines.append(f"- {d.get('document_type')} → field `{d.get('fieldname')}` (disabled={d.get('disabled')})")

    h("Tolerance custom fields")
    for d in (data.get("tolerance_custom_fields") or []):
        lines.append(f"- {d.get('dt')}.{d.get('fieldname')} ({d.get('fieldtype')}) default={d.get('default')}")

    h("Non-standard reports")
    for r in (data.get("nonstandard_reports") or []):
        lines.append(f"- {r.get('name')} [{r.get('report_type')}] on {r.get('ref_doctype')} (disabled={r.get('disabled')})")

    h("Print formats")
    for pf in (data.get("print_formats") or []):
        lines.append(f"- {pf.get('name')} on {pf.get('doc_type')} ({pf.get('print_format_type')})")

    h("ETA / cut-optimization detection")
    eta = [e.get("name") for e in (data.get("eta_doctype_hits") or [])]
    lines.append(f"- ETA-named doctypes: {eta or 'none found'}")

    h("Errors")
    errs = data.get("errors") or {}
    if not errs:
        lines.append("- none")
    for k, v in errs.items():
        lines.append(f"- {k}: {v}")

    return "\n".join(lines)


def run(to_file=True):
    """Collect the audit and (optionally) write dump files. Returns the dict."""
    data = collect()
    if to_file:
        try:
            base = frappe.get_site_path()
        except Exception:  # noqa: BLE001 - fall back to cwd outside a full site context
            base = os.getcwd()
        json_path = os.path.join(base, "audit_dump.json")
        md_path = os.path.join(base, "audit_dump.md")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(_md(data))
        print(f"Audit written:\n  {json_path}\n  {md_path}")
    return data


if __name__ == "__main__":
    raise SystemExit(
        "This module must run inside a bench context, e.g. "
        "`bench --site <clone> execute contracting.scripts.audit.run`"
    )
