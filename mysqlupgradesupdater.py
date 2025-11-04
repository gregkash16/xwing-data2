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
    "database": "railway",  # initial connect only; we'll USE upgrades schema per table
    "port": 47124
}

UPGRADE_DIR = r"C:\Users\gregk\Documents\GitHub\xwa-points\xwing-data2\data\upgrades"
LOG_FILE = "upload_upgrade_errors.txt"
UPGRADE_SCHEMA = "upgrades"
DRY_RUN = False  # set True to preview without writing

# === LOGGING ===
def log_error(context, error):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] ERROR in {context}:\n")
        f.write(f"{traceback.format_exc()}\n")
        f.write("-" * 80 + "\n")

def log_info(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] {msg}\n")

# === HELPERS ===
def hyphen_to_underscore(s: str) -> str:
    return s.replace("-", "_")

def extract_cost_value(upgrade: dict):
    """
    Returns an int cost if available at upgrade['cost']['value'] (or a plain int at upgrade['cost']).
    If absent or non-numeric (e.g., variable/array), returns None.
    """
    c = upgrade.get("cost")
    if isinstance(c, dict):
        v = c.get("value")
        if isinstance(v, int):
            return v
    elif isinstance(c, int):
        return c
    return None

def table_has_columns(cur, table: str, needed: list):
    cur.execute(f"SHOW COLUMNS FROM `{table}`")
    cols = {row[0].lower() for row in cur.fetchall()}
    return all(c.lower() in cols for c in needed), cols

def update_cost(cur, schema: str, table: str, xws: str, cost: int):
    """
    Returns a tuple (status, affected_rows)
      - status in {"missing_cols","no_row","up_to_date","updated"}
      - affected_rows is 0/1 for updated, else 0
    """
    cur.execute(f"USE `{schema}`")

    exists, cols = table_has_columns(cur, table, ["xws", "cost"])
    if not exists:
        missing = [c for c in ("xws", "cost") if c not in cols]
        log_info(f"[{schema}.{table}] Missing columns {missing}; skipping table.")
        return ("missing_cols", 0)

    # 1) Does the row exist?
    cur.execute(f"SELECT `cost` FROM `{table}` WHERE `xws` = %s LIMIT 1", (xws,))
    row = cur.fetchone()
    if not row:
        return ("no_row", 0)

    # 2) Compare to avoid no-op updates appearing as "no row"
    current_cost = row[0]
    try:
        current_cost_int = int(current_cost) if current_cost is not None else None
    except Exception:
        current_cost_int = None  # if stored as non-numeric text

    if current_cost_int == cost:
        return ("up_to_date", 0)

    # 3) Perform the update (or preview)
    if DRY_RUN:
        log_info(f"DRY_RUN: UPDATE `{schema}`.`{table}` SET cost={cost} WHERE xws='{xws}'")
        return ("updated", 1)

    cur.execute(
        f"UPDATE `{table}` SET `cost` = %s WHERE `xws` = %s",
        (cost, xws)
    )
    return ("updated", cur.rowcount)

# === MAIN ===
def process_upgrades_cost_only():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
    except Exception as e:
        log_error("MySQL connection", e)
        return

    total_files = 0
    total_items = 0
    total_updates = 0
    total_up_to_date = 0
    total_missing_rows = 0
    total_missing_cols_tables = set()

    for file_name in os.listdir(UPGRADE_DIR):
        if not file_name.endswith('.json'):
            continue

        file_path = os.path.join(UPGRADE_DIR, file_name)
        table_name = hyphen_to_underscore(os.path.splitext(file_name)[0])

        total_files += 1
        log_info(f"Processing: {file_path} → {UPGRADE_SCHEMA}.{table_name}")

        # Ensure schema.table exists
        try:
            cur.execute(f"USE `{UPGRADE_SCHEMA}`")
            cur.execute("SHOW TABLES LIKE %s", (table_name,))
            if cur.fetchone() is None:
                log_info(f"[{UPGRADE_SCHEMA}.{table_name}] Table not found; skipping file.")
                continue
        except Exception as e:
            log_error(f"schema/table check ({UPGRADE_SCHEMA}.{table_name})", e)
            continue

        # Load upgrades list
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                upgrades = json.load(f)
            if not isinstance(upgrades, list):
                log_info(f"[{file_path}] JSON root not a list; skipping.")
                continue
        except Exception as e:
            log_error(f"open_json({file_path})", e)
            continue

        # Update each upgrade's cost by xws
        for upgrade in upgrades:
            total_items += 1
            xws = upgrade.get("xws")
            if not xws:
                log_info(f"[{UPGRADE_SCHEMA}.{table_name}] Missing xws; skipping upgrade '{upgrade.get('name','<no name>')}'")
                continue

            cost_val = extract_cost_value(upgrade)
            if cost_val is None:
                log_info(f"[{UPGRADE_SCHEMA}.{table_name}] No simple numeric cost for xws='{xws}'; skipping")
                continue

            try:
                status, affected = update_cost(cur, UPGRADE_SCHEMA, table_name, xws, cost_val)
                if status == "no_row":
                    total_missing_rows += 1
                    log_info(f"[{UPGRADE_SCHEMA}.{table_name}] No DB row for xws='{xws}'")
                elif status == "up_to_date":
                    total_up_to_date += 1
                    # optional: uncomment to log each up-to-date item
                    # log_info(f"[{UPGRADE_SCHEMA}.{table_name}] Up-to-date for xws='{xws}'")
                elif status == "updated":
                    total_updates += affected
                    if not DRY_RUN:
                        conn.commit()
                elif status == "missing_cols":
                    total_missing_cols_tables.add(f"{UPGRADE_SCHEMA}.{table_name}")
            except Exception as e:
                log_error(f"update_cost({UPGRADE_SCHEMA}.{table_name}, xws={xws})", e)

    try:
        cur.close()
        conn.close()
    except Exception as e:
        log_error("closing connection", e)

    if total_missing_cols_tables:
        log_info("Tables missing required columns (xws, cost): " + ", ".join(sorted(total_missing_cols_tables)))

    log_info(
        f"Done. files={total_files}, upgrades_seen={total_items}, "
        f"updated={total_updates}, up_to_date={total_up_to_date}, rows_not_found={total_missing_rows}"
    )

if __name__ == "__main__":
    process_upgrades_cost_only()
