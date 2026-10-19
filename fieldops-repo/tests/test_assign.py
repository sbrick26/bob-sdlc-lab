import pytest
from fieldops import assign, store


def make_crew(crew_id, home_site="North Substation", skills=None, load=0):
    if skills is None:
        skills = ["transformer"]
    return {
        "id": crew_id,
        "name": f"Crew {crew_id}",
        "home_site": home_site,
        "skills": list(skills),
        "load": load,
    }


# --- pick_crew: Priority 1 rule ---

def test_pick_crew_priority_1_home_crew_selected_without_skill():
    # Priority 1 rule: home crew goes first, skill or not
    crew_home = make_crew("B", home_site="North Substation", skills=["switchgear"], load=0)
    crew_other = make_crew("C", home_site="South Substation", skills=["transformer"], load=0)
    order = {"site": "North Substation", "equipment": "transformer", "priority": 1}
    assert assign.pick_crew(order, [crew_home, crew_other]) == "B"


def test_pick_crew_priority_1_home_crew_selected_with_skill():
    crew_home = make_crew("B", home_site="North Substation", skills=["transformer"], load=0)
    crew_other = make_crew("C", home_site="South Substation", skills=["transformer"], load=0)
    order = {"site": "North Substation", "equipment": "transformer", "priority": 1}
    assert assign.pick_crew(order, [crew_home, crew_other]) == "B"


# --- pick_crew: Priority 2 rule & Site rule ---

def test_pick_crew_priority_2_home_crew_selected_with_skill():
    # Priority 2 rule: home crew selected only when they also have the skill
    crew_home = make_crew("B", home_site="North Substation", skills=["transformer"], load=0)
    crew_other = make_crew("C", home_site="South Substation", skills=["transformer"], load=0)
    order = {"site": "North Substation", "equipment": "transformer", "priority": 2}
    assert assign.pick_crew(order, [crew_home, crew_other]) == "B"


def test_pick_crew_priority_2_home_crew_lacks_skill_falls_back():
    # Priority 2: home crew lacks skill, so fallback picks first free crew with skill
    crew_home = make_crew("B", home_site="North Substation", skills=["switchgear"], load=0)
    crew_other = make_crew("C", home_site="South Substation", skills=["transformer"], load=0)
    order = {"site": "North Substation", "equipment": "transformer", "priority": 2}
    assert assign.pick_crew(order, [crew_home, crew_other]) == "C"


# --- pick_crew: Skill fallback ---

def test_pick_crew_skill_fallback_first_free_crew_in_order():
    # Priority 3 or non-home site: picks first free crew in order with required skill
    crew_1 = make_crew("B", home_site="North Substation", skills=["feeder"], load=0)
    crew_2 = make_crew("C", home_site="South Substation", skills=["transformer"], load=0)
    crew_3 = make_crew("D", home_site="East Yard", skills=["transformer"], load=0)
    order = {"site": "North Substation", "equipment": "transformer", "priority": 3}
    assert assign.pick_crew(order, [crew_1, crew_2, crew_3]) == "C"


# --- pick_crew: No site / Empty site edge cases ---

def test_pick_crew_empty_site_uses_skill_fallback():
    # Observation (2014 quirk): missing/empty site skips site rules and falls back to skill match
    crew_1 = make_crew("B", home_site="North Substation", skills=["transformer"], load=0)
    crew_2 = make_crew("C", home_site="South Substation", skills=["transformer"], load=0)
    order = {"site": "", "equipment": "transformer", "priority": 1}
    assert assign.pick_crew(order, [crew_1, crew_2]) == "B"


def test_pick_crew_missing_site_key_uses_skill_fallback():
    # Order without 'site' key skips site rules and falls back to skill match
    crew_1 = make_crew("B", home_site="North Substation", skills=["switchgear"], load=0)
    crew_2 = make_crew("C", home_site="South Substation", skills=["transformer"], load=0)
    order = {"equipment": "transformer", "priority": 1}
    assert assign.pick_crew(order, [crew_1, crew_2]) == "C"


# --- pick_crew: Unknown equipment & Fallback to DEFAULT_CREW ---

def test_pick_crew_unknown_equipment_returns_default_crew():
    crew_1 = make_crew("B", home_site="North Substation", skills=["transformer"], load=0)
    order = {"site": "North Substation", "equipment": "solar_panel", "priority": 1}
    assert assign.pick_crew(order, [crew_1]) == assign.DEFAULT_CREW


def test_pick_crew_all_crews_busy_returns_default_crew():
    # When all crews are at MAX_LOAD (4), overflow goes to DEFAULT_CREW ("A")
    crew_1 = make_crew("B", home_site="North Substation", skills=["transformer"], load=4)
    crew_2 = make_crew("C", home_site="North Substation", skills=["transformer"], load=5)
    order = {"site": "North Substation", "equipment": "transformer", "priority": 1}
    assert assign.pick_crew(order, [crew_1, crew_2]) == assign.DEFAULT_CREW


def test_pick_crew_no_matching_skills_returns_default_crew():
    crew_1 = make_crew("B", home_site="North Substation", skills=["feeder"], load=0)
    crew_2 = make_crew("C", home_site="South Substation", skills=["switchgear"], load=0)
    order = {"site": "East Yard", "equipment": "transformer", "priority": 3}
    assert assign.pick_crew(order, [crew_1, crew_2]) == assign.DEFAULT_CREW


# --- crew_load ---

def test_crew_load_counts_only_assigned_orders():
    crews = [make_crew("A"), make_crew("B"), make_crew("C")]
    orders = [
        {"id": 1, "status": "assigned", "crew": "A"},
        {"id": 2, "status": "assigned", "crew": "A"},
        {"id": 3, "status": "open", "crew": "A"},
        {"id": 4, "status": "closed", "crew": "A"},
        {"id": 5, "status": "assigned", "crew": "B"},
        {"id": 6, "status": "assigned", "crew": "UNKNOWN"},
    ]
    result = assign.crew_load(crews, orders)
    load_map = {c["id"]: c["load"] for c in result}
    assert load_map["A"] == 2
    assert load_map["B"] == 1
    assert load_map["C"] == 0


def test_crew_load_uses_store_when_orders_none(temp_store):
    crews = [make_crew("A"), make_crew("B"), make_crew("C"), make_crew("D")]
    result = assign.crew_load(crews)
    load_map = {c["id"]: c["load"] for c in result}
    # In temp_store, order 2 is assigned to crew C
    assert load_map["C"] == 1
    assert load_map["A"] == 0
    assert load_map["B"] == 0
    assert load_map["D"] == 0


# --- assign_order ---

def test_assign_order_success(temp_store):
    assert assign.assign_order(1, "A") is True
    order = store.get_order(1)
    assert order["status"] == "assigned"
    assert order["crew"] == "A"


def test_assign_order_unknown_crew(temp_store):
    assert assign.assign_order(1, "NONEXISTENT") is False
    order = store.get_order(1)
    assert order["status"] == "open"
    assert order["crew"] == ""


def test_assign_order_missing_order(temp_store):
    assert assign.assign_order(999, "A") is False


def test_assign_order_closed_order(temp_store):
    # Order 3 is closed in temp_store
    assert assign.assign_order(3, "A") is False
    order = store.get_order(3)
    assert order["status"] == "closed"
    assert order["crew"] == "D"
