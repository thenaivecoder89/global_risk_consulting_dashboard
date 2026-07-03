from view_1_global_landscape import view1_global_risk_landscape_scraper as scraper
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

# Initializing API application
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/health", status_code=200)
def get_health():
    return {"status": "ok", "message": "FastAPI service is running"}

@app.get("/debug_paths")
def debug_paths():
    base = Path("/app")

    return {
        "app_exists": base.exists(),
        "app_children": [str(p) for p in base.iterdir()] if base.exists() else [],
        "cwd": str(Path.cwd()),
    }

@app.get("/view_1_scraper", status_code=200)
def view_1_scraper():
    output = scraper.run_scraper(
        out="/tmp/view1"
    )
    return output