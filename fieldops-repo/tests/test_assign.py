"""Characterization tests for fieldops/assign.py: they lock in today's behaviour.

Anything that looks wrong is noted in a comment and asserted as-is, not fixed.
"""
from fieldops import assign, store


def crew(cid, home_site, skills, load=0):
    return {"id": cid, "home_site": home_site, "skills": skills, "load": load}


def order(site="North", equipment="transformer", priority=3):
    return {"site": site, "equipment": equipment, "priority": priority}


# ---- pick_crew -------------------------------------------------------------

def test_pick_crew_priority1_home_crew():
    # Priority 1: the free home crew goes first, even without the skill.
    # Crew X comes first in file order and has the skill; crew H is home but lacks it.
    crews = [crew("X", "South", ["transformer"]), crew("H", "North", ["rack"])]
    assert assign.pick_crew(order(site="North", equipment="transformer", priority=1), crews) == "H"


def test_pick_crew_priority1_busy_home_crew_falls_back_to_skill():
    crews = [
        crew("H", "North", ["rack"], load=assign.MAX_LOAD),
        crew("X", "South", ["transformer"]),
    ]
    assert assign.pick_crew(order(site="North", equipment="transformer", priority=1), crews) == "X"


def test_pick_crew_priority2_home_crew_with_skill():
    # Priority 2: the home crew goes only if it has the skill, even when
    # another crew with the skill comes earlier in file order.
    crews = [crew("X", "South", ["transformer"]), crew("H", "North", ["transformer"])]
    assert assign.pick_crew(order(site="North", equipment="transformer", priority=2), crews) == "H"


def test_pick_crew_priority2_home_crew_without_skill_uses_skill_fallback():
    crews = [crew("H", "North", ["rack"]), crew("X", "South", ["transformer"])]
    assert assign.pick_crew(order(site="North", equipment="transformer", priority=2), crews) == "X"


def test_pick_crew_priority3_ignores_home_crew():
    # Priority 3 has no site rule: first free crew with the skill wins.
    crews = [crew("X", "South", ["transformer"]), crew("H", "North", ["transformer"])]
    assert assign.pick_crew(order(site="North", equipment="transformer", priority=3), crews) == "X"


def test_pick_crew_skill_fallback():
    # No home crew at the site: first free crew in file order with the skill.
    crews = [
        crew("X", "South", ["feeder"]),
        crew("Y", "South", ["transformer"]),
        crew("Z", "East", ["transformer"]),
    ]
    assert assign.pick_crew(order(site="North", equipment="transformer", priority=1), crews) == "Y"


def test_pick_crew_skill_fallback_skips_busy_crews():
    crews = [
        crew("X", "South", ["transformer"], load=assign.MAX_LOAD),
        crew("Y", "South", ["transformer"], load=assign.MAX_LOAD - 1),
    ]
    assert assign.pick_crew(order(site="North", priority=3), crews) == "Y"


def test_pick_crew_no_site_uses_skill_fallback():
    # Looks wrong (2014 TODO): a missing site silently skips the site rules,
    # so even a priority 1 order does not go to a home crew. Asserted as-is.
    crews = [crew("X", "South", ["transformer"]), crew("H", "North", ["rack"])]
    assert assign.pick_crew(order(site="", priority=1), crews) == "X"


def test_pick_crew_missing_or_blank_site_key_uses_skill_fallback():
    crews = [crew("X", "South", ["transformer"])]
    assert assign.pick_crew({"equipment": "transformer", "priority": 1}, crews) == "X"
    assert assign.pick_crew(order(site="   ", priority=1), crews) == "X"


def test_pick_crew_unknown_equipment_goes_to_crew_a():
    crews = [crew("B", "North", ["transformer"])]
    assert assign.pick_crew(order(equipment="toaster", priority=1), crews) == "A"


def test_pick_crew_equipment_is_case_insensitive():
    crews = [crew("B", "North", ["transformer"])]
    assert assign.pick_crew(order(equipment=" Transformer ", priority=1), crews) == "B"


def test_pick_crew_all_busy_overflows_to_crew_a():
    crews = [
        crew("B", "North", ["transformer"], load=assign.MAX_LOAD),
        crew("C", "South", ["transformer"], load=assign.MAX_LOAD + 1),
    ]
    assert assign.pick_crew(order(priority=1), crews) == "A"


def test_pick_crew_no_free_crew_has_skill_goes_to_crew_a():
    crews = [crew("B", "South", ["rack"])]
    assert assign.pick_crew(order(equipment="transformer", priority=3), crews) == "A"


def test_pick_crew_missing_priority_defaults_to_3():
    crews = [crew("X", "South", ["transformer"]), crew("H", "North", ["transformer"])]
    o = {"site": "North", "equipment": "transformer"}
    assert assign.pick_crew(o, crews) == "X"


# ---- crew_load -------------------------------------------------------------

def test_crew_load_counts_only_assigned_orders():
    crews = [crew("A", "North", []), crew("B", "North", [])]
    orders = [
        {"status": "assigned", "crew": "A"},
        {"status": "assigned", "crew": "A"},
        {"status": "open", "crew": "A"},
        {"status": "closed", "crew": "A"},
        {"status": "assigned", "crew": "B"},
        {"status": "assigned", "crew": "Z"},  # unknown crew is ignored
    ]
    result = assign.crew_load(crews, orders)
    assert {c["id"]: c["load"] for c in result} == {"A": 2, "B": 1}


def test_crew_load_reads_orders_from_store_when_not_given():
    crews = store.load_crews()
    result = assign.crew_load(crews)
    # temp store from conftest: one assigned order, on crew C
    assert {c["id"]: c["load"] for c in result} == {"A": 0, "B": 0, "C": 1}


# ---- assign_order ----------------------------------------------------------

def test_assign_order_success_persists_crew_and_status():
    assert assign.assign_order(1, "B") is True
    saved = store.get_order(1)
    assert saved["crew"] == "B"
    assert saved["status"] == "assigned"


def test_assign_order_unknown_crew_returns_false_and_changes_nothing():
    assert assign.assign_order(1, "Z") is False
    saved = store.get_order(1)
    assert saved["crew"] == ""
    assert saved["status"] == "open"


def test_assign_order_missing_order_returns_false():
    assert assign.assign_order(999, "B") is False


def test_assign_order_closed_order_returns_false_and_changes_nothing():
    assert assign.assign_order(2, "B") is False
    saved = store.get_order(2)
    assert saved["crew"] == "C"
    assert saved["status"] == "closed"


def test_assign_order_can_reassign_an_assigned_order():
    assert assign.assign_order(3, "A") is True
    assert store.get_order(3)["crew"] == "A"
