import asyncio
import json
import os
import signal
import sys

from pounce import config

_PID_FILE = config.POUNCE_DIR / "daemon.pid"


def _load_cron() -> str | None:
    if not config.CONFIG_FILE.exists():
        return None
    cfg = json.loads(config.CONFIG_FILE.read_text())
    return cfg.get("cron")


def start_daemon() -> None:
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    except ImportError:
        print("APScheduler not installed. Run: pip install apscheduler sqlalchemy", file=sys.stderr)
        sys.exit(1)

    cron = _load_cron()
    if not cron:
        print("No schedule configured. Run: pounce schedule set --daily --at 09:00")
        sys.exit(1)

    # Write PID for stop command
    _PID_FILE.write_text(str(os.getpid()))

    jobstore = SQLAlchemyJobStore(url=f"sqlite:///{config.SCHEDULER_DB}")
    scheduler = BlockingScheduler(jobstores={"default": jobstore})

    def _run_job():
        from pounce.core.runner import PounceRunner
        runner = PounceRunner(interactive=False)  # automated in daemon mode
        asyncio.run(runner.run_all_pending())

    scheduler.add_job(
        _run_job,
        CronTrigger.from_crontab(cron),
        id="pounce_apply",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    def _handle_stop(signum, frame):
        scheduler.shutdown(wait=False)
        _PID_FILE.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    print(f"[POUNCE] Daemon started. Schedule: {cron}")
    print(f"[POUNCE] PID {os.getpid()} saved to {_PID_FILE}")
    print("[POUNCE] Press Ctrl+C to stop.")
    scheduler.start()


def stop_daemon() -> None:
    if not _PID_FILE.exists():
        print("No daemon running (PID file not found).")
        return
    pid = int(_PID_FILE.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        _PID_FILE.unlink(missing_ok=True)
        print(f"[POUNCE] Sent SIGTERM to daemon (PID {pid}).")
    except ProcessLookupError:
        print(f"[POUNCE] No process with PID {pid}. Cleaning up PID file.")
        _PID_FILE.unlink(missing_ok=True)
