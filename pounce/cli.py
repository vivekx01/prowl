import asyncio
import json
import sys

import click

from pounce import config


@click.group()
def cli():
    """Pounce — self-learning job application bot for The Prowl."""


@cli.command()
def commands():
    """Show all available commands and usage examples."""
    click.echo("""
POUNCE COMMANDS
===============

AUTH
  pounce login --server <url> --email <email>   Log in and save credentials
  pounce logout                                  Remove saved credentials
  pounce whoami                                  Show current logged-in user

QUEUE
  pounce jobs                                    List saved jobs ready to apply
  pounce jobs --all                              Include jobs below score threshold

LISTINGS (browse all scraped openings)
  pounce listings                                Show recent scraped jobs
  pounce listings --search "backend engineer"    Filter by title/company keyword
  pounce listings --company "Google"             Filter by company name
  pounce listings --min-score 0.7                Only show high-score listings
  pounce listings --limit 100                    Return up to 100 results

APPLY
  pounce apply --job-id <id>                     Apply by listing ID
  pounce apply --url <url>                       Apply to any URL directly
  pounce apply --all                             Apply to entire saved queue

  Flags:
    --dry-run      Fill form but do not submit
    --headed       Show browser window
    --supervised   Pause after each page for confirmation
    --automated    Never pause for user input (for scheduled runs)
    --min-score    Score threshold when using --all (default 0.5)

MEMORY
  pounce memory list                             Show stored Q&A answers
  pounce memory list --company <domain>          Filter by company domain
  pounce memory delete --id <id>                 Delete a memory entry

FLOWS
  pounce flows list                              Show learned portal flows
  pounce flows reset --domain <domain>           Force re-learn a company flow

SCHEDULE
  pounce schedule set --daily --at 09:00         Run every weekday at 9am
  pounce schedule set --cron "0 9 * * 1-5"       Set custom cron expression
  pounce schedule status                         Show current schedule + next run
  pounce schedule run-now                        Trigger immediate run

DAEMON
  pounce start                                   Start background scheduler daemon
  pounce stop                                    Stop daemon

TIP: Every command supports --help for full option details.
     e.g.  pounce apply --help
""")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--server", default=None, help="The Prowl server URL (e.g. https://theprowl.com)")
@click.option("--email", prompt="Email", help="Your Prowl account email")
@click.option("--password", default=None, hide_input=True, help="Password (prompted if omitted)")
def login(server, email, password):
    """Log in to The Prowl and save credentials locally."""
    from pounce.auth.manager import login as do_login

    server = server or config.API_BASE_URL
    try:
        data = do_login(server, email, password)
        click.echo(f"Logged in as {data['email']} (user_id={data['user_id']})")
        click.echo(f"Credentials saved to {config.CREDENTIALS_FILE}")
    except Exception as e:
        click.echo(f"Login failed: {e}", err=True)
        sys.exit(1)


@cli.command()
def logout():
    """Remove saved credentials."""
    from pounce.auth.manager import logout as do_logout
    do_logout()
    click.echo("Logged out.")


@cli.command()
def whoami():
    """Show the currently logged-in user."""
    from pounce.auth.manager import _load
    creds = _load()
    if not creds:
        click.echo("Not logged in.")
    else:
        click.echo(f"Email   : {creds.get('email', 'unknown')}")
        click.echo(f"User ID : {creds.get('user_id', 'unknown')}")
        click.echo(f"Server  : {creds.get('server_url', 'unknown')}")


# ---------------------------------------------------------------------------
# Jobs (queue viewer)
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--all", "show_all", is_flag=True, default=False,
              help="Show all saved jobs regardless of score")
def jobs(show_all):
    """List saved jobs in your application queue."""
    from pounce.sync.client import fetch_jobs
    min_score = 0.0 if show_all else 0.5
    records = fetch_jobs(min_score=min_score)
    if not records:
        msg = "No saved jobs" + ("." if show_all else " above score threshold. Try: pounce jobs --all")
        click.echo(msg)
        return
    click.echo(f"\n{'ID':>6}  {'SCORE':>5}  {'COMPANY':<22}  TITLE")
    click.echo("-" * 72)
    for j in records:
        score_str = f"{j.score:.2f}" if j.score is not None else "  —  "
        company = (j.company or "")[:22]
        title = (j.title or "")[:42]
        click.echo(f"{j.listing_id:>6}  {score_str:>5}  {company:<22}  {title}")
    click.echo(f"\nTotal: {len(records)} job(s)")
    click.echo("\nTo apply:  pounce apply --job-id <ID>")
    click.echo("Any URL :  pounce apply --url <apply-url>")


# ---------------------------------------------------------------------------
# Listings (browse scraped openings)
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--search", default=None, help="Search in title or company name")
@click.option("--company", default=None, help="Filter by company name (partial match)")
@click.option("--min-score", type=float, default=0.0, help="Minimum score (0 = show all)")
@click.option("--limit", type=int, default=50, help="Max results to return (default 50)")
def listings(search, company, min_score, limit):
    """Browse scraped job openings — filter and pick an ID to apply."""
    from pounce.sync.client import fetch_listings
    records = fetch_listings(search=search, company=company, min_score=min_score, limit=limit)
    if not records:
        click.echo("No listings found. Try broader filters.")
        return
    click.echo(f"\n{'ID':>6}  {'SCORE':>5}  {'S':>1}  {'COMPANY':<22}  {'TITLE':<38}  LOCATION")
    click.echo("-" * 90)
    for r in records:
        score_str = f"{r.score:.2f}" if r.score is not None else "  —  "
        saved_flag = "*" if r.saved else " "
        company_str = (r.company or "")[:22]
        title_str = (r.title or "")[:38]
        location_str = (r.location or "")[:20]
        click.echo(f"{r.listing_id:>6}  {score_str:>5}  {saved_flag}  {company_str:<22}  {title_str:<38}  {location_str}")
    click.echo(f"\nTotal: {len(records)} listing(s)   (* = already saved/applied)")
    click.echo("\nTo apply:  pounce apply --job-id <ID>")


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--job-id", type=int, default=None,
              help="Apply to a saved job by its listing ID (see: pounce jobs)")
@click.option("--url", "apply_url", default=None,
              help="Apply to any job URL directly — no need to be saved in The Prowl")
@click.option("--all", "apply_all", is_flag=True, default=False,
              help="Apply to all pending saved jobs above the score threshold")
@click.option("--dry-run", is_flag=True, default=False,
              help="Fill the form but do not click submit")
@click.option("--headed", is_flag=True, default=False,
              help="Show browser window")
@click.option("--interactive/--automated", default=True,
              help="Pause for user input when stuck (default: interactive)")
@click.option("--supervised", is_flag=True, default=False,
              help="Confirm before each page (good for first run on a new portal)")
@click.option("--min-score", type=float, default=0.5,
              help="Minimum score threshold when using --all")
def apply(job_id, apply_url, apply_all, dry_run, headed, interactive, supervised, min_score):
    """Apply to a job — by ID, by URL, or all pending."""
    if not job_id and not apply_url and not apply_all:
        click.echo("Provide --job-id <id>, --url <url>, or --all", err=True)
        click.echo("  See your queue:  pounce jobs")
        sys.exit(1)

    from pounce.core.runner import PounceRunner
    runner = PounceRunner(
        interactive=interactive,
        supervised=supervised,
        dry_run=dry_run,
        headless=not headed,
        min_score=min_score,
    )

    if apply_url:
        result = asyncio.run(runner.apply_url(apply_url))
        _print_result(result)
    elif apply_all:
        results = asyncio.run(runner.run_all_pending())
        for r in results:
            _print_result(r)
    else:
        result = asyncio.run(runner.apply_single(job_id))
        _print_result(result)


def _print_result(result) -> None:
    icon = {"applied": "✓", "dry_run_completed": "~", "failed": "✗"}.get(result.status, "?")
    click.echo(f"\n  [{icon}] {result.status.upper()}  "
               f"turns={result.agent_turns}  dry_run={result.dry_run}")
    if result.error_message:
        click.echo(f"      Error: {result.error_message}")
    for step in result.step_results:
        flag = "REPLAY" if step.replay else f"{step.agent_turns}t"
        ok = "OK" if step.success else "FAIL"
        click.echo(f"      [{ok}] {step.step_name} ({flag})")


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

@cli.group()
def memory():
    """Manage Pounce answer memory."""


@memory.command("list")
@click.option("--company", default=None, help="Filter by company domain")
def memory_list(company):
    """List stored Q&A answers."""
    from pounce.sync.client import fetch_memory
    records = fetch_memory()
    if company:
        records = [r for r in records if (r.company_domain or "").startswith(company)]
    if not records:
        click.echo("No memory entries found.")
        return
    for r in records:
        scope = r.company_domain or r.portal_key or "global"
        click.echo(f"  [{r.id}] ({scope}) {r.question_text!r} → {r.answer!r}"
                   f"  [conf={r.confidence:.1f}, used={r.use_count}]")


@memory.command("delete")
@click.option("--id", "entry_id", required=True, type=int, help="Memory entry ID")
def memory_delete(entry_id):
    """Delete a memory entry by ID."""
    # Requires a DELETE endpoint — placeholder for now
    click.echo(f"Delete entry {entry_id} — implement DELETE /api/pounce/memory/{{id}} on server.")


# ---------------------------------------------------------------------------
# Flows
# ---------------------------------------------------------------------------

@cli.group()
def flows():
    """Manage Pounce learned portal flows."""


@flows.command("list")
def flows_list():
    """List learned portal flows."""
    from pounce.sync.client import fetch_flows
    records = fetch_flows()
    if not records:
        click.echo("No learned flows.")
        return
    for f in records:
        click.echo(f"  {f.company_domain}  [{f.portal_key or 'unknown'}]"
                   f"  steps={len(f.steps)}  runs={f.success_count}"
                   f"  last={f.last_success}")


@flows.command("reset")
@click.option("--domain", required=True, help="Company domain to reset")
def flows_reset(domain):
    """Force Pounce to re-learn a company's flow (deletes stored steps)."""
    click.echo(f"Reset {domain} — implement DELETE /api/pounce/flows/{{domain}} on server.")


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

@cli.group()
def schedule():
    """Manage Pounce run schedule."""


@schedule.command("set")
@click.option("--cron", default=None, help='Cron expression (e.g. "0 9 * * 1-5")')
@click.option("--daily", is_flag=True, default=False, help="Run once per day")
@click.option("--at", default="09:00", help="Time for --daily (HH:MM, 24h)")
def schedule_set(cron, daily, at):
    """Set the Pounce run schedule."""
    if not cron and not daily:
        click.echo("Provide --cron or --daily --at HH:MM", err=True)
        sys.exit(1)

    if daily:
        hour, minute = at.split(":")
        cron = f"{minute} {hour} * * *"

    cfg = {}
    if config.CONFIG_FILE.exists():
        cfg = json.loads(config.CONFIG_FILE.read_text())
    cfg["cron"] = cron
    config.CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    click.echo(f"Schedule set: {cron}")
    click.echo("Run 'pounce start' to activate the daemon.")


@schedule.command("status")
def schedule_status():
    """Show current schedule and next run time."""
    if not config.CONFIG_FILE.exists():
        click.echo("No schedule configured. Run: pounce schedule set")
        return
    cfg = json.loads(config.CONFIG_FILE.read_text())
    cron = cfg.get("cron", "none")
    click.echo(f"Cron: {cron}")
    try:
        from apscheduler.triggers.cron import CronTrigger
        from config import IST
        from datetime import datetime
        trigger = CronTrigger.from_crontab(cron)
        next_run = trigger.get_next_fire_time(None, datetime.now(tz=IST))
        click.echo(f"Next run: {next_run}")
    except Exception:
        click.echo("(install apscheduler to show next run time)")


@schedule.command("run-now")
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--headed", is_flag=True, default=False)
def schedule_run_now(dry_run, headed):
    """Trigger an immediate run of all pending jobs."""
    from pounce.core.runner import PounceRunner
    runner = PounceRunner(dry_run=dry_run, headless=not headed)
    results = asyncio.run(runner.run_all_pending())
    for r in results:
        _print_result(r)


# ---------------------------------------------------------------------------
# Daemon
# ---------------------------------------------------------------------------

@cli.command()
def start():
    """Start the Pounce background daemon."""
    from pounce.scheduler.daemon import start_daemon
    start_daemon()


@cli.command()
def stop():
    """Stop the Pounce background daemon."""
    from pounce.scheduler.daemon import stop_daemon
    stop_daemon()


if __name__ == "__main__":
    cli()
