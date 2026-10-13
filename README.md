# The Little Food Journal

A local Streamlit meal planner for a week of familiar homemade meals. The starter plan has three meals a day, keeps chicken momos on Wednesday evening, and limits chicken to three meals. Preferences, meal changes, grocery checks and daily notes are saved in a local JSON file.

## Start the app

From this folder in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

If PowerShell blocks activation, run `.venv\Scripts\python.exe -m pip install -r requirements.txt`, then `.venv\Scripts\python.exe -m streamlit run app.py`.

## Files

`app.py` contains the Streamlit views and interactions. `data/meals.json` holds structured recipes that power the week, swaps, grocery list and recipe browser. `utils` contains local storage, meal rules, grocery consolidation and summary functions. `assets/styles.css` defines the visual theme. `assets/image_manifest.json` tracks food photography.

## Food photography

Authentic food photography sourced from Wikimedia Commons with human authorship and Creative Commons or Public Domain licenses. All 21 meals in the weekly starter plan have verified genuine photographs, alongside popular library dishes. Unverified library dishes display an elegant cream fallback card with the dish title, category badge, and status text "Photograph coming soon". All image source URLs, photographer credits, and licenses are documented in `assets/image_manifest.json`.

## Local data and troubleshooting

Changes are written to `data/user_state.json` on this device. The file is ignored by Git. If it becomes malformed, move or remove it and restart the app to return to the starter plan. The app needs Python and Streamlit only. Google Fonts are optional and fall back to installed serif and sans serif fonts when offline.

Nutrition totals are intentionally not shown. The project does not bundle an ingredient level nutrition reference with traceable data, so showing dish level numbers would imply more certainty than is available. The general protein reference is a broad starting point, not an individual prescription.
