import sqlite3
import os

db_path = 'sicday.db'
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE registrations ADD COLUMN status VARCHAR DEFAULT 'registered'")
        conn.commit()
        print("Column 'status' added successfully.")
    except Exception as e:
        print("Error:", e)
    conn.close()
