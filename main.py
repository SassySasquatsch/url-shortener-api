from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl
import sqlite3, string, random

app = FastAPI(title="URL Shortener")
DB = "urls.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                short_code TEXT PRIMARY KEY,
                original_url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                clicks INTEGER DEFAULT 0
            )
        """)

def generate_code(length=6):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))

class URLRequest(BaseModel):
    url: HttpUrl
    custom_code: str | None = None

class URLResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: str

@app.on_event("startup")
def startup():
    init_db()

@app.post("/shorten", response_model=URLResponse)
def shorten_url(request: URLRequest):
    code =request.custom_code if request.custom_code else generate_code()
    original = str(request.url)

    with get_db() as conn:
        # avoid collision
        if request.custom_code:
            if conn.execute("SELECT 1 FROM urls WHERE short_code=?", (code,)).fetchone():
                raise HTTPException(status_code=409, detail="Custom code already taken")
        else:
            while conn.execute("SELECT 1 FROM urls WHERE short_code=?", (code,)).fetchone():
                code = generate_code()
        conn.execute("INSERT INTO urls (short_code, original_url) VALUES (?, ?)", (code, original))

    return URLResponse(
        short_code=code,
        short_url=f"http://localhost:8000/{code}",
        original_url=original
    )

@app.get("/{short_code}")
def redirect(short_code: str):
    with get_db() as conn:
        row = conn.execute("SELECT original_url FROM urls WHERE short_code=?", (short_code,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Short URL not found")
        conn.execute("UPDATE urls SET clicks = clicks + 1 WHERE short_code=?", (short_code,))
        
    return RedirectResponse(url=row["original_url"], status_code=301)

@app.get("/stats/{short_code}")
def stats(short_code: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM urls WHERE short_code=?", (short_code,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        return dict(row)
