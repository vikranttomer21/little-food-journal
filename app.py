import json
import re
from pathlib import Path
from datetime import date
import streamlit as st
from utils.storage import load_state, save_state
from utils.meal_planner import DAYS, TYPES, make_plan, allowed, chicken_count, generate_weekly_plan
from utils.grocery import build_grocery
from utils.nutrition import summary, PROTEIN_REFERENCE_DATA, MACRONUTRIENT_GUIDES
from utils.image_component import render_meal_photo, resolve_meal_image

ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title="The Little Food Journal",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load CSS stylesheet
css_path = ROOT / "assets" / "styles.css"
if css_path.exists():
    st.markdown("<style>" + css_path.read_text(encoding="utf-8") + "</style>", unsafe_allow_html=True)

# Load master meal library
meals_path = ROOT / "data" / "meals.json"
meals = json.loads(meals_path.read_text(encoding="utf-8"))
MEALS = {m["id"]: m for m in meals}

# Default user profile
DEFAULT_PROFILE = {
    "diet": "Mostly vegetarian with occasional chicken",
    "chicken_ok": True,
    "allergies": [],
    "exclusions": [],
    "disliked_dishes": ["Poha", "Upma", "Idli"],
    "dislikes": ["poha", "upma", "idli", "eggs", "chicken curry"],
    "favourites": ["chicken_momos", "paneer_tikka", "rajma_chawal", "protein_oats", "aloo_paratha"],
    "preferred_flavours": ["Comfort food", "Cheesy", "Creamy", "Crispy"],
    "preferred_styles": ["Indian comfort food", "Sandwiches", "Wraps and parathas", "Momos"],
    "methods": ["Stovetop", "Air fryer", "Pan cooked"],
    "max_time": 45,
    "water_target": 2000,
    "servings_default": 1
}

# Initialize session state with persistence
if "state" not in st.session_state:
    st.session_state.state = load_state({
        "profile": DEFAULT_PROFILE,
        "plan": make_plan(meals),
        "eaten": [],
        "water": {},
        "notes": {},
        "produce_checked": {},
        "checked": [],
        "custom_grocery": []
    })

state = st.session_state.state
profile = state.get("profile", DEFAULT_PROFILE)

def persist():
    if not save_state(state):
        st.error("Your changes are active for this session, but could not be saved to disk.")

# Navigation management
PAGES = ["My Week", "Recipes", "Grocery List", "Food and Nutrition", "My Preferences"]

if "current_page" not in st.session_state:
    st.session_state.current_page = st.session_state.get("nav", "My Week")

if "pending_nav" in st.session_state and st.session_state.pending_nav:
    st.session_state.current_page = st.session_state.pop("pending_nav")

def set_page(page_name, recipe_id=None):
    if recipe_id is not None:
        st.session_state.recipe_id = recipe_id
    st.session_state.current_page = page_name
    st.session_state.nav_radio = page_name
    st.session_state.nav = page_name

def render_meal_card(day, kind, meal):
    is_chicken = meal.get("is_chicken", not meal.get("vegetarian", True))
    badge_class = "meal-badge-chicken" if is_chicken else "meal-badge"
    type_label = "Chicken" if is_chicken else "Vegetarian"
    
    st.markdown('<div class="meal-card">', unsafe_allow_html=True)
    render_meal_photo(meal, show_attribution=False)
    
    st.markdown(
        f'''<div class="meal-card-body">
            <span class="{badge_class}">{kind}, {type_label}</span>
            <div class="meal-card-title">{meal["name"]}</div>
            <div class="meal-card-desc">{meal.get("description", "")}</div>
        </div>
        </div>''',
        unsafe_allow_html=True
    )
    
    # Action buttons
    col_a, col_b, col_c = st.columns([1, 1, 1])
    with col_a:
        st.button(
            "View recipe",
            key=f"rec_{day}_{kind}",
            use_container_width=True,
            on_click=set_page,
            args=("Recipes", meal["id"])
        )
    with col_b:
        if st.button("Swap meal", key=f"swp_{day}_{kind}", use_container_width=True):
            st.session_state.swap_key = f"{day}|{kind}"
            st.rerun()
    with col_c:
        is_eaten = f"{day}|{kind}" in state.get("eaten", [])
        eaten_label = "Eaten" if is_eaten else "Mark eaten"
        if st.button(eaten_label, key=f"eat_{day}_{kind}", use_container_width=True):
            key_name = f"{day}|{kind}"
            if is_eaten:
                state["eaten"].remove(key_name)
            else:
                state.setdefault("eaten", []).append(key_name)
            persist()
            st.rerun()


# Sidebar Navigation
st.sidebar.markdown(
    '''<div class="journal-header" style="margin-bottom: 1rem;">
        <div class="section-label">A thoughtful food journal</div>
        <h2 style="margin: 0.2rem 0; font-size: 1.65rem;">The Little Food Journal</h2>
        <div style="font-size: 0.85rem; color: var(--muted); line-height: 1.45;">
            A little inspiration for what to eat, one lovely meal at a time.
        </div>
    </div>''',
    unsafe_allow_html=True
)

if "nav_radio" not in st.session_state or st.session_state.nav_radio != st.session_state.current_page:
    st.session_state.nav_radio = st.session_state.current_page

def on_sidebar_nav_change():
    st.session_state.current_page = st.session_state.nav_radio
    st.session_state.nav = st.session_state.nav_radio

selected_page = st.sidebar.radio(
    "Navigation",
    PAGES,
    key="nav_radio",
    on_change=on_sidebar_nav_change,
    label_visibility="collapsed"
)
st.session_state.nav = selected_page

st.sidebar.divider()
active_chicken = chicken_count(state.get("plan", {}))
st.sidebar.markdown(
    f'''<div style="font-size: 0.82rem; color: var(--muted); line-height: 1.5;">
        <strong>Weekly status</strong><br>
        21 main meals planned<br>
        {active_chicken} of 3 allowed chicken meals<br>
        Wednesday dinner reserved for chicken momos
    </div>''',
    unsafe_allow_html=True
)

# ==========================================
# 1. MY WEEK
# ==========================================
if selected_page == "My Week":
    st.markdown(
        '''<div class="journal-header">
            <div class="section-label">Weekly Meal Plan</div>
            <h1 class="journal-title">Your plan for the week</h1>
            <div class="journal-subtitle">
                A little inspiration for what to eat, one lovely meal at a time.
            </div>
        </div>''',
        unsafe_allow_html=True
    )
    
    # Day selector bar
    current_day = st.session_state.get("selected_day", DAYS[date.today().weekday() if date.today().weekday() < 7 else 0])
    
    day_cols = st.columns(7)
    for idx, d in enumerate(DAYS):
        with day_cols[idx]:
            is_active = (d == current_day)
            btn_type = "primary" if is_active else "secondary"
            if st.button(d[:3], key=f"select_{d}", type=btn_type, use_container_width=True):
                st.session_state.selected_day = d
                st.rerun()
    
    st.markdown(f"### {current_day}")
    
    day_plan = state["plan"].get(current_day, {})
    for kind in TYPES:
        meal = day_plan.get(kind)
        if not meal:
            continue
        
        with st.container():
            st.markdown(f"#### {kind}")
            col1, col2 = st.columns([1, 1.3], gap="large")
            with col1:
                render_meal_card(current_day, kind, meal)
            with col2:
                prep_time = meal.get("prep", 0)
                cook_time = meal.get("cook", 0)
                total_time = prep_time + cook_time
                difficulty = meal.get("difficulty", "Easy")
                
                st.markdown(f"**Serves one, ready in {total_time} minutes**")
                st.write(f"Preparation time: {prep_time} minutes. Cooking time: {cook_time} minutes.")
                st.write(f"Protein source: {meal.get('protein', 'Plant based')}")
                st.write(f"Cooking style: {meal.get('method', 'Stovetop')}. Difficulty: {difficulty}.")
                
                # Ingredients highlight
                ing_sample = [item[0] for item in meal.get("ingredients", [])[:6]]
                st.caption(f"Key ingredients: {', '.join(ing_sample)}")
                
                if meal.get("is_chicken", not meal.get("vegetarian", True)):
                    st.markdown(
                        '''<div class="callout-box" style="margin-top: 0.75rem; font-size: 0.85rem;">
                            Safe chicken preparation: Cook thoroughly until the internal temperature reaches 74 C.
                        </div>''',
                        unsafe_allow_html=True
                    )
                
                if current_day == "Wednesday" and kind == "Dinner":
                    st.markdown(
                        '''<div class="callout-box callout-box-sage" style="margin-top: 0.75rem; font-size: 0.85rem;">
                            Wednesday dinner tradition: homemade steamed chicken momos.
                        </div>''',
                        unsafe_allow_html=True
                    )
            
            # Smart Meal Swapping Interface
            if st.session_state.get("swap_key") == f"{current_day}|{kind}":
                st.markdown(
                    f'''<div class="callout-box" style="margin: 1.5rem 0 1rem;">
                        <h4 style="margin: 0 0 0.3rem;">What are you craving?</h4>
                        <div>Replacing: <strong>{meal['name']}</strong> ({current_day} {kind.lower()}). All other meals in your plan will be preserved.</div>
                    </div>''',
                    unsafe_allow_html=True
                )
                
                fcol1, fcol2, fcol3 = st.columns(3)
                with fcol1:
                    craving_flavour = st.selectbox(
                        "Flavour craving",
                        ["Any", "Comfort food", "Cheesy", "Creamy", "Spicy", "Tangy", "Mild", "Crispy", "Fresh", "Filling", "Quick", "Air fryer", "One pot"],
                        key=f"flavour_{current_day}_{kind}"
                    )
                with fcol2:
                    craving_style = st.selectbox(
                        "Meal style",
                        ["Any", "Indian comfort food", "Sandwiches", "Wraps and parathas", "Noodles and rice", "Pasta", "Rice bowls", "Smoothies and bowls", "Momos", "Burgers", "Homemade fast food"],
                        key=f"style_{current_day}_{kind}"
                    )
                with fcol3:
                    time_limit = st.slider(
                        "Maximum preparation time in minutes",
                        10, 60, 45,
                        key=f"time_{current_day}_{kind}"
                    )
                
                search_term = st.text_input(
                    "Search by dish name or ingredient",
                    placeholder="Try paneer, chole, potato or noodles",
                    key=f"search_{current_day}_{kind}"
                )
                
                candidates = [m for m in meals if m["type"] == kind and m["id"] != meal["id"]]
                
                # Apply discovery filters
                if craving_flavour != "Any":
                    candidates = [m for m in candidates if craving_flavour in m.get("flavours", [])]
                if craving_style != "Any":
                    candidates = [m for m in candidates if craving_style in m.get("styles", [])]
                if search_term.strip():
                    term = search_term.strip().lower()
                    candidates = [
                        m for m in candidates
                        if term in m["name"].lower() or any(term in i[0].lower() for i in m.get("ingredients", []))
                    ]
                candidates = [m for m in candidates if (m.get("prep", 0) + m.get("cook", 0)) <= time_limit]
                
                # Check acceptability against dietary preferences and limits
                evaluated = []
                for candidate in candidates:
                    is_ok, reason = allowed(candidate, profile, state["plan"], current_day, kind)
                    evaluated.append((candidate, is_ok, reason))
                
                valid_options = [c for c, ok, _ in evaluated if ok]
                invalid_options = [(c, reason) for c, ok, reason in evaluated if not ok]
                
                if not valid_options and not invalid_options:
                    st.info("No matching recipes found with these specific filters. Try loosening the time limit or flavour filter.")
                elif not valid_options:
                    st.warning("Alternative dishes are available but restricted by your current dietary preferences or weekly chicken limit.")
                    for c, reason in invalid_options[:3]:
                        st.caption(f"{c['name']}: {reason}")
                else:
                    st.markdown(f"**{len(valid_options)} suitable alternatives found:**")
                    num_cols = min(3, max(1, len(valid_options)))
                    swap_cols = st.columns(num_cols)
                    for idx, opt in enumerate(valid_options[:9]):
                        with swap_cols[idx % num_cols]:
                            opt_time = opt.get("prep", 0) + opt.get("cook", 0)
                            is_opt_chk = opt.get("is_chicken", not opt.get("vegetarian", True))
                            opt_badge = "meal-badge-chicken" if is_opt_chk else "meal-badge"
                            opt_type = "Chicken" if is_opt_chk else "Vegetarian"
                            
                            st.markdown('<div class="swap-card">', unsafe_allow_html=True)
                            render_meal_photo(opt, max_height=180, show_attribution=False)
                            st.markdown(
                                f'''<div class="swap-card-body">
                                    <span class="{opt_badge}">{opt_type}, {opt_time} mins</span>
                                    <div class="swap-card-title">{opt["name"]}</div>
                                    <div class="swap-card-desc">{opt.get("description", "")}</div>
                                </div>
                                </div>''',
                                unsafe_allow_html=True
                            )
                            if st.button("Choose this meal", key=f"btn_swap_{current_day}_{kind}_{opt['id']}", type="primary", use_container_width=True):
                                state["plan"][current_day][kind] = opt
                                if f"{current_day}|{kind}" in state.get("eaten", []):
                                    state["eaten"].remove(f"{current_day}|{kind}")
                                st.session_state.pop("swap_key", None)
                                persist()
                                st.success(f"{opt['name']} replaced {meal['name']} for {current_day} {kind.lower()}. All other meals preserved.")
                                st.rerun()
                
                if st.button("Close discovery", key=f"close_swap_{current_day}_{kind}"):
                    st.session_state.pop("swap_key", None)
                    st.rerun()
            
            st.divider()
    
    # Plan management actions
    col_op1, col_op2, col_op3 = st.columns(3)
    with col_op1:
        if st.button("Generate new weekly plan", use_container_width=True):
            state["plan"] = generate_weekly_plan(meals, profile)
            state["eaten"] = []
            persist()
            st.success("A fresh weekly plan has been generated with your favourites and variety preferences.")
            st.rerun()
    with col_op2:
        if st.button("Restore starter plan", use_container_width=True):
            state["plan"] = make_plan(meals)
            state["eaten"] = []
            persist()
            st.success("Starter weekly plan has been restored.")
            st.rerun()
    with col_op3:
        if st.button("Clear all eaten marks", use_container_width=True):
            state["eaten"] = []
            persist()
            st.success("All meals reset to uneaten.")
            st.rerun()

# ==========================================
# 2. RECIPES
# ==========================================
elif selected_page == "Recipes":
    st.markdown(
        '''<div class="journal-header">
            <div class="section-label">Master Recipe Library</div>
            <h1 class="journal-title">Recipes to keep close</h1>
            <div class="journal-subtitle">
                Over 170 tested homemade recipes with metric measurements, clear steps and realistic cooking times.
            </div>
        </div>''',
        unsafe_allow_html=True
    )
    
    search_q = st.text_input("Search recipes", placeholder="Search by name, spice, ingredient or style")
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        cat_filter = st.selectbox("Category", ["Any", "Breakfast", "Lunch", "Dinner", "Snack"])
    with c2:
        diet_filter = st.selectbox("Food preference", ["Any", "Vegetarian", "Chicken"])
    with c3:
        time_filter = st.slider("Max time in minutes", 5, 60, 45)
    with c4:
        diff_filter = st.selectbox("Difficulty", ["Any", "Easy", "Moderate"])
    
    c5, c6 = st.columns(2)
    with c5:
        flavour_filter = st.selectbox(
            "Flavour profile",
            ["Any", "Comfort food", "Cheesy", "Creamy", "Spicy", "Tangy", "Mild", "Crispy", "Fresh", "Filling", "Quick", "Air fryer", "One pot"]
        )
    with c6:
        all_proteins = ["Any"] + sorted({m.get("protein", "Plant based") for m in meals if m.get("protein")})
        protein_filter = st.selectbox("Protein source", all_proteins)
    
    # Apply filtering
    matching_meals = []
    for m in meals:
        # Search query
        if search_q.strip():
            sq = search_q.strip().lower()
            in_name = sq in m["name"].lower()
            in_desc = sq in m.get("description", "").lower()
            in_ing = any(sq in i[0].lower() for i in m.get("ingredients", []))
            if not (in_name or in_desc or in_ing):
                continue
        
        # Category
        if cat_filter != "Any" and m["type"] != cat_filter:
            continue
        
        # Diet
        is_chk = m.get("is_chicken", not m.get("vegetarian", True))
        if diet_filter == "Vegetarian" and is_chk:
            continue
        if diet_filter == "Chicken" and not is_chk:
            continue
            
        # Cooking time
        total_m_time = m.get("prep", 0) + m.get("cook", 0)
        if total_m_time > time_filter:
            continue
            
        # Difficulty
        if diff_filter != "Any" and m.get("difficulty") != diff_filter:
            continue
            
        # Flavour
        if flavour_filter != "Any" and flavour_filter not in m.get("flavours", []):
            continue
            
        # Protein
        if protein_filter != "Any" and m.get("protein") != protein_filter:
            continue
            
        matching_meals.append(m)
        
    st.write(f"Showing {len(matching_meals)} recipes")
    
    # Image-led Recipe Cards
    for i in range(0, len(matching_meals), 2):
        pair = matching_meals[i:i+2]
        r_cols = st.columns(len(pair))
        for c_idx, meal in enumerate(pair):
            with r_cols[c_idx]:
                is_expanded = (st.session_state.get("recipe_id") == meal["id"])
                is_chk = meal.get("is_chicken", not meal.get("vegetarian", True))
                badge_class = "meal-badge-chicken" if is_chk else "meal-badge"
                type_label = "Chicken" if is_chk else "Vegetarian"
                total_m_time = meal.get("prep", 0) + meal.get("cook", 0)
                
                st.markdown('<div class="recipe-card">', unsafe_allow_html=True)
                render_meal_photo(meal, max_height=260, show_attribution=True)
                
                st.markdown(
                    f'''<div class="recipe-card-header">
                        <span class="{badge_class}">{meal["type"]}, {type_label}</span>
                        <div class="recipe-card-title">{meal["name"]}</div>
                        <div class="recipe-card-meta">
                            Ready in {total_m_time} minutes ({meal.get("prep", 0)} prep, {meal.get("cook", 0)} cook) • Difficulty: {meal.get("difficulty", "Easy")}<br>
                            <strong>Protein source:</strong> {meal.get("protein", "Plant based")} • <strong>Method:</strong> {meal.get("method", "Stovetop")}
                        </div>
                        <div style="font-size: 0.88rem; color: var(--muted); margin-bottom: 0.6rem;">{meal.get("description", "")}</div>
                    </div>''',
                    unsafe_allow_html=True
                )
                
                btn_text = "Hide recipe details" if is_expanded else "View recipe details"
                if st.button(btn_text, key=f"toggle_rec_{meal['id']}", use_container_width=True):
                    if is_expanded:
                        st.session_state.pop("recipe_id", None)
                    else:
                        st.session_state.recipe_id = meal["id"]
                    st.rerun()
                
                if is_expanded:
                    st.markdown('<div class="recipe-card-details">', unsafe_allow_html=True)
                    
                    # Servings scaling
                    serves_default = meal.get("serves", 1)
                    servings = st.number_input(
                        "Number of servings",
                        min_value=1,
                        max_value=8,
                        value=serves_default,
                        key=f"serves_{meal['id']}"
                    )
                    
                    st.markdown("##### Ingredients")
                    for item in meal.get("ingredients", []):
                        ing_name = item[0]
                        ing_qty = item[2] if len(item) >= 3 else ""
                        match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?", ing_qty.strip())
                        if match:
                            base_val = float(match.group(1))
                            unit = match.group(2) or ""
                            scaled_val = base_val * servings
                            scaled_str = f"{scaled_val:g} {unit}".strip()
                        else:
                            scaled_str = ing_qty
                        st.write(f"• {ing_name}: {scaled_str}")
                    
                    st.markdown("##### Cooking Method")
                    for step_num, step_text in enumerate(meal.get("steps", []), 1):
                        st.write(f"{step_num}. {step_text}")
                        
                    if is_chk:
                        st.markdown(
                            '''<div class="callout-box" style="margin-top: 0.5rem; font-size: 0.85rem;">
                                Food safety reminder: Ensure chicken reaches an internal cooking temperature of 74 C before serving.
                            </div>''',
                            unsafe_allow_html=True
                        )
                        
                    st.caption("Store leftovers in an airtight container in the refrigerator and consume within two days. Adjust seasoning to personal taste.")
                    
                    # Favourite toggle
                    fav_list = profile.get("favourites", [])
                    is_fav = meal["id"] in fav_list
                    fav_label = "Remove from favourites" if is_fav else "Save to favourites"
                    if st.button(fav_label, key=f"fav_btn_{meal['id']}"):
                        if is_fav:
                            profile["favourites"].remove(meal["id"])
                        else:
                            profile.setdefault("favourites", []).append(meal["id"])
                        persist()
                        st.rerun()
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 3. GROCERY LIST
# ==========================================
elif selected_page == "Grocery List":
    st.markdown(
        '''<div class="journal-header">
            <div class="section-label">Smart Shopping</div>
            <h1 class="journal-title">On the grocery list</h1>
            <div class="journal-subtitle">
                Combined ingredient quantities automatically aggregated from your selected weekly plan.
            </div>
        </div>''',
        unsafe_allow_html=True
    )
    
    grouped_grocery = build_grocery(state.get("plan", {}))
    checked_items = set(state.get("checked", []))
    
    total_grocery_count = sum(len(items) for items in grouped_grocery.values()) + len(state.get("custom_grocery", []))
    remaining_count = max(0, total_grocery_count - len(checked_items))
    
    st.markdown(
        f'''<div style="font-size: 0.9rem; color: var(--muted); margin-bottom: 1.25rem;">
            {len(checked_items)} items checked, {remaining_count} still to pick up
        </div>''',
        unsafe_allow_html=True
    )
    
    # Display categorized grocery items
    for category, items in grouped_grocery.items():
        st.markdown(f"#### {category}")
        for item in items:
            name = item["name"]
            qty = item["quantity"]
            meals_used = item["meals"]
            
            key_id = f"item_{category}_{name}"
            is_checked = (key_id in checked_items)
            
            item_display = f"{name} ({qty})" if qty else name
            val = st.checkbox(item_display, value=is_checked, key=f"chk_{key_id}")
            if val:
                checked_items.add(key_id)
            else:
                checked_items.discard(key_id)
                
            if meals_used:
                st.caption(f"Used in: {', '.join(meals_used)}")
    
    # Custom items added by user
    custom_items = state.get("custom_grocery", [])
    if custom_items:
        st.markdown("#### Added by you")
        for custom_name in custom_items:
            key_id = f"custom_{custom_name}"
            is_checked = (key_id in checked_items)
            val = st.checkbox(custom_name, value=is_checked, key=f"chk_{key_id}")
            if val:
                checked_items.add(key_id)
            else:
                checked_items.discard(key_id)
                
    state["checked"] = sorted(checked_items)
    persist()
    
    st.divider()
    
    col_add, col_actions = st.columns(2)
    with col_add:
        new_item = st.text_input("Add an additional item to the shopping list")
        if st.button("Add to list") and new_item.strip():
            state.setdefault("custom_grocery", []).append(new_item.strip())
            persist()
            st.rerun()
            
    with col_actions:
        st.write("List actions")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Clear checked items", use_container_width=True):
                state["custom_grocery"] = [
                    x for x in state.get("custom_grocery", [])
                    if f"custom_{x}" not in checked_items
                ]
                state["checked"] = []
                persist()
                st.rerun()
        with b2:
            if st.button("Uncheck all items", use_container_width=True):
                state["checked"] = []
                persist()
                st.rerun()
                
    # Copyable text and download
    text_lines = ["The Little Food Journal, Shopping List\n"]
    for category, items in grouped_grocery.items():
        text_lines.append(f"\n{category}:")
        for item in items:
            key_id = f"item_{category}_{item['name']}"
            mark = "[x]" if key_id in checked_items else "[ ]"
            qty_str = f" ({item['quantity']})" if item['quantity'] else ""
            text_lines.append(f"{mark} {item['name']}{qty_str}")
            
    if custom_items:
        text_lines.append("\nAdded by you:")
        for custom_name in custom_items:
            key_id = f"custom_{custom_name}"
            mark = "[x]" if key_id in checked_items else "[ ]"
            text_lines.append(f"{mark} {custom_name}")
            
    plain_text_grocery = "\n".join(text_lines)
    st.text_area("Shopping list text", plain_text_grocery, height=180)
    st.download_button(
        "Download shopping list",
        plain_text_grocery,
        file_name="shopping_list.txt",
        mime="text/plain"
    )

# ==========================================
# 4. FOOD AND NUTRITION
# ==========================================
elif selected_page == "Food and Nutrition":
    st.markdown(
        '''<div class="journal-header">
            <div class="section-label">Mindful Eating</div>
            <h1 class="journal-title">Food and nutrition</h1>
            <div class="journal-subtitle">
                A calm, balanced perspective on nourishing food, mindful eating and practical protein sources.
            </div>
        </div>''',
        unsafe_allow_html=True
    )
    
    plan_stats = summary(state.get("plan", {}), state.get("eaten", []))
    
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("Planned meals", plan_stats["planned"])
    col_m2.metric("Meals eaten", plan_stats["eaten"])
    col_m3.metric("Vegetarian meals", plan_stats["vegetarian"])
    col_m4.metric("Chicken meals", plan_stats["chicken"])
    
    st.markdown("### Daily Wellness Check In")
    today_name = date.today().strftime("%A")
    day_target = today_name if today_name in DAYS else "Monday"
    
    check_col1, check_col2 = st.columns(2)
    with check_col1:
        current_water = state.get("water", {}).get(day_target, 0)
        water_input = st.number_input(
            f"Water intake for {day_target} in millilitres",
            min_value=0,
            max_value=10000,
            value=int(current_water),
            step=250
        )
        state.setdefault("water", {})[day_target] = water_input
        st.caption(f"Your daily target is {profile.get('water_target', 2000)} ml. This is a gentle reminder rather than a rigid prescription.")
        
    with check_col2:
        had_produce = st.checkbox(
            f"I enjoyed fresh vegetables or fruit on {day_target}",
            value=state.get("produce_checked", {}).get(day_target, False),
            key=f"prod_chk_{day_target}"
        )
        state.setdefault("produce_checked", {})[day_target] = had_produce
        
        day_note = st.text_input(
            f"Journal note for {day_target}",
            value=state.get("notes", {}).get(day_target, ""),
            placeholder="How did meals feel today?"
        )
        state.setdefault("notes", {})[day_target] = day_note
        
    if st.button("Save today's check in"):
        persist()
        st.success(f"Check in for {day_target} has been saved.")
        
    st.divider()
    
    st.markdown("### Nourishing Components")
    for macro_name, macro_desc in MACRONUTRIENT_GUIDES.items():
        st.markdown(f"**{macro_name}**")
        st.write(macro_desc)
        
    st.divider()
    
    st.markdown("### Accessible Indian Protein Reference")
    st.write(
        "Here are standard dietary reference values for familiar Indian ingredients based on official composition tables. "
        "These represent ingredient benchmarks rather than dish level calorie calculations."
    )
    
    prot_cols = st.columns(2)
    for idx, item in enumerate(PROTEIN_REFERENCE_DATA):
        target_col = prot_cols[idx % 2]
        with target_col:
            st.markdown(
                f'''<div style="background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 0.9rem; margin-bottom: 0.75rem;">
                    <strong>{item["source"]}</strong><br>
                    <span style="color: var(--clay); font-weight: 600;">{item["estimate"]}</span><br>
                    <span style="font-size: 0.85rem; color: var(--muted);">{item["notes"]}</span>
                </div>''',
                unsafe_allow_html=True
            )
            
    st.markdown(
        '''<div class="callout-box" style="margin-top: 1rem; font-size: 0.85rem;">
            Source: ICMR-NIN Indian Food Composition Tables (IFCT 2017) and Standard Dietary Guidelines for Indians. Values represent typical nutritional ranges for raw or standard cooked ingredients. Individual requirements vary with physical activity, sleep and personal constitution.
        </div>''',
        unsafe_allow_html=True
    )

# ==========================================
# 5. MY PREFERENCES
# ==========================================
elif selected_page == "My Preferences":
    st.markdown(
        '''<div class="journal-header">
            <div class="section-label">Personalisation</div>
            <h1 class="journal-title">My preferences</h1>
            <div class="journal-subtitle">
                Tailor your weekly planner to your tastes, schedule and dietary preferences. Exclusions and allergies take priority over favourites.
            </div>
        </div>''',
        unsafe_allow_html=True
    )
    
    with st.form("preferences_form"):
        col_p1, col_p2 = st.columns(2)
        
        with col_p1:
            st.markdown("##### Dietary Boundaries")
            chicken_allowed = st.checkbox(
                "Include occasional chicken (approximately three meals weekly)",
                value=profile.get("chicken_ok", True)
            )
            
            allergies_str = st.text_input(
                "Allergies (comma separated)",
                value=", ".join(profile.get("allergies", []))
            )
            
            exclusions_str = st.text_input(
                "Ingredients to strictly exclude (comma separated)",
                value=", ".join(profile.get("exclusions", []))
            )
            
            dislikes_str = st.text_input(
                "Disliked foods (comma separated)",
                value=", ".join(profile.get("dislikes", []))
            )
            
            max_cook_time = st.slider(
                "Maximum cooking time for weeknight meals in minutes",
                15, 90,
                int(profile.get("max_time", 45))
            )
            
        with col_p2:
            st.markdown("##### Tastes and Routine")
            all_flavour_options = ["Comfort food", "Cheesy", "Creamy", "Spicy", "Tangy", "Mild", "Crispy", "Fresh", "Filling", "Quick", "Air fryer", "One pot"]
            saved_flavours = [f for f in profile.get("preferred_flavours", []) if f in all_flavour_options]
            selected_flavours = st.multiselect(
                "Preferred flavour profiles",
                all_flavour_options,
                default=saved_flavours
            )
            
            all_style_options = ["Indian comfort food", "Sandwiches", "Wraps and parathas", "Noodles and rice", "Pasta", "Rice bowls", "Smoothies and bowls", "Momos", "Burgers", "Homemade fast food"]
            saved_styles = [s for s in profile.get("preferred_styles", []) if s in all_style_options]
            selected_styles = st.multiselect(
                "Favourite meal styles",
                all_style_options,
                default=saved_styles
            )
            
            all_methods = ["Stovetop", "Air fryer", "Pan cooked", "Steamer", "Blender", "No cook"]
            saved_methods = [m for m in profile.get("methods", []) if m in all_methods]
            selected_methods = st.multiselect(
                "Preferred cooking methods",
                all_methods,
                default=saved_methods
            )
            
            water_goal = st.number_input(
                "Daily water reminder in millilitres",
                min_value=500,
                max_value=5000,
                value=int(profile.get("water_target", 2000)),
                step=250
            )
            
        submitted = st.form_submit_button("Save preferences", type="primary")
        
    if submitted:
        profile["chicken_ok"] = chicken_allowed
        profile["allergies"] = [x.strip() for x in allergies_str.split(",") if x.strip()]
        profile["exclusions"] = [x.strip() for x in exclusions_str.split(",") if x.strip()]
        profile["dislikes"] = [x.strip() for x in dislikes_str.split(",") if x.strip()]
        profile["max_time"] = max_cook_time
        profile["preferred_flavours"] = selected_flavours
        profile["preferred_styles"] = selected_styles
        profile["methods"] = selected_methods
        profile["water_target"] = water_goal
        
        persist()
        st.success("Your personal preferences have been saved and applied to your meal suggestions.")
        
    st.divider()
    
    st.markdown("##### Favourites Management")
    fav_ids = profile.get("favourites", [])
    fav_names = [MEALS[fid]["name"] for fid in fav_ids if fid in MEALS]
    st.write(f"Currently saved favourites ({len(fav_names)} dishes):")
    if fav_names:
        st.write(", ".join(fav_names))
    else:
        st.caption("No favourites saved yet. You can star dishes from the Recipes section.")
        
    st.markdown("##### Restore Defaults")
    if st.button("Restore starter profile and weekly plan"):
        state["profile"] = DEFAULT_PROFILE.copy()
        state["plan"] = make_plan(meals)
        state["eaten"] = []
        state["checked"] = []
        state["custom_grocery"] = []
        persist()
        st.success("Starter profile and plan restored.")
        st.rerun()

