# Nutrition information and references based on credible Indian dietary standards
# Reference source: ICMR-NIN Indian Food Composition Tables (IFCT 2017)

PROTEIN_REFERENCE_DATA = [
    {
        "source": "Paneer",
        "estimate": "18 g per 100 g",
        "notes": "Rich in protein and calcium, versatile for wraps, sandwiches, curries and grills.",
        "category": "Dairy"
    },
    {
        "source": "Cooked Dal (Lentils)",
        "estimate": "7 to 9 g per 100 g cooked",
        "notes": "Comforting everyday staple providing complex carbohydrates, plant protein and fibre.",
        "category": "Pulses"
    },
    {
        "source": "Cooked Rajma (Kidney Beans)",
        "estimate": "8 to 9 g per 100 g cooked",
        "notes": "Hearty legume rich in dietary fibre, potassium and sustained energy.",
        "category": "Pulses"
    },
    {
        "source": "Cooked Chole (Chickpeas)",
        "estimate": "7 to 8 g per 100 g cooked",
        "notes": "Satisfying pulse loaded with fibre, folate and plant based iron.",
        "category": "Pulses"
    },
    {
        "source": "Fresh Milk",
        "estimate": "3.2 to 3.4 g per 100 ml",
        "notes": "Convenient liquid protein base for smoothies, morning oats and warm beverages.",
        "category": "Dairy"
    },
    {
        "source": "Curd and Plain Yogurt",
        "estimate": "3.5 to 4.0 g per 100 g",
        "notes": "Probiotic fermented dairy supporting digestive wellness and pairing with parathas.",
        "category": "Dairy"
    },
    {
        "source": "Roasted Chana",
        "estimate": "19 to 20 g per 100 g",
        "notes": "Crispy traditional Indian snack with low moisture and high protein density.",
        "category": "Snacks"
    },
    {
        "source": "Chicken Breast",
        "estimate": "25 to 27 g per 100 g cooked",
        "notes": "Lean poultry source included approximately three times weekly as preferred.",
        "category": "Poultry"
    }
]

MACRONUTRIENT_GUIDES = {
    "Protein": "Protein supplies the building blocks for muscles, enzymes and tissue repair. Incorporating a source at every meal promotes sustained fullness without sharp hunger spikes.",
    "Carbohydrates": "Carbohydrates from whole grains, potatoes and fruit fuel brain function and everyday energy. Complex carbs release glucose steadily into the bloodstream.",
    "Healthy Fats": "Fats from nuts, seeds, butter and cooking oils are vital for hormone production and the absorption of fat soluble vitamins including A, D, E and K.",
    "Dietary Fibre": "Soluble and insoluble fibre from vegetables, lentils and oats nourishes the gut microbiome, eases digestion and supports balanced blood sugar levels.",
    "Dietary Variety": "Eating diverse colours, textures and styles of food ensures a broad intake of micronutrients and prevents meal planning fatigue."
}

def summary(plan, eaten):
    all_meals = []
    for day, items in plan.items():
        for kind, meal in items.items():
            all_meals.append((day, kind, meal))
            
    total_planned = len(all_meals)
    eaten_count = len(eaten)
    protein_count = sum(1 for _, _, m in all_meals if m.get("protein"))
    produce_count = sum(
        1 for _, _, m in all_meals 
        if any("fruit" in str(x[1]).lower() or "vegetable" in str(x[1]).lower() for x in m.get("ingredients", []))
    )
    veg_count = sum(1 for _, _, m in all_meals if m.get("vegetarian", True) and not m.get("is_chicken"))
    chk_count = sum(1 for _, _, m in all_meals if m.get("is_chicken") or not m.get("vegetarian", True))
    
    return {
        "planned": total_planned,
        "eaten": eaten_count,
        "protein_rich": protein_count,
        "produce": produce_count,
        "vegetarian": veg_count,
        "chicken": chk_count
    }

