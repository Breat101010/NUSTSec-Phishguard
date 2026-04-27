import sqlite3

DB_NAME = "phishguard.db"

def init_db():
    # Connect to SQLite
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Create Campaigns Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        template_name TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 2. Create Recipients Table (The Targets)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS recipients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        campaign_id INTEGER,
        token TEXT UNIQUE NOT NULL,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY(campaign_id) REFERENCES campaigns(id)
    )
    ''')

    # 3. Create Tracking Events Table... The Trap Logs
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tracking_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT NOT NULL,
        event_type TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        ip_address TEXT,
        FOREIGN KEY(token) REFERENCES recipients(token)
    )
    ''')

    # Save changes and close the connection
    conn.commit()
    conn.close()
    print(f"[*] Success: Database '{DB_NAME}' initialized with NUSTSec core tables.")

if __name__ == "__main__":
    init_db()