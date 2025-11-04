import os
import json
import traceback
from datetime import datetime
import mysql.connector

# ================= CONFIG =================
DB_CONFIG = {
    "host": "metro.proxy.rlwy.net",
    "user": "root",
    "password": "mChKvvEQzxWOKOBhPcYHltMyADqwhpWz",
    "database": "railway",   # just for initial connection; we'll USE schema per faction
    "port": 47124,
}

# Change if your local path differs
PILOT_DIR = r"C:\Users\gregk\Documents\GitHub\xwing-data2\data\pilots"

FACTIONS = [
    #"first-order",
    #"galactic-republic",
    #"galactic-empire",
    #"rebel-alliance",
    #"resistance",
    #"scum-and-villainy",
    "separatist-alliance",   # keeping your spelling as provided
]

LOG_FILE = "upload_errors.txt"
DRY_RUN = False  # set True to see actions without writing DB
# ==========================================

def log_error(context: str, exc: BaseException):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] ERROR in {context}:\n")
        f.write(f"{traceback.format_exc()}\n")
        f.write("-" * 80 + "\n")

def log_info(line: str):
    print(line)
    # optional: also append to the same log file for traceability
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] {line}\n")

def hyphen_to_underscore(s: str) -> str:
    return s.replace("-", "_")

def titleize_slot(slot: str) -> str:
    # "force-power" -> "Force Power", "tech" -> "Tech"
    return slot.replace("-", " ").title()

def normalize_slots(slots):
    if not slots:
        return None
    if isinstance(slots, list):
        return ", ".join(titleize_slot(s) for s in slots)
    # if string already, try to be graceful
    return ", ".join(titleize_slot(x.strip()) for x in str(slots).split(",") if x.strip())

def get_cost(pilot: dict):
    # Handle both "cost" and "points"
    for key in ("cost", "points"):
        if key in pilot:
            try:
                return int(pilot[key])
            except Exception:
                return None
    return None

def get_loadout(pilot: dict):
    # Handle "loadout" or "loadoutValue"
    for key in ("loadout", "loadoutValue"):
        if key in pilot:
            try:
                return int(pilot[key])
            except Exception:
                return None
    return None

def get_slots(pilot: dict, ship_root: dict):
    # Prefer pilot-level; if absent, you can optionally fall back to file-level if your data has it
    slots = pilot.get("slots")
    if not slots:
        slots = ship_root.get("slots")  # optional, many datasets don’t have this at file level
    return normalize_slots(slots)

def update_row(conn, schema: str, table: str, xws: str, cost, loadout, slots_norm):
    cur = conn.cursor()
    try:
        cur.execute(f"USE `{schema}`")
        # Ensure the needed columns exist; if not, we log and skip that column
        cur.execute(f"SHOW COLUMNS FROM `{table}`")
        cols = {row[0].lower() for row in cur.fetchall()}
        missing = [c for c in ("xws", "cost", "loadout", "slots") if c not in cols]
        if "xws" in missing:
            log_info(f"[{schema}.{table}] missing required column 'xws'; skipping table.")
            return

        sets = []
        vals = []

        if "cost" not in missing and cost is not None:
            sets.append("`cost` = %s")
            vals.append(cost)
        if "loadout" not in missing and loadout is not None:
            sets.append("`loadout` = %s")
            vals.append(loadout)
        if "slots" not in missing and slots_norm is not None:
            sets.append("`slots` = %s")
            vals.append(slots_norm)

        if not sets:
            # nothing to update for this pilot
            return

        vals.append(xws)
        sql = f"UPDATE `{table}` SET {', '.join(sets)} WHERE `xws` = %s"

        if DRY_RUN:
            log_info(f"DRY_RUN UPDATE {schema}.{table} SET {sets} WHERE xws={xws}")
            return

        cur.execute(sql, vals)
        if cur.rowcount == 0:
            log_info(f"[{schema}.{table}] No row found for xws='{xws}'")
        else:
            log_info(f"[{schema}.{table}] Updated xws='{xws}' ({', '.join([s.split('=')[0].strip('` ') for s in sets])})")
        conn.commit()
    except Exception as e:
        log_error(f"update_row({schema}.{table}, xws={xws})", e)
    finally:
        cur.close()

def process():
    # Connect once; reuse
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
    except Exception as e:
        log_error("MySQL connection", e)
        return

    for faction in FACTIONS:
        faction_path = os.path.join(PILOT_DIR, faction)
        if not os.path.isdir(faction_path):
            log_info(f"Skipping faction (no folder): {faction_path}")
            continue

        schema = hyphen_to_underscore(faction)

        for file_name in os.listdir(faction_path):
            if not file_name.endswith(".json"):
                continue

            file_path = os.path.join(faction_path, file_name)
            table = hyphen_to_underscore(os.path.splitext(file_name)[0])

            log_info(f"Processing {file_path} -> {schema}.{table}")

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    ship_json = json.load(f)
            except Exception as e:
                log_error(f"open_json({file_path})", e)
                continue

            pilots = ship_json.get("pilots", [])
            if not isinstance(pilots, list):
                log_info(f"[{file_path}] 'pilots' is missing or not a list; skipping file.")
                continue

            for p in pilots:
                try:
                    xws = p.get("xws")
                    if not xws:
                        log_info(f"[{schema}.{table}] pilot missing 'xws'; skipping: {p.get('name','<no name>')}")
                        continue

                    cost = get_cost(p)
                    loadout = get_loadout(p)
                    slots_norm = get_slots(p, ship_json)

                    if cost is None and loadout is None and slots_norm is None:
                        # nothing to update
                        continue

                    update_row(conn, schema, table, xws, cost, loadout, slots_norm)

                except Exception as e:
                    log_error(f"pilot_update({schema}.{table}, xws={p.get('xws')})", e)

    try:
        conn.close()
    except Exception as e:
        log_error("closing connection", e)

if __name__ == "__main__":
    process()
