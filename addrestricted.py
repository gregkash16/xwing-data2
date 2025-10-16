import json
from pathlib import Path
from datetime import datetime
import zipfile

# ====== CONFIG ======
SCRIPT_DIR = Path(__file__).parent
PILOTS_DIR = Path(r"C:\Users\gregk\Documents\GitHub\xwing-data2\data\pilots")
UPGRADES_DIR = Path(r"C:\Users\gregk\Documents\GitHub\xwing-data2\data\upgrades")
# =====================


def backup_all_jsons(pilots_dir: Path, upgrades_dir: Path, out_dir: Path) -> Path:
    """Create a single backup zip of all JSONs before modification."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = out_dir / f"backup_addRestricted_{ts}.zip"
    print(f"[INFO] Creating backup archive: {zip_path}")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for json_path in pilots_dir.rglob("*.json"):
            arcname = json_path.relative_to(pilots_dir.parent)
            zf.write(json_path, arcname)
        for json_path in upgrades_dir.glob("*.json"):
            arcname = json_path.relative_to(upgrades_dir.parent)
            zf.write(json_path, arcname)
    print("[INFO] Backup completed.")
    return zip_path


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def add_restricted_to_pilots(pilots_dir: Path):
    updated = 0
    for json_path in pilots_dir.rglob("*.json"):
        try:
            data = load_json(json_path)
        except Exception as e:
            print(f"[WARN] Could not read {json_path}: {e}")
            continue

        pilots = data.get("pilots")
        if not isinstance(pilots, list):
            continue

        file_changed = False
        for p in pilots:
            if "restricted" not in p:
                p["restricted"] = 0
                file_changed = True

        if file_changed:
            save_json(json_path, data)
            updated += 1
            print(f"  Updated: {json_path.name}")

    print(f"[INFO] Pilot files updated: {updated}")
    return updated


def add_restricted_to_upgrades(upgrades_dir: Path):
    updated = 0
    for json_path in upgrades_dir.glob("*.json"):
        try:
            data = load_json(json_path)
        except Exception as e:
            print(f"[WARN] Could not read {json_path}: {e}")
            continue

        file_changed = False

        def apply(obj):
            if isinstance(obj, dict) and "restricted" not in obj:
                obj["restricted"] = 0
                return True
            return False

        if isinstance(data, dict):
            if apply(data):
                file_changed = True
        elif isinstance(data, list):
            for item in data:
                if apply(item):
                    file_changed = True

        if file_changed:
            save_json(json_path, data)
            updated += 1
            print(f"  Updated: {json_path.name}")

    print(f"[INFO] Upgrade files updated: {updated}")
    return updated


def main():
    print("[INFO] Starting restricted-key insertion process...")
    backup_all_jsons(PILOTS_DIR, UPGRADES_DIR, SCRIPT_DIR)

    pilot_count = add_restricted_to_pilots(PILOTS_DIR)
    upgrade_count = add_restricted_to_upgrades(UPGRADES_DIR)

    print("\n==== SUMMARY ====")
    print(f"Pilot files modified: {pilot_count}")
    print(f"Upgrade files modified: {upgrade_count}")
    print("[DONE]")


if __name__ == "__main__":
    main()
