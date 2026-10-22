import csv
import pytest
from fieldops import store
from fieldops.assign import crew_load, pick_crew, assign_order

def test_crew_load_calculation():
    # Setup test inputs
    crews = [{"id": "A"}, {"id": "B"}, {"id": "C"}]
    orders = [
        {"status": "assigned", "crew": "A"},
        {"status": "assigned", "crew": "A"},
        {"status": "open", "crew": "A"},  # status is not assigned, shouldn't count
        {"status": "assigned", "crew": "B"},
        {"status": "assigned", "crew": "D"}  # crew D is not in crews list, shouldn't count
    ]
    
    res = crew_load(crews, orders)
    loads = {c["id"]: c["load"] for c in res}
    assert loads["A"] == 2
    assert loads["B"] == 1
    assert loads["C"] == 0

def test_crew_load_calculation_from_store():
    # Setup store with orders
    orders = [
        {"id": 1, "status": "assigned", "crew": "A", "priority": 3},
        {"id": 2, "status": "assigned", "crew": "B", "priority": 3}
    ]
    store.save_orders(orders)
    
    crews = [{"id": "A"}, {"id": "B"}]
    res = crew_load(crews)  # loads from store
    loads = {c["id"]: c["load"] for c in res}
    assert loads["A"] == 1
    assert loads["B"] == 1

def test_pick_crew_unknown_equipment():
    # If equip not in KNOWN_EQUIPMENT, return DEFAULT_CREW (which is "A")
    order = {"site": "North Substation", "equipment": "generator", "priority": "1"}
    crews = [
        {"id": "B", "home_site": "North Substation", "skills": ["generator"], "load": 0}
    ]
    assert pick_crew(order, crews) == "A"

def test_pick_crew_all_busy_overflow():
    # If all crews are busy (load >= MAX_LOAD), return DEFAULT_CREW (which is "A")
    order = {"site": "North Substation", "equipment": "transformer", "priority": "1"}
    crews = [
        {"id": "B", "home_site": "North Substation", "skills": ["transformer"], "load": 4},
        {"id": "C", "home_site": "North Substation", "skills": ["transformer"], "load": 5}
    ]
    assert pick_crew(order, crews) == "A"

def test_pick_crew_priority_1_home_crew():
    # Priority 1: home crew goes, skill or not
    order = {"site": "North Substation", "equipment": "transformer", "priority": "1"}
    crews = [
        {"id": "B", "home_site": "North Substation", "skills": [], "load": 0},
        {"id": "C", "home_site": "South Substation", "skills": ["transformer"], "load": 0}
    ]
    assert pick_crew(order, crews) == "B"

def test_pick_crew_priority_2_home_crew_matching_skill():
    # Priority 2: home crew only if they have the skill
    order = {"site": "North Substation", "equipment": "transformer", "priority": "2"}
    crews = [
        {"id": "B", "home_site": "North Substation", "skills": ["transformer"], "load": 0},
        {"id": "C", "home_site": "South Substation", "skills": ["transformer"], "load": 0}
    ]
    assert pick_crew(order, crews) == "B"

def test_pick_crew_priority_2_home_crew_no_skill_fallback():
    # Priority 2: home crew lacks skill, falls back to first free with skill
    order = {"site": "North Substation", "equipment": "transformer", "priority": "2"}
    crews = [
        {"id": "B", "home_site": "North Substation", "skills": [], "load": 0},
        {"id": "C", "home_site": "South Substation", "skills": ["transformer"], "load": 0}
    ]
    assert pick_crew(order, crews) == "C"

def test_pick_crew_no_site_skill_fallback():
    # Order has no site: skips site rules, falls back to first free crew with the skill in list order
    order = {"site": "", "equipment": "transformer", "priority": "1"}
    crews = [
        {"id": "B", "home_site": "North Substation", "skills": ["switchgear"], "load": 0},
        {"id": "C", "home_site": "South Substation", "skills": ["transformer"], "load": 0},
        {"id": "D", "home_site": "East Yard", "skills": ["transformer"], "load": 0}
    ]
    assert pick_crew(order, crews) == "C"

def test_assign_order_success():
    # Write some crews to CREWS_FILE
    crews = [
        {"id": "A", "name": "Alpha", "home_site": "North Substation", "skills": "transformer"},
        {"id": "B", "name": "Bravo", "home_site": "South Substation", "skills": "feeder"}
    ]
    with open(store.CREWS_FILE, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "home_site", "skills"])
        for c in crews:
            w.writerow([c["id"], c["name"], c["home_site"], c["skills"]])
            
    # Write some orders to ORDERS_FILE
    orders = [
        {"id": 1001, "site": "North Substation", "equipment": "transformer", "priority": 1, "status": "open"}
    ]
    store.save_orders(orders)
    
    # Assign order 1001 to crew A
    assert assign_order(1001, "A") is True
    
    # Verify order is updated in store
    updated = store.get_order(1001)
    assert updated is not None
    assert updated["crew"] == "A"
    assert updated["status"] == "assigned"

def test_assign_order_invalid_crew():
    # Write some crews
    crews = [{"id": "A", "name": "Alpha", "home_site": "North", "skills": "transformer"}]
    with open(store.CREWS_FILE, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "home_site", "skills"])
        for c in crews:
            w.writerow([c["id"], c["name"], c["home_site"], c["skills"]])
            
    # Write order
    orders = [{"id": 1001, "site": "North", "equipment": "transformer", "priority": 1, "status": "open"}]
    store.save_orders(orders)
    
    # Assign to non-existent crew "B"
    assert assign_order(1001, "B") is False

def test_assign_order_closed_or_missing():
    # Write some crews
    crews = [{"id": "A", "name": "Alpha", "home_site": "North", "skills": "transformer"}]
    with open(store.CREWS_FILE, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "home_site", "skills"])
        for c in crews:
            w.writerow([c["id"], c["name"], c["home_site"], c["skills"]])
            
    # Write order that is closed
    orders = [
        {"id": 1001, "site": "North", "equipment": "transformer", "priority": 1, "status": "closed"}
    ]
    store.save_orders(orders)
    
    # Assign closed order 1001 to crew A -> should return False
    assert assign_order(1001, "A") is False
    
    # Assign non-existent order 2002 to crew A -> should return False
    assert assign_order(2002, "A") is False
