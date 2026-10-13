import json
from pathlib import Path
from PIL import Image
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "assets" / "image_manifest.json"

_manifest_cache = None

def get_manifest():
    global _manifest_cache
    if _manifest_cache is None:
        if MANIFEST_PATH.exists():
            try:
                _manifest_cache = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            except Exception:
                _manifest_cache = {"images": {}}
        else:
            _manifest_cache = {"images": {}}
    return _manifest_cache

def resolve_meal_image(meal_or_id):
    """
    Resolves verified local image path and attribution metadata for a meal.
    Validates that the file exists and is a valid readable image.
    """
    if isinstance(meal_or_id, dict):
        meal_id = meal_or_id.get("id", "")
        img_id = meal_or_id.get("image_id", meal_id)
    else:
        meal_id = str(meal_or_id)
        img_id = meal_id
        
    manifest = get_manifest()
    images = manifest.get("images", {})
    entry = images.get(img_id) or images.get(meal_id)
    
    if entry and entry.get("verified") and entry.get("local_path"):
        local_file = ROOT / entry["local_path"]
        if local_file.exists():
            try:
                with Image.open(local_file) as im:
                    im.verify()
                return {
                    "path": str(local_file),
                    "attribution": entry.get("attribution", ""),
                    "licence": entry.get("licence", ""),
                    "photographer": entry.get("photographer", ""),
                    "page_url": entry.get("page_url", "")
                }
            except Exception:
                return None
    return None

def render_meal_photo(meal, max_height=None, show_attribution=False):
    """
    Renders a meal photo or compact, elegant cream fallback card.
    Used consistently across My Week, Recipes, and Swap alternatives.
    """
    meal_id = meal.get("id", "") if isinstance(meal, dict) else str(meal)
    meal_name = meal.get("name", meal_id.replace("_", " ").title()) if isinstance(meal, dict) else meal_id.replace("_", " ").title()
    
    img_info = resolve_meal_image(meal)
    if img_info:
        st.image(img_info["path"], width="stretch")
        if show_attribution and img_info.get("attribution"):
            st.caption(f"Verified photo: {img_info['attribution']}")
        return True
    else:
        height_style = f"max-height: {max_height}px;" if max_height else ""
        st.markdown(
            f'''<div class="meal-placeholder" style="{height_style}">
                <div class="meal-placeholder-title">{meal_name}</div>
                <div class="meal-placeholder-status">Photograph coming soon</div>
            </div>''',
            unsafe_allow_html=True
        )
        return False
