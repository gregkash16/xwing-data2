import os
import json
import re

upgrades_path = r"C:\Users\gregk\Documents\GitHub\xwa-points\xwing-data2\data\upgrades"

def format_bracket_content(text):
    def replacer(match):
        content = match.group(1).lower()

        # Special replacements
        if content == "charges":
            return "[Charge]"
        if content == "hard turn left":
            return "[Turn Left]"

        # Capitalize each word inside brackets
        return "[" + " ".join(word.capitalize() for word in content.split()) + "]"

    return re.sub(r"\[([^\[\]]+)\]", replacer, text)

for file in os.listdir(upgrades_path):
    if file.endswith(".json"):
        file_path = os.path.join(upgrades_path, file)

        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"❌ JSON error in {file_path}: {e}")
                continue

        changed = False

        for upgrade in data:
            sides = upgrade.get("sides", [])
            for side in sides:
                if "ability" in side and isinstance(side["ability"], str):
                    updated = format_bracket_content(side["ability"])
                    if updated != side["ability"]:
                        side["ability"] = updated
                        changed = True

        if changed:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"✅ Updated: {file_path}")
