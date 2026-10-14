# Characterization tests: record what fieldops/assign.py does today, odd parts included.
from fieldops import assign, store


def make_order(site, equipment, priority):
    return {"site": site, "equipment": equipment, "priority": priority}


def test_priority1_home_crew_wins_without_skill(crews):
    # B is home at Bravo Site but cannot do transformers; A can. B still wins.
    assert assign.pick_crew(make_order("Bravo Site", "transformer", 1), crews) == "B"


def test_priority2_home_crew_with_skill(crews):
    # Fallback alone would pick B (first with feeder); the site rule picks C.
    assert assign.pick_crew(make_order("Charlie Site", "feeder", 2), crews) == "C"


def test_priority2_home_crew_without_skill_falls_back(crews):
    # B is home but lacks transformer, so fallback picks A, first with the skill.
    assert assign.pick_crew(make_order("Bravo Site", "transformer", 2), crews) == "A"


def test_skill_fallback_first_free_crew_in_file_order(crews):
    order = make_order("Delta Site", "rack", 3)
    assert assign.pick_crew(order, crews) == "B"
    crews[1]["load"] = assign.MAX_LOAD
    assert assign.pick_crew(order, crews) == "C"


def test_no_site_skips_site_rules(crews):
    assert assign.pick_crew(make_order("", "rack", 1), crews) == "B"
    assert assign.pick_crew({"equipment": "rack", "priority": 1}, crews) == "B"


def test_unknown_equipment_goes_to_default_crew(crews):
    assert assign.pick_crew(make_order("Bravo Site", "toaster", 1), crews) == "A"


def test_all_busy_overflows_to_default_crew(crews):
    for c in crews:
        c["load"] = assign.MAX_LOAD
    assert assign.pick_crew(make_order("Delta Site", "switchgear", 1), crews) == "A"


def test_busy_crew_is_skipped(crews):
    order = make_order("Bravo Site", "feeder", 1)
    assert assign.pick_crew(order, crews) == "B"
    crews[1]["load"] = 4
    assert assign.pick_crew(order, crews) == "C"


def test_crew_load_counts_assigned_orders_only(crews):
    orders = [
        {"status": "assigned", "crew": "B"},
        {"status": "assigned", "crew": "B"},
        {"status": "assigned", "crew": "Z"},
        {"status": "open", "crew": "C"},
        {"status": "closed", "crew": "C"},
    ]
    result = assign.crew_load(crews, orders)
    assert {c["id"]: c["load"] for c in result} == {"A": 0, "B": 2, "C": 0, "D": 0}


def test_assign_order_writes_to_temp_csv(temp_store):
    assert assign.assign_order(9001, "C") is True
    order = store.get_order(9001)
    assert order["crew"] == "C"
    assert order["status"] == "assigned"
    assert "9001" in (temp_store / "work_orders.csv").read_text()


def test_assign_order_refuses_unknown_crew(temp_store):
    assert assign.assign_order(9001, "Z") is False
    assert store.get_order(9001)["status"] == "open"


def test_assign_order_refuses_missing_order(temp_store):
    assert assign.assign_order(1, "A") is False


def test_assign_order_refuses_closed_order(temp_store):
    assert assign.assign_order(9002, "C") is False
    assert store.get_order(9002)["crew"] == "B"
