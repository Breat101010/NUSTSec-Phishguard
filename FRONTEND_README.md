# NUSTSec PhishGuard — Frontend

## Files

| File | Purpose |
|------|---------|
| `index.html` | Admin dashboard + campaign builder |
| `trap-mukuru.html` | Fake Mukuru login lure page |
| `trap-zesa.html` | Fake ZESA token lure page |
| `lesson.html` | Security awareness lesson (the "gotcha" page) |

## How to Wire Up

### 1. CORS — add to `main.py`
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict to your domain in production
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Stats endpoint — add to `main.py`
```python
@app.get("/api/stats")
async def get_stats():
    conn = sqlite3.connect("phishguard.db")
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
```

### 3. Compromised endpoint — add to `main.py`
```python
@app.post("/compromised/{token}")
async def mark_compromised(token: str):
    conn = sqlite3.connect("phishguard.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE recipients SET status='compromised' WHERE token=?", (token,))
    conn.commit()
    conn.close()
    return {"status": "logged"}
```

### 4. Update redirect in `main.py`
Change the redirect URL in `/click/{token}` to point to your lure pages:
```python
# Detect which template to redirect to
cursor.execute("SELECT c.template_name FROM campaigns c JOIN recipients r ON r.campaign_id = c.id WHERE r.token=?", (token,))
row = cursor.fetchone()
template = row[0] if row else 'mukuru_verification'
page = 'trap-mukuru.html' if template == 'mukuru_verification' else 'trap-zesa.html'
return RedirectResponse(url=f"http://your-frontend-domain/{page}?token={token}")
```

### 5. Run
```bash
# Initialize DB
python database.py

# Start FastAPI
uvicorn main:app --reload --port 8000

# Serve frontend (any static server)
python -m http.server 3000
```

Then open: http://localhost:3000/index.html
