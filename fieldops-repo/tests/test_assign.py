"""
test_assign.py — characterisation tests for fieldops/assign.py.

These tests lock in the current behaviour of pick_crew, crew_load and
assign_order.  Do NOT change the production code to make a test pass;
if something looks wrong, add a comment here.
"""
import pytest

from fieldops import assign, store


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_crews(load=0):
    """Return the four crews as dicts, matching data/crews.csv."""
    return [
        {"id": "A", "name": "Alpha Crew",   "home_site": "North Substation",
         "skills": ["transformer", "switchgear"], "load": load},
        {"id": "B", "name": "Bravo Crew",   "home_site": "North Substation",
         "skills": ["feeder", "rack", "transformer"], "load": load},
        {"id": "C", "name": "Charlie Crew", "home_site": "South Substation",
         "skills": ["transformer", "feeder"], "load": load},
        {"id": "D", "name": "Delta Crew",   "home_site": "East Yard",
         "skills": ["switchgear", "rack"], "load": load},
    ]


def make_order(**kwargs):
    base = {"site": "North Substation", "equipment": "transformer",
            "priority": "3", "status": "open", "crew": ""}
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# pick_crew — priority-1 rule: home crew goes first regardless of skill
# ---------------------------------------------------------------------------

def test_pick_crew_priority1_home_crew():
    """
    Priority-1 order at North Substation.
    Crew A is home there.  The rule says the home crew goes even without
    the required skill — we use 'feeder' which A does NOT have, to prove
    skill is irrelevant for prio-1.
    """
    order = make_order(site="North Substation", equipment="feeder", priority="1")
    crews = make_crews()
    result = assign.pick_crew(order, crews)
    # A is first in file order with home_site == "North Substation"
    assert result == "A"


# ---------------------------------------------------------------------------
# pick_crew — priority-2 rule: home crew only if they have the skill
# ---------------------------------------------------------------------------

def test_pick_crew_priority2_home_with_skill():
    """
    Priority-2 order at South Substation for a transformer.
    Crew C is home there and has 'transformer' -> C should be chosen.
    """
    order = make_order(site="South Substation", equipment="transformer", priority="2")
    crews = make_crews()
    result = assign.pick_crew(order, crews)
    assert result == "C"


def test_pick_crew_priority2_home_without_skill():
    """
    Priority-2 order at East Yard for a feeder.
    Crew D is home at East Yard but does NOT have 'feeder'.
    The home-crew rule must NOT fire; skill fallback runs instead.
    First free crew in file order with 'feeder' is B.
    """
    order = make_order(site="East Yard", equipment="feeder", priority="2")
    crews = make_crews()
    result = assign.pick_crew(order, crews)
    assert result == "B"


# ---------------------------------------------------------------------------
# pick_crew — skill fallback (no priority / prio-3)
# ---------------------------------------------------------------------------

def test_pick_crew_skill_fallback():
    """
    No priority constraint, no special site match needed.
    Equipment is 'rack'; first crew in file order with 'rack' is B.
    """
    order = make_order(site="", equipment="rack", priority="3")
    crews = make_crews()
    result = assign.pick_crew(order, crews)
    assert result == "B"


# ---------------------------------------------------------------------------
# pick_crew — order with no site
# ---------------------------------------------------------------------------

def test_pick_crew_no_site():
    """
    Order has no site.  The 2014 TODO in assign.py notes that missing
    site silently skips ALL site rules and drops straight to the skill
    fallback.  This test asserts the current (possibly wrong) behaviour
    so that any future fix is a deliberate, visible change.

    We use equipment='feeder' and prio-1 so the assertion is unambiguous:
    - If site rules fired for the South Substation home crew, result would be 'C'.
    - Because site is blank, site rules are skipped; skill fallback runs
      and picks the first free crew in file order with 'feeder' -> 'B'.

    TODO (2014, assign.py line 53): confirm whether skipping site rules
    for a blank site is intentional.
    """
    # equipment='feeder', prio-1, blank site
    # South Substation home crew with feeder skill is C; correct answer is B (fallback)
    order = make_order(site="", equipment="feeder", priority="1")
    crews = make_crews()
    result = assign.pick_crew(order, crews)
    # Skill fallback: first free crew with 'feeder' in file order is B
    assert result == "B"


# ---------------------------------------------------------------------------
# pick_crew — unknown equipment always goes to crew A
# ---------------------------------------------------------------------------

def test_pick_crew_unknown_equipment():
    """Unknown equipment bypasses all rules and returns DEFAULT_CREW ('A')."""
    order = make_order(equipment="widget")
    crews = make_crews()
    assert assign.pick_crew(order, crews) == "A"


# ---------------------------------------------------------------------------
# pick_crew — all crews busy
# ---------------------------------------------------------------------------

def test_pick_crew_all_busy():
    """When every crew is at MAX_LOAD the overflow also goes to crew A."""
    order = make_order(site="South Substation", equipment="feeder", priority="1")
    crews = make_crews(load=assign.MAX_LOAD)
    assert assign.pick_crew(order, crews) == "A"


# ---------------------------------------------------------------------------
# assign_order — integration (uses temp_store fixture)
# ---------------------------------------------------------------------------

def test_assign_order_valid(temp_store):
    """assign_order returns True and updates the order when crew exists."""
    orders = store.load_orders()
    first_open = next(o for o in orders if o["status"] != "closed")
    order_id = first_open["id"]

    result = assign.assign_order(order_id, "B")

    assert result is True
    updated = store.get_order(order_id)
    assert updated["crew"] == "B"
    assert updated["status"] == "assigned"


def test_assign_order_unknown_crew(temp_store):
    """assign_order returns False when the crew id does not exist."""
    orders = store.load_orders()
    first_open = next(o for o in orders if o["status"] != "closed")
    result = assign.assign_order(first_open["id"], "Z")
    assert result is False
