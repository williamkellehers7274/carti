from __future__ import annotations

import datetime as dt

import discord


PANEL_IMAGE_FILENAME = "panel.png"


def build_panel_embed(*, with_image: bool = False) -> discord.Embed:
    embed = discord.Embed(
        title="Приём заявок",
        description=(
            "**Оформление заявки.**\n"
            "**После отправки анкеты сразу создаётся отдельный тикет-канал с вами.**\n\n"
            "> **В канале команда рассматривает заявку и выносит решение: Принять / Отказать.**\n\n"
            "**Также продублируем ссылку на тикет в личные сообщения, чтобы вы ничего не пропустили.**\n"
            "**Подать заявку:**"
        ),
        color=discord.Color.dark_gray(),
    )
    if with_image:
        # "Вверху" — через thumbnail (в правом верхнем углу embed)
        embed.set_thumbnail(url=f"attachment://{PANEL_IMAGE_FILENAME}")
    embed.set_footer(text="Carti • Заявки")
    return embed


def build_application_embed(
    *,
    ticket_id: int,
    application_type: str,
    applicant: discord.abc.User,
    answers: dict[str, str],
    status: str = "⏳ На рассмотрении",
) -> discord.Embed:
    embed = discord.Embed(
        title=f"Заявка #{ticket_id} — {application_type}",
        # Чёрная "палочка" слева (темный цвет)
        color=discord.Color.dark_gray(),
        timestamp=dt.datetime.now(dt.timezone.utc),
    )
    embed.add_field(name="Статус", value=f"**{status}**", inline=False)
    embed.add_field(name="Заявитель", value=f"{applicant.mention}\n`{applicant}`\n`ID: {applicant.id}`", inline=False)

    for q, a in answers.items():
        embed.add_field(name=q, value=(a[:1024] if a else "—"), inline=False)

    embed.set_footer(text="Отправлено через Embed v2")
    if getattr(applicant, "display_avatar", None):
        embed.set_thumbnail(url=applicant.display_avatar.url)
    return embed

