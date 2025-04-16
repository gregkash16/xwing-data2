import json
import os

# Set this to your pilots folder
PILOT_DIR = r"C:\Users\gregk\Documents\GitHub\xwa-points\xwing-data2\data\pilots"

# Loop through all JSON files in all faction folders
for faction in os.listdir(PILOT_DIR):
    faction_dir = os.path.join(PILOT_DIR, faction)
    if not os.path.isdir(faction_dir):
        continue

    for filename in os.listdir(faction_dir):
        if not filename.endswith(".json"):
            continue

        filepath = os.path.join(faction_dir, filename)

        with open(filepath, "r", encoding="utf-8") as f:
            ship_data = json.load(f)

        changed = False

        for pilot in ship_data.get("pilots", []):
            subtitle = pilot.pop("subtitle", None)
            caption = pilot.get("caption", "")

            if subtitle and not caption:
                pilot["caption"] = subtitle
                changed = True
            elif not caption:
                pilot["caption"] = ""
                changed = True
            elif subtitle:
                # subtitle exists but caption already filled — discard subtitle
                changed = True

        if changed:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(ship_data, f, indent=2, ensure_ascii=False)
            print(f"Updated: {filepath}")
