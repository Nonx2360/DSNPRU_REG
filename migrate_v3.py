import sqlite3
import os

db_path = "sicday.db"

if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
    exit()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    print("Adding 'type' column to activities...")
    cursor.execute("ALTER TABLE activities ADD COLUMN type TEXT DEFAULT 'individual'")
except sqlite3.OperationalError as e:
    print(f"Note: {e}")

try:
    print("Adding 'max_team_size' column to activities...")
    cursor.execute("ALTER TABLE activities ADD COLUMN max_team_size INTEGER DEFAULT 1")
except sqlite3.OperationalError as e:
    print(f"Note: {e}")

try:
    print("Adding 'team_name' column to registrations...")
    cursor.execute("ALTER TABLE registrations ADD COLUMN team_name TEXT")
except sqlite3.OperationalError as e:
    print(f"Note: {e}")

conn.commit()
conn.close()
print("Migration V3 completed.")
