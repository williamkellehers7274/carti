from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()


def _get_env_int(name: str, *, required: bool) -> int | None:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        if required:
            raise RuntimeError(f"Missing required env var: {name}")
        return None
    try:
        return int(raw)
    except ValueError as e:
        raise RuntimeError(f"Env var {name} must be int, got: {raw!r}") from e


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
if not DISCORD_TOKEN:
    raise RuntimeError("Missing required env var: DISCORD_TOKEN")

APPLICATION_CHANNEL_ID = _get_env_int("APPLICATION_CHANNEL_ID", required=False)
PANEL_CHANNEL_ID = _get_env_int("PANEL_CHANNEL_ID", required=False)
GUILD_ID = _get_env_int("GUILD_ID", required=False)
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "").strip()
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET", "").strip()

