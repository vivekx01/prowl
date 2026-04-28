"""
Job Scraper — CLI entry point
Run: uv run python main.py
"""

import asyncio
import json

import questionary

from db.database import init_db, SessionLocal
from db.models import Company, ScrapeRun
from runner import run_scrape, seed_companies_from_csv, seed_defaults


def prompt_companies(db) -> list[int] | None:
    companies = db.query(Company).filter_by(active=True).all()
    if not companies:
        print("No active companies in DB.")
        return None

    action = questionary.select(
        "What do you want to do?",
        choices=["Scrape all companies", "Select companies"],
    ).ask()

    if action is None:
        return None

    if action == "Scrape all companies":
        return None

    selected_names = questionary.checkbox(
        "Select companies to scrape:",
        choices=[c.name for c in companies],
    ).ask()

    if not selected_names:
        return None

    name_set = set(selected_names)
    return [c.id for c in companies if c.name in name_set]


def main():
    init_db()

    db = SessionLocal()
    try:
        seeded = seed_companies_from_csv(db)
        if seeded:
            print(f"Imported {seeded} companies from CSV into DB")
        seed_defaults(db)

        company_ids = prompt_companies(db)
        if company_ids is not None and len(company_ids) == 0:
            print("Nothing selected, exiting.")
            return

        run = ScrapeRun(
            status="pending",
            company_ids=json.dumps(company_ids) if company_ids else None,
            completed_company_ids="[]",
        )
        db.add(run)
        db.commit()
        run_id = run.id
    finally:
        db.close()

    asyncio.run(run_scrape(run_id=run_id, company_ids=company_ids))


if __name__ == "__main__":
    main()
