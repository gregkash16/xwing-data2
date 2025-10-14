import json
import shutil
from pathlib import Path

# ==== CONFIG ====
REV_DIR = Path(r"C:\Users\gregk\Documents\GitHub\xwa-points\revisions\50P2")
PILOTS_DIR = Path(r"C:\Users\gregk\Documents\GitHub\xwing-data2\data\pilots")

# Map the 7 source files -> their target faction folders
FACTION_MAP = {
    "firstorder.json": "first-order",
    "galacticempire.json": "galactic-empire",
    "galacticrepublic.json": "galactic-republic",
    "rebelalliance.json": "rebel-alliance",
    "resistance.json": "resistance",
    "scumandvillainy.json": "scum-and-villainy",
    "separatistalliance.json": "separatist-alliance",
}

# Only touch these fields
FIELDS_TO_COPY = ["cost", "loadout", "slots"]


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json_with_backup(path: Path, data):
    # Write a .bak the first time we modify a file in this run
    bak = path.with_suffix(path.suffix + ".bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def iter_source_pilots(source_data):
    """
    Yields tuples: (pilot_xws, payload_dict)
    Where payload_dict contains the fields we want to copy.
    The source_data format is:
      {
        "TIE/ba Interceptor": {
           "ember": { "cost": 10, "loadout": 8, "slots": [...] , ... },
           ...
        },
        "TIE/fo Fighter": { ... },
        ...
      }
    Each inner key (e.g. "ember") is the xws we should match on.
    """
    for ship_name, pilots_block in source_data.items():
        if not isinstance(pilots_block, dict):
            # Some files could have unexpected structure; skip safely.
            continue
        for pilot_key, pilot_obj in pilots_block.items():
            if not isinstance(pilot_obj, dict):
                continue
            payload = {k: pilot_obj.get(k) for k in FIELDS_TO_COPY if k in pilot_obj}
            # Only yield if at least one of our fields is present
            if payload:
                yield pilot_key, payload


def update_faction_folder(faction_folder: Path, updates_by_xws: dict):
    """
    Walk all ship JSON files in faction_folder and update pilots whose 'xws' matches.
    Returns (updated_count, touched_files, missing_xws_set)
    """
    updated = 0
    touched_files = set()
    found_xws = set()

    for ship_json in faction_folder.glob("*.json"):
        try:
            data = load_json(ship_json)
        except Exception as e:
            print(f"[WARN] Failed to read {ship_json}: {e}")
            continue

        pilots = data.get("pilots")
        if not isinstance(pilots, list):
            # Some files may not be ship files (rare), skip
            continue

        file_changed = False
        for p in pilots:
            xws = p.get("xws")
            if not xws:
                continue
            if xws in updates_by_xws:
                payload = updates_by_xws[xws]
                # Apply only the requested fields if present
                for field, value in payload.items():
                    p[field] = value
                updated += 1
                found_xws.add(xws)
                file_changed = True

        if file_changed:
            try:
                save_json_with_backup(ship_json, data)
                touched_files.add(ship_json.name)
            except Exception as e:
                print(f"[ERROR] Failed to write {ship_json}: {e}")

    missing = set(updates_by_xws.keys()) - found_xws
    return updated, touched_files, missing


def main():
    total_updated = 0
    total_missing = []
    total_touched_files = set()

    for src_name, faction_folder_name in FACTION_MAP.items():
        src_path = REV_DIR / src_name
        if not src_path.exists():
            print(f"[WARN] Source not found (skipping): {src_path}")
            continue

        try:
            source_data = load_json(src_path)
        except Exception as e:
            print(f"[WARN] Couldn't parse {src_path}: {e}")
            continue

        # Build a dict of xws -> {cost, loadout, slots}
        updates_by_xws = {}
        for pilot_xws, payload in iter_source_pilots(source_data):
            updates_by_xws[pilot_xws] = payload

        if not updates_by_xws:
            print(f"[INFO] No updatable fields found in {src_name}")
            continue

        faction_folder = PILOTS_DIR / faction_folder_name
        if not faction_folder.exists():
            print(f"[WARN] Faction folder missing (skipping): {faction_folder}")
            continue

        print(f"[INFO] Updating {faction_folder_name} from {src_name} "
              f"({len(updates_by_xws)} pilot entries) ...")
        updated_count, touched_files, missing_xws = update_faction_folder(
            faction_folder, updates_by_xws
        )

        print(f"  - Updated pilots: {updated_count}")
        if touched_files:
            for fn in sorted(touched_files):
                print(f"    * wrote {fn}")
        if missing_xws:
            print(f"  - Not found (by xws) in {faction_folder_name}: {len(missing_xws)}")
            # For brevity, show a limited preview; comment out to print all.
            preview = sorted(list(missing_xws))[:25]
            for k in preview:
                print(f"    - {k}")
            if len(missing_xws) > 25:
                print(f"    ... (+{len(missing_xws) - 25} more)")

        total_updated += updated_count
        total_touched_files |= touched_files
        total_missing.extend(missing_xws)

    print("\n==== SUMMARY ====")
    print(f"Total pilots updated: {total_updated}")
    print(f"Files modified: {len(total_touched_files)}")
    if total_missing:
        print(f"Missing pilots (xws not found across target ship files): {len(total_missing)}")
        # Print a small, de-duplicated sample
        uniq_missing = sorted(set(total_missing))
        for k in uniq_missing[:50]:
            print(f"  - {k}")
        if len(uniq_missing) > 50:
            print(f"  ... (+{len(uniq_missing) - 50} more)")


if __name__ == "__main__":
    main()
