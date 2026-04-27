import sqlite3
import uuid
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import List
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Import the NUSTSec Mail Cannon
from mailer import send_phishing_email

# Initialize the API
app = FastAPI(title="NUSTSec PhishGuard API", description="Backend Engine for Localized Threat Simulation")

# Initialize Rate Limiter (Tracks users by their IP address)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/")
async def root():
    return {
        "status": "online", 
        "service": "NUSTSec PhishGuard API", 
        "docs_url": "/docs"
    }

# --- Security Helper ---
def is_valid_uuid(val: str) -> bool:
    """Security Layer: Validate token format to prevent injection/malformed requests."""
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False

# 1. Data Model definition... Rules
class CampaignCreate(BaseModel):
    name: str
    template_name: str  # e.g., 'zesa_token_error', 'mukuru_verification'
    recipients: List[str]

# 2. Create Campaign Route... Engine
@app.post("/api/campaigns/create")
async def create_campaign(campaign: CampaignCreate):
    try:
        # Connect to our local database
        conn = sqlite3.connect("phishguard.db")
        cursor = conn.cursor()

        # Step A: Insert the Campaign details
        cursor.execute(
            "INSERT INTO campaigns (name, template_name) VALUES (?, ?)",
            (campaign.name, campaign.template_name)
        )
        # Grab the ID of the campaign we just created
        campaign_id = cursor.lastrowid

        # Step B: Generate secure UUIDs, save to DB, fire emails
        inserted_count = 0
        for email in campaign.recipients:
            # Generate a random, secure UUID for the tracking link
            target_uuid = str(uuid.uuid4())
            
            # Save the target securely in the database
            cursor.execute(
                "INSERT INTO recipients (email, campaign_id, token) VALUES (?, ?, ?)",
                (email, campaign_id, target_uuid)
            )
            inserted_count += 1
            
            # --- FIRE THE CANNON ---
            send_phishing_email(email, campaign.template_name, target_uuid)
            
            # --- RATE LIMIT BYPASS ---
            # Pause for 1.5 seconds so Mailtrap doesn't block us for spamming
            time.sleep(1.5)

        # Save the changes and close the connection
        conn.commit()
        conn.close()

        # Return a success message to frontend
        return {
            "status": "success", 
            "message": f"Campaign '{campaign.name}' initiated. Generated and dispatched {inserted_count} payloads."
        }
        
    except Exception as e:
        # If anything fails, tell the frontend exactly what went wrong
        raise HTTPException(status_code=500, detail=f"System error: {str(e)}")

# 3. The Infrastructure Tracking Route... The Trap
@app.get("/click/{token}")
async def track_click(token: str, request: Request):
    # 1. Security Check: Validate UUID
    if not is_valid_uuid(token):
        raise HTTPException(status_code=400, detail="Invalid token format.")

    # 2. Extract Client IP
    client_ip = request.client.host if request.client else "Unknown"

    try:
        conn = sqlite3.connect("phishguard.db")
        cursor = conn.cursor()

        # 3. Verify token exists in database to prevent rogue entries
        cursor.execute("SELECT id FROM recipients WHERE token = ?", (token,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Token not found.")

        # 4. Update target status to 'clicked' (only if currently pending to avoid overriding 'compromised')
        cursor.execute(
            "UPDATE recipients SET status = 'clicked' WHERE token = ? AND status = 'pending'",
            (token,)
        )

        # 5. Log the "click" event with IP
        cursor.execute(
            "INSERT INTO tracking_events (token, event_type, ip_address) VALUES (?, ?, ?)",
            (token, "click", client_ip)
        )

        conn.commit()
        conn.close()

        # 6. Safe Redirect
        # NOTE: Replace with the actual frontend phishing landing page URL
        return RedirectResponse(url="https://www.google.com")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tracking error: {str(e)}")

# 4. The Compromised Route... The Final Payload
@app.post("/compromised/{token}")
@limiter.limit("5/minute")  # <-- SECURITY: Max 5 requests per minute per IP
async def track_compromised(token: str, request: Request):
    # 1. Security Check: Validate UUID
    if not is_valid_uuid(token):
        raise HTTPException(status_code=400, detail="Invalid token format.")

    client_ip = request.client.host if request.client else "Unknown"

    try:
        conn = sqlite3.connect("phishguard.db")
        cursor = conn.cursor()

        # 2. Verify token exists
        cursor.execute("SELECT id FROM recipients WHERE token = ?", (token,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Token not found.")

        # 3. Update target status to 'compromised'
        cursor.execute(
            "UPDATE recipients SET status = 'compromised' WHERE token = ?",
            (token,)
        )

        # 4. Log the "compromised" event
        cursor.execute(
            "INSERT INTO tracking_events (token, event_type, ip_address) VALUES (?, ?, ?)",
            (token, "compromised", client_ip)
        )

        conn.commit()
        conn.close()

        return {"status": "success", "message": "Compromised event logged securely."}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tracking error: {str(e)}")