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
    "database": "railway",  # Needed for initial connect; schema changes dynamically
    "port": 47124
}

UPGRADE_DIR = r"C:\Users\gregk\Documents\GitHub\xwa-points\xwing-data2\data\upgrades"
LOG_FILE = "upload_upgrade_errors.txt"
UPGRADE_SCHEMA = "upgrades"

# === LOGGING ===
def log_error(context, error):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] ERROR in {context}:\n")
        f.write(f"{traceback.format_exc()}\n")
        f.write("-" * 80 + "\n")

# === HELPERS ===
def normalize_list(val):
    return ', '.join(str(v) for v in val) if isinstance(val, list) else val

def normalize_dict(val):
    return json.dumps(val) if isinstance(val, dict) else val

def extract_factions(restrictions):
    if not isinstance(restrictions, list):
        return None
    factions = set()
    for r in restrictions:
        if isinstance(r, dict) and "factions" in r:
            factions.update(r["factions"])
    return ", ".join(factions) if factions else None

def gather_all_headers(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            items = json.load(f)
        headers = set()
        for upgrade in items:
            headers.update(upgrade.keys())
            for side in upgrade.get("sides", []):
                headers.update(side.keys())
        headers.add("factions")  # our flattened field
        headers.add("cost")      # we'll pull cost.value
        headers.discard("sides")  # we split this
        headers.discard("restrictions")  # replaced with factions
        return sorted(headers)
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

def insert_upgrades(cursor, schema_name, table_name, headers, file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            upgrades = json.load(f)
    except Exception as e:
        log_error(f"open_json({file_path})", e)
        return

    for upgrade in upgrades:
        try:
            base = {k: upgrade.get(k) for k in headers if k not in ("sides", "restrictions", "cost")}
            base["cost"] = upgrade.get("cost", {}).get("value")
            base["factions"] = extract_factions(upgrade.get("restrictions"))

            sides = upgrade.get("sides", [{}])
            for side in sides:
                row = base.copy()
                for k, v in side.items():
                    if isinstance(v, list):
                        row[k] = normalize_list(v)
                    elif isinstance(v, dict):
                        row[k] = normalize_dict(v)
                    else:
                        row[k] = v

                columns = ', '.join(f"`{k}`" for k in headers)
                placeholders = ', '.join(['%s'] * len(headers))
                values = [row.get(k) for k in headers]

                cursor.execute(
                    f"INSERT INTO `{schema_name}`.`{table_name}` ({columns}) VALUES ({placeholders})", values
                )
        except Exception as e:
            log_error(f"insert_upgrade({schema_name}.{table_name} - {upgrade.get('name', 'unknown')})", e)

# === MAIN PROCESSING FUNCTION ===

def process_upgrades():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
    except Exception as e:
        log_error("MySQL connection", e)
        return

    for file_name in os.listdir(UPGRADE_DIR):
        if not file_name.endswith('.json'):
            continue

        file_path = os.path.join(UPGRADE_DIR, file_name)
        table_name = os.path.splitext(file_name)[0].replace('-', '_')

        print(f"Processing: {file_path} → {UPGRADE_SCHEMA}.{table_name}")

        try:
            headers = gather_all_headers(file_path)
            if not headers:
                continue
            create_schema_and_table(cursor, UPGRADE_SCHEMA, table_name, headers)
            insert_upgrades(cursor, UPGRADE_SCHEMA, table_name, headers, file_path)
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
    process_upgrades()
