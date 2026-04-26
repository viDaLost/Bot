from datetime import datetime, timedelta
import calendar

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from astral import LocationInfo
from astral.sun import sun
from aiogram import Bot
from aiogram.types import FSInputFile

from config import ADMIN_IDS
from database import (
    add_send_log,
    get_active_jobs,
    mark_job_done,
    update_job_last_sent,
)
from image_generator import create_sunset_image

scheduler = AsyncIOScheduler()

WEEKDAY_NAME_TO_NUM = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def calculate_sunset_minus_hour(
    location_name: str,
    latitude: float,
    longitude: float,
    timezone: str,
    target_date: str,
) -> str:
    tz = pytz.timezone(timezone)
    loc = LocationInfo(location_name, "", timezone, latitude, longitude)
    d = datetime.strptime(target_date, "%Y-%m-%d").date()
    s = sun(loc.observer, date=d, tzinfo=tz)
    return (s["sunset"] - timedelta(hours=1)).strftime("%H:%M")


def _current_target_date(job) -> str:
    if job["schedule_type"] == "once":
        return job["publish_date"]
    tz = pytz.timezone(job["timezone"])
    return datetime.now(tz).strftime("%Y-%m-%d")


def _sent_key(job, target_date: str) -> str:
    return f"{job['id']}:{target_date}:{job['publish_time']}"


async def _notify_admins(bot: Bot, text: str):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass


async def send_job(bot: Bot, job):
    target_date = _current_target_date(job)
    key = _sent_key(job, target_date)

    if job["schedule_type"] != "once" and job["last_sent_key"] == key:
        return

    try:
        sunset_minus_hour = calculate_sunset_minus_hour(
            job["location_name"],
            job["latitude"],
            job["longitude"],
            job["timezone"],
            target_date,
        )

        image_path = create_sunset_image(
            sunset_time=sunset_minus_hour,
            publish_date=target_date,
            style=job["image_style"] or "classic",
            title_text=job["title_text"] or "Заход солнца",
            location_name=job["location_name"],
            show_city=bool(job["show_city"]),
            show_weekday=bool(job["show_weekday"]),
        )

        # В канал/чат отправляется только картинка, без подписи.
        await bot.send_photo(
            chat_id=job["chat_id"],
            photo=FSInputFile(image_path),
        )

        await add_send_log(
            job_id=job["id"],
            owner_id=job["owner_id"],
            target_id=job["target_id"],
            status="success",
            target_date=target_date,
            sunset_time=sunset_minus_hour,
        )

        if job["schedule_type"] == "once":
            await mark_job_done(job["id"])
        else:
            await update_job_last_sent(job["id"], key)

    except Exception as e:
        error = str(e)
        await add_send_log(
            job_id=job["id"],
            owner_id=job["owner_id"],
            target_id=job["target_id"],
            status="error",
            target_date=target_date,
            sunset_time="",
            error=error[:900],
        )
        await _notify_admins(
            bot,
            "❌ Ошибка отправки\n\n"
            f"Расписание ID: {job['id']}\n"
            f"Канал/чат: {job['target_title']}\n"
            f"Ошибка: {error}",
        )
        raise


def remove_scheduled_job(job_id: int):
    prefix = f"job_{job_id}"
    for existing in list(scheduler.get_jobs()):
        if existing.id == prefix or existing.id.startswith(prefix + "_"):
            try:
                scheduler.remove_job(existing.id)
            except Exception:
                pass


def schedule_single_job(bot: Bot, job):
    remove_scheduled_job(job["id"])

    if job["status"] != "active":
        return

    hour, minute = [int(x) for x in job["publish_time"].split(":")]

    if job["schedule_type"] == "once":
        if not job["publish_date"]:
            return
        tz = pytz.timezone(job["timezone"])
        run_dt = tz.localize(
            datetime.strptime(
                f"{job['publish_date']} {job['publish_time']}",
                "%Y-%m-%d %H:%M",
            )
        )
        if run_dt <= datetime.now(tz):
            return
        scheduler.add_job(
            send_job,
            trigger="date",
            run_date=run_dt,
            args=[bot, job],
            id=f"job_{job['id']}",
            replace_existing=True,
        )
        return

    if job["schedule_type"] == "daily":
        scheduler.add_job(
            send_job,
            trigger="cron",
            hour=hour,
            minute=minute,
            timezone=job["timezone"],
            args=[bot, job],
            id=f"job_{job['id']}",
            replace_existing=True,
        )
        return

    if job["schedule_type"] == "weekly":
        weekdays = [x.strip() for x in (job["weekdays"] or "").split(",") if x.strip()]
        nums = [str(WEEKDAY_NAME_TO_NUM[x]) for x in weekdays if x in WEEKDAY_NAME_TO_NUM]
        if not nums:
            return
        scheduler.add_job(
            send_job,
            trigger="cron",
            day_of_week=",".join(nums),
            hour=hour,
            minute=minute,
            timezone=job["timezone"],
            args=[bot, job],
            id=f"job_{job['id']}",
            replace_existing=True,
        )
        return

    if job["schedule_type"] == "monthly":
        day = int(job["month_day"] or 1)
        day = max(1, min(31, day))
        scheduler.add_job(
            send_job,
            trigger="cron",
            day=str(day),
            hour=hour,
            minute=minute,
            timezone=job["timezone"],
            args=[bot, job],
            id=f"job_{job['id']}",
            replace_existing=True,
        )


async def restore_jobs(bot: Bot):
    jobs = await get_active_jobs()
    for job in jobs:
        schedule_single_job(bot, job)


def next_run_text(job) -> str:
    job_id = f"job_{job['id']}"
    for existing in scheduler.get_jobs():
        if existing.id == job_id or existing.id.startswith(job_id + "_"):
            if existing.next_run_time:
                return existing.next_run_time.strftime("%Y-%m-%d %H:%M")
    return "не запланировано"
