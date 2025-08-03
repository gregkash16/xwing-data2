import os
import json
import mysql.connector
import traceback
from datetime import datetime

# === CONFIGURATION ===
DB_CONFIG = {
    "host": "metro.proxy.rlwy.net",
    "user": "root",
    "password": "mChKvvEQzxWOKOBhPcYHltMyADqwhpWz",
    "database": "railway",  # Used for initial connection; we'll create others
    "port": 47124
}

PILOT_DIR = r"C:\Users\gregk\Documents\GitHub\xwa-points\xwing-data2\data\pilots"
LOG_FILE = "upload_errors.txt"

DESIRED_HEADER_ORDER = [
    "xws", "limited", "name", "caption", "initiative", "text", "ability",
    "charges", "force", "shipAbility", "cost", "loadout", "standardLoadout",
    "slots", "shipActions", "shipStats", "keywords",
    "standard", "extended", "epic", "image", "artwork"
]

# === LOGGING ===
def log_error(context, error):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] ERROR in {context}:\n")
        f.write(f"{traceback.format_exc()}\n")
        f.write("-" * 80 + "\n")

# === HELPERS ===
def normalize_list(lst):
    if isinstance(lst, list):
        return ', '.join(str(item) for item in lst)
    return lst

def normalize_ship_actions(actions):
    if not isinstance(actions, list):
        return None
    result = []
    for action in actions:
        base = f"{action.get('difficulty', '')} {action.get('type', '')}".strip()
        if "linked" in action:
            linked = action["linked"]
            base += f" > {linked.get('difficulty', '')} {linked.get('type', '')}".strip()
        result.append(base)
    return ', '.join(result)

def normalize_ship_ability(ability):
    if not isinstance(ability, dict):
        return None
    return f"{ability.get('name', '')}: {ability.get('text', '')}"

def gather_all_headers(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        found_headers = set()
        for pilot in data.get('pilots', []):
            found_headers.update(pilot.keys())
        found_headers.update(["shipActions", "shipAbility", "shipStats"])  # Ensure these are always present
        ordered_headers = [h for h in DESIRED_HEADER_ORDER if h in found_headers]
        remaining = [h for h in found_headers if h not in ordered_headers]
        return ordered_headers + sorted(remaining)
    except Exception as e:
        log_error(f"gather_all_headers({file_path})", e)
        return []

def create_schema_and_table(cursor, schema_name, table_name, headers):
    try:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{schema_name}`")
        cursor.execute(f"USE `{schema_name}`")
        safe_headers = [f"`{h}` TEXT" for h in headers]
        cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
        cursor.execute(f"CREATE TABLE `{table_name}` ({', '.join(safe_headers)})")
    except Exception as e:
        log_error(f"create_schema_and_table({schema_name}.{table_name})", e)

def insert_pilots(cursor, schema_name, table_name, headers, file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        log_error(f"open_json({file_path})", e)
        return

    for pilot in data.get('pilots', []):
        try:
            row = {}
            for key in headers:
                val = pilot.get(key)
                if key == "shipActions":
                    val = normalize_ship_actions(pilot.get("shipActions", None))
                elif key == "shipAbility":
                    val = normalize_ship_ability(pilot.get("shipAbility", None))
                elif isinstance(val, list):
                    val = normalize_list(val)
                elif isinstance(val, dict):
                    val = json.dumps(val)
                row[key] = val

            columns = ', '.join(f"`{k}`" for k in headers)
            placeholders = ', '.join(['%s'] * len(headers))
            values = [row.get(k) for k in headers]

            cursor.execute(f"INSERT INTO `{schema_name}`.`{table_name}` ({columns}) VALUES ({placeholders})", values)
        except Exception as e:
            log_error(f"insert_pilot({schema_name}.{table_name} - {pilot.get('name', 'unknown')})", e)

# === MAIN PROCESSING FUNCTION ===

def process_all():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
    except Exception as e:
        log_error("MySQL connection", e)
        return

    for faction in os.listdir(PILOT_DIR):
        faction_path = os.path.join(PILOT_DIR, faction)
        if not os.path.isdir(faction_path):
            continue

        schema_name = faction.replace("-", "_")

        for file_name in os.listdir(faction_path):
            if not file_name.endswith('.json'):
                continue

            file_path = os.path.join(faction_path, file_name)
            table_name = os.path.splitext(file_name)[0].replace('-', '_')

            print(f"Processing: {file_path} → {schema_name}.{table_name}")

            try:
                headers = gather_all_headers(file_path)
                if not headers:
                    continue
                create_schema_and_table(cursor, schema_name, table_name, headers)
                insert_pilots(cursor, schema_name, table_name, headers, file_path)
                conn.commit()
            except Exception as e:
                log_error(f"process_file({file_path})", e)

    try:
        cursor.close()
        conn.close()
    except Exception as e:
        log_error("closing connection", e)

    print("Done!")

# === ENTRY POINT ===
if __name__ == "__main__":
    process_all()
