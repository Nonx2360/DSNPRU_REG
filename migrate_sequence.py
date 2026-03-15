import sqlite3
import os

db_path = "sicday.db"

if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
    exit()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    print("Adding 'sequence' column to students...")
    cursor.execute("ALTER TABLE students ADD COLUMN sequence INTEGER")
except sqlite3.OperationalError as e:
    print(f"Note: {e}")

conn.commit()
conn.close()
print("Migration Sequence completed.")
