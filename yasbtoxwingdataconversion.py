import os
import re
import json
from pathlib import Path

# === CONFIGURATION ===
coffee_file = Path(r"C:\Users\gregk\Documents\GitHub\xwing\coffeescripts\content\cards-common.coffee")
pilots_dir = Path(r"C:\Users\gregk\Documents\GitHub\xwa-points\xwing-data2\data\pilots")
error_log_path = Path("unmatched_ships.txt")

# Faction to folder mapping
faction_map = {
    "Rebel Alliance": "rebel-alliance",
    "Galactic Empire": "galactic-empire",
    "Scum and Villainy": "scum-and-villainy",
    "Resistance": "resistance",
    "First Order": "first-order",
    "Galactic Republic": "galactic-republic",
    "Separatist Alliance": "separatist-alliance"
}

# === FUNCTIONS ===
def parse_coffee(path):
    with open(path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    ships = []
    current = {}
    capture = False

    for line in lines:
        line = line.strip()
        if line.startswith("xws_name:"):
            if current:
                if all(k in current for k in ["xws_name", "faction", "pointsxwa", "loadoutxwa", "slotsxwa"]):
                    ships.append(current)
                else:
                    print(f"Skipping incomplete entry: {current}")
                current = {}
            capture = True
            current["xws_name"] = line.split(":", 1)[1].strip().strip("'\"")

        if not capture:
            continue

        if line.startswith("faction:"):
            current["faction"] = line.split(":", 1)[1].strip().strip("'\"")
        elif line.startswith("pointsxwa:"):
            current["pointsxwa"] = int(line.split(":", 1)[1].strip())
        elif line.startswith("loadoutxwa:"):
            current["loadoutxwa"] = int(line.split(":", 1)[1].strip())
        elif line.startswith("slotsxwa:"):
            slot_list = re.findall(r"'(.*?)'", line)
            current["slotsxwa"] = slot_list

    if current and all(k in current for k in ["xws_name", "faction", "pointsxwa", "loadoutxwa", "slotsxwa"]):
        ships.append(current)
    return ships


def update_jsons(ships, base_dir):
    unmatched = []

    for ship in ships:
        faction_name = ship.get("faction")
        if not faction_name or faction_name not in faction_map:
            unmatched.append(f"{ship.get('xws_name')} (invalid or missing faction)")
            continue

        folder = faction_map[faction_name]
        folder_path = base_dir / folder
        found = False

        for json_file in folder_path.glob("*.json"):
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            updated = False
            for pilot in data.get("pilots", []):
                if pilot.get("xws") == ship["xws_name"]:
                    pilot["cost"] = ship["pointsxwa"]
                    pilot["loadout"] = ship["loadoutxwa"]
                    pilot["slots"] = ship.get("slotsxwa", [])
                    updated = True
                    found = True

            if updated:
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                break

        if not found:
            unmatched.append(ship["xws_name"])

    return unmatched


# === MAIN EXECUTION ===
def main():
    print("Parsing coffee file...")
    ships = parse_coffee(coffee_file)

    print("Updating JSON files...")
    unmatched = update_jsons(ships, pilots_dir)

    if unmatched:
        print(f"{len(unmatched)} ships not matched. Writing to log.")
        with open(error_log_path, "w", encoding="utf-8") as log:
            for name in unmatched:
                log.write(f"{name}\n")
    else:
        print("All ships matched and updated successfully.")

if __name__ == "__main__":
    main()
