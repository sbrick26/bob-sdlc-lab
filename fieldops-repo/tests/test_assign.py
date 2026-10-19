"""Tests that lock in the current behaviour of fieldops/assign.py.

These tests call pick_crew directly with synthetic crew/order dicts.
No real CSV files are read or written by pick_crew itself.
The conftest.py fixture redirects store.ORDERS_FILE / store.CREWS_FILE so that
any indirect store call in assign_order also stays off the real files.
"""
from fieldops.assign import pick_crew


def _crew(id_, home_site, skills, load=0):
    return {"id": id_, "home_site": home_site, "skills": skills, "load": load}


# ---------------------------------------------------------------------------
# AC-1: priority-1 rule — home crew goes first regardless of skill
# ---------------------------------------------------------------------------
def test_pick_crew_priority1_home_crew_goes_first():
    crews = [
        _crew("B", "north", ["transformer"]),
        _crew("A", "south", ["feeder"]),   # home crew for south, wrong skill
    ]
    order = {"site": "south", "equipment": "transformer", "priority": 1}
    # Crew A is the home crew for "south"; at priority 1 it must be chosen
    # even though its skills list does not contain "transformer".
    assert pick_crew(order, crews) == "A"


# ---------------------------------------------------------------------------
# AC-2: site rule — priority-2 home crew needs the skill
# ---------------------------------------------------------------------------
def test_pick_crew_priority2_home_crew_needs_skill():
    crews = [
        _crew("B", "north", ["transformer"]),
        _crew("A", "south", ["transformer"]),  # home crew with the skill
    ]
    order = {"site": "south", "equipment": "transformer", "priority": 2}
    assert pick_crew(order, crews) == "A"


# ---------------------------------------------------------------------------
# AC-3: skill fallback — first free crew in file order with the required skill
# ---------------------------------------------------------------------------
def test_pick_crew_skill_fallback():
    crews = [
        _crew("C", "east",  ["feeder"]),
        _crew("B", "west",  ["transformer"]),
        _crew("A", "north", ["transformer"]),
    ]
    # site="south" matches no home crew, so fallback to skill search
    order = {"site": "south", "equipment": "transformer", "priority": 3}
    # B comes before A in file order and has the skill
    assert pick_crew(order, crews) == "B"


# ---------------------------------------------------------------------------
# AC-4: no-site edge case — returns without error
# ---------------------------------------------------------------------------
def test_pick_crew_no_site():
    crews = [
        _crew("B", "north", ["transformer"]),
        _crew("A", "south", ["transformer"]),
    ]
    order = {"site": "", "equipment": "transformer", "priority": 3}
    result = pick_crew(order, crews)
    # No assertion on which crew — just that it returns a non-empty string
    assert isinstance(result, str) and result != ""
