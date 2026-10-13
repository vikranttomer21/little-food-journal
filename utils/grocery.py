from collections import defaultdict
import re

UNIT_ALIASES = {
    "piece": "pieces",
    "pieces": "pieces",
    "g": "g",
    "gram": "g",
    "grams": "g",
    "kg": "kg",
    "ml": "ml",
    "l": "l",
    "litre": "l",
    "tbsp": "tbsp",
    "tsp": "tsp",
    "cloves": "cloves",
    "clove": "cloves",
    "slices": "slices",
    "slice": "slices",
    "rotis": "rotis",
    "roti": "rotis"
}

def combine(quantity_entries):
    parsed = []
    unparsed = []
    
    for q in quantity_entries:
        if not q:
            continue
        m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s*", str(q), re.I)
        if m:
            val = float(m.group(1))
            raw_unit = m.group(2).lower()
            canon_unit = UNIT_ALIASES.get(raw_unit, raw_unit)
            
            # Standardize kg to g, l to ml if mixed
            if canon_unit == "kg":
                val *= 1000.0
                canon_unit = "g"
            elif canon_unit == "l":
                val *= 1000.0
                canon_unit = "ml"
                
            parsed.append((val, canon_unit))
        else:
            unparsed.append(str(q).strip())
            
    if not parsed and not unparsed:
        return ""
    
    # If all parsed have the same canonical unit
    units = {u for _, u in parsed}
    if len(units) == 1 and not unparsed:
        total = sum(n for n, _ in parsed)
        unit = next(iter(units))
        if unit == "g" and total >= 1000:
            return f"{total/1000:g} kg"
        if unit == "ml" and total >= 1000:
            return f"{total/1000:g} l"
        return f"{total:g} {unit}"
    
    parts = []
    if parsed:
        unit_sums = defaultdict(float)
        for val, u in parsed:
            unit_sums[u] += val
        for u, total in unit_sums.items():
            parts.append(f"{total:g} {u}")
    if unparsed:
        parts.extend(sorted(set(unparsed)))
        
    return ", ".join(parts)

def build_grocery(plan):
    # grouped: { category: { ingredient_name: {"quantities": [...], "meals": set()} } }
    grouped = defaultdict(lambda: defaultdict(lambda: {"quantities": [], "meals": set()}))
    
    for day, meals in plan.items():
        for kind, meal in meals.items():
            dish_name = meal.get("name", "")
            for item in meal.get("ingredients", []):
                if len(item) >= 3:
                    name, category, qty = item[0], item[1], item[2]
                elif len(item) == 2:
                    name, category, qty = item[0], item[1], ""
                else:
                    continue
                
                name_clean = name.strip()
                cat_clean = category.strip()
                grouped[cat_clean][name_clean]["quantities"].append(qty)
                if dish_name:
                    grouped[cat_clean][name_clean]["meals"].add(dish_name)
                    
    result = {}
    for cat in sorted(grouped.keys()):
        items_list = []
        for name in sorted(grouped[cat].keys()):
            q_combined = combine(grouped[cat][name]["quantities"])
            meals_list = sorted(grouped[cat][name]["meals"])
            items_list.append({
                "name": name,
                "quantity": q_combined,
                "meals": meals_list
            })
        result[cat] = items_list
        
    return result

