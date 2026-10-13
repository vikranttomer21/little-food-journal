import json
import re
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.meal_planner import DAYS, TYPES, make_plan, allowed, chicken_count, generate_weekly_plan
from utils.grocery import build_grocery, combine
from utils.nutrition import summary, PROTEIN_REFERENCE_DATA
from utils.storage import load_state, save_state


def load_meals():
    meals_path = ROOT / "data" / "meals.json"
    assert meals_path.exists(), "meals.json must exist"
    return json.loads(meals_path.read_text(encoding="utf-8"))

def test_meal_library_count_and_structure():
    meals = load_meals()
    assert len(meals) >= 150, f"Master meal library must contain at least 150 meals, found {len(meals)}"
    
    ids = [m["id"] for m in meals]
    assert len(ids) == len(set(ids)), "All meal IDs must be strictly unique"
    
    required_keys = {
        "id", "name", "type", "vegetarian", "is_chicken", "protein",
        "prep", "cook", "serves", "description", "ingredients", "steps",
        "method", "flavours", "styles", "image_id"
    }
    
    for m in meals:
        missing = required_keys - set(m.keys())
        assert not missing, f"Meal {m.get('id')} is missing keys: {missing}"
        assert m["type"] in ["Breakfast", "Lunch", "Dinner", "Snack"], f"Invalid type in {m['id']}"
        assert isinstance(m["ingredients"], list) and len(m["ingredients"]) > 0
        assert isinstance(m["steps"], list) and len(m["steps"]) > 0

def test_no_eggs_in_any_recipe():
    meals = load_meals()
    for m in meals:
        text = (
            m["name"] + " " +
            m.get("description", "") + " " +
            " ".join(i[0] for i in m.get("ingredients", [])) + " " +
            " ".join(m.get("steps", []))
        ).lower()
        
        # Replace occurrences of 'vegg' to avoid false positives on 'veggie'
        clean_text = text.replace("vegg", "").replace("eggless", "")
        assert "egg" not in clean_text, f"Dish {m['id']} contains egg reference!"

def test_no_chicken_curry_in_any_recipe():
    meals = load_meals()
    for m in meals:
        text = (
            m["name"] + " " +
            m.get("description", "") + " " +
            " ".join(i[0] for i in m.get("ingredients", [])) + " " +
            " ".join(m.get("steps", []))
        ).lower()
        assert "chicken curry" not in text, f"Dish {m['id']} contains chicken curry reference!"

def test_chicken_handling_temperature_in_steps():
    meals = load_meals()
    for m in meals:
        if m.get("is_chicken"):
            steps_text = " ".join(m.get("steps", []))
            assert "74" in steps_text, f"Chicken dish {m['id']} missing 74 C safe cooking temperature in steps!"

def test_weekly_plan_starter_structure():
    meals = load_meals()
    plan = make_plan(meals)
    
    # 7 days
    assert len(plan) == 7
    total_slots = sum(len(day_meals) for day_meals in plan.values())
    assert total_slots == 21, f"Weekly plan must have exactly 21 main meals, found {total_slots}"
    
    # Wednesday dinner must be chicken momos
    wed_dinner = plan["Wednesday"]["Dinner"]
    assert wed_dinner["id"] == "chicken_momos", f"Wednesday dinner must be chicken momos, got {wed_dinner['id']}"
    
    # Exactly 3 chicken meals in starter plan
    c_count = chicken_count(plan)
    assert c_count == 3, f"Starter plan must contain exactly 3 chicken meals, found {c_count}"

def test_plan_generator_variety_and_chicken_limit():
    meals = load_meals()
    profile = {
        "chicken_ok": True,
        "allergies": [],
        "exclusions": [],
        "dislikes": ["poha", "upma", "idli"],
        "favourites": ["chicken_momos", "paneer_tikka", "rajma_chawal"]
    }
    
    plan = generate_weekly_plan(meals, profile, seed=42)
    assert len(plan) == 7
    total_meals = sum(len(d) for d in plan.values())
    assert total_meals == 21
    
    assert plan["Wednesday"]["Dinner"]["id"] == "chicken_momos"
    assert chicken_count(plan) == 3
    
    # When chicken_ok is False
    profile_veg = {"chicken_ok": False, "exclusions": [], "allergies": []}
    plan_veg = generate_weekly_plan(meals, profile_veg, seed=42)
    assert chicken_count(plan_veg) == 0

def test_meal_swaps_preserve_other_meals():
    meals = load_meals()
    plan = make_plan(meals)
    
    # Record meal IDs before swap
    before_ids = {d: {k: m["id"] for k, m in meals_in_day.items()} for d, meals_in_day in plan.items()}
    
    # Swap Monday Lunch (rajma_chawal -> chole_chawal)
    by_id = {m["id"]: m for m in meals}
    new_meal = by_id["chole_chawal"]
    plan["Monday"]["Lunch"] = new_meal
    
    # Check that ONLY Monday Lunch changed
    for d in DAYS:
        for k in TYPES:
            if d == "Monday" and k == "Lunch":
                assert plan[d][k]["id"] == "chole_chawal"
            else:
                assert plan[d][k]["id"] == before_ids[d][k], f"Meal at {d} {k} was unintentionally changed!"

def test_meal_swaps_enforce_rules():
    meals = load_meals()
    by_id = {m["id"]: m for m in meals}
    plan = make_plan(meals)
    profile = {"chicken_ok": True, "exclusions": ["bell pepper"], "dislikes": []}
    
    # Attempting to add a 4th chicken meal when plan already has 3 (Tuesday Dinner is veg)
    chk_option = by_id["honey_garlic_chicken_bowl"]
    ok, reason = allowed(chk_option, profile, plan, "Tuesday", "Dinner")
    assert not ok
    assert "limit" in reason.lower()
    
    # Swapping away Wednesday dinner chicken momos must be rejected
    other_dinner = by_id["creamy_paneer_roti"]
    ok, reason = allowed(other_dinner, profile, plan, "Wednesday", "Dinner")
    assert not ok
    assert "chicken momos" in reason.lower()
    
    # Excluded ingredient check
    pepper_dish = by_id["paneer_tikka"]
    ok, reason = allowed(pepper_dish, profile, plan, "Tuesday", "Lunch")
    assert not ok
    assert "exclusions" in reason.lower()

def test_grocery_list_aggregation_and_usage():
    meals = load_meals()
    plan = make_plan(meals)
    grocery = build_grocery(plan)
    
    assert len(grocery) > 0, "Grocery list must not be empty"
    
    # Ensure items have combined quantities and meals usage lists
    for cat, items in grocery.items():
        for item in items:
            assert "name" in item
            assert "quantity" in item
            assert "meals" in item
            assert isinstance(item["meals"], list)
            assert len(item["meals"]) > 0, f"Item {item['name']} must record which meals use it"
            
    # Test combine logic
    combined = combine(["50 g", "100 g", "150 g"])
    assert combined == "300 g"
    
    combined_kg = combine(["800 g", "400 g"])
    assert combined_kg == "1.2 kg"
    
    combined_ml = combine(["200 ml", "300 ml"])
    assert combined_ml == "500 ml"

def test_storage_roundtrip():
    from utils import storage
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_state_file = Path(tmp_dir) / "user_state.json"
        orig_state_path = storage.STATE_PATH
        try:
            storage.STATE_PATH = test_state_file
            data = {"profile": {"chicken_ok": True}, "checked": ["item_1", "item_2"]}
            saved = storage.save_state(data)
            assert saved is True
            assert test_state_file.exists()
            
            loaded = storage.load_state({"default_key": "val"})
            assert loaded["checked"] == ["item_1", "item_2"]
        finally:
            storage.STATE_PATH = orig_state_path

def test_image_manifest_integrity():
    manifest_path = ROOT / "assets" / "image_manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    
    images = manifest.get("images", {})
    verified_found = 0
    for img_id, entry in images.items():
        if entry.get("verified"):
            verified_found += 1
            local_path = ROOT / entry["local_path"]
            assert local_path.exists(), f"Verified image {img_id} file {local_path} must exist on disk"
            assert entry.get("licence"), f"Verified image {img_id} must specify licence"
            assert entry.get("photographer"), f"Verified image {img_id} must specify photographer"
            assert entry.get("page_url"), f"Verified image {img_id} must specify page_url"
            
    assert verified_found > 0, "At least some images must be verified and checked"

def test_all_starter_plan_meals_have_verified_photos():
    meals = load_meals()
    plan = make_plan(meals)
    manifest_path = ROOT / "assets" / "image_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    images = manifest.get("images", {})
    
    missing_photos = []
    for day, slots in plan.items():
        for kind, meal in slots.items():
            img_id = meal.get("image_id", meal["id"])
            entry = images.get(img_id, {})
            if not entry.get("verified") or not entry.get("local_path"):
                missing_photos.append(f"{day} {kind} ({meal['id']})")
            else:
                img_file = ROOT / entry["local_path"]
                assert img_file.exists(), f"Image file {img_file} not found on disk"
                
    assert not missing_photos, f"Starter plan has dishes without verified photos: {missing_photos}"

def test_fallback_placeholder_text():
    comp_text = (ROOT / "utils" / "image_component.py").read_text(encoding="utf-8")
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Photograph coming soon" in comp_text or "Photograph coming soon" in app_text, "Image component must contain fallback text 'Photograph coming soon'"
    assert "Verified photograph not added yet" not in comp_text and "Verified photograph not added yet" not in app_text, "Old placeholder text must not exist"

def test_no_emojis_or_dash_punctuation_in_ui():
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    
    # Emoji check
    emojis = re.findall(r'[\U00010000-\U0010ffff]', app_text)
    assert not emojis, f"Found emojis in app.py: {emojis}"
    
    # Dash punctuation check in visible copy
    dash_punct = re.findall(r'(\w+[\s\u00A0]*[—–·][\s\u00A0]*\w+)', app_text)
    assert not dash_punct, f"Found dash punctuation in app.py: {dash_punct}"

def test_every_meal_has_manifest_entry():
    meals = load_meals()
    manifest_path = ROOT / "assets" / "image_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    images = manifest.get("images", {})
    
    missing_entries = [m["id"] for m in meals if m["id"] not in images]
    assert not missing_entries, f"Meals missing manifest entry: {missing_entries}"

def test_verified_images_readable_and_attributed():
    from PIL import Image
    manifest_path = ROOT / "assets" / "image_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    images = manifest.get("images", {})
    
    for img_id, entry in images.items():
        if entry.get("verified"):
            local_path = ROOT / entry["local_path"]
            assert local_path.exists(), f"Image file not found on disk: {local_path}"
            with Image.open(local_path) as im:
                im.verify()
            assert entry.get("photographer"), f"Missing photographer for {img_id}"
            assert entry.get("licence"), f"Missing licence for {img_id}"
            assert entry.get("attribution"), f"Missing attribution for {img_id}"

def test_no_cross_contamination_photo_mapping():
    meals = load_meals()
    manifest_path = ROOT / "assets" / "image_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    images = manifest.get("images", {})
    
    chicken_ids = {m["id"] for m in meals if m.get("is_chicken", not m.get("vegetarian", True))}
    veg_ids = {m["id"] for m in meals if not m.get("is_chicken", not m.get("vegetarian", True))}
    
    for m in meals:
        mid = m["id"]
        is_chk = mid in chicken_ids
        entry = images.get(mid, {})
        if entry.get("verified") and entry.get("local_path"):
            lp = entry["local_path"].lower()
            if is_chk:
                # Must not map to pure veg dishes like paneer, dal, rajma, chole, etc.
                assert not any(v in lp for v in ["paneer", "rajma", "chole", "dal_rice", "dal_roti", "khichdi"]), f"Chicken dish {mid} mapped to vegetarian image {lp}"
            else:
                # Must not map to chicken
                assert "chicken" not in lp, f"Vegetarian dish {mid} mapped to chicken image {lp}"

def test_shared_image_component_usage():
    from utils.image_component import resolve_meal_image, render_meal_photo
    meals = load_meals()
    
    # Test resolve
    res = resolve_meal_image(meals[0])
    assert res is None or "path" in res
    
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "render_meal_photo" in app_text, "app.py must use render_meal_photo"
    assert "resolve_meal_image" in app_text, "app.py must import resolve_meal_image"

def test_navigation_error_fixed():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20)
    at.run()
    assert not at.exception, f"Exception on initial run: {at.exception}"
    
    # Find View recipe buttons
    view_btns = [b for b in at.button if b.label == "View recipe"]
    assert len(view_btns) > 0, "No 'View recipe' button found on My Week page"
    
    # Click View recipe
    view_btns[0].click().run()
    assert not at.exception, f"Clicking 'View recipe' raised an exception: {at.exception}"
    
    # Verify we transitioned to Recipes page without WidgetAlreadyInstantiatedError
    assert at.session_state.current_page == "Recipes"
    assert at.session_state.nav == "Recipes"

def test_no_footers_in_app():
    app_text = (ROOT / "app.py").read_text(encoding="utf-8").lower()
    styles_text = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8").lower()
    
    assert "footer" not in app_text, "app.py must not contain any footer markup or references"
    assert "tagline" not in app_text, "app.py must not contain closing taglines"

if __name__ == "__main__":
    tests = [
        test_meal_library_count_and_structure,
        test_no_eggs_in_any_recipe,
        test_no_chicken_curry_in_any_recipe,
        test_chicken_handling_temperature_in_steps,
        test_weekly_plan_starter_structure,
        test_plan_generator_variety_and_chicken_limit,
        test_meal_swaps_preserve_other_meals,
        test_meal_swaps_enforce_rules,
        test_grocery_list_aggregation_and_usage,
        test_storage_roundtrip,
        test_image_manifest_integrity,
        test_every_meal_has_manifest_entry,
        test_verified_images_readable_and_attributed,
        test_no_cross_contamination_photo_mapping,
        test_shared_image_component_usage,
        test_navigation_error_fixed,
        test_all_starter_plan_meals_have_verified_photos,
        test_fallback_placeholder_text,
        test_no_emojis_or_dash_punctuation_in_ui,
        test_no_footers_in_app,
    ]
    
    passed = 0
    failed = 0
    print("=" * 60)
    print("Running The Little Food Journal Test Suite")
    print("=" * 60)
    for t in tests:
        name = t.__name__
        try:
            t()
            print(f"PASS: {name}")
            passed += 1
        except Exception as e:
            print(f"FAIL: {name} -> {e}")
            failed += 1
            
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests.")
    print("=" * 60)
    if failed > 0:
        exit(1)
    else:
        print("All project requirements verified successfully!")
