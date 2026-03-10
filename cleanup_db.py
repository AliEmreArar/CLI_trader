import sqlite3
import os

DB_PATH = 'data/bist_model_ready.db'
NEW_DB_PATH = 'data/bist_model_ready_new.db'

try:
    if os.path.exists(NEW_DB_PATH):
        os.remove(NEW_DB_PATH)
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    new_conn = sqlite3.connect(NEW_DB_PATH)
    
    # Copy schema first
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='model_data'")
    schema = cursor.fetchone()[0]
    new_conn.execute(schema)
    
    # Copy only recent data
    print("Copying recent data...")
    cursor.execute("SELECT * FROM model_data WHERE date >= '2023-01-01'")
    
    batch_size = 10000
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
            
        new_conn.executemany("INSERT INTO model_data VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        new_conn.commit()
        
    # Copy portfolio table if it exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='portfolio'")
    if cursor.fetchone():
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='portfolio'")
        schema = cursor.fetchone()[0]
        new_conn.execute(schema)
        cursor.execute("SELECT * FROM portfolio")
        rows = cursor.fetchall()
        if rows:
             # Get column count dynamically
            col_count = len(rows[0])
            placeholders = ','.join(['?'] * col_count)
            new_conn.executemany(f"INSERT INTO portfolio VALUES ({placeholders})", rows)
        new_conn.commit()

    conn.close()
    new_conn.close()
    
    # Replace old db with new one
    os.replace(NEW_DB_PATH, DB_PATH)
    print("Database cleanup complete.")
    
except Exception as e:
    print(f"Error: {e}")
    if os.path.exists(NEW_DB_PATH):
        os.remove(NEW_DB_PATH)
