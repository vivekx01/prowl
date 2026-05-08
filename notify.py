import httpx
import config


async def notify_new_matches(user_id: int, matches: list[dict], db) -> None:
    """POST new job matches to Nexus notify endpoint if user has configured a chat ID."""
    if not config.NEXUS_NOTIFY_URL or not config.NEXUS_API_KEY:
        return

    from db.models import Setting
    row = db.query(Setting).filter_by(user_id=user_id, key="telegram_chat_id").first()
    if not row or not row.value.strip():
        return

    payload = {
        "event": "new_matches",
        "chat_id": row.value.strip(),
        "count": len(matches),
        "jobs": matches,
        "link": config.PROWL_URL,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            await client.post(
                config.NEXUS_NOTIFY_URL,
                json=payload,
                headers={"X-Api-Key": config.NEXUS_API_KEY},
            )
        except Exception as e:
            print(f"[notify] failed to send notification: {e}")
