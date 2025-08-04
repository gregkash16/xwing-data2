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
    "database": "railway",
    "port": 47124
}

PILOT_DIR = r"C:\Users\gregk\Documents\GitHub\xwa-points\xwing-data2\data\pilots"
UPGRADE_DIR = r"C:\Users\gregk\Documents\GitHub\xwa-points\xwing-data2\data\upgrades"
LOG_FILE = "upload_entities_errors.txt"
TABLE_NAME = "entities"

# === LOGGING ===
def log_error(context, error):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] ERROR in {context}:\n")
        f.write(f"{traceback.format_exc()}\n")
        f.write("-" * 80 + "\n")

# === PILOTS ===
def collect_pilot_entities():
    rows = []
    for faction_folder in os.listdir(PILOT_DIR):
        faction_path = os.path.join(PILOT_DIR, faction_folder)
        if not os.path.isdir(faction_path):
            continue

        for file_name in os.listdir(faction_path):
            if not file_name.endswith('.json'):
                continue
            file_path = os.path.join(faction_path, file_name)
            table_base = os.path.splitext(file_name)[0].replace('-', '_')
            full_table_name = f"{faction_folder}.{table_base}"

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for pilot in data.get("pilots", []):
                    xws = pilot.get("xws")
                    name = pilot.get("name")
                    if xws and name:
                        rows.append({
                            "xws": xws,
                            "name": name,
                            "type": "pilot",
                            "faction": faction_folder,
                            "table_name": full_table_name
                        })
            except Exception as e:
                log_error(f"collect_pilot_entities({file_path})", e)
    return rows

# === UPGRADES ===
def collect_upgrade_entities():
    rows = []
    for file_name in os.listdir(UPGRADE_DIR):
        if not file_name.endswith(".json"):
            continue
        file_path = os.path.join(UPGRADE_DIR, file_name)
        table_base = os.path.splitext(file_name)[0].replace('-', '_')
        full_table_name = f"upgrades.{table_base}"

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                upgrades = json.load(f)
            for upgrade in upgrades:
                xws = upgrade.get("xws")
                name = upgrade.get("name")
                faction = upgrade.get("faction") or "Generic"
                if xws and name:
                    rows.append({
                        "xws": xws,
                        "name": name,
                        "type": "upgrade",
                        "faction": faction,
                        "table_name": full_table_name
                    })
        except Exception as e:
            log_error(f"collect_upgrade_entities({file_path})", e)
    return rows

# === MYSQL ===
def create_entity_table(cursor):
    try:
        cursor.execute(f"DROP TABLE IF EXISTS `{TABLE_NAME}`")
        cursor.execute(f"""
            CREATE TABLE `{TABLE_NAME}` (
                `xws` VARCHAR(255) PRIMARY KEY,
                `name` TEXT,
                `type` VARCHAR(10),
                `faction` VARCHAR(255),
                `table_name` VARCHAR(255)
            )
        """)
    except Exception as e:
        log_error("create_entity_table", e)

def insert_entities(cursor, rows):
    seen = set()
    for row in rows:
        try:
            if row['xws'] in seen:
                continue
            seen.add(row['xws'])
            cursor.execute(
                f"INSERT INTO `{TABLE_NAME}` (`xws`, `name`, `type`, `faction`, `table_name`) VALUES (%s, %s, %s, %s, %s)",
                (row["xws"], row["name"], row["type"], row["faction"], row["table_name"])
            )
        except Exception as e:
            log_error(f"insert_entity({row['xws']})", e)

# === MAIN ===
def process_entities():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
    except Exception as e:
        log_error("MySQL connection", e)
        return

    try:
        create_entity_table(cursor)
        pilots = collect_pilot_entities()
        upgrades = collect_upgrade_entities()
        insert_entities(cursor, pilots + upgrades)
        conn.commit()
    except Exception as e:
        log_error("process_entities", e)
    finally:
        cursor.close()
        conn.close()

    print("Entity collection complete.")

# === ENTRY POINT ===
if __name__ == "__main__":
    process_entities()
