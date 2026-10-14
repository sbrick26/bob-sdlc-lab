"""test_assign.py – lock in the current behaviour of fieldops/assign.py."""
import pytest
from fieldops import assign


# ---------------------------------------------------------------------------
# Helpers: plain crew / order dicts used in unit tests that don't touch CSVs.
# ---------------------------------------------------------------------------

def _crew(id_, home_site, skills, load=0):
    return {"id": id_, "home_site": home_site, "skills": skills, "load": load}


def _order(priority=3, site="Alpha", equipment="transformer"):
    return {"priority": priority, "site": site, "equipment": equipment}


# ---------------------------------------------------------------------------
# crew_load
# ---------------------------------------------------------------------------

def test_crew_load_counts_only_assigned(csv_store):
    """crew_load counts only orders whose status is 'assigned'."""
    from fieldops import store
    crews = store.load_crews()
    orders = [
        {"status": "assigned", "crew": "A"},
        {"status": "open",     "crew": "A"},   # not counted
        {"status": "assigned", "crew": "A"},
        {"status": "assigned", "crew": "B"},
    ]
    result = assign.crew_load(crews, orders=orders)
    load_by_id = {c["id"]: c["load"] for c in result}
    assert load_by_id["A"] == 2
    assert load_by_id["B"] == 1
    assert load_by_id["C"] == 0


# ---------------------------------------------------------------------------
# pick_crew – unknown equipment
# ---------------------------------------------------------------------------

def test_unknown_equipment_goes_to_crew_a():
    """Unknown equipment always returns DEFAULT_CREW ('A')."""
    crews = [_crew("B", "Beta", ["transformer"], load=0)]
    order = _order(equipment="nuclear_reactor")
    assert assign.pick_crew(order, crews) == "A"


# ---------------------------------------------------------------------------
# pick_crew – all crews busy
# ---------------------------------------------------------------------------

def test_all_busy_goes_to_crew_a():
    """When every crew is at MAX_LOAD, return DEFAULT_CREW ('A')."""
    crews = [
        _crew("B", "Alpha", ["transformer"], load=assign.MAX_LOAD),
        _crew("C", "Alpha", ["transformer"], load=assign.MAX_LOAD),
    ]
    order = _order(equipment="transformer")
    assert assign.pick_crew(order, crews) == "A"


# ---------------------------------------------------------------------------
# pick_crew – priority 1: home crew goes first, skill or not
# ---------------------------------------------------------------------------

def test_priority_1_home_crew_goes_first_without_skill():
    """Priority 1: the first home-site crew in file order is chosen, skill or not."""
    crews = [
        _crew("H", "Alpha", ["switchgear"],   load=0),   # home crew, NO skill – first in file
        _crew("A", "Alpha", ["feeder"],       load=0),   # has skill, same site
        _crew("B", "Beta",  ["transformer"],  load=0),   # has the skill, wrong site
    ]
    order = _order(priority=1, site="Alpha", equipment="transformer")
    # H is the first free home crew in file order, wins even without the skill.
    assert assign.pick_crew(order, crews) == "H"


# ---------------------------------------------------------------------------
# pick_crew – priority 2: home crew only if it has the skill
# ---------------------------------------------------------------------------

def test_priority_2_home_crew_needs_skill():
    """Priority 2: home crew is chosen only when it also has the required skill."""
    crews = [
        _crew("X", "Alpha", ["feeder"],     load=0),   # home crew, wrong skill
        _crew("Y", "Beta",  ["transformer"],load=0),   # has skill, wrong site
    ]
    order = _order(priority=2, site="Alpha", equipment="transformer")
    # No home crew qualifies, so fall through to skill fallback: Y.
    assert assign.pick_crew(order, crews) == "Y"


def test_priority_2_home_crew_with_skill_is_chosen():
    """Priority 2: home crew with the skill is chosen before others in file order."""
    crews = [
        _crew("X", "Beta",  ["transformer"], load=0),  # has skill, wrong site
        _crew("H", "Alpha", ["transformer"], load=0),  # home crew + skill
    ]
    order = _order(priority=2, site="Alpha", equipment="transformer")
    assert assign.pick_crew(order, crews) == "H"


# ---------------------------------------------------------------------------
# pick_crew – skill fallback
# ---------------------------------------------------------------------------

def test_skill_fallback_first_free_in_file_order():
    """Skill fallback picks the first free crew in file order that has the skill."""
    crews = [
        _crew("A", "Other", ["feeder"],       load=0),  # wrong skill
        _crew("B", "Other", ["transformer"],  load=0),  # has skill – first match
        _crew("C", "Other", ["transformer"],  load=0),  # also has skill – second
    ]
    order = _order(priority=3, site="", equipment="transformer")
    assert assign.pick_crew(order, crews) == "B"


# ---------------------------------------------------------------------------
# pick_crew – no site skips site rules
# ---------------------------------------------------------------------------

def test_no_site_skips_site_rules():
    """An order with no site skips priority-site rules and uses skill fallback."""
    crews = [
        _crew("H", "Alpha", ["feeder"], load=0),        # would be home crew if site set
        _crew("S", "Beta",  ["transformer"], load=0),   # has the skill
    ]
    order = _order(priority=1, site="", equipment="transformer")
    # site is empty → site rules are skipped → skill fallback → S
    assert assign.pick_crew(order, crews) == "S"


# ---------------------------------------------------------------------------
# assign_order
# ---------------------------------------------------------------------------

def test_assign_order_ok(csv_store):
    """assign_order returns True and updates the order when crew and order exist."""
    from fieldops import store
    result = assign.assign_order(1, "A")
    assert result is True
    updated = store.get_order(1)
    assert updated["crew"] == "A"
    assert updated["status"] == "assigned"


def test_assign_order_unknown_crew(csv_store):
    """assign_order returns False when the crew_id is not in the crews file."""
    result = assign.assign_order(1, "Z")
    assert result is False


def test_assign_order_missing_order(csv_store):
    """assign_order returns False when order_id does not exist."""
    result = assign.assign_order(999, "A")
    assert result is False


def test_assign_order_closed_order(csv_store):
    """assign_order returns False when the order is closed."""
    from fieldops import store
    store.update_order(1, status="closed")
    result = assign.assign_order(1, "A")
    assert result is False
