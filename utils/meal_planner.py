from copy import deepcopy
import random

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TYPES = ["Breakfast", "Lunch", "Dinner"]

STARTER = {
    "Monday": ["protein_oats", "rajma_chawal", "garlic_chicken"],
    "Tuesday": ["paneer_sandwich", "dal_roti", "paneer_bhurji"],
    "Wednesday": ["smoothie_toast", "chole_chawal", "chicken_momos"],
    "Thursday": ["aloo_paratha", "paneer_pulao", "paneer_noodles"],
    "Friday": ["fruit_oats", "dal_rice", "paneer_wrap"],
    "Saturday": ["cheese_sandwich", "homemade_burger", "khichdi"],
    "Sunday": ["protein_oats", "tandoori_chicken", "momos_veg"]
}

def make_plan(meals):
    by_id = {m["id"]: m for m in meals}
    return {
        day: {kind: deepcopy(by_id.get(mid, by_id[list(by_id.keys())[0]])) for kind, mid in zip(TYPES, ids)}
        for day, ids in STARTER.items()
    }

def chicken_count(plan):
    count = 0
    for day in plan.values():
        for meal in day.values():
            if meal.get("is_chicken") or not meal.get("vegetarian", True):
                count += 1
    return count

def allowed(meal, profile, plan, day, kind):
    # Prohibit breakfast items for lunch or dinner, etc.
    if meal.get("type") != kind:
        return False, f"Choose a dish prepared for {kind.lower()}."
    
    text = (meal["name"] + " " + " ".join(x[0] for x in meal.get("ingredients", []))).lower()
    
    # Strictly forbid eggs in any form
    if "egg" in text and "vegg" not in text:
        return False, "Dishes containing eggs are not included in this planner."
    
    # Strictly forbid chicken curry
    if "chicken curry" in text:
        return False, "Chicken curry is not included in this planner."
    
    # Check exclusions and allergies
    excluded = [x.strip().lower() for x in profile.get("exclusions", []) + profile.get("allergies", []) if x.strip()]
    if any(word in text for word in excluded):
        return False, "This dish contains an ingredient on your exclusions list."
    
    # Check disliked dishes
    disliked_names = [x.strip().lower() for x in profile.get("disliked_dishes", []) + profile.get("dislikes", []) if x.strip()]
    if any(d in meal["name"].lower() or d == meal["id"].lower() for d in disliked_names):
        return False, "This dish is marked as disliked in your preferences."
    
    # Wednesday dinner rule: must remain chicken momos in default plan
    is_chicken_meal = meal.get("is_chicken", not meal.get("vegetarian", True))
    if day == "Wednesday" and kind == "Dinner":
        if profile.get("chicken_ok", True) and meal["id"] != "chicken_momos":
            return False, "Wednesday dinner is reserved for chicken momos."
    
    # Check chicken limits
    current = plan.get(day, {}).get(kind, {})
    current_is_chicken = current.get("is_chicken", not current.get("vegetarian", True)) if current else False
    current_chicken_total = chicken_count(plan)
    projected_count = current_chicken_total - (1 if current_is_chicken else 0) + (1 if is_chicken_meal else 0)
    
    if is_chicken_meal:
        if not profile.get("chicken_ok", True):
            return False, "Chicken is turned off in your preferences."
        if projected_count > 3:
            return False, "This would exceed the weekly limit of three chicken meals."
    
    # Check max cooking time if user specified a limit
    max_time = profile.get("max_time")
    if max_time and (meal.get("prep", 0) + meal.get("cook", 0)) > max_time:
        return False, f"Total cooking time exceeds your preference of {max_time} minutes."
    
    return True, ""

def generate_weekly_plan(meals, profile, seed=None):
    if seed is not None:
        random.seed(seed)
    
    by_id = {m["id"]: m for m in meals}
    chicken_ok = profile.get("chicken_ok", True)
    favourites = set(profile.get("favourites", []))
    
    # Filter meals by category and basic acceptability
    breakfast_pool = [m for m in meals if m["type"] == "Breakfast" and not m.get("is_chicken")]
    lunch_veg_pool = [m for m in meals if m["type"] == "Lunch" and not m.get("is_chicken")]
    lunch_chk_pool = [m for m in meals if m["type"] == "Lunch" and m.get("is_chicken")]
    dinner_veg_pool = [m for m in meals if m["type"] == "Dinner" and not m.get("is_chicken")]
    dinner_chk_pool = [m for m in meals if m["type"] == "Dinner" and m.get("is_chicken")]
    
    # Exclude dishes with user allergens / exclusions
    excluded_terms = [x.strip().lower() for x in profile.get("exclusions", []) + profile.get("allergies", []) if x.strip()]
    disliked_terms = [x.strip().lower() for x in profile.get("disliked_dishes", []) + profile.get("dislikes", []) if x.strip()]
    
    def is_acceptable(m):
        txt = (m["name"] + " " + " ".join(x[0] for x in m.get("ingredients", []))).lower()
        if any(e in txt for e in excluded_terms):
            return False
        if any(d in m["name"].lower() or d == m["id"].lower() for d in disliked_terms):
            return False
        if "egg" in txt and "vegg" not in txt:
            return False
        if "chicken curry" in txt:
            return False
        return True
    
    breakfast_pool = [m for m in breakfast_pool if is_acceptable(m)] or breakfast_pool
    lunch_veg_pool = [m for m in lunch_veg_pool if is_acceptable(m)] or lunch_veg_pool
    dinner_veg_pool = [m for m in dinner_veg_pool if is_acceptable(m)] or dinner_veg_pool
    dinner_chk_pool = [m for m in dinner_chk_pool if is_acceptable(m)] or dinner_chk_pool
    lunch_chk_pool = [m for m in lunch_chk_pool if is_acceptable(m)] or lunch_chk_pool
    
    new_plan = {day: {} for day in DAYS}
    used_meal_ids = set()
    
    # 1. Place Wednesday dinner
    if chicken_ok and "chicken_momos" in by_id and is_acceptable(by_id["chicken_momos"]):
        new_plan["Wednesday"]["Dinner"] = deepcopy(by_id["chicken_momos"])
        used_meal_ids.add("chicken_momos")
    else:
        candidates = [m for m in dinner_veg_pool if m["id"] not in used_meal_ids]
        choice = random.choice(candidates) if candidates else dinner_veg_pool[0]
        new_plan["Wednesday"]["Dinner"] = deepcopy(choice)
        used_meal_ids.add(choice["id"])
    
    # 2. Place remaining chicken meals if chicken_ok (total must be exactly 3)
    if chicken_ok:
        # We need 2 more chicken meals. Good distribution: Monday Dinner and Sunday Lunch, or similar non-consecutive
        remaining_chk_slots = [("Monday", "Dinner"), ("Sunday", "Lunch")]
        all_chk_options = [m for m in dinner_chk_pool + lunch_chk_pool if m["id"] != "chicken_momos" and is_acceptable(m)]
        random.shuffle(all_chk_options)
        
        for slot_day, slot_kind in remaining_chk_slots:
            pool = dinner_chk_pool if slot_kind == "Dinner" else lunch_chk_pool
            candidates = [m for m in pool if m["id"] not in used_meal_ids and is_acceptable(m)]
            if candidates:
                # Prioritize favourites if available
                favs = [m for m in candidates if m["id"] in favourites]
                chosen = random.choice(favs) if favs else random.choice(candidates)
                new_plan[slot_day][slot_kind] = deepcopy(chosen)
                used_meal_ids.add(chosen["id"])
    
    # 3. Fill all remaining slots with varied vegetarian meals
    for day in DAYS:
        # Breakfast
        if "Breakfast" not in new_plan[day]:
            candidates = [m for m in breakfast_pool if m["id"] not in used_meal_ids]
            if not candidates:
                candidates = breakfast_pool
            favs = [m for m in candidates if m["id"] in favourites]
            chosen = random.choice(favs) if favs and random.random() < 0.6 else random.choice(candidates)
            new_plan[day]["Breakfast"] = deepcopy(chosen)
            used_meal_ids.add(chosen["id"])
        
        # Lunch
        if "Lunch" not in new_plan[day]:
            candidates = [m for m in lunch_veg_pool if m["id"] not in used_meal_ids]
            if not candidates:
                candidates = lunch_veg_pool
            favs = [m for m in candidates if m["id"] in favourites]
            chosen = random.choice(favs) if favs and random.random() < 0.6 else random.choice(candidates)
            new_plan[day]["Lunch"] = deepcopy(chosen)
            used_meal_ids.add(chosen["id"])
        
        # Dinner
        if "Dinner" not in new_plan[day]:
            candidates = [m for m in dinner_veg_pool if m["id"] not in used_meal_ids]
            if not candidates:
                candidates = dinner_veg_pool
            favs = [m for m in candidates if m["id"] in favourites]
            chosen = random.choice(favs) if favs and random.random() < 0.6 else random.choice(candidates)
            new_plan[day]["Dinner"] = deepcopy(chosen)
            used_meal_ids.add(chosen["id"])
            
    return new_plan

