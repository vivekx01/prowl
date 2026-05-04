from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.database import init_db, SessionLocal
from runner import seed_companies_from_csv, seed_defaults
from api.routers import companies, jobs, applications, profile, scraper, runs, insights
from api.routers import auth, score, admin, listings, pounce


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seeded = seed_companies_from_csv(db)
        if seeded:
            print(f"[startup] Imported {seeded} companies from CSV")
        seed_defaults(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Job Scraper API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(companies.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(applications.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(scraper.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
app.include_router(insights.router, prefix="/api")
app.include_router(score.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(listings.router, prefix="/api")
app.include_router(pounce.router, prefix="/api")
