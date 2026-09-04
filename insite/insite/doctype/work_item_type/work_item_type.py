"""Work Item Type — a kind of work: Glass, Cladding, Doors.

It is a name and a switch, and that is all it should ever be. How the work is
measured lives on its Measurement Rules, which are their own records so each
can name the fields it reads; the form lists them under Measurement.

It used to carry default accounts per company. Nothing read them, and ERPNext
already holds exactly that — company, income account, expense account, cost
centre — as Item Defaults on the Item and the Item Group, which is what
actually posts. Two places to set an account, one of them a decoration, is
worse than one.
"""

from __future__ import annotations

from frappe.model.document import Document


class WorkItemType(Document):
	pass
