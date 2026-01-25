import sqlite3
import os

db_path = "sicday.db"

if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
    exit()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    print("Adding columns to activity_groups...")
    cursor.execute("ALTER TABLE activity_groups ADD COLUMN allowed_classrooms TEXT")
except sqlite3.OperationalError as e:
    print(f"Note: {e}")

try:
    cursor.execute("ALTER TABLE activity_groups ADD COLUMN is_visible BOOLEAN DEFAULT 1")
except sqlite3.OperationalError as e:
    print(f"Note: {e}")

try:
    print("Adding columns to activities...")
    cursor.execute("ALTER TABLE activities ADD COLUMN allowed_classrooms TEXT")
except sqlite3.OperationalError as e:
    print(f"Note: {e}")

try:
    cursor.execute("ALTER TABLE activities ADD COLUMN start_time DATETIME")
except sqlite3.OperationalError as e:
    print(f"Note: {e}")

try:
    cursor.execute("ALTER TABLE activities ADD COLUMN end_time DATETIME")
except sqlite3.OperationalError as e:
    print(f"Note: {e}")

try:
    cursor.execute("ALTER TABLE activities ADD COLUMN color TEXT DEFAULT '#e11d48'")
except sqlite3.OperationalError as e:
    print(f"Note: {e}")

conn.commit()
conn.close()
print("Migration completed.")
