import sqlite3
import pandas as pd
import csv
import os
import shutil
import sys
import logging
from datetime import datetime

# initialize logger
logger = logging.getLogger(__name__)

# define paths
INPUT_DIR = "/home/globaladmin/IOTstack/volumes/nodered/data/datarsync"
OUTPUT_DIR = "/home/globaladmin/IOTstack/volumes/nodered/data/dataexport"
ARCHIVE_DIR = os.path.join(OUTPUT_DIR, "archive")

def ensure_directory_exists(directory):
    """ensures the given directory exists and sets the correct permissions."""
    try:
        os.makedirs(directory, exist_ok=True)
        os.chmod(directory, 0o777)
    except PermissionError:
        logger.error("Error: insufficient permissions to access %s. Try running as sudo.", directory)
        sys.exit(1)

def extract_boat_name(filename):
    """extracts the boat name from the given SQLite filename."""
    base_name = os.path.basename(filename)
    if "_" in base_name and base_name.endswith(".db"):
        return base_name.split("_")[-1].replace(".db", "")
    raise ValueError(f"Invalid filename format: {filename}. Expected format: datalog_<boatname>.db")

def archive_existing_files(boat_name):
    """moves existing CSV files for the same boat name into an 'Archive' folder."""
    ensure_directory_exists(ARCHIVE_DIR)
    for file in os.listdir(OUTPUT_DIR):
        if file.startswith(boat_name) and file.endswith(".csv"):
            old_path = os.path.join(OUTPUT_DIR, file)
            new_path = os.path.join(ARCHIVE_DIR, file)
            shutil.move(old_path, new_path)
            logger.debug("Moved %s to %s", file, ARCHIVE_DIR)

def export_sqlite_to_csv(db_name):
    """converts the SQLite "logdata" table into a CSV file."""
    table_name = "logdata"
    db_path = os.path.join(INPUT_DIR, db_name)
    if not os.path.exists(db_path):
        logger.error("Error: Database file %s does not exist.", db_path)
        return {"filename": db_name, "status": "error", "message": f"Database file {db_path} does not exist."}
    try:
        boat_name = extract_boat_name(db_name)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        output_csv = os.path.join(OUTPUT_DIR, f"{boat_name}_{timestamp}.csv")
        ensure_directory_exists(OUTPUT_DIR)
        archive_existing_files(boat_name)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        conn.close()
        rename_mapping = {"datetime": "ISODateTimeUTC", "lat": "Lat", "long": "Lon"}
        df.rename(columns=rename_mapping, inplace=True)
        standard_columns = ["ISODateTimeUTC", "Lat", "Lon", "SOG", "COG"]
        additional_columns = [col for col in columns if col not in rename_mapping.keys() and col not in standard_columns]
        final_columns = standard_columns + additional_columns
        df.to_csv(output_csv, index=False, quoting=csv.QUOTE_MINIMAL, columns=final_columns)
        logger.debug("Export successful! Data saved to %s", output_csv)
        return {"filename": db_name, "status": "success", "message": f"Export successful! Data saved to {output_csv}"}
    except Exception as e:
        logger.error("Error processing %s: %s", db_name, str(e))
        return {"filename": db_name, "status": "error", "message": str(e)}

if __name__ == "__main__":
    ensure_directory_exists(INPUT_DIR)
    for filename in os.listdir(INPUT_DIR):
        if filename.endswith(".db") and filename.startswith("datalog_"):
            result = export_sqlite_to_csv(filename)
            logger.debug("Processing result: %s", result)
