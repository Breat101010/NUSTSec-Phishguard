import sqlite3
import uuid
import time
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

# Import the NUSTSec Mail Cannon
from mailer import send_phishing_email

app = FastAPI(title="NUSTSec PhishGuard API")

# --- 1. ENABLE CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class CampaignCreate(BaseModel):
    name: str
    template_name: str
    recipients: List[str]

# --- 2. STATS API (For the Dashboard) ---
@app.get("/api/stats")
async def get_stats():
    conn = sqlite3.connect("../phishguard.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM campaigns")
    total_campaigns = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM recipients")
    total_sent = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM recipients WHERE status IN ('clicked','compromised')")
    total_clicked = cursor.fetchone()[0]

    cursor.execute("""
        SELECT c.id, c.name, c.template_name, c.created_at,
               COUNT(r.id) as total_sent,
               SUM(CASE WHEN r.status IN ('clicked','compromised') THEN 1 ELSE 0 END) as total_clicked,
               SUM(CASE WHEN r.status = 'compromised' THEN 1 ELSE 0 END) as total_compromised
        FROM campaigns c LEFT JOIN recipients r ON r.campaign_id = c.id
        GROUP BY c.id ORDER BY c.created_at DESC LIMIT 20
    """)
    campaigns = [{"id":r[0],"name":r[1],"template_name":r[2],"created_at":r[3],
                  "total_sent":r[4],"total_clicked":r[5],"total_compromised":r[6]} for r in cursor.fetchall()]
    conn.close()
    return {"total_campaigns": total_campaigns, "total_sent": total_sent,
            "total_clicked": total_clicked, "campaigns": campaigns}

# --- 3. CREATE CAMPAIGN ---
@app.post("/api/campaigns/create")
async def create_campaign(campaign: CampaignCreate):
    try:
        conn = sqlite3.connect("../phishguard.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO campaigns (name, template_name) VALUES (?, ?)", (campaign.name, campaign.template_name))
        campaign_id = cursor.lastrowid

        for email in campaign.recipients:
            target_uuid = str(uuid.uuid4())
            cursor.execute("INSERT INTO recipients (email, campaign_id, token) VALUES (?, ?, ?)", (email, campaign_id, target_uuid))
            send_phishing_email(email, campaign.template_name, target_uuid)
            time.sleep(1.5)

        conn.commit()
        conn.close()
        return {"status": "success", "message": f"Dispatched {len(campaign.recipients)} payloads."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 4. TRACKING & REDIRECT ---
@app.get("/click/{token}")
async def track_click(token: str):
    try:
        # Use the base directory to find the DB in the root folder
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(BASE_DIR, "phishguard.db")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 1. Update the status to 'clicked'
        cursor.execute("UPDATE recipients SET status = 'clicked' WHERE token = ?", (token,))
        cursor.execute("INSERT INTO tracking_events (token) VALUES (?)", (token,))

        # 2. Find out which template was used to decide the redirect page
        cursor.execute("""
            SELECT c.template_name 
            FROM campaigns c 
            JOIN recipients r ON r.campaign_id = c.id 
            WHERE r.token = ?
        """, (token,))
        
        row = cursor.fetchone()
        template = row[0] if row else 'mukuru_verification'
        
        conn.commit()
        conn.close()

        # 3. Determine the redirect path
        page = 'trap-mukuru.html' if template == 'mukuru_verification' else 'trap-zesa.html'
        
        # NOTE: If your HTML files are NOT inside a 'frontend' folder, 
        # remove 'frontend/' from the line below.
        redirect_url = f"http://localhost:5500/frontend/{page}?token={token}"
        
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        print(f"Error in track_click: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
# --- 5. COMPROMISED ENDPOINT ---
@app.post("/compromised/{token}")
async def mark_compromised(token: str):
    conn = sqlite3.connect("../phishguard.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE recipients SET status='compromised' WHERE token=?", (token,))
    conn.commit()
    conn.close()
    return {"status": "logged"}
