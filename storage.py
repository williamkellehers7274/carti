from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_DATA_DIR = Path(__file__).resolve().parent / "data"
_BINDINGS_FILE = _DATA_DIR / "bindings.json"


def _ensure_files() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not _BINDINGS_FILE.exists():
        _BINDINGS_FILE.write_text("{}", encoding="utf-8")


def _read_json() -> dict[str, Any]:
    _ensure_files()
    try:
        return json.loads(_BINDINGS_FILE.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        # if file corrupted, reset to empty
        return {}


def _write_json(obj: dict[str, Any]) -> None:
    _ensure_files()
    tmp = _BINDINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_BINDINGS_FILE)


def set_destination_channel_id(*, guild_id: int, channel_id: int) -> None:
    data = _read_json()
    data[str(guild_id)] = int(channel_id)
    _write_json(data)


def get_destination_channel_id(*, guild_id: int) -> int | None:
    data = _read_json()
    raw = data.get(str(guild_id))
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def set_reports_channel_id(*, guild_id: int, channel_id: int) -> None:
    data = _read_json()
    data[f"{guild_id}:reports_channel_id"] = int(channel_id)
    _write_json(data)


def get_reports_channel_id(*, guild_id: int) -> int | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:reports_channel_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def set_logs_channel_id(*, guild_id: int, channel_id: int) -> None:
    data = _read_json()
    data[f"{guild_id}:logs_channel_id"] = int(channel_id)
    _write_json(data)


def get_logs_channel_id(*, guild_id: int) -> int | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:logs_channel_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def set_reports_panel_message_id(*, guild_id: int, channel_id: int, message_id: int) -> None:
    data = _read_json()
    data[f"{guild_id}:reports_panel"] = {"channel_id": int(channel_id), "message_id": int(message_id)}
    _write_json(data)


def get_reports_panel_message_id(*, guild_id: int) -> tuple[int, int] | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:reports_panel")
    if not isinstance(raw, dict):
        return None
    try:
        return int(raw["channel_id"]), int(raw["message_id"])
    except Exception:
        return None


def set_report_types(*, guild_id: int, types: list[dict[str, Any]]) -> None:
    data = _read_json()
    key = f"{guild_id}:report_types"
    clean: list[dict[str, Any]] = []
    for item in types:
        if not isinstance(item, dict):
            continue
        raw_key = str(item.get("key", "")).strip().lower()
        raw_key = "".join(ch for ch in raw_key if ch.isalnum() or ch == "_")[:32]
        label = str(item.get("label", "")).strip()[:100]
        desc = str(item.get("desc", "")).strip()[:100]
        try:
            reward = int(item.get("reward", 0))
        except (TypeError, ValueError):
            continue
        if not raw_key or not label or reward <= 0:
            continue
        clean.append({"key": raw_key, "label": label, "desc": desc, "reward": reward})
    data[key] = clean
    _write_json(data)


def get_report_types(*, guild_id: int) -> list[dict[str, Any]]:
    data = _read_json()
    raw = data.get(f"{guild_id}:report_types", [])
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", "")).strip().lower()
        key = "".join(ch for ch in key if ch.isalnum() or ch == "_")[:32]
        label = str(item.get("label", "")).strip()[:100]
        desc = str(item.get("desc", "")).strip()[:100]
        try:
            reward = int(item.get("reward", 0))
        except (TypeError, ValueError):
            continue
        if not key or not label or reward <= 0:
            continue
        out.append({"key": key, "label": label, "desc": desc, "reward": reward})
    return out


def next_ticket_id(*, guild_id: int) -> int:
    data = _read_json()
    key = f"{guild_id}:ticket_counter"
    current = data.get(key, 0)
    try:
        current_int = int(current)
    except (TypeError, ValueError):
        current_int = 0
    new_val = current_int + 1
    data[key] = new_val
    _write_json(data)
    return new_val


def set_panel_message_id(*, guild_id: int, channel_id: int, message_id: int) -> None:
    data = _read_json()
    data[f"{guild_id}:panel"] = {"channel_id": int(channel_id), "message_id": int(message_id)}
    _write_json(data)


def get_panel_message_id(*, guild_id: int) -> tuple[int, int] | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:panel")
    if not isinstance(raw, dict):
        return None
    try:
        return int(raw["channel_id"]), int(raw["message_id"])
    except Exception:
        return None


def set_ticket_view_role_ids(*, guild_id: int, role_ids: list[int]) -> None:
    data = _read_json()
    data[f"{guild_id}:ticket_view_roles"] = [int(x) for x in role_ids]
    _write_json(data)


def get_ticket_view_role_ids(*, guild_id: int) -> list[int]:
    data = _read_json()
    raw = data.get(f"{guild_id}:ticket_view_roles", [])
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for x in raw:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out


def set_call_category_id(*, guild_id: int, category_id: int | None) -> None:
    data = _read_json()
    key = f"{guild_id}:call_category_id"
    if category_id is None:
        data.pop(key, None)
    else:
        data[key] = int(category_id)
    _write_json(data)


def get_call_category_id(*, guild_id: int) -> int | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:call_category_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def set_voice_lobby_channel_id(*, guild_id: int, channel_id: int | None) -> None:
    data = _read_json()
    key = f"{guild_id}:voice_lobby_channel_id"
    if channel_id is None:
        data.pop(key, None)
    else:
        data[key] = int(channel_id)
    _write_json(data)


def get_voice_lobby_channel_id(*, guild_id: int) -> int | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:voice_lobby_channel_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def set_temp_voice_owner_id(*, guild_id: int, channel_id: int, owner_id: int) -> None:
    data = _read_json()
    key = f"{guild_id}:temp_voice_owners"
    raw = data.get(key, {})
    if not isinstance(raw, dict):
        raw = {}
    raw[str(int(channel_id))] = int(owner_id)
    data[key] = raw
    _write_json(data)


def get_temp_voice_owner_id(*, guild_id: int, channel_id: int) -> int | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:temp_voice_owners", {})
    if not isinstance(raw, dict):
        return None
    owner = raw.get(str(int(channel_id)))
    if owner is None:
        return None
    try:
        return int(owner)
    except (TypeError, ValueError):
        return None


def remove_temp_voice_owner_id(*, guild_id: int, channel_id: int) -> None:
    data = _read_json()
    key = f"{guild_id}:temp_voice_owners"
    raw = data.get(key, {})
    if not isinstance(raw, dict):
        return
    raw.pop(str(int(channel_id)), None)
    data[key] = raw
    _write_json(data)


def set_portfolio_category_id(*, guild_id: int, category_id: int | None) -> None:
    data = _read_json()
    key = f"{guild_id}:portfolio_category_id"
    if category_id is None:
        data.pop(key, None)
    else:
        data[key] = int(category_id)
    _write_json(data)


def get_portfolio_category_id(*, guild_id: int) -> int | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:portfolio_category_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def get_portfolio_profile(*, guild_id: int, user_id: int) -> dict[str, Any]:
    data = _read_json()
    raw = data.get(f"{guild_id}:portfolio_profiles", {})
    if not isinstance(raw, dict):
        return {}
    prof = raw.get(str(int(user_id)), {})
    return prof if isinstance(prof, dict) else {}


def set_portfolio_profile(*, guild_id: int, user_id: int, profile: dict[str, Any]) -> None:
    data = _read_json()
    key = f"{guild_id}:portfolio_profiles"
    raw = data.get(key, {})
    if not isinstance(raw, dict):
        raw = {}
    raw[str(int(user_id))] = profile
    data[key] = raw
    _write_json(data)


def set_tier_role_id(*, guild_id: int, tier: int, role_id: int | None) -> None:
    data = _read_json()
    key = f"{guild_id}:tier_roles"
    raw = data.get(key, {})
    if not isinstance(raw, dict):
        raw = {}
    tkey = str(int(tier))
    if role_id is None:
        raw.pop(tkey, None)
    else:
        raw[tkey] = int(role_id)
    data[key] = raw
    _write_json(data)


def get_tier_role_id(*, guild_id: int, tier: int) -> int | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:tier_roles", {})
    if not isinstance(raw, dict):
        return None
    rid = raw.get(str(int(tier)))
    if rid is None:
        return None
    try:
        return int(rid)
    except (TypeError, ValueError):
        return None


def set_rank_role_id(*, guild_id: int, rank: int, role_id: int | None) -> None:
    data = _read_json()
    key = f"{guild_id}:rank_roles"
    raw = data.get(key, {})
    if not isinstance(raw, dict):
        raw = {}
    rkey = str(int(rank))
    if role_id is None:
        raw.pop(rkey, None)
    else:
        raw[rkey] = int(role_id)
    data[key] = raw
    _write_json(data)


def get_rank_role_id(*, guild_id: int, rank: int) -> int | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:rank_roles", {})
    if not isinstance(raw, dict):
        return None
    rid = raw.get(str(int(rank)))
    if rid is None:
        return None
    try:
        return int(rid)
    except (TypeError, ValueError):
        return None


def set_portfolio_channel_owner_id(*, guild_id: int, channel_id: int, owner_id: int) -> None:
    data = _read_json()
    key = f"{guild_id}:portfolio_channel_owners"
    raw = data.get(key, {})
    if not isinstance(raw, dict):
        raw = {}
    raw[str(int(channel_id))] = int(owner_id)
    data[key] = raw
    _write_json(data)


def get_portfolio_channel_owner_id(*, guild_id: int, channel_id: int) -> int | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:portfolio_channel_owners", {})
    if not isinstance(raw, dict):
        return None
    owner = raw.get(str(int(channel_id)))
    if owner is None:
        return None
    try:
        return int(owner)
    except (TypeError, ValueError):
        return None


def set_accept_role_id(*, guild_id: int, role_id: int | None) -> None:
    data = _read_json()
    key = f"{guild_id}:accept_role_id"
    if role_id is None:
        data.pop(key, None)
    else:
        data[key] = int(role_id)
    _write_json(data)


def get_accept_role_id(*, guild_id: int) -> int | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:accept_role_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def set_afk(*, guild_id: int, user_id: int, until_ts: int, reason: str) -> None:
    data = _read_json()
    key = f"{guild_id}:afk"
    afk_obj = data.get(key, {})
    if not isinstance(afk_obj, dict):
        afk_obj = {}
    afk_obj[str(int(user_id))] = {"until_ts": int(until_ts), "reason": str(reason)}
    data[key] = afk_obj
    _write_json(data)


def clear_afk(*, guild_id: int, user_id: int) -> None:
    data = _read_json()
    key = f"{guild_id}:afk"
    afk_obj = data.get(key, {})
    if not isinstance(afk_obj, dict):
        return
    afk_obj.pop(str(int(user_id)), None)
    data[key] = afk_obj
    _write_json(data)


def get_afk_map(*, guild_id: int) -> dict[int, dict[str, Any]]:
    data = _read_json()
    raw = data.get(f"{guild_id}:afk", {})
    if not isinstance(raw, dict):
        return {}
    out: dict[int, dict[str, Any]] = {}
    for uid, payload in raw.items():
        try:
            uid_int = int(uid)
        except (TypeError, ValueError):
            continue
        if isinstance(payload, dict):
            out[uid_int] = payload
    return out


def set_afk_panel_message_id(*, guild_id: int, channel_id: int, message_id: int) -> None:
    data = _read_json()
    data[f"{guild_id}:afk_panel"] = {"channel_id": int(channel_id), "message_id": int(message_id)}
    _write_json(data)


def get_afk_panel_message_id(*, guild_id: int) -> tuple[int, int] | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:afk_panel")
    if not isinstance(raw, dict):
        return None
    try:
        return int(raw["channel_id"]), int(raw["message_id"])
    except Exception:
        return None


def set_vacation(
    *,
    guild_id: int,
    user_id: int,
    until_ts: int,
    reason: str,
    duration_text: str,
    removed_role_ids: list[int] | None = None,
) -> None:
    data = _read_json()
    key = f"{guild_id}:vacation"
    obj = data.get(key, {})
    if not isinstance(obj, dict):
        obj = {}
    obj[str(int(user_id))] = {
        "until_ts": int(until_ts),
        "reason": str(reason),
        "duration_text": str(duration_text),
        "removed_role_ids": [int(x) for x in (removed_role_ids or [])],
    }
    data[key] = obj
    _write_json(data)


def clear_vacation(*, guild_id: int, user_id: int) -> None:
    data = _read_json()
    key = f"{guild_id}:vacation"
    obj = data.get(key, {})
    if not isinstance(obj, dict):
        return
    obj.pop(str(int(user_id)), None)
    data[key] = obj
    _write_json(data)


def get_vacation_map(*, guild_id: int) -> dict[int, dict[str, Any]]:
    data = _read_json()
    raw = data.get(f"{guild_id}:vacation", {})
    if not isinstance(raw, dict):
        return {}
    out: dict[int, dict[str, Any]] = {}
    for uid, payload in raw.items():
        try:
            uid_int = int(uid)
        except (TypeError, ValueError):
            continue
        if isinstance(payload, dict):
            out[uid_int] = payload
    return out


def set_vacation_panel_message_id(*, guild_id: int, channel_id: int, message_id: int) -> None:
    data = _read_json()
    data[f"{guild_id}:vacation_panel"] = {"channel_id": int(channel_id), "message_id": int(message_id)}
    _write_json(data)


def get_vacation_panel_message_id(*, guild_id: int) -> tuple[int, int] | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:vacation_panel")
    if not isinstance(raw, dict):
        return None
    try:
        return int(raw["channel_id"]), int(raw["message_id"])
    except Exception:
        return None


def set_vacation_channel_id(*, guild_id: int, channel_id: int) -> None:
    data = _read_json()
    data[f"{guild_id}:vacation_channel_id"] = int(channel_id)
    _write_json(data)


def get_vacation_channel_id(*, guild_id: int) -> int | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:vacation_channel_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def set_vacation_role_id(*, guild_id: int, role_id: int | None) -> None:
    data = _read_json()
    key = f"{guild_id}:vacation_role_id"
    if role_id is None:
        data.pop(key, None)
    else:
        data[key] = int(role_id)
    _write_json(data)


def get_vacation_role_id(*, guild_id: int) -> int | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:vacation_role_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def set_vacation_remove_role_ids(*, guild_id: int, role_ids: list[int]) -> None:
    data = _read_json()
    data[f"{guild_id}:vacation_remove_role_ids"] = [int(x) for x in role_ids]
    _write_json(data)


def get_vacation_remove_role_ids(*, guild_id: int) -> list[int]:
    data = _read_json()
    raw = data.get(f"{guild_id}:vacation_remove_role_ids", [])
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for x in raw:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out


def get_points_map(*, guild_id: int) -> dict[int, float]:
    data = _read_json()
    raw = data.get(f"{guild_id}:points", {})
    if not isinstance(raw, dict):
        return {}
    out: dict[int, float] = {}
    for uid, balance in raw.items():
        try:
            uid_int = int(uid)
            bal = float(balance)
        except (TypeError, ValueError):
            continue
        out[uid_int] = max(0.0, bal)
    return out


def get_user_points(*, guild_id: int, user_id: int) -> float:
    return float(get_points_map(guild_id=guild_id).get(int(user_id), 0.0))


def set_user_points(*, guild_id: int, user_id: int, points: float) -> float:
    data = _read_json()
    key = f"{guild_id}:points"
    raw = data.get(key, {})
    if not isinstance(raw, dict):
        raw = {}
    safe_points = max(0.0, float(points))
    raw[str(int(user_id))] = safe_points
    data[key] = raw
    _write_json(data)
    return safe_points


def add_user_points(*, guild_id: int, user_id: int, delta: float) -> float:
    current = get_user_points(guild_id=guild_id, user_id=user_id)
    new_val = max(0.0, current + float(delta))
    return set_user_points(guild_id=guild_id, user_id=user_id, points=new_val)


def get_pending_reports(*, guild_id: int, user_id: int) -> list[dict[str, Any]]:
    data = _read_json()
    raw = data.get(f"{guild_id}:pending_reports", {})
    if not isinstance(raw, dict):
        return []
    user_raw = raw.get(str(int(user_id)), [])
    if not isinstance(user_raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in user_raw:
        if isinstance(item, dict):
            out.append(item)
    return out


def add_pending_report(
    *,
    guild_id: int,
    user_id: int,
    review_message_id: int,
    report_type: str,
    report_url: str,
    created_ts: int,
) -> None:
    data = _read_json()
    key = f"{guild_id}:pending_reports"
    obj = data.get(key, {})
    if not isinstance(obj, dict):
        obj = {}
    user_key = str(int(user_id))
    current = obj.get(user_key, [])
    if not isinstance(current, list):
        current = []
    current.append(
        {
            "review_message_id": int(review_message_id),
            "type": str(report_type),
            "url": str(report_url),
            "created_ts": int(created_ts),
        }
    )
    obj[user_key] = current
    data[key] = obj
    _write_json(data)


def remove_pending_report(*, guild_id: int, user_id: int, review_message_id: int) -> None:
    data = _read_json()
    key = f"{guild_id}:pending_reports"
    obj = data.get(key, {})
    if not isinstance(obj, dict):
        return
    user_key = str(int(user_id))
    current = obj.get(user_key, [])
    if not isinstance(current, list):
        return
    kept: list[dict[str, Any]] = []
    for item in current:
        if not isinstance(item, dict):
            continue
        try:
            mid = int(item.get("review_message_id"))
        except (TypeError, ValueError):
            continue
        if mid != int(review_message_id):
            kept.append(item)
    obj[user_key] = kept
    data[key] = obj
    _write_json(data)


def set_shop_orders_channel_id(*, guild_id: int, channel_id: int) -> None:
    data = _read_json()
    data[f"{guild_id}:shop_orders_channel_id"] = int(channel_id)
    _write_json(data)


def get_shop_orders_channel_id(*, guild_id: int) -> int | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:shop_orders_channel_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def set_shop_items(*, guild_id: int, items: list[dict[str, Any]]) -> None:
    data = _read_json()
    key = f"{guild_id}:shop_items"
    clean: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        try:
            price = int(item.get("price", 0))
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        clean.append({"name": name[:100], "price": price})
    data[key] = clean
    _write_json(data)


def get_shop_items(*, guild_id: int) -> list[dict[str, Any]]:
    data = _read_json()
    raw = data.get(f"{guild_id}:shop_items", [])
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        try:
            price = int(item.get("price", 0))
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        out.append({"name": name, "price": price})
    return out


def set_shop_panel_message_id(*, guild_id: int, channel_id: int, message_id: int) -> None:
    data = _read_json()
    data[f"{guild_id}:shop_panel"] = {"channel_id": int(channel_id), "message_id": int(message_id)}
    _write_json(data)


def get_shop_panel_message_id(*, guild_id: int) -> tuple[int, int] | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:shop_panel")
    if not isinstance(raw, dict):
        return None
    try:
        return int(raw["channel_id"]), int(raw["message_id"])
    except Exception:
        return None


def set_promo_channel_id(*, guild_id: int, channel_id: int) -> None:
    data = _read_json()
    data[f"{guild_id}:promo_channel_id"] = int(channel_id)
    _write_json(data)


def get_promo_channel_id(*, guild_id: int) -> int | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:promo_channel_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def set_stream_announce_channel_id(*, guild_id: int, channel_id: int) -> None:
    data = _read_json()
    data[f"{guild_id}:stream_announce_channel_id"] = int(channel_id)
    _write_json(data)


def get_stream_announce_channel_id(*, guild_id: int) -> int | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:stream_announce_channel_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def set_stream_announce_user_ids(*, guild_id: int, user_ids: list[int]) -> None:
    data = _read_json()
    data[f"{guild_id}:stream_announce_user_ids"] = [int(x) for x in user_ids]
    _write_json(data)


def get_stream_announce_user_ids(*, guild_id: int) -> list[int]:
    data = _read_json()
    raw = data.get(f"{guild_id}:stream_announce_user_ids", [])
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for x in raw:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out


def set_stream_announce_twitch_map(*, guild_id: int, mapping: dict[int, str]) -> None:
    data = _read_json()
    cleaned: dict[str, str] = {}
    for uid, login in mapping.items():
        try:
            user_id = int(uid)
        except (TypeError, ValueError):
            continue
        tw = str(login).strip().lower()
        if not tw:
            continue
        cleaned[str(user_id)] = tw[:50]
    data[f"{guild_id}:stream_announce_twitch_map"] = cleaned
    _write_json(data)


def get_stream_announce_twitch_map(*, guild_id: int) -> dict[int, str]:
    data = _read_json()
    raw = data.get(f"{guild_id}:stream_announce_twitch_map", {})
    if not isinstance(raw, dict):
        return {}
    out: dict[int, str] = {}
    for k, v in raw.items():
        try:
            uid = int(k)
        except (TypeError, ValueError):
            continue
        tw = str(v).strip().lower()
        if not tw:
            continue
        out[uid] = tw
    return out

def set_promo_panel_message_id(*, guild_id: int, channel_id: int, message_id: int) -> None:
    data = _read_json()
    data[f"{guild_id}:promo_panel"] = {"channel_id": int(channel_id), "message_id": int(message_id)}
    _write_json(data)


def get_promo_panel_message_id(*, guild_id: int) -> tuple[int, int] | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:promo_panel")
    if not isinstance(raw, dict):
        return None
    try:
        return int(raw["channel_id"]), int(raw["message_id"])
    except Exception:
        return None


def set_giveaway_state(*, guild_id: int, message_id: int, payload: dict[str, Any]) -> None:
    data = _read_json()
    key = f"{guild_id}:giveaways"
    raw = data.get(key, {})
    if not isinstance(raw, dict):
        raw = {}
    raw[str(int(message_id))] = payload
    data[key] = raw
    _write_json(data)


def get_giveaway_state(*, guild_id: int, message_id: int) -> dict[str, Any] | None:
    data = _read_json()
    raw = data.get(f"{guild_id}:giveaways", {})
    if not isinstance(raw, dict):
        return None
    payload = raw.get(str(int(message_id)))
    if not isinstance(payload, dict):
        return None
    return payload


def remove_giveaway_state(*, guild_id: int, message_id: int) -> None:
    data = _read_json()
    key = f"{guild_id}:giveaways"
    raw = data.get(key, {})
    if not isinstance(raw, dict):
        return
    raw.pop(str(int(message_id)), None)
    data[key] = raw
    _write_json(data)


def get_pending_shop_orders(*, guild_id: int, user_id: int) -> list[dict[str, Any]]:
    data = _read_json()
    raw = data.get(f"{guild_id}:pending_shop_orders", {})
    if not isinstance(raw, dict):
        return []
    user_raw = raw.get(str(int(user_id)), [])
    if not isinstance(user_raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in user_raw:
        if isinstance(item, dict):
            out.append(item)
    return out


def add_pending_shop_order(
    *,
    guild_id: int,
    user_id: int,
    review_message_id: int,
    item_name: str,
    price: float,
    created_ts: int,
    debited: bool = False,
) -> None:
    data = _read_json()
    key = f"{guild_id}:pending_shop_orders"
    obj = data.get(key, {})
    if not isinstance(obj, dict):
        obj = {}
    user_key = str(int(user_id))
    current = obj.get(user_key, [])
    if not isinstance(current, list):
        current = []
    current.append(
        {
            "review_message_id": int(review_message_id),
            "item": str(item_name),
            "price": float(price),
            "created_ts": int(created_ts),
            "debited": bool(debited),
        }
    )
    obj[user_key] = current
    data[key] = obj
    _write_json(data)


def remove_pending_shop_order(*, guild_id: int, user_id: int, review_message_id: int) -> None:
    data = _read_json()
    key = f"{guild_id}:pending_shop_orders"
    obj = data.get(key, {})
    if not isinstance(obj, dict):
        return
    user_key = str(int(user_id))
    current = obj.get(user_key, [])
    if not isinstance(current, list):
        return
    kept: list[dict[str, Any]] = []
    for item in current:
        if not isinstance(item, dict):
            continue
        try:
            mid = int(item.get("review_message_id"))
        except (TypeError, ValueError):
            continue
        if mid != int(review_message_id):
            kept.append(item)
    obj[user_key] = kept
    data[key] = obj
    _write_json(data)

