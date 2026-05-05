from __future__ import annotations

from pathlib import Path
import asyncio
import datetime as dt
import json
import re
import random
import time
import urllib.parse
import urllib.request

import discord
from discord import app_commands

import config
from afk import AFKPanelView, _afk_image_file, build_afk_panel_embed, process_expired_afk_for_guild
from applications import PANEL_IMAGE_FILENAME, build_panel_embed
from promo import PromoPanelView, PromoReviewView, _promo_image_file, build_promo_panel_embed
from vacation import (
    VacationPanelView,
    _vacation_image_file,
    build_vacation_panel_embed,
    process_expired_vacation_for_guild,
)
from storage import (
    add_pending_report,
    add_user_points,
    get_afk_panel_message_id,
    get_destination_channel_id,
    get_call_category_id,
    get_temp_voice_owner_id,
    get_voice_lobby_channel_id,
    get_panel_message_id,
    get_pending_reports,
    get_points_map,
    get_logs_channel_id,
    get_report_types,
    get_reports_channel_id,
    get_reports_panel_message_id,
    get_giveaway_state,
    get_portfolio_category_id,
    get_portfolio_profile,
    get_rank_role_id,
    get_tier_role_id,
    get_portfolio_channel_owner_id,
    get_shop_orders_channel_id,
    get_shop_panel_message_id,
    get_shop_items,
    get_stream_announce_channel_id,
    get_stream_announce_twitch_map,
    get_stream_announce_user_ids,
    get_ticket_view_role_ids,
    get_user_points,
    get_promo_channel_id,
    get_promo_panel_message_id,
    add_pending_shop_order,
    get_pending_shop_orders,
    remove_pending_shop_order,
    get_vacation_remove_role_ids,
    get_vacation_role_id,
    get_vacation_panel_message_id,
    remove_pending_report,
    set_user_points,
    set_afk_panel_message_id,
    set_accept_role_id,
    set_destination_channel_id,
    set_call_category_id,
    set_temp_voice_owner_id,
    set_voice_lobby_channel_id,
    set_panel_message_id,
    set_logs_channel_id,
    set_report_types,
    set_reports_channel_id,
    set_reports_panel_message_id,
    set_giveaway_state,
    set_portfolio_category_id,
    set_portfolio_profile,
    set_rank_role_id,
    set_tier_role_id,
    set_portfolio_channel_owner_id,
    set_shop_orders_channel_id,
    set_shop_panel_message_id,
    set_shop_items,
    set_stream_announce_channel_id,
    set_stream_announce_twitch_map,
    set_stream_announce_user_ids,
    set_ticket_view_role_ids,
    set_promo_channel_id,
    set_promo_panel_message_id,
    set_vacation_channel_id,
    set_vacation_remove_role_ids,
    set_vacation_role_id,
    set_vacation_panel_message_id,
    remove_temp_voice_owner_id,
    remove_giveaway_state,
)
from ui import ApplicationPanelView

EMBED_COLOR = discord.Color.from_rgb(0, 0, 0)
# Единый цвет всех embed'ов (чёрная полоса слева).
discord.Color.dark_gray = classmethod(lambda cls: EMBED_COLOR)  # type: ignore[assignment]


_RU_LAT_MAP: dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def _slugify_event_key(name: str) -> str:
    s = (name or "").strip().lower()
    if not s:
        return ""
    out_chars: list[str] = []
    for ch in s:
        if "a" <= ch <= "z" or "0" <= ch <= "9" or ch == "_":
            out_chars.append(ch)
        elif ch in {" ", "-", ".", "/"}:
            out_chars.append("_")
        else:
            mapped = _RU_LAT_MAP.get(ch)
            if mapped is not None:
                out_chars.append(mapped)
            else:
                out_chars.append("_")
    key = "".join(out_chars)
    key = re.sub(r"_+", "_", key).strip("_")[:32]
    return key


def _normalize_twitch_login(raw: str) -> str:
    login = (raw or "").strip().lower()
    login = re.sub(r"^https?://(www\.)?twitch\.tv/", "", login)
    login = login.split("/")[0].strip().lower()
    login = "".join(ch for ch in login if ("a" <= ch <= "z") or ("0" <= ch <= "9") or ch == "_")
    if len(login) < 3:
        return ""
    return login[:25]


def _sync_http_json(*, url: str, method: str = "GET", headers: dict[str, str] | None = None, body: dict | None = None) -> dict:
    req_headers = {"User-Agent": "bot-carti/1.0"}
    if headers:
        req_headers.update(headers)
    data_bytes = None
    if body is not None:
        data_bytes = urllib.parse.urlencode(body).encode("utf-8")
    req = urllib.request.Request(url=url, method=method, headers=req_headers, data=data_bytes)
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw or "{}")


async def _events_key_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    if interaction.guild is None:
        return []
    cur = (current or "").strip().lower()
    m = _get_report_types_for_guild(interaction.guild.id)
    items: list[tuple[str, str, int]] = []
    for key, v in m.items():
        label = str(v.get("label", "Ивент"))
        reward = int(v.get("reward", 0) or 0)
        items.append((key, label, reward))
    items.sort(key=lambda x: (x[1].casefold(), x[0]))
    res: list[app_commands.Choice[str]] = []
    for key, label, reward in items:
        hay = f"{key} {label}".lower()
        if cur and cur not in hay:
            continue
        res.append(app_commands.Choice(name=f"{label} ({reward}) — {key}"[:100], value=key))
        if len(res) >= 25:
            break
    return res


class EventsManageEventSelect(discord.ui.Select):
    def __init__(self, *, guild_id: int):
        m = _get_report_types_for_guild(guild_id)
        items: list[tuple[str, str, int]] = []
        for key, v in m.items():
            items.append((str(key), str(v.get("label", "Ивент")), int(v.get("reward", 0) or 0)))
        items.sort(key=lambda x: (x[1].casefold(), x[0]))
        if items:
            options = [
                discord.SelectOption(
                    label=label[:100],
                    value=key[:100],
                    description=f"{reward} балл."[:100],
                )
                for key, label, reward in items[:25]
            ]
            disabled = False
        else:
            options = [discord.SelectOption(label="Список пуст", value="__none__", description="Сначала добавьте ивент")]
            disabled = True
        super().__init__(
            placeholder="Выберите ивент",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="events_manage_event_select",
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.message is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if isinstance(self.view, EventsManageView):
            self.view.selected_key = self.values[0]
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return
        try:
            await interaction.message.edit(view=self.view)
        except (discord.Forbidden, discord.HTTPException):
            pass
        await interaction.followup.send("Ивент выбран.", ephemeral=True)


class EventsManageActionSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Выберите действие",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="Добавить", value="add"),
                discord.SelectOption(label="Изменить", value="update"),
                discord.SelectOption(label="Удалить", value="remove"),
            ],
            custom_id="events_manage_action_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.message is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Только администрация может настраивать ивенты.", ephemeral=True)
            return
        if not isinstance(self.view, EventsManageView):
            await interaction.response.send_message("Не удалось прочитать состояние панели.", ephemeral=True)
            return

        action = self.values[0]
        if action == "add":
            await interaction.response.send_modal(EventsAddModal())
            return

        key = (self.view.selected_key or "").strip().lower()
        if not key:
            await interaction.response.send_message("Сначала выбери ивент в первом списке.", ephemeral=True)
            return

        current_map = _get_report_types_for_guild(interaction.guild.id)
        cur = current_map.get(key)
        if not cur:
            await interaction.response.send_message("Ивент не найден (возможно уже удалён).", ephemeral=True)
            return

        if action == "update":
            await interaction.response.send_modal(
                EventsEditModal(
                    event_key=key,
                    current_label=str(cur.get("label", "")),
                    current_desc=str(cur.get("desc", "")),
                    current_reward=int(cur.get("reward", 0) or 0),
                )
            )
            return

        if action == "remove":
            removed_label = str(cur.get("label", key))
            new_list: list[dict[str, str | int]] = [
                {"key": k, "label": str(v["label"]), "desc": str(v.get("desc", "")), "reward": int(v["reward"])}
                for k, v in current_map.items()
                if str(k) != key
            ]
            set_report_types(guild_id=interaction.guild.id, types=new_list)
            updated_panel = await _refresh_reports_panel_message(guild=interaction.guild)
            try:
                await interaction.message.edit(view=EventsManageView(guild_id=interaction.guild.id))
            except (discord.Forbidden, discord.HTTPException):
                pass
            await interaction.response.send_message(
                f"Готово. Ивент удалён: **{removed_label}** (`{key}`)"
                + (" Панель отчётов обновлена автоматически." if updated_panel else " Запусти `/панель-отчетов` один раз."),
                ephemeral=True,
            )
            return

        await interaction.response.send_message("Неизвестное действие.", ephemeral=True)


class EventsEditModal(discord.ui.Modal):
    def __init__(
        self,
        *,
        event_key: str,
        current_label: str,
        current_desc: str,
        current_reward: int,
    ):
        self.event_key = event_key
        self.current_reward = int(current_reward)
        super().__init__(title=f"Ивент • {current_label or event_key}"[:45])
        self.new_label = discord.ui.TextInput(
            label="Название (пусто = оставить)",
            placeholder=current_label[:100] or "Название",
            style=discord.TextStyle.short,
            required=False,
            max_length=100,
        )
        self.new_desc = discord.ui.TextInput(
            label="Описание (пусто = оставить)",
            placeholder=(current_desc[:100] or "Короткое описание")[:100],
            style=discord.TextStyle.short,
            required=False,
            max_length=100,
        )
        self.new_reward = discord.ui.TextInput(
            label="Баллы (пусто = оставить)",
            placeholder=str(int(current_reward)),
            style=discord.TextStyle.short,
            required=False,
            max_length=12,
        )
        self.add_item(self.new_label)
        self.add_item(self.new_desc)
        self.add_item(self.new_reward)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Только администрация может настраивать ивенты.", ephemeral=True)
            return

        current_map = _get_report_types_for_guild(interaction.guild.id)
        cur = current_map.get(self.event_key)
        if not cur:
            await interaction.response.send_message("Ивент не найден (возможно уже удалён).", ephemeral=True)
            return

        label = (self.new_label.value or "").strip() or str(cur.get("label", "Ивент"))
        desc = (self.new_desc.value or "").strip() or str(cur.get("desc", "")).strip()
        reward = int(cur.get("reward", 0) or 0)
        raw_reward = (self.new_reward.value or "").strip()
        if raw_reward:
            m = re.search(r"-?\d+", raw_reward)
            if not m:
                await interaction.response.send_message("В поле `Баллы` укажи число.", ephemeral=True)
                return
            reward = int(m.group(0))
        if reward <= 0:
            await interaction.response.send_message("Баллы должны быть > 0.", ephemeral=True)
            return
        if not desc:
            desc = f"{int(reward)} коин(а)"

        new_list: list[dict[str, str | int]] = []
        for k, v in current_map.items():
            if str(k) == self.event_key:
                new_list.append(
                    {"key": self.event_key, "label": label[:100], "desc": desc[:100], "reward": int(reward)}
                )
            else:
                new_list.append(
                    {"key": str(k), "label": str(v["label"]), "desc": str(v.get("desc", "")), "reward": int(v["reward"])}
                )
        set_report_types(guild_id=interaction.guild.id, types=new_list)
        updated_panel = await _refresh_reports_panel_message(guild=interaction.guild)
        await interaction.response.send_message(
            f"Готово. Ивент обновлён: **{label}** (`{self.event_key}`)"
            + (" Панель отчётов обновлена автоматически." if updated_panel else " Запусти `/панель-отчетов` один раз."),
            ephemeral=True,
        )


class EventsAddModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Добавить ивент")
        self.new_label = discord.ui.TextInput(
            label="Название",
            placeholder="Например: Рейд на босса",
            style=discord.TextStyle.short,
            required=True,
            max_length=100,
        )
        self.new_reward = discord.ui.TextInput(
            label="Баллы",
            placeholder="Например: 10",
            style=discord.TextStyle.short,
            required=True,
            max_length=12,
        )
        self.new_desc = discord.ui.TextInput(
            label="Описание (необязательно)",
            placeholder="Короткое описание в списке",
            style=discord.TextStyle.short,
            required=False,
            max_length=100,
        )
        self.add_item(self.new_label)
        self.add_item(self.new_reward)
        self.add_item(self.new_desc)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Только администрация может настраивать ивенты.", ephemeral=True)
            return

        label = (self.new_label.value or "").strip()
        if not label:
            await interaction.response.send_message("Укажи название ивента.", ephemeral=True)
            return

        m = re.search(r"-?\d+", (self.new_reward.value or "").strip())
        if not m:
            await interaction.response.send_message("В поле `Баллы` укажи число.", ephemeral=True)
            return
        reward = int(m.group(0))
        if reward <= 0:
            await interaction.response.send_message("Баллы должны быть > 0.", ephemeral=True)
            return

        current_map = _get_report_types_for_guild(interaction.guild.id)
        base_key = _slugify_event_key(label) or f"evt_{int(dt.datetime.now().timestamp())}"
        key = base_key
        n = 2
        while key in current_map and n < 99:
            suffix = f"_{n}"
            key = (base_key[: (32 - len(suffix))] + suffix)[:32]
            n += 1

        desc = (self.new_desc.value or "").strip() or f"{int(reward)} коин(а)"
        new_list: list[dict[str, str | int]] = [
            {"key": str(k), "label": str(v["label"]), "desc": str(v.get("desc", "")), "reward": int(v["reward"])}
            for k, v in current_map.items()
        ]
        new_list.append({"key": key, "label": label[:100], "desc": desc[:100], "reward": int(reward)})
        set_report_types(guild_id=interaction.guild.id, types=new_list)
        updated_panel = await _refresh_reports_panel_message(guild=interaction.guild)
        await interaction.response.send_message(
            f"Готово. Ивент добавлен: **{label[:100]}** (`{key}`)"
            + (" Панель отчётов обновлена автоматически." if updated_panel else " Запусти `/панель-отчетов` один раз."),
            ephemeral=True,
        )


class EventsManageView(discord.ui.View):
    def __init__(self, *, guild_id: int):
        super().__init__(timeout=900)
        self.selected_key: str | None = None
        self.add_item(EventsManageEventSelect(guild_id=guild_id))
        self.add_item(EventsManageActionSelect())


async def _shop_item_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    if interaction.guild is None:
        return []
    cur = (current or "").strip().lower()
    items = _get_shop_items_for_guild(interaction.guild.id)
    # name, price
    res: list[app_commands.Choice[str]] = []
    for name, price in items:
        hay = f"{name} {price}".lower()
        if cur and cur not in hay:
            continue
        res.append(app_commands.Choice(name=f"{name} — {price}"[:100], value=name))
        if len(res) >= 25:
            break
    return res


class Bot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.presences = True
        intents.message_content = True
        intents.voice_states = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self._twitch_access_token: str | None = None
        self._twitch_token_expire_ts: float = 0.0
        self._twitch_live_state_by_guild: dict[int, set[int]] = {}

    async def setup_hook(self) -> None:
        # Persistent view fallback for panels created with env-configured destination
        if config.APPLICATION_CHANNEL_ID:
            self.add_view(ApplicationPanelView(destination_channel_id=config.APPLICATION_CHANNEL_ID))
        self.add_view(AFKPanelView())
        self.add_view(VacationPanelView())
        self.add_view(VzpMapView())
        self.add_view(ShopPanelView())
        self.add_view(ShopOrderReviewView())
        self.add_view(ReportPanelView())
        self.add_view(ReportReviewView())
        self.add_view(PromoPanelView())
        self.add_view(PromoReviewView())
        self.add_view(PortfolioPanelView())
        self.add_view(GiveawayView())

        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

        self.loop.create_task(self._afk_expire_loop())
        self.loop.create_task(self._twitch_stream_watch_loop())

    async def _get_twitch_access_token(self, *, force_refresh: bool = False) -> str | None:
        if not config.TWITCH_CLIENT_ID or not config.TWITCH_CLIENT_SECRET:
            return None
        now = time.time()
        if not force_refresh and self._twitch_access_token and now < (self._twitch_token_expire_ts - 60):
            return self._twitch_access_token
        try:
            payload = await asyncio.to_thread(
                _sync_http_json,
                url="https://id.twitch.tv/oauth2/token",
                method="POST",
                body={
                    "client_id": config.TWITCH_CLIENT_ID,
                    "client_secret": config.TWITCH_CLIENT_SECRET,
                    "grant_type": "client_credentials",
                },
            )
            token = str(payload.get("access_token", "")).strip()
            expires = int(payload.get("expires_in", 0) or 0)
            if not token or expires <= 0:
                return None
            self._twitch_access_token = token
            self._twitch_token_expire_ts = now + float(expires)
            return token
        except Exception:
            return None

    async def _fetch_live_twitch_logins(self, logins: list[str]) -> set[str]:
        if not logins:
            return set()
        token = await self._get_twitch_access_token()
        if not token:
            return set()

        query = "&".join(f"user_login={urllib.parse.quote(login)}" for login in logins[:100])
        url = f"https://api.twitch.tv/helix/streams?{query}"
        headers = {
            "Client-Id": config.TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}",
        }
        for attempt in range(2):
            try:
                data = await asyncio.to_thread(_sync_http_json, url=url, headers=headers)
                out: set[str] = set()
                for item in data.get("data", []) or []:
                    login = str(item.get("user_login", "")).strip().lower()
                    if login:
                        out.add(login)
                return out
            except Exception:
                if attempt == 0:
                    fresh = await self._get_twitch_access_token(force_refresh=True)
                    if not fresh:
                        break
                    headers["Authorization"] = f"Bearer {fresh}"
                    continue
                break
        return set()

    async def _twitch_stream_watch_loop(self) -> None:
        await self.wait_until_ready()
        while not self.is_closed():
            if not config.TWITCH_CLIENT_ID or not config.TWITCH_CLIENT_SECRET:
                await asyncio.sleep(30)
                continue

            for guild in self.guilds:
                channel_id = get_stream_announce_channel_id(guild_id=guild.id)
                if channel_id is None:
                    self._twitch_live_state_by_guild[guild.id] = set()
                    continue

                allowed_ids = set(get_stream_announce_user_ids(guild_id=guild.id))
                twitch_map = get_stream_announce_twitch_map(guild_id=guild.id)
                tracked = [(uid, twitch_map.get(uid, "")) for uid in allowed_ids]
                tracked = [(uid, login) for uid, login in tracked if login]
                if not tracked:
                    self._twitch_live_state_by_guild[guild.id] = set()
                    continue

                live_logins = await self._fetch_live_twitch_logins([login for _, login in tracked])
                current_live_ids = {uid for uid, login in tracked if login in live_logins}
                prev_live_ids = self._twitch_live_state_by_guild.get(guild.id)
                if prev_live_ids is None:
                    self._twitch_live_state_by_guild[guild.id] = set(current_live_ids)
                    continue

                started_now = current_live_ids - prev_live_ids
                if started_now:
                    channel = guild.get_channel(channel_id)
                    if channel is None:
                        try:
                            channel = await guild.fetch_channel(channel_id)
                        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                            channel = None
                    if isinstance(channel, discord.TextChannel):
                        for uid in started_now:
                            login = twitch_map.get(uid, "")
                            if not login:
                                continue
                            text = f"@everyone 🔴 <@{uid}> запустил стрим! Заходи смотреть: https://twitch.tv/{login}"
                            try:
                                await channel.send(text, allowed_mentions=discord.AllowedMentions(everyone=True, users=True))
                            except (discord.Forbidden, discord.HTTPException):
                                pass
                self._twitch_live_state_by_guild[guild.id] = set(current_live_ids)
            await asyncio.sleep(45)

    async def _afk_expire_loop(self) -> None:
        await self.wait_until_ready()
        while not self.is_closed():
            for guild in self.guilds:
                try:
                    await process_expired_afk_for_guild(guild)
                except Exception:
                    pass
                try:
                    await process_expired_vacation_for_guild(guild)
                except Exception:
                    pass
            await asyncio.sleep(30)


bot = Bot()


def _extract_target(raw: str | None) -> int | None:
    if not raw:
        return None
    m = re.search(r"\d+", raw)
    if not m:
        return None
    try:
        return int(m.group(0))
    except ValueError:
        return None


def _format_member_list(guild: discord.Guild, ids: set[int]) -> str:
    if not ids:
        return "—"
    chunks: list[str] = []
    for uid in ids:
        member = guild.get_member(uid)
        chunks.append(member.mention if member is not None else f"<@{uid}>")
    return "\n".join(chunks[:25])


class SborView(discord.ui.View):
    def __init__(self, *, author_id: int, main_target: int | None, sub_target: int | None):
        super().__init__(timeout=None)
        self.author_id = author_id
        self.main_target = main_target
        self.sub_target = sub_target
        self.main_ids: set[int] = set()
        self.sub_ids: set[int] = set()
        self.published_channel_id: int | None = None
        self.published_message_id: int | None = None
        self.is_published: bool = False

    def _apply_to_embed(self, embed: discord.Embed, guild: discord.Guild) -> discord.Embed:
        main_title = f"Участники ({len(self.main_ids)}/{self.main_target})" if self.main_target else f"Участники ({len(self.main_ids)})"
        sub_title = f"Замены ({len(self.sub_ids)}/{self.sub_target})" if self.sub_target else f"Замены ({len(self.sub_ids)})"
        if len(embed.fields) >= 2:
            embed.set_field_at(0, name=main_title, value=_format_member_list(guild, self.main_ids), inline=False)
            embed.set_field_at(1, name=sub_title, value=_format_member_list(guild, self.sub_ids), inline=False)
        return embed

    async def _refresh_message(self, interaction: discord.Interaction) -> None:
        if interaction.message is None or interaction.guild is None:
            return
        embeds = interaction.message.embeds
        if not embeds:
            return
        e = self._apply_to_embed(embeds[0], interaction.guild)
        await interaction.message.edit(embed=e, view=self)
        await self._update_published_message(guild=interaction.guild, source_embed=e)

    async def _update_published_message(self, *, guild: discord.Guild, source_embed: discord.Embed) -> None:
        if not self.published_channel_id or not self.published_message_id:
            return
        ch = guild.get_channel(self.published_channel_id)
        if not isinstance(ch, discord.TextChannel):
            return
        try:
            msg = await ch.fetch_message(self.published_message_id)
            pub_embed = self.build_publish_embed(guild=guild, source_embed=source_embed)
            await msg.edit(embed=pub_embed)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    def _set_signup_buttons_disabled(self, disabled: bool) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id in {
                "sbor_join_main",
                "sbor_join_sub",
                "sbor_leave",
            }:
                child.disabled = disabled

    def _can_moderate(self, user: discord.abc.User) -> bool:
        if user.id == self.author_id:
            return True
        if isinstance(user, discord.Member):
            return user.guild_permissions.manage_messages or user.guild_permissions.administrator
        return False

    def _member_select_options(self, guild: discord.Guild) -> list[discord.SelectOption]:
        ids = list(self.main_ids | self.sub_ids)
        options: list[discord.SelectOption] = []
        for uid in ids[:25]:
            member = guild.get_member(uid)
            label = member.display_name if member is not None else str(uid)
            in_main = uid in self.main_ids
            role = "основа" if in_main else "замена"
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    value=str(uid),
                    description=f"Сейчас: {role}",
                )
            )
        return options

    def _moderate_member(self, user_id: int, action: str) -> str:
        if action == "main":
            self.sub_ids.discard(user_id)
            self.main_ids.add(user_id)
            return "Пользователь перемещён в основу."
        if action == "sub":
            self.main_ids.discard(user_id)
            self.sub_ids.add(user_id)
            return "Пользователь перемещён в замены."
        if action == "remove":
            removed = user_id in self.main_ids or user_id in self.sub_ids
            self.main_ids.discard(user_id)
            self.sub_ids.discard(user_id)
            return "Пользователь удалён из списка." if removed else "Пользователя не было в списке."
        return "Неизвестное действие."

    def build_publish_embed(self, *, guild: discord.Guild, source_embed: discord.Embed) -> discord.Embed:
        out = discord.Embed(
            title=f"{source_embed.title or 'Сбор'} — опубликованный список",
            description=source_embed.description or "—",
            color=discord.Color.dark_gray(),
            timestamp=dt.datetime.now(dt.timezone.utc),
        )
        out.add_field(
            name=f"Основа ({len(self.main_ids)})",
            value=_format_member_list(guild, self.main_ids),
            inline=False,
        )
        out.add_field(
            name=f"Замены ({len(self.sub_ids)})",
            value=_format_member_list(guild, self.sub_ids),
            inline=False,
        )
        out.set_footer(text="Опубликовано модератором")
        return out

    @discord.ui.button(label="В основу", style=discord.ButtonStyle.success, custom_id="sbor_join_main")
    async def join_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.is_published:
            await interaction.response.send_message("Список уже опубликован. Запись закрыта, доступна только модерация.", ephemeral=True)
            return
        uid = interaction.user.id
        self.sub_ids.discard(uid)
        self.main_ids.add(uid)
        await self._refresh_message(interaction)
        await interaction.response.send_message("Ты записан в основу.", ephemeral=True)

    @discord.ui.button(label="На замену", style=discord.ButtonStyle.secondary, custom_id="sbor_join_sub")
    async def join_sub(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.is_published:
            await interaction.response.send_message("Список уже опубликован. Запись закрыта, доступна только модерация.", ephemeral=True)
            return
        uid = interaction.user.id
        self.main_ids.discard(uid)
        self.sub_ids.add(uid)
        await self._refresh_message(interaction)
        await interaction.response.send_message("Ты записан на замену.", ephemeral=True)

    @discord.ui.button(label="Выйти", style=discord.ButtonStyle.danger, custom_id="sbor_leave")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.is_published:
            await interaction.response.send_message("Список уже опубликован. Запись закрыта, доступна только модерация.", ephemeral=True)
            return
        uid = interaction.user.id
        self.main_ids.discard(uid)
        self.sub_ids.discard(uid)
        await self._refresh_message(interaction)
        await interaction.response.send_message("Ты убран из списка.", ephemeral=True)

    @discord.ui.button(label="Модерация", style=discord.ButtonStyle.primary, custom_id="sbor_moderate")
    async def moderate(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None or interaction.channel is None or interaction.message is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not self._can_moderate(interaction.user):
            await interaction.response.send_message(
                "Только организатор сбора или администратор может модерировать список.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            "Панель модерации:",
            ephemeral=True,
            view=SborModerationPanelView(
                sbor_view=self,
                source_channel_id=interaction.channel.id,
                source_message_id=interaction.message.id,
                guild=interaction.guild,
            ),
        )


class SborMemberSelect(discord.ui.Select):
    def __init__(self, *, panel: "SborModerationPanelView", guild: discord.Guild):
        self.panel = panel
        options = panel.sbor_view._member_select_options(guild)
        if not options:
            options = [discord.SelectOption(label="Список пуст", value="none", description="Некого модерировать")]
        super().__init__(
            placeholder="Выбери участника",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="sbor_mod_member_select",
            disabled=(len(panel.sbor_view.main_ids | panel.sbor_view.sub_ids) == 0),
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self.panel.selected_user_id = None if self.values[0] == "none" else int(self.values[0])
        await interaction.response.send_message("Участник выбран.", ephemeral=True)


class SborActionSelect(discord.ui.Select):
    def __init__(self, *, panel: "SborModerationPanelView"):
        self.panel = panel
        super().__init__(
            placeholder="Выбери действие",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="Переместить в основу", value="main"),
                discord.SelectOption(label="Переместить в замены", value="sub"),
                discord.SelectOption(label="Удалить из списка", value="remove"),
                discord.SelectOption(label="Опубликовать список", value="publish"),
            ],
            custom_id="sbor_mod_action_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not self.panel.sbor_view._can_moderate(interaction.user):
            await interaction.response.send_message("У тебя нет прав на модерацию.", ephemeral=True)
            return

        action = self.values[0]
        if action == "publish":
            source_msg = await self.panel._fetch_source_message(interaction.guild)
            if source_msg is None:
                await interaction.response.send_message("Не удалось найти исходное сообщение сбора.", ephemeral=True)
                return
            source_embed = source_msg.embeds[0] if source_msg.embeds else discord.Embed(title="Сбор")
            pub_embed = self.panel.sbor_view.build_publish_embed(guild=interaction.guild, source_embed=source_embed)
            view_ref = self.panel.sbor_view
            if view_ref.published_channel_id and view_ref.published_message_id:
                ch = interaction.guild.get_channel(view_ref.published_channel_id)
                if isinstance(ch, discord.TextChannel):
                    try:
                        old_pub = await ch.fetch_message(view_ref.published_message_id)
                        await old_pub.edit(embed=pub_embed)
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        new_pub = await interaction.channel.send(embed=pub_embed)
                        view_ref.published_channel_id = new_pub.channel.id
                        view_ref.published_message_id = new_pub.id
                else:
                    new_pub = await interaction.channel.send(embed=pub_embed)
                    view_ref.published_channel_id = new_pub.channel.id
                    view_ref.published_message_id = new_pub.id
            else:
                new_pub = await interaction.channel.send(embed=pub_embed)
                view_ref.published_channel_id = new_pub.channel.id
                view_ref.published_message_id = new_pub.id

            view_ref.is_published = True
            view_ref._set_signup_buttons_disabled(True)
            await source_msg.edit(view=view_ref)
            await interaction.response.send_message("Список опубликован. Запись закрыта, доступна только модерация.", ephemeral=True)
            return

        if self.panel.selected_user_id is None:
            await interaction.response.send_message("Сначала выбери участника в первом выпадающем списке.", ephemeral=True)
            return

        result_text = self.panel.sbor_view._moderate_member(user_id=self.panel.selected_user_id, action=action)
        source_msg = await self.panel._fetch_source_message(interaction.guild)
        if source_msg is not None and source_msg.embeds:
            e = self.panel.sbor_view._apply_to_embed(source_msg.embeds[0], interaction.guild)
            await source_msg.edit(embed=e, view=self.panel.sbor_view)
            await self.panel.sbor_view._update_published_message(guild=interaction.guild, source_embed=e)
        await interaction.response.send_message(result_text, ephemeral=True)


class SborModerationPanelView(discord.ui.View):
    def __init__(self, *, sbor_view: SborView, source_channel_id: int, source_message_id: int, guild: discord.Guild):
        super().__init__(timeout=300)
        self.sbor_view = sbor_view
        self.source_channel_id = source_channel_id
        self.source_message_id = source_message_id
        self.selected_user_id: int | None = None
        self.add_item(SborMemberSelect(panel=self, guild=guild))
        self.add_item(SborActionSelect(panel=self))

    async def _fetch_source_message(self, guild: discord.Guild) -> discord.Message | None:
        source_channel = guild.get_channel(self.source_channel_id)
        if not isinstance(source_channel, discord.TextChannel):
            return None
        try:
            return await source_channel.fetch_message(self.source_message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

def _format_sbor_type(t: str, detail: str | None) -> str:
    base = {"vzp": "ВЗП", "biz": "Биз", "capt": "Капт", "content": "Контент"}.get(t, t)
    if t == "content" and detail:
        return f"{base}: {detail}"
    return base


def _parse_sbor_time(raw: str) -> tuple[dt.datetime, str] | None:
    text = raw.strip()
    if not text:
        return None

    # "15" => через 15 минут
    if re.fullmatch(r"\d{1,3}", text):
        mins = int(text)
        if mins <= 0 or mins > 24 * 60:
            return None
        when = dt.datetime.now() + dt.timedelta(minutes=mins)
        return when, f"через {mins} мин"

    # "19:00" or "19 00"
    m = re.fullmatch(r"(\d{1,2})[:\s](\d{2})", text)
    if not m:
        return None
    hh = int(m.group(1))
    mm = int(m.group(2))
    if hh > 23 or mm > 59:
        return None

    now = dt.datetime.now()
    when = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if when <= now:
        when = when + dt.timedelta(days=1)
    return when, when.strftime("%d.%m %H:%M")


VZP_MAP_FILE_MAP: dict[str, list[str]] = {
    "Байкерка": ["1.png"],
    "Большой миррор": ["2.png"],
    "Веспуччи": ["3.png"],
    "Ветряки": ["4.png"],
    "Киностудия": ["5.png"],
    "Лесопилка": ["6.png"],
    "Маленький миррор": ["7.png"],
    "Муравейник": ["8.png"],
    "Мусорка": ["9.png"],
    "Мясо": ["10.png"],
    "Нефть": ["11.png", "11_2.png"],
    "Палетка": ["12.png"],
    "Порт Биз": ["13.png"],
    "Сендик": ["14.png"],
    "Стройка": ["15.png"],
    "Татушка": ["16.png"],
}


def _vzp_photo_paths(map_name: str) -> list[Path]:
    base_dir = Path(__file__).resolve().parent / "foto_vzp"
    return [base_dir / fn for fn in VZP_MAP_FILE_MAP.get(map_name, [])]


def _build_vzp_embed() -> discord.Embed:
    maps_inline = " | ".join(VZP_MAP_FILE_MAP.keys())
    e = discord.Embed(
        title="Все карты VZP",
        description=f"> **{maps_inline}**\n\n> *Выбери карту:*",
        color=discord.Color.dark_gray(),
    )
    e.set_footer(text="VZP • Карты")
    return e


class VzpMapSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=name, value=name) for name in VZP_MAP_FILE_MAP.keys()]
        super().__init__(
            placeholder="Выбирай",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="vzp_map_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        # Быстро подтверждаем interaction, чтобы не ловить "Unknown interaction"
        # при чтении/загрузке файлов.
        try:
            await interaction.response.defer(ephemeral=True, thinking=False)
        except (discord.NotFound, discord.HTTPException):
            return

        map_name = self.values[0]
        paths = _vzp_photo_paths(map_name)
        missing = [str(p.name) for p in paths if not p.exists() or not p.is_file()]
        if missing:
            await interaction.followup.send(
                f"Не нашёл файлы для **{map_name}**: {', '.join(missing)}\nПроверь папку `foto_vzp`.",
                ephemeral=True,
            )
            return

        files = [discord.File(str(p), filename=p.name) for p in paths]
        await interaction.followup.send(
            content=map_name,
            files=files,
            ephemeral=True,
        )


class VzpMapView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(VzpMapSelect())


SHOP_PANEL_IMAGE_FILENAME = "magaz.png"
REPORT_PANEL_IMAGE_FILENAME = "otchet.png"
PORTFOLIO_PANEL_IMAGE_FILENAME = "archive.png"

DEFAULT_SHOP_ITEMS: list[tuple[str, int]] = [
    ("Снять ВАРН", 25),
    ("1.000 Majestic Coins", 100),
    ("100.000$", 100),
    ("1.000 Рублей", 200),
]

REPORT_TYPES: dict[str, dict[str, str | int]] = {
    "airdrop_screen": {"label": "Air Drop скрин", "desc": "Скрин — 1 коин", "reward": 1},
    "airdrop_otkat": {"label": "Air Drop откат", "desc": "Откат — 2 коина", "reward": 2},
    "ceha_screen": {"label": "Цеха/Дилеры скрин", "desc": "Скрин — 1 коин", "reward": 1},
    "ceha_otkat": {"label": "Цеха/Дилеры откат", "desc": "Откат — 2 коина", "reward": 2},
    "postavka_screen": {"label": "Поставка/Крафт скрин", "desc": "Скрин — 1 коин", "reward": 1},
}


MSK_TZ = dt.timezone(dt.timedelta(hours=3), name="MSK")


def _get_report_types_for_guild(guild_id: int) -> dict[str, dict[str, str | int]]:
    stored = get_report_types(guild_id=guild_id)
    if not stored:
        return dict(REPORT_TYPES)
    out: dict[str, dict[str, str | int]] = {}
    for item in stored:
        key = str(item.get("key", "")).strip().lower()
        label = str(item.get("label", "")).strip()
        desc = str(item.get("desc", "")).strip()
        try:
            reward = int(item.get("reward", 0))
        except (TypeError, ValueError):
            continue
        if key and label and reward > 0:
            out[key] = {"label": label, "desc": desc or f"{reward} коин(а)", "reward": reward}
    return out or dict(REPORT_TYPES)


class GiveawayState:
    def __init__(
        self,
        *,
        creator_id: int,
        creator_name: str,
        prize: str,
        channel_id: int,
        max_participants: int,
        winners_count: int,
        ends_at: dt.datetime,
    ):
        self.creator_id = int(creator_id)
        self.creator_name = str(creator_name)
        self.prize = str(prize)
        self.channel_id = int(channel_id)
        self.max_participants = int(max_participants)
        self.winners_count = int(winners_count)
        self.ends_at = ends_at
        self.participants: set[int] = set()
        self.finished = False
        self.winners: list[int] = []

    def to_payload(self) -> dict[str, object]:
        return {
            "creator_id": self.creator_id,
            "creator_name": self.creator_name,
            "prize": self.prize,
            "channel_id": self.channel_id,
            "max_participants": self.max_participants,
            "winners_count": self.winners_count,
            "ends_at_ts": int(self.ends_at.timestamp()),
            "participants": sorted(self.participants),
            "finished": self.finished,
            "winners": list(self.winners),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "GiveawayState | None":
        try:
            state = cls(
                creator_id=int(payload.get("creator_id", 0)),
                creator_name=str(payload.get("creator_name", "")),
                prize=str(payload.get("prize", "")),
                channel_id=int(payload.get("channel_id", 0)),
                max_participants=int(payload.get("max_participants", 0)),
                winners_count=int(payload.get("winners_count", 0)),
                ends_at=dt.datetime.fromtimestamp(int(payload.get("ends_at_ts", 0)), tz=MSK_TZ),
            )
        except (TypeError, ValueError, OSError):
            return None
        if state.creator_id <= 0 or state.channel_id <= 0:
            return None
        if not state.prize or state.max_participants <= 0 or state.winners_count <= 0:
            return None
        raw_participants = payload.get("participants", [])
        if isinstance(raw_participants, list):
            for uid in raw_participants:
                try:
                    state.participants.add(int(uid))
                except (TypeError, ValueError):
                    continue
        raw_winners = payload.get("winners", [])
        if isinstance(raw_winners, list):
            for uid in raw_winners:
                try:
                    state.winners.append(int(uid))
                except (TypeError, ValueError):
                    continue
        state.finished = bool(payload.get("finished", False))
        return state


GIVEAWAYS: dict[tuple[int, int], GiveawayState] = {}


def _giveaway_key(*, guild_id: int, message_id: int) -> tuple[int, int]:
    return int(guild_id), int(message_id)


def _persist_giveaway(*, guild_id: int, message_id: int, state: GiveawayState) -> None:
    set_giveaway_state(guild_id=guild_id, message_id=message_id, payload=state.to_payload())


def _load_giveaway(*, guild_id: int, message_id: int) -> GiveawayState | None:
    key = _giveaway_key(guild_id=guild_id, message_id=message_id)
    cached = GIVEAWAYS.get(key)
    if cached is not None:
        return cached
    payload = get_giveaway_state(guild_id=guild_id, message_id=message_id)
    if payload is None:
        return None
    state = GiveawayState.from_payload(payload)
    if state is None:
        remove_giveaway_state(guild_id=guild_id, message_id=message_id)
        return None
    GIVEAWAYS[key] = state
    return state


def _parse_msk_datetime(raw: str) -> dt.datetime | None:
    text = (raw or "").strip()
    try:
        parsed = dt.datetime.strptime(text, "%d.%m.%Y %H:%M")
    except ValueError:
        return None
    return parsed.replace(tzinfo=MSK_TZ)


def _format_remaining(ends_at: dt.datetime) -> str:
    now = dt.datetime.now(MSK_TZ)
    if now >= ends_at:
        return "завершён"
    delta = ends_at - now
    total_minutes = int(delta.total_seconds() // 60)
    days = total_minutes // (24 * 60)
    hours = (total_minutes % (24 * 60)) // 60
    minutes = total_minutes % 60
    parts: list[str] = []
    if days:
        parts.append(f"{days}д")
    if hours:
        parts.append(f"{hours}ч")
    if minutes or not parts:
        parts.append(f"{minutes}м")
    return "через " + " ".join(parts)


def _giveaway_participants_text(*, user_ids: set[int]) -> str:
    if not user_ids:
        return "—"
    lines: list[str] = [f"{idx}. <@{uid}>" for idx, uid in enumerate(sorted(user_ids), start=1)]
    joined = "\n".join(lines)
    if len(joined) <= 1024:
        return joined
    trimmed: list[str] = []
    for idx, uid in enumerate(sorted(user_ids), start=1):
        candidate = "\n".join(trimmed + [f"{idx}. <@{uid}>"])
        if len(candidate) > 980:
            break
        trimmed.append(f"{idx}. <@{uid}>")
    rest = len(user_ids) - len(trimmed)
    suffix = f"\n... и ещё {rest}" if rest > 0 else ""
    return "\n".join(trimmed) + suffix


def _build_giveaway_embed(*, state: GiveawayState) -> discord.Embed:
    participants_count = len(state.participants)
    end_text = f"{state.ends_at.strftime('%d.%m.%Y %H:%M')} МСК"
    status = "Завершён" if state.finished else "Открыт — жми **Участвовать**"
    e = discord.Embed(
        title="🎁 Розыгрыш",
        description=f"**На что розыгрыш**\n{state.prize}",
        color=discord.Color.dark_gray(),
        timestamp=dt.datetime.now(dt.timezone.utc),
    )
    e.add_field(name="Участники", value=f"{participants_count} / {state.max_participants}", inline=True)
    e.add_field(name="Победителей (слотов)", value=str(state.winners_count), inline=True)
    e.add_field(name="До какого (МСК в вводе)", value=f"{end_text}\n{_format_remaining(state.ends_at)}", inline=False)
    e.add_field(name="Список участников", value=_giveaway_participants_text(user_ids=state.participants), inline=False)
    e.add_field(name="Статус", value=status, inline=False)
    if state.winners:
        winners_text = "\n".join(f"{idx}. <@{uid}>" for idx, uid in enumerate(state.winners, start=1))
        e.add_field(name="Победители", value=winners_text, inline=False)
    e.set_footer(text=f"Организатор: {state.creator_name} • {state.creator_id}")
    return e


class GiveawayView(discord.ui.View):
    def __init__(self, *, disabled: bool = False):
        super().__init__(timeout=None)
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = disabled

    @discord.ui.button(label="Участвовать", style=discord.ButtonStyle.success, custom_id="giveaway_join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None or interaction.message is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return

        state = _load_giveaway(guild_id=interaction.guild.id, message_id=interaction.message.id)
        if state is None:
            await interaction.response.send_message("Данные розыгрыша не найдены. Создай новый розыгрыш.", ephemeral=True)
            return
        if state.finished:
            await interaction.response.send_message("Розыгрыш уже завершён.", ephemeral=True)
            return
        if dt.datetime.now(MSK_TZ) >= state.ends_at:
            await interaction.response.send_message("Время розыгрыша уже вышло.", ephemeral=True)
            return
        if interaction.user.id == state.creator_id:
            await interaction.response.send_message("Организатор не участвует в своём розыгрыше.", ephemeral=True)
            return
        if interaction.user.id in state.participants:
            await interaction.response.send_message("Ты уже участвуешь.", ephemeral=True)
            return
        if len(state.participants) >= state.max_participants:
            await interaction.response.send_message("Лимит участников уже достигнут.", ephemeral=True)
            return

        state.participants.add(interaction.user.id)
        _persist_giveaway(guild_id=interaction.guild.id, message_id=interaction.message.id, state=state)
        await interaction.message.edit(embed=_build_giveaway_embed(state=state), view=GiveawayView())
        await interaction.response.send_message("Ты добавлен в список участников.", ephemeral=True)

    @discord.ui.button(label="Разыграть", style=discord.ButtonStyle.danger, custom_id="giveaway_draw")
    async def draw(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None or interaction.message is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return

        state = _load_giveaway(guild_id=interaction.guild.id, message_id=interaction.message.id)
        if state is None:
            await interaction.response.send_message("Данные розыгрыша не найдены. Создай новый розыгрыш.", ephemeral=True)
            return
        if interaction.user.id != state.creator_id:
            await interaction.response.send_message("Разыграть может только создатель розыгрыша.", ephemeral=True)
            return
        if state.finished:
            await interaction.response.send_message("Этот розыгрыш уже завершён.", ephemeral=True)
            return

        eligible = [uid for uid in state.participants if uid != state.creator_id]
        if not eligible:
            await interaction.response.send_message("Нет участников для выбора победителей.", ephemeral=True)
            return

        winners_to_pick = min(state.winners_count, len(eligible))
        state.winners = random.sample(eligible, k=winners_to_pick)
        state.finished = True
        _persist_giveaway(guild_id=interaction.guild.id, message_id=interaction.message.id, state=state)

        await interaction.message.edit(embed=_build_giveaway_embed(state=state), view=GiveawayView(disabled=True))
        await interaction.response.send_message("Розыгрыш завершён. Победители выбраны.", ephemeral=True)


class GiveawayCreateModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Новый розыгрыш")
        self.prize = discord.ui.TextInput(
            label="1. На что розыгрыш",
            placeholder="Например: подписка Nitro",
            max_length=200,
            required=True,
        )
        self.max_participants = discord.ui.TextInput(
            label="2. Макс. участников (число)",
            placeholder="50",
            max_length=4,
            required=True,
        )
        self.winners_count = discord.ui.TextInput(
            label="3. Сколько победителей",
            placeholder="1",
            max_length=3,
            required=True,
        )
        self.until_msk = discord.ui.TextInput(
            label="4. До какого (МСК)",
            placeholder="05.04.2026 21:30",
            max_length=16,
            required=True,
        )
        self.add_item(self.prize)
        self.add_item(self.max_participants)
        self.add_item(self.winners_count)
        self.add_item(self.until_msk)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Команда доступна только в текстовом канале сервера.", ephemeral=True)
            return

        try:
            max_participants = int(str(self.max_participants.value).strip())
            winners_count = int(str(self.winners_count.value).strip())
        except ValueError:
            await interaction.response.send_message("Поля участников и победителей должны быть числами.", ephemeral=True)
            return

        if max_participants < 1 or max_participants > 500:
            await interaction.response.send_message("Макс. участников должен быть в диапазоне 1..500.", ephemeral=True)
            return
        if winners_count < 1:
            await interaction.response.send_message("Количество победителей должно быть не меньше 1.", ephemeral=True)
            return
        if winners_count > max_participants:
            await interaction.response.send_message("Победителей не может быть больше, чем макс. участников.", ephemeral=True)
            return

        ends_at = _parse_msk_datetime(str(self.until_msk.value))
        if ends_at is None:
            await interaction.response.send_message("Неверный формат даты. Используй `ДД.ММ.ГГГГ ЧЧ:ММ`.", ephemeral=True)
            return
        if ends_at <= dt.datetime.now(MSK_TZ):
            await interaction.response.send_message("Дата завершения должна быть в будущем.", ephemeral=True)
            return

        state = GiveawayState(
            creator_id=interaction.user.id,
            creator_name=interaction.user.display_name,
            prize=str(self.prize.value).strip(),
            channel_id=interaction.channel.id,
            max_participants=max_participants,
            winners_count=winners_count,
            ends_at=ends_at,
        )
        msg = await interaction.channel.send(embed=_build_giveaway_embed(state=state), view=GiveawayView())
        key = _giveaway_key(guild_id=interaction.guild.id, message_id=msg.id)
        GIVEAWAYS[key] = state
        _persist_giveaway(guild_id=interaction.guild.id, message_id=msg.id, state=state)
        await interaction.response.send_message(f"Розыгрыш создан: {msg.jump_url}", ephemeral=True)


def _shop_image_file() -> discord.File | None:
    p = Path(__file__).resolve().parent / "foto" / SHOP_PANEL_IMAGE_FILENAME
    if p.exists() and p.is_file():
        return discord.File(str(p), filename=SHOP_PANEL_IMAGE_FILENAME)
    return None


def _report_image_file() -> discord.File | None:
    p = Path(__file__).resolve().parent / "foto" / REPORT_PANEL_IMAGE_FILENAME
    if p.exists() and p.is_file():
        return discord.File(str(p), filename=REPORT_PANEL_IMAGE_FILENAME)
    return None


def _portfolio_image_file() -> discord.File | None:
    p = Path(__file__).resolve().parent / "foto" / PORTFOLIO_PANEL_IMAGE_FILENAME
    if p.exists() and p.is_file():
        return discord.File(str(p), filename=PORTFOLIO_PANEL_IMAGE_FILENAME)
    return None


def _build_shop_embed(*, with_image: bool = False) -> discord.Embed:
    # Как на нужном скрине магазина: один embed-блок, картинка внутри embed.
    items_lines = "\n\n".join(
        f"**{name} - {price}** <:coin:1369487243715264542>"
        for name, price in DEFAULT_SHOP_ITEMS
    )
    e = discord.Embed(
        description=(
            "— ・ **Магазин товаров**\n\n"
            "• Используйте выпадающий список ниже для выбора товара\n\n"
            "• **Доступные товары:**\n\n"
            f"{items_lines}"
        ),
        color=discord.Color.dark_gray(),
    )
    if with_image:
        e.set_image(url=f"attachment://{SHOP_PANEL_IMAGE_FILENAME}")
    e.set_footer(text="Баланс обновляется автоматически после мероприятий и активности")
    return e


def _get_shop_items_for_guild(guild_id: int) -> list[tuple[str, int]]:
    raw = get_shop_items(guild_id=guild_id)
    if raw:
        return [(str(x["name"]), int(x["price"])) for x in raw]
    return list(DEFAULT_SHOP_ITEMS)


def _build_shop_embed_for_guild(*, guild_id: int, with_image: bool = False) -> discord.Embed:
    items = _get_shop_items_for_guild(guild_id)
    items_lines = "\n\n".join(f"**{name} - {price}** <:coin:1369487243715264542>" for name, price in items)
    e = discord.Embed(
        description=(
            "— ・ **Магазин товаров**\n\n"
            "• Используйте выпадающий список ниже для выбора товара\n\n"
            "• **Доступные товары:**\n\n"
            f"{items_lines}"
        ),
        color=discord.Color.dark_gray(),
    )
    if with_image:
        e.set_image(url=f"attachment://{SHOP_PANEL_IMAGE_FILENAME}")
    e.set_footer(text="Баланс обновляется автоматически после мероприятий и активности")
    return e


async def _refresh_shop_panel_message(*, guild: discord.Guild) -> bool:
    existing = get_shop_panel_message_id(guild_id=guild.id)
    if not existing:
        return False

    channel_id, message_id = existing
    channel = guild.get_channel(channel_id)
    if channel is None:
        try:
            channel = await guild.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return False
    if not isinstance(channel, discord.TextChannel):
        return False

    try:
        panel_msg = await channel.fetch_message(message_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return False

    embed = _build_shop_embed_for_guild(guild_id=guild.id, with_image=False)
    try:
        await panel_msg.edit(embed=embed, view=ShopPanelView(guild_id=guild.id))
    except (discord.Forbidden, discord.HTTPException):
        return False
    return True


async def _refresh_reports_panel_message(*, guild: discord.Guild) -> bool:
    existing = get_reports_panel_message_id(guild_id=guild.id)
    if not existing:
        return False

    channel_id, message_id = existing
    channel = guild.get_channel(channel_id)
    if channel is None:
        try:
            channel = await guild.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return False
    if not isinstance(channel, discord.TextChannel):
        return False

    try:
        panel_msg = await channel.fetch_message(message_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return False

    embed = _build_report_embed(guild_id=guild.id, with_image=False)
    try:
        await panel_msg.edit(embed=embed, view=ReportPanelView(guild_id=guild.id))
    except (discord.Forbidden, discord.HTTPException):
        return False
    return True


def _build_report_embed(*, guild_id: int, with_image: bool = False) -> discord.Embed:
    # Один цельный embed-блок: картинка + текст (как единая "семья").
    e = discord.Embed(
        description=(
            "— ・ **Отчёт о проделанной работе**\n\n"
            "• Выберите тип отчёта из списка ниже. После выбора укажите ссылку на отчёт в модальном окне.\n\n"
            "• Отчёт будет считаться подлинным, если он был отправлен в течение **48 часов**\n\n"
            "• Ссылка должна вести только на 1 отчёт.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "• **Выберите тип отчёта**"
        ),
        color=discord.Color.dark_gray(),
    )
    if with_image:
        e.set_image(url=f"attachment://{REPORT_PANEL_IMAGE_FILENAME}")
    return e


def _build_portfolio_embed(*, with_image: bool = False) -> discord.Embed:
    e = discord.Embed(
        description=(
            "🗂️ **Создание портфеля**\n\n"
            "• В привязанном канале личным слотом оценят ваши откаты и решат — повысить вам ранг или порекомендовать "
            "дополнительную тренировку, указав на допущенные ошибки.\n\n"
            "• В вашем канале также идёт рассмотрение вашего Tier, решение принимают уполномоченные роли.\n\n"
            "• Видеоматериалы желательно заливать на видеохостинги YouTube, Rutube.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "**Создай личный канал → прикрепи откаты → High решит твой Ранг**"
        ),
        color=discord.Color.dark_gray(),
    )
    if with_image:
        e.set_image(url=f"attachment://{PORTFOLIO_PANEL_IMAGE_FILENAME}")
    return e


def _safe_text_channel_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^\w\-]+", "-", name, flags=re.UNICODE)
    name = re.sub(r"_{1,}", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-")
    return name[:70] or "user"


def _build_portfolio_channel_embed(*, member: discord.Member) -> discord.Embed:
    profile = get_portfolio_profile(guild_id=member.guild.id, user_id=member.id)
    try:
        rank_num = int(profile.get("rank") or 0)
    except (TypeError, ValueError):
        rank_num = 0
    try:
        tier_num = int(profile.get("tier") or 0)
    except (TypeError, ValueError):
        tier_num = 0

    rank_rid = get_rank_role_id(guild_id=member.guild.id, rank=rank_num) if rank_num else None
    tier_rid = get_tier_role_id(guild_id=member.guild.id, tier=tier_num) if tier_num else None

    rank_text = f"<@&{rank_rid}>" if rank_rid else "Нет ранга"
    tier_text = f"<@&{tier_rid}>" if tier_rid else "Нет тира"
    e = discord.Embed(
        description=(
            "## ▰▰ Личные текстовые каналы участника\n\n"
            f"Личный канал участника — {member.mention} | {member.id}\n\n"
            "—\n"
            "▸ Присылайте в текстовый канал видео откатов с МП(желательно геймплей\n"
            "от 10 минут со слышным лобби).\n"
            "▸ Изучайте записи, это важно для участия в мейн-составе на каптах.\n"
            "▸ Ссылка на карту залазов\n"
            "▸ Пожалуйста, прикрепляйте откаты с лучшей стрельбой и демонстрацией\n"
            "понимания игры.\n\n"
            "**Текущий Ранг:**\n"
            f"{rank_text}\n\n"
            "**Текущий Тир:**\n"
            f"{tier_text}"
        ),
        color=discord.Color.dark_gray(),
    )
    return e


class PortfolioChannelActionSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Взаимодействие с каналом",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="Удалить канал", value="delete"),
                discord.SelectOption(label="Повышение ранга", value="rank_up"),
                discord.SelectOption(label="Понижение ранга", value="rank_down"),
            ],
            custom_id="portfolio_channel_action_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Команда доступна только в текстовом канале.", ephemeral=True)
            return

        is_admin = interaction.user.guild_permissions.administrator
        allowed_role_ids = set(get_ticket_view_role_ids(guild_id=interaction.guild.id))
        has_role = any(r.id in allowed_role_ids for r in interaction.user.roles)
        if not (is_admin or has_role):
            await interaction.response.send_message("Нет прав.", ephemeral=True)
            return

        owner_id = get_portfolio_channel_owner_id(guild_id=interaction.guild.id, channel_id=interaction.channel.id)
        if not owner_id:
            await interaction.response.send_message("Это не личный архив-канал.", ephemeral=True)
            return

        owner = interaction.guild.get_member(owner_id)
        if owner is None:
            try:
                owner = await interaction.guild.fetch_member(owner_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                owner = None
        if owner is None:
            await interaction.response.send_message("Не смог найти владельца канала.", ephemeral=True)
            return

        action = self.values[0]
        if action == "delete":
            await interaction.response.send_message("Канал удалится через 3 секунды.", ephemeral=True)
            try:
                await asyncio.sleep(3)
                await interaction.channel.delete(reason="Удалено через меню архива")
            except Exception:
                pass
            return

        prof = get_portfolio_profile(guild_id=interaction.guild.id, user_id=owner.id)
        try:
            current_rank = int(prof.get("rank") or 0)
        except (TypeError, ValueError):
            current_rank = 0
        if current_rank <= 0:
            current_rank = 1

        if action == "rank_up":
            new_rank = min(2, current_rank + 1)
        elif action == "rank_down":
            new_rank = max(1, current_rank - 1)
        else:
            await interaction.response.send_message("Неизвестное действие.", ephemeral=True)
            return

        rid = get_rank_role_id(guild_id=interaction.guild.id, rank=new_rank)
        role_result: str | None = None
        if rid:
            role = interaction.guild.get_role(rid)
            if role is None:
                role_result = "роль ранга не найдена (удалена?)"
            else:
                bot_member = interaction.guild.me
                if bot_member is None:
                    role_result = "не смог определить права бота"
                else:
                    if not bot_member.guild_permissions.manage_roles:
                        role_result = "боту не хватает права **Manage Roles**"
                    elif role >= bot_member.top_role:
                        role_result = "роль выше/равна роли бота (подними роль бота выше)"
                    else:
                        to_remove: list[discord.Role] = []
                        for rnk in (1, 2):
                            rr = get_rank_role_id(guild_id=interaction.guild.id, rank=rnk)
                            if not rr or rr == rid:
                                continue
                            r_obj = interaction.guild.get_role(rr)
                            if r_obj and r_obj in owner.roles and r_obj < bot_member.top_role:
                                to_remove.append(r_obj)
                        try:
                            if to_remove:
                                await owner.remove_roles(*to_remove, reason="Смена ранга")
                            if role not in owner.roles:
                                await owner.add_roles(role, reason=f"Смена ранга на {new_rank}")
                            role_result = f"роль выдана: {role.mention}"
                        except discord.Forbidden:
                            role_result = "нет прав выдать/снять роль (иерархия/права)"
                        except discord.HTTPException:
                            role_result = "ошибка Discord при выдаче роли"

        prof["rank"] = int(new_rank)
        set_portfolio_profile(guild_id=interaction.guild.id, user_id=owner.id, profile=prof)

        if interaction.message is not None:
            try:
                await interaction.message.edit(embed=_build_portfolio_channel_embed(member=owner), view=PortfolioChannelView())
            except (discord.Forbidden, discord.HTTPException):
                pass

        extra = f"\nРоль: {role_result}" if role_result else ""
        await interaction.response.send_message(f"Ранг обновлён: **{new_rank}** для {owner.mention}.{extra}", ephemeral=True)


class PortfolioTierSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Выдача тира",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="Выдать Тир 1", value="tier_1"),
                discord.SelectOption(label="Выдать Тир 2", value="tier_2"),
                discord.SelectOption(label="Выдать Тир 3", value="tier_3"),
            ],
            custom_id="portfolio_channel_tier_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return

        is_admin = interaction.user.guild_permissions.administrator
        allowed_role_ids = set(get_ticket_view_role_ids(guild_id=interaction.guild.id))
        has_role = any(r.id in allowed_role_ids for r in interaction.user.roles)
        if not (is_admin or has_role):
            await interaction.response.send_message("Нет прав выдавать тир.", ephemeral=True)
            return

        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Команда доступна только в текстовом канале.", ephemeral=True)
            return

        owner_id = get_portfolio_channel_owner_id(guild_id=interaction.guild.id, channel_id=interaction.channel.id)
        if not owner_id:
            await interaction.response.send_message("Это не личный архив-канал (нет привязки владельца).", ephemeral=True)
            return

        owner = interaction.guild.get_member(owner_id)
        if owner is None:
            try:
                owner = await interaction.guild.fetch_member(owner_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                owner = None
        if owner is None:
            await interaction.response.send_message("Не смог найти владельца канала на сервере.", ephemeral=True)
            return

        tier_value = {"tier_1": "Тир 1", "tier_2": "Тир 2", "tier_3": "Тир 3"}.get(self.values[0])
        if tier_value is None:
            await interaction.response.send_message("Неизвестный тир.", ephemeral=True)
            return

        tier_num = {"tier_1": 1, "tier_2": 2, "tier_3": 3}.get(self.values[0], 0)
        rid = get_tier_role_id(guild_id=interaction.guild.id, tier=tier_num) if tier_num else None
        role_result: str | None = None

        # Выдача роли по привязке (если настроено)
        if rid:
            role = interaction.guild.get_role(rid)
            if role is None:
                role_result = "роль тира не найдена (удалена?)"
            else:
                bot_member = interaction.guild.me
                if bot_member is None:
                    role_result = "не смог определить права бота"
                else:
                    if not bot_member.guild_permissions.manage_roles:
                        role_result = "боту не хватает права **Manage Roles**"
                    elif role >= bot_member.top_role:
                        role_result = "роль выше/равна роли бота (подними роль бота выше)"
                    else:
                        # Снимаем роли других тиров (если они привязаны) и выдаём выбранную
                        to_remove: list[discord.Role] = []
                        for t in (1, 2, 3):
                            tr = get_tier_role_id(guild_id=interaction.guild.id, tier=t)
                            if not tr or tr == rid:
                                continue
                            r_obj = interaction.guild.get_role(tr)
                            if r_obj and r_obj in owner.roles and r_obj < bot_member.top_role:
                                to_remove.append(r_obj)
                        try:
                            if to_remove:
                                await owner.remove_roles(*to_remove, reason="Смена тира")
                            if role not in owner.roles:
                                await owner.add_roles(role, reason=f"Выдача {tier_value}")
                            role_result = f"роль выдана: {role.mention}"
                        except discord.Forbidden:
                            role_result = "нет прав выдать/снять роль (иерархия/права)"
                        except discord.HTTPException:
                            role_result = "ошибка Discord при выдаче роли"

        prof = get_portfolio_profile(guild_id=interaction.guild.id, user_id=owner.id)
        prof["tier"] = int(tier_num)
        set_portfolio_profile(guild_id=interaction.guild.id, user_id=owner.id, profile=prof)

        if interaction.message is not None:
            try:
                await interaction.message.edit(embed=_build_portfolio_channel_embed(member=owner), view=PortfolioChannelView())
            except (discord.Forbidden, discord.HTTPException):
                pass

        extra = f"\nРоль: {role_result}" if role_result else ""
        await interaction.response.send_message(f"Выдано: **{tier_value}** для {owner.mention}.{extra}", ephemeral=True)


@bot.tree.command(name="настройка-роль-тир", description="Привязать роли для Тир 1/2/3")
@app_commands.describe(
    действие="Что сделать (установить/очистить/показать)",
    тир="Какой тир (1/2/3)",
    роль="Роль (нужно только для 'установить')",
)
@app_commands.default_permissions(administrator=True)
@app_commands.choices(
    действие=[
        app_commands.Choice(name="установить", value="set"),
        app_commands.Choice(name="очистить", value="clear"),
        app_commands.Choice(name="показать", value="show"),
    ],
    тир=[
        app_commands.Choice(name="Тир 1", value="1"),
        app_commands.Choice(name="Тир 2", value="2"),
        app_commands.Choice(name="Тир 3", value="3"),
    ],
)
async def configure_tier_roles(
    interaction: discord.Interaction,
    действие: app_commands.Choice[str],
    тир: app_commands.Choice[str],
    роль: discord.Role | None = None,
):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return

    tier_num = int(тир.value)

    if действие.value == "show":
        rid = get_tier_role_id(guild_id=interaction.guild.id, tier=tier_num)
        pretty = f"<@&{rid}>" if rid else "—"
        await interaction.response.send_message(f"Роль для {тир.name}: {pretty}", ephemeral=True)
        return

    if действие.value == "clear":
        set_tier_role_id(guild_id=interaction.guild.id, tier=tier_num, role_id=None)
        await interaction.response.send_message(f"Готово. Роль для {тир.name} очищена.", ephemeral=True)
        return

    if действие.value == "set":
        if роль is None:
            await interaction.response.send_message("Выбери роль в параметре `роль`.", ephemeral=True)
            return
        set_tier_role_id(guild_id=interaction.guild.id, tier=tier_num, role_id=роль.id)
        await interaction.response.send_message(f"Готово. Для {тир.name} привязана роль {роль.mention}.", ephemeral=True)
        return

    await interaction.response.send_message("Неизвестное действие.", ephemeral=True)


@bot.tree.command(name="настройка-роль-ранг", description="Привязать роли для Ранг 1/2 (для повышения/понижения)")
@app_commands.describe(
    действие="Что сделать (установить/очистить/показать)",
    ранг="Какой ранг (1/2)",
    роль="Роль (нужно только для 'установить')",
)
@app_commands.default_permissions(administrator=True)
@app_commands.choices(
    действие=[
        app_commands.Choice(name="установить", value="set"),
        app_commands.Choice(name="очистить", value="clear"),
        app_commands.Choice(name="показать", value="show"),
    ],
    ранг=[
        app_commands.Choice(name="Ранг 1", value="1"),
        app_commands.Choice(name="Ранг 2", value="2"),
    ],
)
async def configure_rank_roles(
    interaction: discord.Interaction,
    действие: app_commands.Choice[str],
    ранг: app_commands.Choice[str],
    роль: discord.Role | None = None,
):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return

    rank_num = int(ранг.value)

    if действие.value == "show":
        rid = get_rank_role_id(guild_id=interaction.guild.id, rank=rank_num)
        pretty = f"<@&{rid}>" if rid else "—"
        await interaction.response.send_message(f"Роль для {ранг.name}: {pretty}", ephemeral=True)
        return

    if действие.value == "clear":
        set_rank_role_id(guild_id=interaction.guild.id, rank=rank_num, role_id=None)
        await interaction.response.send_message(f"Готово. Роль для {ранг.name} очищена.", ephemeral=True)
        return

    if действие.value == "set":
        if роль is None:
            await interaction.response.send_message("Выбери роль в параметре `роль`.", ephemeral=True)
            return
        set_rank_role_id(guild_id=interaction.guild.id, rank=rank_num, role_id=роль.id)
        await interaction.response.send_message(f"Готово. Для {ранг.name} привязана роль {роль.mention}.", ephemeral=True)
        return

    await interaction.response.send_message("Неизвестное действие.", ephemeral=True)


class PortfolioChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PortfolioChannelActionSelect())
        self.add_item(PortfolioTierSelect())


class PortfolioSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Выберите действие",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label="Повысить Ранг (создать личный канал)",
                    value="create_channel",
                )
            ],
            custom_id="portfolio_panel_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return

        # Создание канала/веток может занять >3s, поэтому сразу подтверждаем interaction.
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return

        guild = interaction.guild
        user = interaction.user

        category = None
        bound_category_id = get_portfolio_category_id(guild_id=guild.id)
        if bound_category_id:
            category = guild.get_channel(bound_category_id)
            if category is None:
                try:
                    category = await guild.fetch_channel(bound_category_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    category = None
        if not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send(
                "Категория для портфелей не настроена. Администрации нужно сделать `/привязка-категория-портфелей`.",
                ephemeral=True,
            )
            return

        base = _safe_text_channel_name(user.display_name)
        ch_name = f"archiv-{base}"[:100]

        # Права: архив видит только создатель + заданные роли + админы (Administrator обходит оверрайды).
        # Важно: глушим "протекание" прав из категории — если у роли есть доступ к категории,
        # но она не в списке разрешённых, то явно запрещаем ей view_channel в канале.
        allowed_roles: list[discord.Role] = []
        for rid in get_ticket_view_role_ids(guild_id=guild.id):
            role = guild.get_role(rid)
            if role is not None:
                allowed_roles.append(role)

        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),  # type: ignore[arg-type]
        }
        for role in allowed_roles:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, read_message_history=True)

        # Запретим всем ролям/юзерам из оверрайтов категории, кроме разрешённых.
        allowed_keys: set[int] = {guild.default_role.id, user.id}
        allowed_keys.update(r.id for r in allowed_roles)
        if guild.me is not None:
            allowed_keys.add(guild.me.id)
        for target in category.overwrites.keys():
            try:
                tid = target.id  # type: ignore[attr-defined]
            except Exception:
                continue
            if tid in allowed_keys:
                continue
            # Явно скрываем канал от ролей/пользователей, которые могли видеть категорию.
            overwrites[target] = discord.PermissionOverwrite(view_channel=False)

        try:
            ch = await guild.create_text_channel(
                name=ch_name,
                category=category,
                overwrites=overwrites,
                reason="Создание личного канала портфеля",
            )
        except discord.Forbidden:
            await interaction.followup.send("Нет прав создавать каналы.", ephemeral=True)
            return
        except discord.HTTPException:
            await interaction.followup.send("Не смог создать канал (ошибка Discord).", ephemeral=True)
            return

        # Сразу отправляем оформление канала (как на скрине) + создаём ветки.
        set_portfolio_channel_owner_id(guild_id=guild.id, channel_id=ch.id, owner_id=user.id)
        try:
            await ch.send(embed=_build_portfolio_channel_embed(member=user), view=PortfolioChannelView())
        except (discord.Forbidden, discord.HTTPException):
            pass

        # Ветки/треды (best-effort): если не получится — просто пропускаем.
        for thread_name in ("Рп мероприятия", "Капт/мкл", "Арена(гг)"):
            try:
                # auto_archive_duration: 1440 = 24h
                await ch.create_thread(name=thread_name, type=discord.ChannelType.public_thread, auto_archive_duration=1440)
            except Exception:
                pass

        await interaction.followup.send(f"Канал создан: {ch.mention}", ephemeral=True)

        # Сбрасываем выбор в селекте, чтобы пункт можно было выбирать многократно подряд.
        if interaction.message is not None:
            try:
                await interaction.message.edit(view=PortfolioPanelView())
            except (discord.Forbidden, discord.HTTPException):
                pass


class PortfolioPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PortfolioSelect())


def _build_report_sent_embed(*, with_image: bool = False) -> discord.Embed:
    e = discord.Embed(
        description=(
            "— ・ **Готово**\n\n"
            "Отчёт отправлен на проверку. Ожидайте оповещение о результате в ЛС от бота."
        ),
        color=discord.Color.dark_gray(),
    )
    if with_image:
        e.set_image(url=f"attachment://{REPORT_PANEL_IMAGE_FILENAME}")
    return e


def _build_report_verdict_embed(
    *,
    guild: discord.Guild,
    admin: discord.Member,
    approved: bool,
    reason: str | None = None,
    reward: int | None = None,
    balance: float | None = None,
) -> discord.Embed:
    if approved:
        desc = "Ваш отчёт был **одобрен**!\nПоздравляем!"
        if reward is not None:
            desc += f"\n\n**Начислено:** {reward} коин(а)"
        if balance is not None:
            desc += f"\n**Баланс:** {_fmt_points(balance)}"
    else:
        desc = "Ваш отчёт был **отклонён**."
        if reason:
            desc += f"\n\n**Причина:** {reason}"

    e = discord.Embed(
        title="— ・ Вердикт по отчёту",
        description=f"{desc}\n\n**Администратор:**\n{admin.mention} | {admin.display_name} | {admin.id}",
        color=discord.Color.dark_gray(),
        timestamp=dt.datetime.now(dt.timezone.utc),
    )
    if guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    e.set_footer(text=dt.datetime.now().strftime("%d.%m.%Y %H:%M"))
    return e


def _fmt_points(value: float) -> str:
    return f"{value:.2f}"


def _build_shop_order_sent_embed() -> discord.Embed:
    return discord.Embed(
        description="— ・ **Готово**\n\nЗаявка на покупку отправлена на проверку. Ожидайте результат в ЛС от бота.",
        color=discord.Color.dark_gray(),
    )


def _build_shop_order_verdict_embed(
    *,
    guild: discord.Guild,
    admin: discord.Member,
    approved: bool,
    item_name: str,
    price: int,
    reason: str | None = None,
    balance: float | None = None,
) -> discord.Embed:
    if approved:
        desc = f"Ваша покупка **{item_name}** была **одобрена**!"
        desc += f"\n\n**Списано:** {price} баллов"
        if balance is not None:
            desc += f"\n**Баланс:** {_fmt_points(balance)}"
    else:
        desc = f"Ваша покупка **{item_name}** была **отклонена**."
        if reason:
            desc += f"\n\n**Причина:** {reason}"

    e = discord.Embed(
        title="— ・ Вердикт по покупке",
        description=f"{desc}\n\n**Администратор:**\n{admin.mention} | {admin.display_name} | {admin.id}",
        color=discord.Color.dark_gray(),
        timestamp=dt.datetime.now(dt.timezone.utc),
    )
    if guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    e.set_footer(text=dt.datetime.now().strftime("%d.%m.%Y %H:%M"))
    return e


class ShopSelect(discord.ui.Select):
    def __init__(self, *, guild_id: int):
        self.guild_id = guild_id
        shop_items = _get_shop_items_for_guild(guild_id)
        options = [
            discord.SelectOption(label=f"{name} — {price}", value=name)
            for name, price in shop_items[:25]
        ]
        super().__init__(
            placeholder="Выберите товар для покупки",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="shop_panel_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return

        review_channel_id = get_shop_orders_channel_id(guild_id=interaction.guild.id)
        if not review_channel_id:
            await interaction.response.send_message(
                "Покупки через магазин не настроены. Администрации нужно сделать `/привязка-магазина`.",
                ephemeral=True,
            )
            if interaction.message is not None:
                try:
                    await interaction.message.edit(view=ShopPanelView(guild_id=interaction.guild.id))
                except (discord.Forbidden, discord.HTTPException):
                    pass
            return

        review_channel = interaction.guild.get_channel(review_channel_id)
        if review_channel is None:
            try:
                review_channel = await interaction.guild.fetch_channel(review_channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                review_channel = None
        if not isinstance(review_channel, discord.TextChannel):
            await interaction.response.send_message(
                "Не удалось найти канал проверки магазина. Обратитесь к администрации.",
                ephemeral=True,
            )
            return

        item_name = self.values[0]
        price_map = {name: price for name, price in _get_shop_items_for_guild(interaction.guild.id)}
        price = float(price_map.get(item_name, 0))
        if price <= 0:
            await interaction.response.send_message("Этот товар больше недоступен. Обновите панель магазина.", ephemeral=True)
            return
        balance = get_user_points(guild_id=interaction.guild.id, user_id=interaction.user.id)
        if balance < price:
            await interaction.response.send_message(
                f"Недостаточно баллов! Ваш баланс: {_fmt_points(balance)}/{int(price)}",
                ephemeral=True,
            )
            if interaction.message is not None:
                try:
                    await interaction.message.edit(view=ShopPanelView(guild_id=interaction.guild.id))
                except (discord.Forbidden, discord.HTTPException):
                    pass
            return

        # Списываем сразу при покупке (резерв). Если заявку отклонят — вернём.
        balance_after = add_user_points(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            delta=-float(price),
        )

        review_embed = discord.Embed(
            title="— ・ Заявка на покупку",
            description=(
                f"**Пользователь:** {interaction.user.mention}\n"
                f"**Товар:** {item_name}\n"
                f"**Цена:** {int(price)} баллов\n"
                f"**Баланс:** {_fmt_points(balance)} → {_fmt_points(balance_after)}"
            ),
            color=discord.Color.dark_gray(),
            timestamp=dt.datetime.now(dt.timezone.utc),
        )
        review_embed.add_field(name="Статус", value="**⏳ На проверке**", inline=False)
        review_embed.add_field(name="ID пользователя", value=str(interaction.user.id), inline=False)
        review_embed.add_field(name="Товар", value=item_name, inline=False)
        review_embed.add_field(name="Цена", value=str(int(price)), inline=False)
        review_embed.set_footer(text="shop_order")

        review_msg = await review_channel.send(embed=review_embed, view=ShopOrderReviewView())
        add_pending_shop_order(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            review_message_id=review_msg.id,
            item_name=item_name,
            price=float(price),
            created_ts=int(dt.datetime.now(dt.timezone.utc).timestamp()),
            debited=True,
        )

        await interaction.response.send_message(embed=_build_shop_order_sent_embed(), ephemeral=True)
        if interaction.message is not None:
            try:
                await interaction.message.edit(view=ShopPanelView(guild_id=interaction.guild.id))
            except (discord.Forbidden, discord.HTTPException):
                pass


class ShopPanelView(discord.ui.View):
    def __init__(self, *, guild_id: int | None = None):
        super().__init__(timeout=None)
        self.add_item(ShopSelect(guild_id=int(guild_id or 0)))


class ShopManageItemSelect(discord.ui.Select):
    def __init__(self, *, guild_id: int):
        items = _get_shop_items_for_guild(guild_id)
        if items:
            options = [
                discord.SelectOption(label=str(name)[:100], value=str(name)[:100], description=str(int(price))[:100])
                for name, price in items[:25]
            ]
            disabled = False
        else:
            options = [discord.SelectOption(label="Список пуст", value="__none__", description="Сначала добавьте товар")]
            disabled = True
        super().__init__(
            placeholder="Выберите товар",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="shop_manage_item_select",
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.message is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if isinstance(self.view, ShopManageView):
            self.view.selected_item = self.values[0]
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return
        try:
            await interaction.message.edit(view=self.view)
        except (discord.Forbidden, discord.HTTPException):
            pass
        await interaction.followup.send(f"Выбрано: **{self.values[0]}**", ephemeral=True)


class ShopManageActionSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Выберите действие",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="Добавить товар", value="add"),
                discord.SelectOption(label="Изменить цену", value="update_price"),
                discord.SelectOption(label="Удалить товар", value="remove"),
            ],
            custom_id="shop_manage_action_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.message is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Только администрация может настраивать магазин.", ephemeral=True)
            return
        if not isinstance(self.view, ShopManageView):
            await interaction.response.send_message("Не удалось прочитать состояние панели.", ephemeral=True)
            return
        action = self.values[0]
        if action == "add":
            await interaction.response.send_modal(ShopAddItemModal())
            return

        item = (self.view.selected_item or "").strip()
        if not item:
            await interaction.response.send_message("Сначала выбери товар в первом списке.", ephemeral=True)
            return

        if action == "update_price":
            await interaction.response.send_modal(ShopSetPriceModal(item_name=item))
            return
        if action == "remove":
            guild_id = interaction.guild.id
            current = _get_shop_items_for_guild(guild_id)
            updated = [(name, price) for name, price in current if name.casefold() != item.casefold()]
            if len(updated) == len(current):
                await interaction.response.send_message("Товар не найден (возможно уже удалён).", ephemeral=True)
                return
            set_shop_items(guild_id=guild_id, items=[{"name": name, "price": price} for name, price in updated])
            updated_panel = await _refresh_shop_panel_message(guild=interaction.guild)
            try:
                await interaction.message.edit(view=ShopManageView(guild_id=guild_id))
            except (discord.Forbidden, discord.HTTPException):
                pass
            await interaction.response.send_message(
                f"Готово. Товар удалён: **{item}**" + (" Панель обновлена автоматически." if updated_panel else ""),
                ephemeral=True,
            )
            return

        await interaction.response.send_message("Неизвестное действие.", ephemeral=True)


class ShopSetPriceModal(discord.ui.Modal):
    def __init__(self, *, item_name: str):
        self.item_name = item_name
        super().__init__(title=f"Цена товара • {item_name}"[:45])
        self.price = discord.ui.TextInput(
            label="Новая цена",
            placeholder="Например: 100",
            style=discord.TextStyle.short,
            required=True,
            max_length=12,
        )
        self.add_item(self.price)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Только администрация может настраивать магазин.", ephemeral=True)
            return
        m = re.search(r"-?\d+", str(self.price.value))
        if not m:
            await interaction.response.send_message("Укажи число в поле цены.", ephemeral=True)
            return
        new_price = int(m.group(0))
        if new_price <= 0:
            await interaction.response.send_message("Цена должна быть > 0.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        current = _get_shop_items_for_guild(guild_id)
        updated = list(current)
        found_idx: int | None = None
        for i, (name, _) in enumerate(updated):
            if name.casefold() == self.item_name.casefold():
                found_idx = i
                break
        if found_idx is None:
            await interaction.response.send_message("Товар не найден (возможно уже удалён).", ephemeral=True)
            return
        updated[found_idx] = (updated[found_idx][0], int(new_price))
        set_shop_items(guild_id=guild_id, items=[{"name": name, "price": price} for name, price in updated])
        updated_panel = await _refresh_shop_panel_message(guild=interaction.guild)
        await interaction.response.send_message(
            f"Готово. Цена обновлена: **{updated[found_idx][0]}** — **{int(new_price)}**"
            + (" Панель обновлена автоматически." if updated_panel else ""),
            ephemeral=True,
        )


class ShopAddItemModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Добавить товар")
        self.item_name = discord.ui.TextInput(
            label="Название товара",
            placeholder="Например: Nitro Basic",
            style=discord.TextStyle.short,
            required=True,
            max_length=100,
        )
        self.price = discord.ui.TextInput(
            label="Цена",
            placeholder="Например: 100",
            style=discord.TextStyle.short,
            required=True,
            max_length=12,
        )
        self.add_item(self.item_name)
        self.add_item(self.price)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Только администрация может настраивать магазин.", ephemeral=True)
            return

        item_name = str(self.item_name.value).strip()
        if not item_name:
            await interaction.response.send_message("Укажи название товара.", ephemeral=True)
            return

        m = re.search(r"-?\d+", str(self.price.value))
        if not m:
            await interaction.response.send_message("Укажи число в поле цены.", ephemeral=True)
            return
        new_price = int(m.group(0))
        if new_price <= 0:
            await interaction.response.send_message("Цена должна быть > 0.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        current = _get_shop_items_for_guild(guild_id)
        if any(name.casefold() == item_name.casefold() for name, _ in current):
            await interaction.response.send_message("Такой товар уже есть. Используй действие `Изменить цену`.", ephemeral=True)
            return

        updated = list(current)
        updated.append((item_name[:100], int(new_price)))
        set_shop_items(guild_id=guild_id, items=[{"name": name, "price": price} for name, price in updated])
        updated_panel = await _refresh_shop_panel_message(guild=interaction.guild)
        await interaction.response.send_message(
            f"Готово. Товар добавлен: **{item_name[:100]}** — **{int(new_price)}**"
            + (" Панель обновлена автоматически." if updated_panel else ""),
            ephemeral=True,
        )


class ShopManageView(discord.ui.View):
    def __init__(self, *, guild_id: int):
        super().__init__(timeout=900)
        self.selected_item: str | None = None
        self.add_item(ShopManageItemSelect(guild_id=guild_id))
        self.add_item(ShopManageActionSelect())


class ShopRejectReasonModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Причина отказа")
        self.reason = discord.ui.TextInput(
            label="Укажите причину отказа",
            placeholder="Например: недостаточно баллов / нет в наличии / ошибка заявки",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=600,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.message is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Только администрация может отклонять покупки.", ephemeral=True)
            return
        if not interaction.message.embeds:
            await interaction.response.send_message("Не удалось прочитать данные заявки.", ephemeral=True)
            return

        e = interaction.message.embeds[0]
        user_id: int | None = None
        item_name: str = "Товар"
        price: int = 0
        for fld in e.fields:
            if fld.name == "ID пользователя":
                try:
                    user_id = int(fld.value.strip())
                except ValueError:
                    user_id = None
            if fld.name == "Товар":
                item_name = fld.value.strip() or item_name
            if fld.name == "Цена":
                m = re.search(r"\d+", fld.value)
                price = int(m.group(0)) if m else price

        if e.fields:
            e.set_field_at(0, name="Статус", value=f"**❌ Отказано**\nПричина: {self.reason.value}", inline=False)
        else:
            e.add_field(name="Статус", value=f"**❌ Отказано**\nПричина: {self.reason.value}", inline=False)
        e.color = EMBED_COLOR
        await interaction.message.edit(embed=e, view=None)

        if user_id is not None:
            # Возврат средств при отказе (только если покупка списывалась сразу).
            should_refund = False
            refunded_balance: float | None = None
            try:
                pending = get_pending_shop_orders(guild_id=interaction.guild.id, user_id=user_id)
                for p in pending:
                    if int(p.get("review_message_id", 0)) == int(interaction.message.id):
                        should_refund = bool(p.get("debited", False))
                        break
            except Exception:
                should_refund = False

            if should_refund and price > 0:
                refunded_balance = add_user_points(
                    guild_id=interaction.guild.id,
                    user_id=user_id,
                    delta=float(price),
                )

            remove_pending_shop_order(
                guild_id=interaction.guild.id,
                user_id=user_id,
                review_message_id=interaction.message.id,
            )
            user = interaction.guild.get_member(user_id)
            if user is None:
                try:
                    user = await interaction.guild.fetch_member(user_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    user = None
            if user is not None:
                try:
                    await user.send(
                        embed=_build_shop_order_verdict_embed(
                            guild=interaction.guild,
                            admin=interaction.user,
                            approved=False,
                            item_name=item_name,
                            price=price,
                            reason=self.reason.value,
                            balance=refunded_balance,
                        )
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass

        await interaction.response.send_message("Покупка отклонена.", ephemeral=True)


class ShopOrderReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Принять", style=discord.ButtonStyle.success, custom_id="shop_review_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None or interaction.message is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Только администрация может принимать покупки.", ephemeral=True)
            return
        if not interaction.message.embeds:
            await interaction.response.send_message("Не удалось прочитать данные заявки.", ephemeral=True)
            return

        e = interaction.message.embeds[0]
        user_id: int | None = None
        item_name: str = "Товар"
        price: int = 0
        for fld in e.fields:
            if fld.name == "ID пользователя":
                try:
                    user_id = int(fld.value.strip())
                except ValueError:
                    user_id = None
            if fld.name == "Товар":
                item_name = fld.value.strip() or item_name
            if fld.name == "Цена":
                m = re.search(r"\d+", fld.value)
                price = int(m.group(0)) if m else price

        if user_id is None or price <= 0:
            await interaction.response.send_message("Не смог прочитать ID пользователя или цену.", ephemeral=True)
            return

        # Принимаем без доп. списания: списание было в момент покупки (резерв).
        new_balance = get_user_points(guild_id=interaction.guild.id, user_id=user_id)
        remove_pending_shop_order(
            guild_id=interaction.guild.id,
            user_id=user_id,
            review_message_id=interaction.message.id,
        )

        if e.fields:
            e.set_field_at(
                0,
                name="Статус",
                value=(
                    f"**✅ Принято**\n"
                    f"Проверил: {interaction.user.mention}\n"
                    f"Списано: {price}"
                ),
                inline=False,
            )
        else:
            e.add_field(name="Статус", value=f"**✅ Принято**\nПроверил: {interaction.user.mention}\nСписано: {price}", inline=False)
        e.color = EMBED_COLOR
        await interaction.message.edit(embed=e, view=None)

        user = interaction.guild.get_member(user_id)
        if user is None:
            try:
                user = await interaction.guild.fetch_member(user_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                user = None
        if user is not None:
            try:
                await user.send(
                    embed=_build_shop_order_verdict_embed(
                        guild=interaction.guild,
                        admin=interaction.user,
                        approved=True,
                        item_name=item_name,
                        price=price,
                        balance=new_balance,
                    )
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        await interaction.response.send_message("Покупка принята.", ephemeral=True)

    @discord.ui.button(label="Отказать", style=discord.ButtonStyle.danger, custom_id="shop_review_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Только администрация может отклонять покупки.", ephemeral=True)
            return
        await interaction.response.send_modal(ShopRejectReasonModal())


class ReportLinkModal(discord.ui.Modal):
    def __init__(self, *, report_key: str, report_label: str):
        title = report_label
        super().__init__(title=f"Отчёт • {title}")
        self.report_key = report_key
        self.report_link = discord.ui.TextInput(
            label="Ссылка на отчёт",
            placeholder="Вставьте ссылку на ваш отчёт",
            style=discord.TextStyle.short,
            required=True,
            max_length=500,
        )
        self.add_item(self.report_link)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return

        review_channel_id = get_reports_channel_id(guild_id=interaction.guild.id)
        if not review_channel_id:
            await interaction.response.send_message(
                "Канал проверки отчётов не настроен. Обратитесь к администрации.",
                ephemeral=True,
            )
            return

        review_channel = interaction.guild.get_channel(review_channel_id)
        if review_channel is None:
            try:
                review_channel = await interaction.guild.fetch_channel(review_channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                review_channel = None
        if not isinstance(review_channel, discord.TextChannel):
            await interaction.response.send_message(
                "Не удалось найти канал проверки отчётов. Обратитесь к администрации.",
                ephemeral=True,
            )
            return

        report_types = _get_report_types_for_guild(interaction.guild.id)
        data = report_types.get(self.report_key)
        if data is None:
            await interaction.response.send_message(
                "Этот тип отчёта больше недоступен. Обновите панель отчётов.",
                ephemeral=True,
            )
            return
        reward = int(data["reward"])
        review_embed = discord.Embed(
            title="— ・ Новый отчёт",
            description=(
                f"**Пользователь:** {interaction.user.mention}\n"
                f"**Тип:** {data['label']}\n"
                f"**Ссылка:** {self.report_link.value}"
            ),
            color=discord.Color.dark_gray(),
            timestamp=dt.datetime.now(dt.timezone.utc),
        )
        review_embed.add_field(name="Статус", value="**⏳ На проверке**", inline=False)
        review_embed.add_field(name="Награда", value=f"**{reward}** коин(а)", inline=False)
        review_embed.add_field(name="ID пользователя", value=str(interaction.user.id), inline=False)
        review_embed.set_footer(text=f"report:{self.report_key}")

        review_msg = await review_channel.send(embed=review_embed, view=ReportReviewView())
        add_pending_report(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            review_message_id=review_msg.id,
            report_type=str(data["label"]),
            report_url=self.report_link.value.strip(),
            created_ts=int(dt.datetime.now(dt.timezone.utc).timestamp()),
        )

        f = _report_image_file()
        done_embed = _build_report_sent_embed(with_image=(f is not None))
        if f is not None:
            await interaction.response.send_message(embed=done_embed, file=f, ephemeral=True)
        else:
            await interaction.response.send_message(embed=done_embed, ephemeral=True)


class ReportTypeSelect(discord.ui.Select):
    def __init__(self, *, guild_id: int | None = None):
        report_types = _get_report_types_for_guild(int(guild_id or 0))
        options = [
            discord.SelectOption(
                label=str(data["label"])[:100],
                value=key,
                description=str(data.get("desc", ""))[:100] or f"{int(data['reward'])} коин(а)",
            )
            for key, data in list(report_types.items())[:25]
        ]
        super().__init__(
            placeholder="Выберите тип отчёта",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="report_panel_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        report_key = self.values[0]
        report_types = _get_report_types_for_guild(interaction.guild.id)
        data = report_types.get(report_key)
        if data is None:
            await interaction.response.send_message("Этот тип отчёта больше недоступен.", ephemeral=True)
            return
        await interaction.response.send_modal(
            ReportLinkModal(report_key=report_key, report_label=str(data["label"]))
        )
        if interaction.message is not None:
            try:
                await interaction.message.edit(view=ReportPanelView(guild_id=interaction.guild.id))
            except (discord.Forbidden, discord.HTTPException):
                pass


class ReportPanelView(discord.ui.View):
    def __init__(self, *, guild_id: int | None = None):
        super().__init__(timeout=None)
        self.add_item(ReportTypeSelect(guild_id=guild_id))

    @discord.ui.button(label="Информация", style=discord.ButtonStyle.secondary, custom_id="report_info_button")
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        pending = get_pending_reports(guild_id=interaction.guild.id, user_id=interaction.user.id)
        if not pending:
            e = discord.Embed(
                description="— ・ **Ваши необработанные отчёты**\n\nУ вас нет непроверенных отчётов.",
                color=discord.Color.dark_gray(),
            )
            await interaction.response.send_message(embed=e, ephemeral=True)
            return

        lines: list[str] = []
        for item in pending[:10]:
            report_type = str(item.get("type", "Отчёт"))
            report_url = str(item.get("url", "")).strip() or "https://discord.com"
            try:
                created_ts = int(item.get("created_ts", 0))
            except (TypeError, ValueError):
                created_ts = 0
            if created_ts > 0:
                created_dt = dt.datetime.fromtimestamp(created_ts)
                created_text = created_dt.strftime("%d.%m.%Y %H:%M")
            else:
                created_text = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
            lines.append(
                f"⚙️ **{report_type}**\n{created_text} МСК  |  [перейти]({report_url})"
            )

        e = discord.Embed(
            description="— ・ **Ваши необработанные отчёты**\n\n" + "\n\n".join(lines),
            color=discord.Color.dark_gray(),
        )
        await interaction.response.send_message(embed=e, ephemeral=True)


class ReportRejectReasonModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Причина отказа")
        self.reason = discord.ui.TextInput(
            label="Укажите причину отказа",
            placeholder="Например: ссылка невалидна / отчёт старше 48 часов",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=600,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.message is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Только администрация может отклонять отчёты.", ephemeral=True)
            return
        if not interaction.message.embeds:
            await interaction.response.send_message("Не удалось прочитать данные отчёта.", ephemeral=True)
            return

        e = interaction.message.embeds[0]
        user_id: int | None = None
        for fld in e.fields:
            if fld.name == "ID пользователя":
                try:
                    user_id = int(fld.value.strip())
                except ValueError:
                    user_id = None
                break

        if e.fields:
            e.set_field_at(0, name="Статус", value=f"**❌ Отказано**\nПричина: {self.reason.value}", inline=False)
        else:
            e.add_field(name="Статус", value=f"**❌ Отказано**\nПричина: {self.reason.value}", inline=False)
        e.color = EMBED_COLOR
        await interaction.message.edit(embed=e, view=None)

        if user_id is not None:
            remove_pending_report(
                guild_id=interaction.guild.id,
                user_id=user_id,
                review_message_id=interaction.message.id,
            )
            user = interaction.guild.get_member(user_id)
            if user is None:
                try:
                    user = await interaction.guild.fetch_member(user_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    user = None
            if user is not None:
                try:
                    await user.send(
                        embed=_build_report_verdict_embed(
                            guild=interaction.guild,
                            admin=interaction.user,
                            approved=False,
                            reason=self.reason.value,
                        )
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass

        await interaction.response.send_message("Отчёт отклонён.", ephemeral=True)


class ReportReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Принять", style=discord.ButtonStyle.success, custom_id="report_review_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None or interaction.message is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Только администрация может принимать отчёты.", ephemeral=True)
            return
        if not interaction.message.embeds:
            await interaction.response.send_message("Не удалось прочитать данные отчёта.", ephemeral=True)
            return

        e = interaction.message.embeds[0]
        user_id: int | None = None
        reward: int = 0
        for fld in e.fields:
            if fld.name == "ID пользователя":
                try:
                    user_id = int(fld.value.strip())
                except ValueError:
                    user_id = None
            if fld.name == "Награда":
                m = re.search(r"\d+", fld.value)
                reward = int(m.group(0)) if m else 0

        if user_id is None:
            await interaction.response.send_message("Не найден ID пользователя в отчёте.", ephemeral=True)
            return

        new_balance = add_user_points(guild_id=interaction.guild.id, user_id=user_id, delta=float(reward))
        remove_pending_report(
            guild_id=interaction.guild.id,
            user_id=user_id,
            review_message_id=interaction.message.id,
        )
        if e.fields:
            e.set_field_at(
                0,
                name="Статус",
                value=f"**✅ Принято**\nПроверил: {interaction.user.mention}\nНачислено: {reward}",
                inline=False,
            )
        else:
            e.add_field(
                name="Статус",
                value=f"**✅ Принято**\nПроверил: {interaction.user.mention}\nНачислено: {reward}",
                inline=False,
            )
        e.color = EMBED_COLOR
        await interaction.message.edit(embed=e, view=None)

        user = interaction.guild.get_member(user_id)
        if user is None:
            try:
                user = await interaction.guild.fetch_member(user_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                user = None
        if user is not None:
            try:
                await user.send(
                    embed=_build_report_verdict_embed(
                        guild=interaction.guild,
                        admin=interaction.user,
                        approved=True,
                        reward=reward,
                        balance=new_balance,
                    )
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        await interaction.response.send_message("Отчёт принят и баллы начислены.", ephemeral=True)

    @discord.ui.button(label="Отказать", style=discord.ButtonStyle.danger, custom_id="report_review_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Только администрация может отклонять отчёты.", ephemeral=True)
            return
        await interaction.response.send_modal(ReportRejectReasonModal())


@bot.tree.command(name="сбор", description="Создать сбор и отправить пинг в ЛС роли")
@app_commands.describe(
    роль="Роль для пинга и рассылки",
    тип="Тип сбора",
    участников="Сколько участников нужно (необязательно)",
    замены="Сколько замен нужно (необязательно)",
    время="19:00 / 19 00 / 15 (через 15 минут)",
    уточнение="Текст для типа 'контент' (необязательно)",
)
@app_commands.choices(
    тип=[
        app_commands.Choice(name="взп", value="vzp"),
        app_commands.Choice(name="биз", value="biz"),
        app_commands.Choice(name="капт", value="capt"),
        app_commands.Choice(name="контент", value="content"),
    ]
)
async def sbor_command(
    interaction: discord.Interaction,
    роль: discord.Role,
    тип: app_commands.Choice[str],
    время: str,
    участников: str | None = None,
    замены: str | None = None,
    уточнение: str | None = None,
):
    if interaction.guild is None or not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("Команда доступна только в текстовом канале сервера.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    if тип.value == "content" and (уточнение is None or not уточнение.strip()):
        await interaction.followup.send("Для типа `контент` укажи параметр `уточнение`.", ephemeral=True)
        return

    parsed = _parse_sbor_time(время)
    if parsed is None:
        await interaction.followup.send(
            "Неверный формат `время`. Используй: `19:00`, `19 00` или `15` (через 15 минут).",
            ephemeral=True,
        )
        return
    when_dt, pretty_time = parsed
    type_text = _format_sbor_type(тип.value, уточнение.strip() if уточнение else None)
    main_target = _extract_target(участников)
    sub_target = _extract_target(замены)

    e = discord.Embed(
        title="— ・ Сбор",
        description=(
            f"**Тип:** {type_text}\n"
            f"**Время:** {pretty_time}\n"
            f"**Организатор:** {interaction.user.mention}"
        ),
        color=discord.Color.dark_gray(),
        timestamp=when_dt,
    )
    e.add_field(
        name=f"Участники (0/{main_target})" if main_target else "Участники (0)",
        value="—",
        inline=False,
    )
    e.add_field(
        name=f"Замены (0/{sub_target})" if sub_target else "Замены (0)",
        value="—",
        inline=False,
    )
    e.set_footer(text="Сбор")
    view = SborView(author_id=interaction.user.id, main_target=main_target, sub_target=sub_target)

    msg = await interaction.channel.send(
        content=роль.mention,
        embed=e,
        view=view,
        allowed_mentions=discord.AllowedMentions(roles=True),
    )

    dm_text = (
        f"Тебя собирают на **{type_text}**.\n"
        f"Канал: {interaction.channel.mention}\n"
        f"Старт: {when_dt.strftime('%d.%m.%Y %H:%M')} МСК\n"
        f"Записаться: {msg.jump_url}"
    )
    sent = 0
    failed = 0
    for member in роль.members:
        if member.bot:
            continue
        try:
            await member.send(dm_text)
            sent += 1
        except (discord.Forbidden, discord.HTTPException):
            failed += 1

    await interaction.followup.send(
        f"Сбор создан: {msg.jump_url}\nЛС отправлено: {sent}. Не удалось: {failed}.",
        ephemeral=True,
    )


@bot.tree.command(name="спам", description="Массовая рассылка в ЛС участникам выбранной роли")
@app_commands.describe(
    роль="Роль, участникам которой отправится сообщение",
    текст="Текст, который бот отправит в ЛС",
)
@app_commands.default_permissions(administrator=True)
async def spam_command(
    interaction: discord.Interaction,
    роль: discord.Role,
    текст: str,
):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return

    message_text = текст.strip()
    if not message_text:
        await interaction.response.send_message("Укажи непустой текст для рассылки.", ephemeral=True)
        return
    if len(message_text) > 2000:
        await interaction.response.send_message("Текст слишком длинный (максимум 2000 символов).", ephemeral=True)
        return
    formatted_text = f"**{message_text}**"

    await interaction.response.defer(ephemeral=True)

    sent = 0
    failed = 0
    skipped = 0
    failed_mentions: list[str] = []
    for idx, member in enumerate(роль.members, start=1):
        if member.bot:
            skipped += 1
            continue
        try:
            await member.send(formatted_text)
            sent += 1
        except (discord.Forbidden, discord.HTTPException):
            failed += 1
            if len(failed_mentions) < 10:
                failed_mentions.append(member.mention)
        if idx % 5 == 0:
            await asyncio.sleep(0.5)

    fail_preview = "\n".join(failed_mentions) if failed_mentions else "—"
    if failed > len(failed_mentions):
        fail_preview += f"\n...и ещё {failed - len(failed_mentions)}"

    await interaction.followup.send(
        (
            f"Рассылка по роли {роль.mention} завершена.\n"
            f"Отправлено: {sent}\n"
            f"Пропущено (боты): {skipped}\n"
            f"Не удалось отправить: {failed}\n"
            f"Кому не дошло (до 10):\n{fail_preview}"
        ),
        ephemeral=True,
        allowed_mentions=discord.AllowedMentions.none(),
    )


@bot.tree.command(name="розыгрыш", description="Создать розыгрыш с кнопками участия")
@app_commands.default_permissions(administrator=True)
async def giveaway_command(interaction: discord.Interaction):
    await interaction.response.send_modal(GiveawayCreateModal())


def _build_voice_room_control_embed(*, owner: discord.Member) -> discord.Embed:
    return discord.Embed(
        title="Панель управления",
        description=(
            "Кнопки ниже - настройки твоей голосовой комнаты.\n"
            "(чат справа у этого войса): **Название, Лимит, Регион**\n"
            "- сразу меняют войс; **Кикнуть** - из списка;\n"
            "**Прихожая** - закрыть вход для всех, кроме тебя;\n"
            "**Забрать** - передать владельца из списка; **Друзья / Баны** - выбор из списка.\n\n"
            f"Владелец: {owner.mention}\n"
            "Комната создана автоматически после входа в прихожую."
        ),
        color=discord.Color.dark_gray(),
    )


def _who_line(user: discord.abc.User) -> str:
    display = user.display_name if isinstance(user, discord.Member) else user.name
    return f"{user.mention} | {display} | {user.id}"


async def _get_logs_text_channel(guild: discord.Guild) -> discord.TextChannel | None:
    logs_id = get_logs_channel_id(guild_id=guild.id)
    if not logs_id:
        return None
    ch = guild.get_channel(logs_id)
    if ch is None:
        try:
            ch = await guild.fetch_channel(logs_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None
    return ch if isinstance(ch, discord.TextChannel) else None


async def _send_action_log(
    *,
    guild: discord.Guild,
    action_name: str,
    actor: discord.abc.User,
    target: discord.abc.User,
) -> None:
    channel = await _get_logs_text_channel(guild)
    if channel is None:
        return
    e = discord.Embed(
        title="— ・ Действие",
        description=(
            f"**Действие:** {action_name}\n\n"
            f"**Кто:**\n{_who_line(actor)}\n\n"
            f"**Кого:**\n{_who_line(target)}"
        ),
        color=discord.Color.dark_gray(),
    )
    e.set_footer(text=dt.datetime.now().strftime("%d.%m.%Y %H:%M"))
    try:
        await channel.send(embed=e)
    except (discord.Forbidden, discord.HTTPException):
        return


async def _send_join_leave_log(
    *,
    guild: discord.Guild,
    action_name: str,
    member: discord.Member,
) -> None:
    channel = await _get_logs_text_channel(guild)
    if channel is None:
        return
    created_text = member.created_at.astimezone(MSK_TZ).strftime("%d.%m.%Y %H:%M МСК")
    e = discord.Embed(
        title="— ・ Действие",
        description=(
            f"**Действие:** {action_name}\n\n"
            f"**Кто:**\n{_who_line(member)}\n\n"
            f"**Когда регистрация аккаунта:**\n{created_text}"
        ),
        color=discord.Color.dark_gray(),
    )
    e.set_footer(text=dt.datetime.now().strftime("%d.%m.%Y %H:%M"))
    try:
        await channel.send(embed=e)
    except (discord.Forbidden, discord.HTTPException):
        return


async def _find_recent_audit_actor(
    *,
    guild: discord.Guild,
    action: discord.AuditLogAction,
    target_id: int,
    max_age_s: int = 20,
    retries: int = 3,
) -> discord.abc.User | None:
    attempts = max(1, int(retries))
    for attempt in range(attempts):
        now = dt.datetime.now(dt.timezone.utc)
        try:
            async for entry in guild.audit_logs(limit=12, action=action):
                entry_target_id = getattr(entry.target, "id", None)
                if entry_target_id is None:
                    continue
                try:
                    if int(entry_target_id) != int(target_id):
                        continue
                except (TypeError, ValueError):
                    continue
                age_s = (now - entry.created_at).total_seconds()
                if age_s < 0 or age_s > max_age_s:
                    continue
                if isinstance(entry.user, (discord.Member, discord.User)):
                    return entry.user
        except (discord.Forbidden, discord.HTTPException):
            return None
        if attempt < attempts - 1:
            await asyncio.sleep(1.0)
    return None


def _parse_member_id(raw: str) -> int | None:
    m = re.search(r"\d{6,25}", raw or "")
    if not m:
        return None
    try:
        return int(m.group(0))
    except ValueError:
        return None


def _can_manage_voice_room(member: discord.Member, owner_id: int | None) -> bool:
    if owner_id is not None and member.id == owner_id:
        return True
    return member.guild_permissions.administrator or member.guild_permissions.manage_channels


class VoiceRoomNameModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Название комнаты")
        self.new_name = discord.ui.TextInput(
            label="Новое название",
            placeholder="Например: Комната • prestige",
            max_length=100,
            required=True,
        )
        self.add_item(self.new_name)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.VoiceChannel):
            await interaction.response.send_message("Эта кнопка работает только в чате голосовой комнаты.", ephemeral=True)
            return

        owner_id = get_temp_voice_owner_id(guild_id=interaction.guild.id, channel_id=interaction.channel.id)
        if not _can_manage_voice_room(interaction.user, owner_id):
            await interaction.response.send_message("Только владелец комнаты или админ может это делать.", ephemeral=True)
            return
        try:
            await interaction.channel.edit(name=self.new_name.value.strip()[:100], reason=f"Переименование: {interaction.user}")
        except (discord.Forbidden, discord.HTTPException):
            await interaction.response.send_message("Не удалось изменить название.", ephemeral=True)
            return
        await interaction.response.send_message("Название обновлено.", ephemeral=True)


class VoiceRoomLimitModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Лимит комнаты")
        self.limit = discord.ui.TextInput(
            label="Лимит (0-99)",
            placeholder="0 = без лимита",
            max_length=2,
            required=True,
        )
        self.add_item(self.limit)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.VoiceChannel):
            await interaction.response.send_message("Эта кнопка работает только в чате голосовой комнаты.", ephemeral=True)
            return

        owner_id = get_temp_voice_owner_id(guild_id=interaction.guild.id, channel_id=interaction.channel.id)
        if not _can_manage_voice_room(interaction.user, owner_id):
            await interaction.response.send_message("Только владелец комнаты или админ может это делать.", ephemeral=True)
            return
        try:
            value = int(self.limit.value.strip())
        except ValueError:
            await interaction.response.send_message("Введи число от 0 до 99.", ephemeral=True)
            return
        if value < 0 or value > 99:
            await interaction.response.send_message("Лимит должен быть от 0 до 99.", ephemeral=True)
            return
        try:
            await interaction.channel.edit(user_limit=value, reason=f"Лимит: {interaction.user}")
        except (discord.Forbidden, discord.HTTPException):
            await interaction.response.send_message("Не удалось изменить лимит.", ephemeral=True)
            return
        await interaction.response.send_message(f"Лимит обновлён: {value}.", ephemeral=True)


async def _apply_voice_room_member_action(
    *,
    interaction: discord.Interaction,
    action: str,
    target_member: discord.Member,
) -> str:
    if interaction.guild is None or not isinstance(interaction.channel, discord.VoiceChannel):
        return "Команда доступна только в чате голосовой комнаты."

    if action == "kick":
        if target_member not in interaction.channel.members:
            return "Пользователь не в этой комнате."
        await target_member.move_to(None, reason=f"Кик из комнаты: {interaction.user}")
        return f"{target_member.mention} кикнут из комнаты."

    if action == "owner":
        if target_member not in interaction.channel.members:
            return "Новый владелец должен быть в комнате."
        set_temp_voice_owner_id(
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            owner_id=target_member.id,
        )
        await interaction.channel.set_permissions(
            target_member,
            connect=True,
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            speak=True,
            stream=True,
            use_voice_activation=True,
            priority_speaker=True,
            move_members=True,
            mute_members=True,
            deafen_members=True,
            manage_channels=True,
        )
        return f"Владелец комнаты: {target_member.mention}."

    if action == "friend":
        await interaction.channel.set_permissions(
            target_member,
            connect=True,
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            speak=True,
            stream=True,
        )
        return f"{target_member.mention} добавлен в друзья комнаты."

    if action == "ban":
        if target_member in interaction.channel.members:
            try:
                await target_member.move_to(None, reason=f"Бан в комнате: {interaction.user}")
            except (discord.Forbidden, discord.HTTPException):
                pass
        await interaction.channel.set_permissions(
            target_member,
            connect=False,
            view_channel=False,
            send_messages=False,
            read_message_history=False,
        )
        return f"{target_member.mention} добавлен в бан комнаты."

    return "Неизвестное действие."


class VoiceRoomMemberSelect(discord.ui.Select):
    def __init__(self, *, action: str, members: list[discord.Member]):
        self.action = action
        label_map = {
            "kick": "Выбери кого кикнуть",
            "owner": "Выбери нового владельца",
            "friend": "Выбери друга",
            "ban": "Выбери кого забанить",
        }
        options: list[discord.SelectOption] = []
        for member in members[:25]:
            options.append(
                discord.SelectOption(
                    label=member.display_name[:100],
                    value=str(member.id),
                    description=str(member.id),
                )
            )
        super().__init__(
            placeholder=label_map.get(action, "Выбери участника"),
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.VoiceChannel):
            await interaction.response.send_message("Эта кнопка работает только в чате голосовой комнаты.", ephemeral=True)
            return
        owner_id = get_temp_voice_owner_id(guild_id=interaction.guild.id, channel_id=interaction.channel.id)
        if not _can_manage_voice_room(interaction.user, owner_id):
            await interaction.response.send_message("Только владелец комнаты или админ может это делать.", ephemeral=True)
            return

        try:
            target_id = int(self.values[0])
        except (TypeError, ValueError):
            await interaction.response.send_message("Не смог прочитать выбранного пользователя.", ephemeral=True)
            return
        target_member = interaction.guild.get_member(target_id)
        if target_member is None:
            await interaction.response.send_message("Пользователь не найден на сервере.", ephemeral=True)
            return

        try:
            result_text = await _apply_voice_room_member_action(
                interaction=interaction,
                action=self.action,
                target_member=target_member,
            )
        except (discord.Forbidden, discord.HTTPException):
            await interaction.response.send_message("Не удалось применить действие (права/иерархия).", ephemeral=True)
            return
        await interaction.response.send_message(result_text, ephemeral=True)


class VoiceRoomMemberPickerView(discord.ui.View):
    def __init__(self, *, action: str, members: list[discord.Member]):
        super().__init__(timeout=120)
        self.add_item(VoiceRoomMemberSelect(action=action, members=members))


class VoiceRoomControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @staticmethod
    def _pickable_members(channel: discord.VoiceChannel, *, action: str, actor_id: int) -> list[discord.Member]:
        out: list[discord.Member] = []
        for member in channel.members:
            if member.bot:
                continue
            if action in {"kick", "ban", "owner"} and member.id == actor_id:
                continue
            out.append(member)
        return out

    @discord.ui.button(label="Название", style=discord.ButtonStyle.secondary, emoji="🔤")
    async def set_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VoiceRoomNameModal())

    @discord.ui.button(label="Лимит", style=discord.ButtonStyle.secondary, emoji="👥")
    async def set_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VoiceRoomLimitModal())

    @discord.ui.button(label="Регион", style=discord.ButtonStyle.secondary, emoji="🌐")
    async def set_region(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.VoiceChannel):
            await interaction.response.send_message("Эта кнопка работает только в чате голосовой комнаты.", ephemeral=True)
            return
        owner_id = get_temp_voice_owner_id(guild_id=interaction.guild.id, channel_id=interaction.channel.id)
        if not _can_manage_voice_room(interaction.user, owner_id):
            await interaction.response.send_message("Только владелец комнаты или админ может это делать.", ephemeral=True)
            return

        regions: list[str | None] = [None, "rotterdam", "frankfurt", "singapore", "us-central", "us-east", "us-west"]
        current = str(interaction.channel.rtc_region) if interaction.channel.rtc_region is not None else None
        try:
            idx = regions.index(current)
        except ValueError:
            idx = 0
        next_region = regions[(idx + 1) % len(regions)]
        try:
            await interaction.channel.edit(rtc_region=next_region, reason=f"Смена региона: {interaction.user}")
        except (discord.Forbidden, discord.HTTPException):
            await interaction.response.send_message("Не удалось изменить регион.", ephemeral=True)
            return
        pretty = next_region if next_region is not None else "auto"
        await interaction.response.send_message(f"Регион: `{pretty}`.", ephemeral=True)

    @discord.ui.button(label="Кикнуть", style=discord.ButtonStyle.secondary, emoji="🦶")
    async def kick_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.channel, discord.VoiceChannel):
            await interaction.response.send_message("Эта кнопка работает только в чате голосовой комнаты.", ephemeral=True)
            return
        members = self._pickable_members(interaction.channel, action="kick", actor_id=interaction.user.id)
        if not members:
            await interaction.response.send_message("В комнате нет доступных участников для кика.", ephemeral=True)
            return
        await interaction.response.send_message("Кого кикнуть?", view=VoiceRoomMemberPickerView(action="kick", members=members), ephemeral=True)

    @discord.ui.button(label="Гайд", style=discord.ButtonStyle.primary, emoji="ℹ️")
    async def guide(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            (
                "Настройки комнаты:\n"
                "- `Название` — меняет имя войса\n"
                "- `Лимит` — максимум участников\n"
                "- `Регион` — цикл регионов звонка\n"
                "- `Кикнуть` — выгнать участника\n"
                "- `Прихожая` — закрыть/открыть вход всем\n"
                "- `Забрать` — передать владельца\n"
                "- `Друзья` — дать доступ участнику\n"
                "- `Баны` — запретить доступ участнику"
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="Прихожая", style=discord.ButtonStyle.secondary, emoji="🕓")
    async def toggle_lobby(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.VoiceChannel):
            await interaction.response.send_message("Эта кнопка работает только в чате голосовой комнаты.", ephemeral=True)
            return
        owner_id = get_temp_voice_owner_id(guild_id=interaction.guild.id, channel_id=interaction.channel.id)
        if not _can_manage_voice_room(interaction.user, owner_id):
            await interaction.response.send_message("Только владелец комнаты или админ может это делать.", ephemeral=True)
            return

        ow = interaction.channel.overwrites_for(interaction.guild.default_role)
        currently_locked = ow.connect is False
        new_connect = True if currently_locked else False
        try:
            await interaction.channel.set_permissions(
                interaction.guild.default_role,
                connect=new_connect,
                view_channel=ow.view_channel,
                send_messages=ow.send_messages,
                read_message_history=ow.read_message_history,
            )
        except (discord.Forbidden, discord.HTTPException):
            await interaction.response.send_message("Не удалось обновить доступ в комнату.", ephemeral=True)
            return
        state_text = "открыт" if new_connect else "закрыт"
        await interaction.response.send_message(f"Вход для всех: **{state_text}**.", ephemeral=True)

    @discord.ui.button(label="Забрать", style=discord.ButtonStyle.secondary, emoji="⭐")
    async def transfer_owner(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.channel, discord.VoiceChannel):
            await interaction.response.send_message("Эта кнопка работает только в чате голосовой комнаты.", ephemeral=True)
            return
        members = self._pickable_members(interaction.channel, action="owner", actor_id=interaction.user.id)
        if not members:
            await interaction.response.send_message("Некому передавать владельца.", ephemeral=True)
            return
        await interaction.response.send_message(
            "Кому передать владельца?",
            view=VoiceRoomMemberPickerView(action="owner", members=members),
            ephemeral=True,
        )

    @discord.ui.button(label="Друзья", style=discord.ButtonStyle.success, emoji="👥")
    async def add_friend(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.channel, discord.VoiceChannel):
            await interaction.response.send_message("Эта кнопка работает только в чате голосовой комнаты.", ephemeral=True)
            return
        members = self._pickable_members(interaction.channel, action="friend", actor_id=interaction.user.id)
        if not members:
            await interaction.response.send_message("В комнате нет участников для добавления в друзья.", ephemeral=True)
            return
        await interaction.response.send_message(
            "Кого добавить в друзья?",
            view=VoiceRoomMemberPickerView(action="friend", members=members),
            ephemeral=True,
        )

    @discord.ui.button(label="Баны", style=discord.ButtonStyle.danger, emoji="⛔")
    async def add_ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.channel, discord.VoiceChannel):
            await interaction.response.send_message("Эта кнопка работает только в чате голосовой комнаты.", ephemeral=True)
            return
        members = self._pickable_members(interaction.channel, action="ban", actor_id=interaction.user.id)
        if not members:
            await interaction.response.send_message("В комнате нет доступных участников для бана.", ephemeral=True)
            return
        await interaction.response.send_message("Кого забанить в комнате?", view=VoiceRoomMemberPickerView(action="ban", members=members), ephemeral=True)


@bot.tree.command(name="панель-магазин", description="Отправить панель магазина в выбранный канал")
@app_commands.describe(panel_channel="Канал, куда отправить панель магазина")
@app_commands.default_permissions(administrator=True)
async def shop_panel(interaction: discord.Interaction, panel_channel: discord.TextChannel):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return

    # Важно: отправка embed + файла может занять >3s, поэтому сразу подтверждаем interaction.
    await interaction.response.defer(ephemeral=True)

    f = _shop_image_file()
    embed = _build_shop_embed_for_guild(guild_id=interaction.guild.id, with_image=(f is not None))
    view = ShopPanelView(guild_id=interaction.guild.id)
    existing = get_shop_panel_message_id(guild_id=interaction.guild.id)
    edited = False
    if existing and existing[0] == panel_channel.id:
        try:
            old_msg = await panel_channel.fetch_message(existing[1])
            await old_msg.edit(embed=embed, view=view)
            edited = True
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            edited = False

    if not edited:
        if f is not None:
            msg = await panel_channel.send(embed=embed, view=view, file=f)
        else:
            msg = await panel_channel.send(embed=embed, view=view)
        set_shop_panel_message_id(guild_id=interaction.guild.id, channel_id=panel_channel.id, message_id=msg.id)

    await interaction.followup.send(
        f"Панель магазина {'обновлена' if edited else 'отправлена'} в {panel_channel.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="привязка-отчетов", description="Выбрать канал, куда будут отправляться отчёты на проверку")
@app_commands.describe(send_to="Канал, куда бот будет отправлять отчёты")
@app_commands.default_permissions(administrator=True)
async def bind_reports(interaction: discord.Interaction, send_to: discord.TextChannel):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return
    set_reports_channel_id(guild_id=interaction.guild.id, channel_id=send_to.id)
    await interaction.response.send_message(
        f"Готово. Теперь отчёты будут отправляться в {send_to.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="привязка-логов", description="Выбрать канал, куда бот будет отправлять логи действий")
@app_commands.describe(send_to="Канал для логов: бан, исключение, войс-действия")
@app_commands.default_permissions(administrator=True)
async def bind_logs(interaction: discord.Interaction, send_to: discord.TextChannel):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return
    set_logs_channel_id(guild_id=interaction.guild.id, channel_id=send_to.id)
    await interaction.response.send_message(
        f"Готово. Логи действий будут отправляться в {send_to.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="привязка-магазина", description="Выбрать канал, куда будут отправляться покупки из магазина на проверку")
@app_commands.describe(send_to="Канал, куда бот будет отправлять заявки на покупку")
@app_commands.default_permissions(administrator=True)
async def bind_shop_orders(interaction: discord.Interaction, send_to: discord.TextChannel):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return
    set_shop_orders_channel_id(guild_id=interaction.guild.id, channel_id=send_to.id)
    await interaction.response.send_message(
        f"Готово. Теперь покупки из магазина будут отправляться в {send_to.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="настройка-магазина", description="Открыть всплывающую панель управления товарами магазина")
@app_commands.default_permissions(administrator=True)
async def shop_manage_panel(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return
    e = discord.Embed(
        title="— ・ Настройка магазина",
        description=(
            "Выбери **действие** во втором списке.\n"
            "Для `изменить`/`удалить` сначала выбери **товар** в первом списке."
        ),
        color=discord.Color.dark_gray(),
    )
    await interaction.response.send_message(embed=e, view=ShopManageView(guild_id=interaction.guild.id), ephemeral=True)


@bot.tree.command(name="настройка-ивентов", description="Открыть всплывающую панель настройки ивентов")
@app_commands.default_permissions(administrator=True)
async def events_manage_panel(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return
    current = _get_report_types_for_guild(interaction.guild.id)
    if not current:
        await interaction.response.send_message("Список ивентов пуст. Добавь через `/ивент-добавить`.", ephemeral=True)
        return
    e = discord.Embed(
        title="— ・ Настройка ивентов",
        description=(
            "Выбери **действие** во втором списке.\n"
            "Для `изменить`/`удалить` сначала выбери **ивент** в первом списке."
        ),
        color=discord.Color.dark_gray(),
    )
    await interaction.response.send_message(embed=e, view=EventsManageView(guild_id=interaction.guild.id), ephemeral=True)


@bot.tree.command(name="привязка-промо", description="Выбрать канал, куда будут отправляться промокоды на проверку")
@app_commands.describe(send_to="Канал, куда бот будет отправлять промокоды")
@app_commands.default_permissions(administrator=True)
async def bind_promo(interaction: discord.Interaction, send_to: discord.TextChannel):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return
    set_promo_channel_id(guild_id=interaction.guild.id, channel_id=send_to.id)
    await interaction.response.send_message(
        f"Готово. Теперь промокоды будут отправляться в {send_to.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="привязка-стрима", description="Выбрать канал для оповещений о начале стрима")
@app_commands.describe(send_to="Канал, куда бот будет писать про старт стрима")
@app_commands.default_permissions(administrator=True)
async def bind_stream_announce(interaction: discord.Interaction, send_to: discord.TextChannel):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return
    set_stream_announce_channel_id(guild_id=interaction.guild.id, channel_id=send_to.id)
    await interaction.response.send_message(
        f"Готово. Теперь при старте стрима бот будет писать в {send_to.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="настройка-стримеров", description="Кого анонсить при старте стрима")
@app_commands.describe(
    действие="Что сделать (добавить/убрать/список/очистить)",
    пользователь="Пользователь (нужно только для добавить/убрать)",
)
@app_commands.default_permissions(administrator=True)
@app_commands.choices(
    действие=[
        app_commands.Choice(name="добавить", value="add"),
        app_commands.Choice(name="убрать", value="remove"),
        app_commands.Choice(name="список", value="list"),
        app_commands.Choice(name="очистить", value="clear"),
    ]
)
async def configure_streamers(
    interaction: discord.Interaction,
    действие: app_commands.Choice[str],
    пользователь: discord.Member | None = None,
):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return

    guild = interaction.guild
    user_ids = get_stream_announce_user_ids(guild_id=guild.id)

    if действие.value == "list":
        pretty = " ".join(f"<@{uid}>" for uid in user_ids) if user_ids else "—"
        await interaction.response.send_message(f"Кого анонсить при старте стрима: {pretty}", ephemeral=True)
        return

    if действие.value == "clear":
        set_stream_announce_user_ids(guild_id=guild.id, user_ids=[])
        await interaction.response.send_message("Готово. Список стримеров очищен.", ephemeral=True)
        return

    if пользователь is None:
        await interaction.response.send_message("Выбери пользователя в параметре `пользователь`.", ephemeral=True)
        return

    if действие.value == "add":
        if пользователь.id not in user_ids:
            user_ids.append(пользователь.id)
            set_stream_announce_user_ids(guild_id=guild.id, user_ids=user_ids)
        pretty = " ".join(f"<@{uid}>" for uid in user_ids) if user_ids else "—"
        await interaction.response.send_message(
            f"Готово. Добавлен {пользователь.mention}. Теперь анонс для: {pretty}",
            ephemeral=True,
        )
        return

    if действие.value == "remove":
        if пользователь.id in user_ids:
            user_ids = [uid for uid in user_ids if uid != пользователь.id]
            set_stream_announce_user_ids(guild_id=guild.id, user_ids=user_ids)
        pretty = " ".join(f"<@{uid}>" for uid in user_ids) if user_ids else "—"
        await interaction.response.send_message(
            f"Готово. Убран {пользователь.mention}. Теперь анонс для: {pretty}",
            ephemeral=True,
        )
        return

    await interaction.response.send_message("Неизвестное действие.", ephemeral=True)


@bot.tree.command(name="настройка-твич-стримеров", description="Привязать Twitch-логин к конкретному пользователю")
@app_commands.describe(
    действие="Что сделать (добавить/убрать/список/очистить)",
    пользователь="Пользователь (для добавить/убрать)",
    twitch_login="Логин на Twitch или ссылка на канал (для добавить)",
)
@app_commands.default_permissions(administrator=True)
@app_commands.choices(
    действие=[
        app_commands.Choice(name="добавить", value="add"),
        app_commands.Choice(name="убрать", value="remove"),
        app_commands.Choice(name="список", value="list"),
        app_commands.Choice(name="очистить", value="clear"),
    ]
)
async def configure_twitch_streamers(
    interaction: discord.Interaction,
    действие: app_commands.Choice[str],
    пользователь: discord.Member | None = None,
    twitch_login: str | None = None,
):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return

    guild = interaction.guild
    twitch_map = get_stream_announce_twitch_map(guild_id=guild.id)

    if действие.value == "list":
        if not twitch_map:
            await interaction.response.send_message("Список Twitch-привязок пуст.", ephemeral=True)
            return
        lines = [f"<@{uid}> -> `{login}`" for uid, login in twitch_map.items()]
        await interaction.response.send_message("Twitch-привязки:\n" + "\n".join(lines[:25]), ephemeral=True)
        return

    if действие.value == "clear":
        set_stream_announce_twitch_map(guild_id=guild.id, mapping={})
        await interaction.response.send_message("Готово. Twitch-привязки очищены.", ephemeral=True)
        return

    if пользователь is None:
        await interaction.response.send_message("Выбери пользователя в параметре `пользователь`.", ephemeral=True)
        return

    if действие.value == "remove":
        if пользователь.id in twitch_map:
            twitch_map.pop(пользователь.id, None)
            set_stream_announce_twitch_map(guild_id=guild.id, mapping=twitch_map)
        await interaction.response.send_message(f"Готово. Twitch-привязка для {пользователь.mention} удалена.", ephemeral=True)
        return

    if действие.value == "add":
        login = _normalize_twitch_login(twitch_login or "")
        if not login:
            await interaction.response.send_message("Укажи корректный `twitch_login` (например `nickname`).", ephemeral=True)
            return
        twitch_map[пользователь.id] = login
        set_stream_announce_twitch_map(guild_id=guild.id, mapping=twitch_map)
        allowed = get_stream_announce_user_ids(guild_id=guild.id)
        if пользователь.id not in allowed:
            allowed.append(пользователь.id)
            set_stream_announce_user_ids(guild_id=guild.id, user_ids=allowed)
        await interaction.response.send_message(
            f"Готово. {пользователь.mention} привязан к Twitch: `https://twitch.tv/{login}`",
            ephemeral=True,
        )
        return

    await interaction.response.send_message("Неизвестное действие.", ephemeral=True)

@bot.tree.command(name="панель-промо", description="Отправить панель промокодов в выбранный канал")
@app_commands.describe(panel_channel="Канал, куда отправить панель промокодов")
@app_commands.default_permissions(administrator=True)
async def promo_panel(interaction: discord.Interaction, panel_channel: discord.TextChannel):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    f = _promo_image_file()
    embed = build_promo_panel_embed(with_image=(f is not None))
    view = PromoPanelView()
    existing = get_promo_panel_message_id(guild_id=interaction.guild.id)
    edited = False
    if existing and existing[0] == panel_channel.id:
        try:
            old_msg = await panel_channel.fetch_message(existing[1])
            await old_msg.edit(embed=embed, view=view)
            edited = True
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            edited = False

    if not edited:
        if f is not None:
            msg = await panel_channel.send(embed=embed, view=view, file=f)
        else:
            msg = await panel_channel.send(embed=embed, view=view)
        set_promo_panel_message_id(guild_id=interaction.guild.id, channel_id=panel_channel.id, message_id=msg.id)

    await interaction.followup.send(
        f"Панель промокодов {'обновлена' if edited else 'отправлена'} в {panel_channel.mention}.",
        ephemeral=True,
    )


@app_commands.describe(
    действие="Что сделать",
    товар="Название товара (для добавить/изменить/удалить)",
    цена="Цена товара (для добавить/изменить)",
)
@app_commands.default_permissions(administrator=True)
@app_commands.choices(
    действие=[
        app_commands.Choice(name="показать", value="list"),
        app_commands.Choice(name="добавить", value="add"),
        app_commands.Choice(name="изменить", value="update"),
        app_commands.Choice(name="удалить", value="remove"),
        app_commands.Choice(name="сбросить", value="reset"),
    ]
)
async def _shop_settings_legacy(
    interaction: discord.Interaction,
    действие: app_commands.Choice[str],
    товар: str | None = None,
    цена: int | None = None,
):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return

    guild_id = interaction.guild.id
    action = действие.value
    current = _get_shop_items_for_guild(guild_id)

    if action == "list":
        lines = [f"{idx}. {name} — {price}" for idx, (name, price) in enumerate(current, start=1)]
        await interaction.response.send_message(
            "Товары магазина:\n" + ("\n".join(lines) if lines else "—"),
            ephemeral=True,
        )
        return

    if action == "reset":
        set_shop_items(
            guild_id=guild_id,
            items=[{"name": name, "price": price} for name, price in DEFAULT_SHOP_ITEMS],
        )
        updated_panel = await _refresh_shop_panel_message(guild=interaction.guild)
        await interaction.response.send_message(
            "Готово. Магазин сброшен к стандартным товарам."
            + (" Панель обновлена автоматически." if updated_panel else ""),
            ephemeral=True,
        )
        return

    item_name = (товар or "").strip()
    if not item_name:
        await interaction.response.send_message("Укажи параметр `товар`.", ephemeral=True)
        return

    if action in {"add", "update"}:
        if цена is None or int(цена) <= 0:
            await interaction.response.send_message("Укажи параметр `цена` (> 0).", ephemeral=True)
            return
        updated = list(current)
        found_idx: int | None = None
        for i, (name, _) in enumerate(updated):
            if name.casefold() == item_name.casefold():
                found_idx = i
                break
        if action == "add":
            if found_idx is not None:
                await interaction.response.send_message("Такой товар уже есть. Используй действие `изменить`.", ephemeral=True)
                return
            updated.append((item_name[:100], int(цена)))
        else:
            if found_idx is None:
                await interaction.response.send_message("Товар не найден. Используй действие `добавить`.", ephemeral=True)
                return
            updated[found_idx] = (updated[found_idx][0], int(цена))
        set_shop_items(
            guild_id=guild_id,
            items=[{"name": name, "price": price} for name, price in updated],
        )
        updated_panel = await _refresh_shop_panel_message(guild=interaction.guild)
        await interaction.response.send_message(
            "Готово. Магазин обновлён." + (" Панель обновлена автоматически." if updated_panel else ""),
            ephemeral=True,
        )
        return

    if action == "remove":
        updated = [(name, price) for name, price in current if name.casefold() != item_name.casefold()]
        if len(updated) == len(current):
            await interaction.response.send_message("Товар не найден.", ephemeral=True)
            return
        set_shop_items(
            guild_id=guild_id,
            items=[{"name": name, "price": price} for name, price in updated],
        )
        updated_panel = await _refresh_shop_panel_message(guild=interaction.guild)
        await interaction.response.send_message(
            "Товар удалён." + (" Панель обновлена автоматически." if updated_panel else ""),
            ephemeral=True,
        )
        return

    await interaction.response.send_message("Неизвестное действие.", ephemeral=True)


@bot.tree.command(name="товар-изменить", description="Изменить цену товара через выбор из списка")
@app_commands.describe(
    товар="Начни вводить название и выбери из списка",
    цена="Новая цена",
)
@app_commands.default_permissions(administrator=True)
@app_commands.autocomplete(товар=_shop_item_autocomplete)
async def shop_item_update_simple(
    interaction: discord.Interaction,
    товар: str,
    цена: int,
):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return
    item_name = (товар or "").strip()
    if not item_name:
        await interaction.response.send_message("Выбери `товар`.", ephemeral=True)
        return
    if int(цена) <= 0:
        await interaction.response.send_message("Укажи `цена` (> 0).", ephemeral=True)
        return

    guild_id = interaction.guild.id
    current = _get_shop_items_for_guild(guild_id)
    updated = list(current)
    found_idx: int | None = None
    for i, (name, _) in enumerate(updated):
        if name.casefold() == item_name.casefold():
            found_idx = i
            break
    if found_idx is None:
        await interaction.response.send_message("Товар не найден (возможно уже удалён).", ephemeral=True)
        return

    updated[found_idx] = (updated[found_idx][0], int(цена))
    set_shop_items(guild_id=guild_id, items=[{"name": name, "price": price} for name, price in updated])
    updated_panel = await _refresh_shop_panel_message(guild=interaction.guild)
    await interaction.response.send_message(
        f"Готово. Цена обновлена: **{updated[found_idx][0]}** — **{int(цена)}**"
        + (" Панель обновлена автоматически." if updated_panel else ""),
        ephemeral=True,
    )


@bot.tree.command(name="товар-удалить", description="Удалить товар через выбор из списка")
@app_commands.describe(товар="Начни вводить название и выбери из списка")
@app_commands.default_permissions(administrator=True)
@app_commands.autocomplete(товар=_shop_item_autocomplete)
async def shop_item_remove_simple(
    interaction: discord.Interaction,
    товар: str,
):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return
    item_name = (товар or "").strip()
    if not item_name:
        await interaction.response.send_message("Выбери `товар`.", ephemeral=True)
        return

    guild_id = interaction.guild.id
    current = _get_shop_items_for_guild(guild_id)
    updated = [(name, price) for name, price in current if name.casefold() != item_name.casefold()]
    if len(updated) == len(current):
        await interaction.response.send_message("Товар не найден (возможно уже удалён).", ephemeral=True)
        return

    set_shop_items(guild_id=guild_id, items=[{"name": name, "price": price} for name, price in updated])
    updated_panel = await _refresh_shop_panel_message(guild=interaction.guild)
    await interaction.response.send_message(
        f"Готово. Товар удалён: **{item_name}**" + (" Панель обновлена автоматически." if updated_panel else ""),
        ephemeral=True,
    )


@bot.tree.command(name="привязка-категория-обзвона", description="Выбрать категорию, где будут создаваться каналы обзвона")
@app_commands.describe(category="Категория для каналов обзвона (форум/категория)")
@app_commands.default_permissions(administrator=True)
async def bind_call_category(interaction: discord.Interaction, category: discord.CategoryChannel):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return
    set_call_category_id(guild_id=interaction.guild.id, category_id=category.id)
    await interaction.response.send_message(
        f"Готово. Теперь каналы обзвона будут создаваться в категории {category.name}.",
        ephemeral=True,
    )


@bot.tree.command(name="привязка-прихожая", description="Выбрать голосовой канал-прихожую для авто-комнат")
@app_commands.describe(channel="Голосовой канал, вход в который создаёт личную комнату")
@app_commands.default_permissions(administrator=True)
async def bind_voice_lobby(interaction: discord.Interaction, channel: discord.VoiceChannel):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return
    set_voice_lobby_channel_id(guild_id=interaction.guild.id, channel_id=channel.id)
    await interaction.response.send_message(
        f"Готово. Прихожая для авто-комнат: {channel.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="привязка-категория-портфелей", description="Выбрать категорию, где будут создаваться личные каналы портфеля")
@app_commands.describe(category="Категория для каналов портфеля")
@app_commands.default_permissions(administrator=True)
async def bind_portfolio_category(interaction: discord.Interaction, category: discord.CategoryChannel):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return
    set_portfolio_category_id(guild_id=interaction.guild.id, category_id=category.id)
    await interaction.response.send_message(
        f"Готово. Теперь личные каналы портфеля будут создаваться в категории {category.name}.",
        ephemeral=True,
    )


@bot.tree.command(name="панель-портфеля", description="Отправить панель создания портфеля в выбранный канал")
@app_commands.describe(panel_channel="Канал, куда отправить панель портфеля")
@app_commands.default_permissions(administrator=True)
async def portfolio_panel(interaction: discord.Interaction, panel_channel: discord.TextChannel):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    f = _portfolio_image_file()
    embed = _build_portfolio_embed(with_image=(f is not None))
    view = PortfolioPanelView()
    if f is not None:
        await panel_channel.send(embed=embed, view=view, file=f)
    else:
        await panel_channel.send(embed=embed, view=view)
    await interaction.followup.send(f"Панель портфеля отправлена в {panel_channel.mention}.", ephemeral=True)


@bot.tree.command(name="панель-отчетов", description="Отправить панель отчётов в выбранный канал")
@app_commands.describe(panel_channel="Канал, куда отправить панель отчётов")
@app_commands.default_permissions(administrator=True)
async def reports_panel(interaction: discord.Interaction, panel_channel: discord.TextChannel):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return

    # Важно: отправка embed + файла может занять >3s, поэтому сразу подтверждаем interaction.
    await interaction.response.defer(ephemeral=True)

    f = _report_image_file()
    embed = _build_report_embed(guild_id=interaction.guild.id, with_image=(f is not None))
    view = ReportPanelView(guild_id=interaction.guild.id)
    existing = get_reports_panel_message_id(guild_id=interaction.guild.id)
    edited = False
    if existing and existing[0] == panel_channel.id:
        try:
            old_msg = await panel_channel.fetch_message(existing[1])
            await old_msg.edit(embed=embed, view=view)
            edited = True
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            edited = False

    if not edited:
        if f is not None:
            msg = await panel_channel.send(embed=embed, view=view, file=f)
        else:
            msg = await panel_channel.send(embed=embed, view=view)
        set_reports_panel_message_id(guild_id=interaction.guild.id, channel_id=panel_channel.id, message_id=msg.id)

    await interaction.followup.send(
        f"Панель отчётов {'обновлена' if edited else 'отправлена'} в {panel_channel.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="баланс", description="Показать баланс баллов пользователя")
@app_commands.describe(пользователь="Если не указан, покажет ваш баланс")
async def points_balance(interaction: discord.Interaction, пользователь: discord.Member | None = None):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return
    target = пользователь or interaction.user
    points = get_user_points(guild_id=interaction.guild.id, user_id=target.id)
    await interaction.response.send_message(
        f"Баланс {target.mention}: **{_fmt_points(points)}**",
        ephemeral=True,
    )


@bot.tree.command(name="баллы-выдать", description="Выдать или списать баллы пользователю")
@app_commands.describe(пользователь="Кому изменить баланс", количество="Положительное число - выдать, отрицательное - списать")
@app_commands.default_permissions(administrator=True)
async def points_grant(interaction: discord.Interaction, пользователь: discord.Member, количество: float):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return
    new_balance = add_user_points(guild_id=interaction.guild.id, user_id=пользователь.id, delta=количество)
    await interaction.response.send_message(
        f"Готово. Новый баланс {пользователь.mention}: **{_fmt_points(new_balance)}**",
        ephemeral=True,
    )


@bot.tree.command(name="баллы-лог", description="Лог баллов: сколько у кого очков")
@app_commands.default_permissions(administrator=True)
async def points_log(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return

    points_map = get_points_map(guild_id=interaction.guild.id)
    if not points_map:
        await interaction.response.send_message("Лог баллов пуст.", ephemeral=True)
        return

    ranked = sorted(points_map.items(), key=lambda x: x[1], reverse=True)
    lines: list[str] = []
    for uid, bal in ranked[:50]:
        lines.append(f"<@{uid}> — **{_fmt_points(bal)}**")
    await interaction.response.send_message(
        "Лог баллов (топ 50):\n" + "\n".join(lines),
        ephemeral=True,
    )


@bot.tree.command(name="карты-взп", description="Панель выбора карт VZP")
@app_commands.default_permissions(administrator=True)
async def vzp_maps_panel(interaction: discord.Interaction):
    if interaction.guild is None or not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return

    await interaction.channel.send(embed=_build_vzp_embed(), view=VzpMapView())
    await interaction.response.send_message("Панель VZP отправлена в канал.", ephemeral=True)


@bot.tree.command(name="настройка-роль-принять", description="Настроить роль, которую выдавать при принятии заявки")
@app_commands.describe(
    действие="Что сделать (установить/очистить/показать)",
    роль="Роль для выдачи при принятии (нужно только для 'установить')",
)
@app_commands.default_permissions(administrator=True)
@app_commands.choices(
    действие=[
        app_commands.Choice(name="установить", value="set"),
        app_commands.Choice(name="очистить", value="clear"),
        app_commands.Choice(name="показать", value="show"),
    ]
)
async def configure_accept_role(
    interaction: discord.Interaction,
    действие: app_commands.Choice[str],
    роль: discord.Role | None = None,
):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return

    guild = interaction.guild

    if действие.value == "show":
        from storage import get_accept_role_id

        rid = get_accept_role_id(guild_id=guild.id)
        pretty = f"<@&{rid}>" if rid else "—"
        await interaction.response.send_message(f"Роль для выдачи при принятии: {pretty}", ephemeral=True)
        return

    if действие.value == "clear":
        set_accept_role_id(guild_id=guild.id, role_id=None)
        await interaction.response.send_message("Готово. Роль для выдачи при принятии очищена.", ephemeral=True)
        return

    if действие.value == "set":
        if роль is None:
            await interaction.response.send_message("Выбери роль в параметре `роль`.", ephemeral=True)
            return
        set_accept_role_id(guild_id=guild.id, role_id=роль.id)
        await interaction.response.send_message(f"Готово. При принятии будет выдаваться роль {роль.mention}.", ephemeral=True)
        return

    await interaction.response.send_message("Неизвестное действие.", ephemeral=True)


@bot.tree.command(name="настройка-смотреть-тикеты", description="Настроить роли, которые могут смотреть каналы тикетов/обзвона")
@app_commands.describe(
    действие="Что сделать (добавить/убрать/список/очистить)",
    роль="Роль (нужно только для добавить/убрать)",
)
@app_commands.default_permissions(administrator=True)
@app_commands.choices(
    действие=[
        app_commands.Choice(name="добавить", value="add"),
        app_commands.Choice(name="убрать", value="remove"),
        app_commands.Choice(name="список", value="list"),
        app_commands.Choice(name="очистить", value="clear"),
    ]
)
async def configure_ticket_view_roles(
    interaction: discord.Interaction,
    действие: app_commands.Choice[str],
    роль: discord.Role | None = None,
):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return

    guild = interaction.guild

    if действие.value == "list":
        role_ids = get_ticket_view_role_ids(guild_id=guild.id)
        pretty = " ".join(f"<@&{rid}>" for rid in role_ids) if role_ids else "—"
        await interaction.response.send_message(f"Роли, которые могут смотреть тикеты: {pretty}", ephemeral=True)
        return

    if действие.value == "clear":
        set_ticket_view_role_ids(guild_id=interaction.guild.id, role_ids=[])
        await interaction.response.send_message("Готово. Доп. роли для просмотра тикетов очищены.", ephemeral=True)
        return

    if роль is None:
        await interaction.response.send_message("Выбери роль в параметре `роль`.", ephemeral=True)
        return

    role_ids = get_ticket_view_role_ids(guild_id=guild.id)

    if действие.value == "add":
        if роль.id not in role_ids:
            role_ids.append(роль.id)
            set_ticket_view_role_ids(guild_id=guild.id, role_ids=role_ids)
        await interaction.response.send_message(
            f"Готово. Роль {роль.mention} добавлена. Теперь смотреть тикеты смогут: "
            f"{' '.join(f'<@&{rid}>' for rid in role_ids)}",
            ephemeral=True,
        )
        return

    if действие.value == "remove":
        if роль.id in role_ids:
            role_ids = [rid for rid in role_ids if rid != роль.id]
            set_ticket_view_role_ids(guild_id=guild.id, role_ids=role_ids)
        pretty = " ".join(f"<@&{rid}>" for rid in role_ids) if role_ids else "—"
        await interaction.response.send_message(
            f"Готово. Роль {роль.mention} убрана. Теперь смотреть тикеты смогут: {pretty}",
            ephemeral=True,
        )
        return

    await interaction.response.send_message("Неизвестное действие.", ephemeral=True)


@bot.tree.command(name="привязка-отпусков", description="Выбрать канал, куда будут отправляться логи отпусков")
@app_commands.describe(send_to="Канал, куда бот будет отправлять логи отпусков")
@app_commands.default_permissions(administrator=True)
async def bind_vacations(interaction: discord.Interaction, send_to: discord.TextChannel):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return
    set_vacation_channel_id(guild_id=interaction.guild.id, channel_id=send_to.id)
    await interaction.response.send_message(
        f"Готово. Теперь логи отпусков будут отправляться в {send_to.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="настройка-роль-отпуск", description="Настроить роль, которую выдавать при уходе в отпуск")
@app_commands.describe(
    действие="Что сделать (установить/очистить/показать)",
    роль="Роль отпуска (нужно только для 'установить')",
)
@app_commands.default_permissions(administrator=True)
@app_commands.choices(
    действие=[
        app_commands.Choice(name="установить", value="set"),
        app_commands.Choice(name="очистить", value="clear"),
        app_commands.Choice(name="показать", value="show"),
    ]
)
async def configure_vacation_role(
    interaction: discord.Interaction,
    действие: app_commands.Choice[str],
    роль: discord.Role | None = None,
):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return
    guild = interaction.guild
    if действие.value == "show":
        rid = get_vacation_role_id(guild_id=guild.id)
        pretty = f"<@&{rid}>" if rid else "—"
        await interaction.response.send_message(f"Роль отпуска: {pretty}", ephemeral=True)
        return
    if действие.value == "clear":
        set_vacation_role_id(guild_id=guild.id, role_id=None)
        await interaction.response.send_message("Готово. Роль отпуска очищена.", ephemeral=True)
        return
    if действие.value == "set":
        if роль is None:
            await interaction.response.send_message("Выбери роль в параметре `роль`.", ephemeral=True)
            return
        set_vacation_role_id(guild_id=guild.id, role_id=роль.id)
        await interaction.response.send_message(f"Готово. Роль отпуска установлена: {роль.mention}.", ephemeral=True)
        return
    await interaction.response.send_message("Неизвестное действие.", ephemeral=True)


@bot.tree.command(name="настройка-снимать-роли-отпуск", description="Настроить роли, которые снимать при уходе в отпуск")
@app_commands.describe(
    действие="Что сделать (добавить/убрать/список/очистить)",
    роль="Роль (нужно только для добавить/убрать)",
)
@app_commands.default_permissions(administrator=True)
@app_commands.choices(
    действие=[
        app_commands.Choice(name="добавить", value="add"),
        app_commands.Choice(name="убрать", value="remove"),
        app_commands.Choice(name="список", value="list"),
        app_commands.Choice(name="очистить", value="clear"),
    ]
)
async def configure_vacation_remove_roles(
    interaction: discord.Interaction,
    действие: app_commands.Choice[str],
    роль: discord.Role | None = None,
):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return
    guild = interaction.guild
    if действие.value == "list":
        role_ids = get_vacation_remove_role_ids(guild_id=guild.id)
        pretty = " ".join(f"<@&{rid}>" for rid in role_ids) if role_ids else "—"
        await interaction.response.send_message(f"Роли для снятия при отпуске: {pretty}", ephemeral=True)
        return
    if действие.value == "clear":
        set_vacation_remove_role_ids(guild_id=guild.id, role_ids=[])
        await interaction.response.send_message("Готово. Список ролей для снятия очищен.", ephemeral=True)
        return
    if роль is None:
        await interaction.response.send_message("Выбери роль в параметре `роль`.", ephemeral=True)
        return
    role_ids = get_vacation_remove_role_ids(guild_id=guild.id)
    if действие.value == "add":
        if роль.id not in role_ids:
            role_ids.append(роль.id)
            set_vacation_remove_role_ids(guild_id=guild.id, role_ids=role_ids)
        await interaction.response.send_message("Готово. Роль добавлена в список снятия.", ephemeral=True)
        return
    if действие.value == "remove":
        if роль.id in role_ids:
            role_ids = [rid for rid in role_ids if rid != роль.id]
            set_vacation_remove_role_ids(guild_id=guild.id, role_ids=role_ids)
        await interaction.response.send_message("Готово. Роль убрана из списка снятия.", ephemeral=True)
        return
    await interaction.response.send_message("Неизвестное действие.", ephemeral=True)


def _panel_image_file() -> discord.File | None:
    p = Path(__file__).resolve().parent / "foto" / PANEL_IMAGE_FILENAME
    if p.exists() and p.is_file():
        return discord.File(str(p), filename=PANEL_IMAGE_FILENAME)
    return None


@bot.tree.command(name="привязка-заявок", description="Выбрать канал, куда будут отправляться заявки")
@app_commands.describe(send_to="Канал, куда бот будет отправлять заявки")
@app_commands.default_permissions(administrator=True)
async def bind_applications(interaction: discord.Interaction, send_to: discord.TextChannel):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return

    set_destination_channel_id(guild_id=interaction.guild.id, channel_id=send_to.id)
    await interaction.response.send_message(
        f"Готово. Теперь заявки будут отправляться в {send_to.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="панель-заявок", description="Отправить панель заявок в выбранный канал")
@app_commands.describe(panel_channel="Канал, куда отправить панель")
@app_commands.default_permissions(administrator=True)
async def applications_panel(interaction: discord.Interaction, panel_channel: discord.TextChannel):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return

    destination_id = get_destination_channel_id(guild_id=interaction.guild.id) or config.APPLICATION_CHANNEL_ID
    if not destination_id:
        await interaction.response.send_message(
            "Сначала сделай `/привязка-заявок` и выбери канал для заявок (или заполни `APPLICATION_CHANNEL_ID` в `.env`).",
            ephemeral=True,
        )
        return

    f = _panel_image_file()
    embed = build_panel_embed(with_image=(f is not None))
    view = ApplicationPanelView(destination_channel_id=int(destination_id))

    # Если панель уже была отправлена раньше — обновляем (edit), чтобы не плодить сообщения
    existing = get_panel_message_id(guild_id=interaction.guild.id)
    edited = False
    if existing and existing[0] == panel_channel.id:
        try:
            old_msg = await panel_channel.fetch_message(existing[1])
            # Важно: при edit НЕ пере-заливаем файл. Это стабильно обновляет 1 сообщение,
            # а уже прикреплённый `panel.png` остаётся у сообщения.
            await old_msg.edit(embed=embed, view=view)
            edited = True
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            edited = False

    if not edited:
        if f is not None:
            msg = await panel_channel.send(embed=embed, view=view, file=f)
        else:
            msg = await panel_channel.send(embed=embed, view=view)
        set_panel_message_id(guild_id=interaction.guild.id, channel_id=panel_channel.id, message_id=msg.id)

    await interaction.response.send_message(
        f"Панель {'обновлена' if edited else 'отправлена'} в {panel_channel.mention}. Заявки будут уходить в <#{destination_id}>.",
        ephemeral=True,
    )


@bot.tree.command(name="афк-панель", description="Отправить AFK-панель в выбранный канал")
@app_commands.describe(panel_channel="Канал, куда отправить AFK-панель")
@app_commands.default_permissions(administrator=True)
async def afk_panel(interaction: discord.Interaction, panel_channel: discord.TextChannel):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return

    f = _afk_image_file()
    embed = build_afk_panel_embed(with_image=(f is not None))
    view = AFKPanelView()

    existing = get_afk_panel_message_id(guild_id=interaction.guild.id)
    edited = False
    if existing and existing[0] == panel_channel.id:
        try:
            old_msg = await panel_channel.fetch_message(existing[1])
            await old_msg.edit(embed=embed, view=view)
            edited = True
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            edited = False

    if not edited:
        if f is not None:
            msg = await panel_channel.send(embed=embed, view=view, file=f)
        else:
            msg = await panel_channel.send(embed=embed, view=view)
        set_afk_panel_message_id(guild_id=interaction.guild.id, channel_id=panel_channel.id, message_id=msg.id)

    await interaction.response.send_message(
        f"AFK-панель {'обновлена' if edited else 'отправлена'} в {panel_channel.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="отпуск-панель", description="Отправить панель отпусков в выбранный канал")
@app_commands.describe(panel_channel="Канал, куда отправить панель отпусков")
@app_commands.default_permissions(administrator=True)
async def vacation_panel(interaction: discord.Interaction, panel_channel: discord.TextChannel):
    if interaction.guild is None:
        await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        return

    f = _vacation_image_file()
    embed = build_vacation_panel_embed(with_image=(f is not None))
    view = VacationPanelView()

    existing = get_vacation_panel_message_id(guild_id=interaction.guild.id)
    edited = False
    if existing and existing[0] == panel_channel.id:
        try:
            old_msg = await panel_channel.fetch_message(existing[1])
            await old_msg.edit(embed=embed, view=view)
            edited = True
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            edited = False

    if not edited:
        if f is not None:
            msg = await panel_channel.send(embed=embed, view=view, file=f)
        else:
            msg = await panel_channel.send(embed=embed, view=view)
        set_vacation_panel_message_id(guild_id=interaction.guild.id, channel_id=panel_channel.id, message_id=msg.id)

    await interaction.response.send_message(
        f"Панель отпусков {'обновлена' if edited else 'отправлена'} в {panel_channel.mention}.",
        ephemeral=True,
    )


@bot.event
async def on_ready():
    if bot.user:
        print(f"Logged in as {bot.user} (ID: {bot.user.id})")


@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    actor = await _find_recent_audit_actor(guild=guild, action=discord.AuditLogAction.ban, target_id=user.id)
    if actor is None:
        return
    await _send_action_log(guild=guild, action_name="Бан на сервере", actor=actor, target=user)


@bot.event
async def on_member_join(member: discord.Member):
    if member.guild is None or member.bot:
        return
    await _send_join_leave_log(
        guild=member.guild,
        action_name="Зашёл на сервер",
        member=member,
    )


@bot.event
async def on_presence_update(before: discord.Member | discord.User, after: discord.Member | discord.User):
    if not isinstance(after, discord.Member) or after.guild is None or after.bot:
        return

    guild = after.guild
    channel_id = get_stream_announce_channel_id(guild_id=guild.id)
    if channel_id is None:
        return
    allowed_user_ids = get_stream_announce_user_ids(guild_id=guild.id)
    if not allowed_user_ids or after.id not in allowed_user_ids:
        return
    twitch_map = get_stream_announce_twitch_map(guild_id=guild.id)
    mapped_login = twitch_map.get(after.id)
    if mapped_login and config.TWITCH_CLIENT_ID and config.TWITCH_CLIENT_SECRET:
        # Для привязанных Twitch-стримеров при наличии Twitch API
        # уведомления отправляет Twitch watcher.
        return

    def _is_streaming(m: discord.Member | discord.User) -> bool:
        for activity in getattr(m, "activities", []) or []:
            if isinstance(activity, discord.Streaming):
                return True
        return False

    was_streaming = _is_streaming(before)
    is_streaming = _is_streaming(after)

    if not was_streaming and is_streaming:
        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                channel = None
        if not isinstance(channel, discord.TextChannel):
            return

        twitch_url = None
        for activity in after.activities:
            if isinstance(activity, discord.Streaming) and activity.url:
                twitch_url = activity.url
                break
        if twitch_url is None and mapped_login:
            twitch_url = f"https://twitch.tv/{mapped_login}"

        text = f"@everyone 🔴 {after.mention} запустил стрим!"
        if twitch_url:
            text += f" Заходи смотреть: {twitch_url}"
        try:
            await channel.send(text, allowed_mentions=discord.AllowedMentions(everyone=True, users=True))
        except (discord.Forbidden, discord.HTTPException):
            return


@bot.event
async def on_member_remove(member: discord.Member):
    if member.guild is None or member.bot:
        return
    actor = await _find_recent_audit_actor(
        guild=member.guild,
        action=discord.AuditLogAction.kick,
        target_id=member.id,
    )
    if actor is None:
        await _send_join_leave_log(
            guild=member.guild,
            action_name="Вышел с сервера",
            member=member,
        )
        return
    await _send_action_log(guild=member.guild, action_name="Исключение с сервера", actor=actor, target=member)


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if member.bot or member.guild is None:
        return

    guild = member.guild
    if before.mute != after.mute:
        actor = await _find_recent_audit_actor(
            guild=guild,
            action=discord.AuditLogAction.member_update,
            target_id=member.id,
            max_age_s=12,
        )
        if actor is not None:
            await _send_action_log(
                guild=guild,
                action_name="Отключил/включил микрофон (сервером)",
                actor=actor,
                target=member,
            )
    if before.deaf != after.deaf:
        actor = await _find_recent_audit_actor(
            guild=guild,
            action=discord.AuditLogAction.member_update,
            target_id=member.id,
            max_age_s=12,
        )
        if actor is not None:
            await _send_action_log(
                guild=guild,
                action_name="Отключил/включил наушники (сервером)",
                actor=actor,
                target=member,
            )
    if before.channel is not None and after.channel is None:
        actor = await _find_recent_audit_actor(
            guild=guild,
            action=discord.AuditLogAction.member_disconnect,
            target_id=member.id,
            max_age_s=12,
        )
        if actor is not None and actor.id != member.id:
            await _send_action_log(
                guild=guild,
                action_name="Кик из голосового канала",
                actor=actor,
                target=member,
            )

    # Удаляем пустые временные комнаты, созданные ботом.
    if before.channel is not None and len(before.channel.members) == 0:
        if get_temp_voice_owner_id(guild_id=guild.id, channel_id=before.channel.id) is not None:
            remove_temp_voice_owner_id(guild_id=guild.id, channel_id=before.channel.id)
            try:
                await before.channel.delete(reason="Временная комната пуста")
            except (discord.Forbidden, discord.HTTPException):
                pass

    lobby_id = get_voice_lobby_channel_id(guild_id=guild.id)
    if lobby_id is None:
        return
    if after.channel is None or after.channel.id != lobby_id:
        return
    if before.channel is not None and before.channel.id == lobby_id:
        return

    lobby_channel = after.channel
    if not isinstance(lobby_channel, discord.VoiceChannel):
        return

    room_name = f"Комната • {member.display_name}"[:100]
    try:
        temp_channel = await guild.create_voice_channel(
            name=room_name,
            category=lobby_channel.category,
            reason=f"Авто-комната для {member}",
        )
    except (discord.Forbidden, discord.HTTPException):
        return

    # Сохраняем правила категории (видимость/доступ), а поверх даём владельцу управление комнатой.
    try:
        await temp_channel.set_permissions(
            member,
            connect=True,
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            speak=True,
            stream=True,
            use_voice_activation=True,
            priority_speaker=True,
            move_members=True,
            mute_members=True,
            deafen_members=True,
            manage_channels=True,
        )
        if guild.me is not None:
            await temp_channel.set_permissions(
                guild.me,
                connect=True,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                move_members=True,
                manage_channels=True,
            )
    except (discord.Forbidden, discord.HTTPException):
        pass

    set_temp_voice_owner_id(guild_id=guild.id, channel_id=temp_channel.id, owner_id=member.id)

    try:
        await member.move_to(temp_channel, reason="Перенос в личную авто-комнату")
    except (discord.Forbidden, discord.HTTPException):
        remove_temp_voice_owner_id(guild_id=guild.id, channel_id=temp_channel.id)
        try:
            await temp_channel.delete(reason="Не удалось перенести владельца")
        except (discord.Forbidden, discord.HTTPException):
            pass
        return

    # Пишем панель в чат голосового канала (если у сервера/клиента доступен voice text chat API).
    panel_embed = _build_voice_room_control_embed(owner=member)
    sent_panel = False
    if hasattr(temp_channel, "send"):
        # После создания voice-канала его текстовый чат может стать доступен не мгновенно.
        for _ in range(5):
            try:
                await temp_channel.send(embed=panel_embed, view=VoiceRoomControlView())  # type: ignore[attr-defined]
                sent_panel = True
                break
            except (discord.Forbidden, TypeError):
                break
            except discord.HTTPException:
                await asyncio.sleep(1.0)
    if not sent_panel:
        try:
            await member.send(embed=panel_embed)
        except (discord.Forbidden, discord.HTTPException):
            pass


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return

    trigger = message.content.strip().lower()
    if trigger in {
        "!картывзп",
        "!карты-взп",
        "!vzp",
        "!mapsvzp",
        ".картывзп",
        ".карты-взп",
    }:
        if not isinstance(message.author, discord.Member):
            return
        if not (message.author.guild_permissions.administrator or message.author.guild_permissions.manage_guild):
            return
        await message.channel.send(embed=_build_vzp_embed(), view=VzpMapView())
        try:
            await message.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass


bot.run(config.DISCORD_TOKEN)

