# Characterisation tests for fieldops/assign.py: they lock in what the code does today.
from fieldops import assign, store


def crew(cid, home_site, skills, load=0):
    return {"id": cid, "home_site": home_site, "skills": skills, "load": load}


def order(site="North", equipment="transformer", priority=3):
    return {"site": site, "equipment": equipment, "priority": priority}


# --- pick_crew: priority 1 -------------------------------------------------

# NOTE (observed behaviour): priority 1 sends the home crew even if it lacks the skill.
def test_pick_crew_priority1_home_site():
    crews = [
        crew("X", "South", ["transformer"]),
        crew("Y", "North", ["rack"]),
    ]
    assert assign.pick_crew(order(site="North", priority=1), crews) == "Y"


def test_pick_crew_priority1_home_crew_busy_falls_back_to_skill():
    crews = [
        crew("X", "South", ["transformer"]),
        crew("Y", "North", ["rack"], load=assign.MAX_LOAD),
    ]
    assert assign.pick_crew(order(site="North", priority=1), crews) == "X"


def test_pick_crew_priority1_no_home_crew_falls_back_to_skill():
    crews = [crew("X", "South", ["rack"]), crew("Y", "East", ["transformer"])]
    assert assign.pick_crew(order(site="North", priority=1), crews) == "Y"


# --- pick_crew: priority 2 (site rule) -------------------------------------

def test_pick_crew_priority2_home_site_with_skill():
    crews = [
        crew("X", "South", ["transformer"]),
        crew("Y", "North", ["transformer"]),
    ]
    # X is first in file order and has the skill, but the home crew Y wins.
    assert assign.pick_crew(order(site="North", priority=2), crews) == "Y"


def test_pick_crew_priority2_home_site_without_skill_uses_fallback():
    crews = [
        crew("X", "South", ["transformer"]),
        crew("Y", "North", ["rack"]),
    ]
    assert assign.pick_crew(order(site="North", priority=2), crews) == "X"


# NOTE (observed behaviour): any priority other than 1 or 2 skips the site rules.
def test_pick_crew_priority3_ignores_home_site():
    crews = [
        crew("X", "South", ["transformer"]),
        crew("Y", "North", ["transformer"]),
    ]
    assert assign.pick_crew(order(site="North", priority=3), crews) == "X"


# NOTE (observed behaviour): a missing priority is treated as priority 3.
def test_pick_crew_missing_priority_defaults_to_3():
    crews = [
        crew("X", "South", ["transformer"]),
        crew("Y", "North", ["transformer"]),
    ]
    o = {"site": "North", "equipment": "transformer"}
    assert assign.pick_crew(o, crews) == "X"


# --- pick_crew: skill fallback ---------------------------------------------

def test_pick_crew_skill_fallback():
    crews = [
        crew("X", "South", ["rack"]),
        crew("Y", "East", ["transformer"]),
        crew("Z", "West", ["transformer"]),
    ]
    assert assign.pick_crew(order(site="North", priority=3), crews) == "Y"


def test_pick_crew_skill_fallback_skips_busy_crews():
    crews = [
        crew("X", "South", ["transformer"], load=assign.MAX_LOAD),
        crew("Y", "East", ["transformer"], load=assign.MAX_LOAD - 1),
    ]
    assert assign.pick_crew(order(priority=3), crews) == "Y"


def test_pick_crew_no_crew_has_skill_returns_default():
    crews = [crew("X", "South", ["rack"]), crew("Y", "East", ["feeder"])]
    assert assign.pick_crew(order(priority=3), crews) == assign.DEFAULT_CREW


# --- pick_crew: order with no site -----------------------------------------

# NOTE (observed behaviour): with no site the site rules are skipped, even at
# priority 1, and the skill fallback decides (see the 2014 TODO in assign.py).
def test_pick_crew_no_site():
    crews = [
        crew("X", "South", ["rack"]),
        crew("Y", "North", ["transformer"]),
    ]
    assert assign.pick_crew(order(site="", priority=1), crews) == "Y"


def test_pick_crew_no_site_skill_fallback_first_in_file_order():
    crews = [
        crew("X", "South", ["transformer"]),
        crew("Y", "North", ["transformer"]),
    ]
    assert assign.pick_crew(order(site=None, priority=1), crews) == "X"


def test_pick_crew_blank_site_is_treated_as_no_site():
    crews = [
        crew("X", "South", ["transformer"]),
        crew("Y", "", ["transformer"]),
    ]
    assert assign.pick_crew(order(site="   ", priority=1), crews) == "X"


# --- pick_crew: default crew rules -----------------------------------------

def test_pick_crew_unknown_equipment_goes_to_default():
    crews = [crew("X", "North", ["gizmo"])]
    assert assign.pick_crew(order(equipment="gizmo", priority=1), crews) == assign.DEFAULT_CREW


def test_pick_crew_everybody_busy_goes_to_default():
    crews = [
        crew("X", "North", ["transformer"], load=assign.MAX_LOAD),
        crew("Y", "South", ["transformer"], load=assign.MAX_LOAD + 1),
    ]
    assert assign.pick_crew(order(priority=1), crews) == assign.DEFAULT_CREW


def test_pick_crew_equipment_is_case_and_space_insensitive():
    crews = [crew("X", "South", ["transformer"])]
    assert assign.pick_crew(order(equipment="  Transformer ", priority=3), crews) == "X"


# --- crew_load -------------------------------------------------------------

# NOTE (observed behaviour): crew_load mutates the crew dicts (adds "load") and returns the same list.
def test_crew_load_counts_only_assigned_orders():
    crews = [{"id": "A"}, {"id": "B"}]
    orders = [
        {"status": "assigned", "crew": "A"},
        {"status": "assigned", "crew": "A"},
        {"status": "open", "crew": "A"},
        {"status": "closed", "crew": "B"},
        {"status": "assigned", "crew": "Z"},  # unknown crew is ignored
    ]
    result = assign.crew_load(crews, orders)
    assert result is crews
    assert [c["load"] for c in result] == [2, 0]


def test_crew_load_reads_orders_from_store_when_not_given():
    store.update_order(1, crew="A", status="assigned")
    crews = [{"id": "A"}, {"id": "B"}, {"id": "C"}]
    assign.crew_load(crews)
    assert [c["load"] for c in crews] == [1, 0, 0]


# --- assign_order ----------------------------------------------------------

def test_assign_order_assigns_and_saves():
    assert assign.assign_order(1, "B") is True
    saved = store.get_order(1)
    assert saved["crew"] == "B"
    assert saved["status"] == "assigned"


def test_assign_order_unknown_crew_returns_false():
    assert assign.assign_order(1, "Z") is False
    assert store.get_order(1)["status"] == "open"


def test_assign_order_unknown_order_returns_false():
    assert assign.assign_order(999, "A") is False


def test_assign_order_closed_order_returns_false():
    assert assign.assign_order(2, "A") is False
    saved = store.get_order(2)
    assert saved["status"] == "closed"
    assert saved["crew"] == "C"


# NOTE (observed behaviour): assign_order does not check crew load, so a busy crew can be assigned.
def test_assign_order_ignores_crew_load():
    for i in range(10, 10 + assign.MAX_LOAD):
        orders = store.load_orders()
        orders.append({"id": i, "site": "North", "equipment": "transformer",
                       "priority": 3, "status": "assigned", "crew": "B"})
        store.save_orders(orders)
    assert assign.assign_order(1, "B") is True
    assert store.get_order(1)["crew"] == "B"
