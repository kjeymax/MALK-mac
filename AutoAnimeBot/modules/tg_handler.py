import asyncio
import requests
import json
from AutoAnimeBot.core.log import LOGGER
from AutoAnimeBot.modules.uploader import upload_video
from AutoAnimeBot.modules.db import (
    add_to_failed,
    del_anime,
    get_channel,
    is_failed,
    is_quality_uploaded,
    save_channel,
    save_uploads,
)
from AutoAnimeBot.modules.downloader import downloader
from AutoAnimeBot.modules.anilist import get_anilist_data, get_anime_img
from config import INDEX_CHANNEL_USERNAME, UPLOADS_CHANNEL_USERNAME, SLEEP_TIME
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import Client

logger = LOGGER("TgHandler")
app = Client

async def tg_handler(appp):
    global app
    app = appp
    queue = app.queue

    while True:
        if queue:
            i = queue[0]
            logger.info(f"Processing: {i}")
            try:
                episode_url = f"https://api3.kajmax.workers.dev/download/{i}"
                data = await fetch_episode_links(episode_url)

                if data:
                    dlinks = data.get("results", {})
                    for q, l in dlinks.items():
                        if await is_quality_uploaded(i, q) or await is_failed(f"{i}-{q}"):
                            continue
                        video_id, anime_id, name, ep_num = await start_uploading(app, q, l, i)
                        await app.update_status(f"Adding Links To Index Channel ({INDEX_CHANNEL_USERNAME})...")
                        await channel_handler(video_id, anime_id, name, ep_num, q)
                        await save_uploads(i, q)
                        await app.update_status(f"Sleeping for {SLEEP_TIME} seconds")
                        await asyncio.sleep(SLEEP_TIME)

                    for q in ["360p", "480p", "720p", "1080p"]:
                        if q not in dlinks:
                            await save_uploads(i, q)
                    await del_anime(i)
                    queue.pop(0)
                else:
                    logger.warning(f"Failed to fetch episode links for {i}")
                    await asyncio.sleep(SLEEP_TIME)
            except Exception as e:
                logger.error(f"Error processing {i}: {e}")
                await del_anime(i)
                await add_to_failed(f"{i}-{q}")
                queue.pop(0)
        else:
            if "Idle..." not in app.status.text:
                await app.update_status("Idle...")
            await asyncio.sleep(SLEEP_TIME)

async def fetch_episode_links(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Failed to fetch episode links: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"An error occurred while fetching episode links: {e}")
        return None

async def start_uploading(app, q, l, eid):
    title = eid.replace("-", " ").title().strip() + f" - {q}"
    file_name = f"{title} [@{UPLOADS_CHANNEL_USERNAME}].mp4"
    anime = eid.split("-episode-")[0].replace("-", " ").title().strip()

    try:
        id, img, tit = await get_anime_img(anime)
        msg = await app.send_photo(app.UPLOADS_CHANNEL_ID, photo=img, caption=title)
        await app.update_status(f"Downloading {title}")
        file = await downloader(msg, l, title, file_name)
        await app.update_status(f"Uploading {title}")
        video_id = await upload_video(app, msg, file, id, tit, title, eid)
        return video_id, id, tit, eid.split("-episode-")[1]
    except Exception as e:
        logger.error(f"Error in start_uploading for {eid}: {e}")
        if msg:
            try:
                await msg.delete()
            except Exception as del_e:
                logger.error(f"Error deleting message: {del_e}")
        return None, None, None, None

import json

async def channel_handler(video_id, anime_id, name, ep_num, quality):
    try:
        dl_id, episodes, post = await get_channel(anime_id)
        if dl_id == 0:
            img, caption = await get_anilist_data(name)
            main = await app.send_photo(
                app.INDEX_CHANNEL_ID,
                photo=img,
                caption=caption,
            )
            link = f"➤ **Episode {ep_num}** : [{quality}](https://t.me/{UPLOADS_CHANNEL_USERNAME}/{video_id})"

            dl = await app.send_message(
                app.INDEX_CHANNEL_ID,
                EPITEXT.format(link),
                disable_web_page_preview=True,
            )
            await app.send_sticker(
                app.INDEX_CHANNEL_ID,
                "CAACAgUAAxkBAAEZVLlmFn2q7tDBSl5MNw8lW9k1Ak4U2gACFQ8AAnAfsVRLXl7c2z-pxDQE",
            )

            dl_id = int(dl.id)
            post = int(main.id)

            caption += f"\n📥 **Download -** [{name}](https://t.me/{INDEX_CHANNEL_USERNAME}/{dl_id})"
            await main.edit_caption(caption)
            episode = {ep_num: [(quality, video_id)]}
            await save_channel(anime_id, post=post, dl_id=dl_id, episodes=episode)

        else:
            if ep_num not in episodes:
                episodes[ep_num] = []
            episodes[ep_num].append((quality, video_id))
            await save_channel(anime_id, post, dl_id, episodes)

            text = generate_episodes_text(episodes)
            if len(text) > 4000:
                dl = await app.send_message(
                    app.INDEX_CHANNEL_ID,
                    EPITEXT.format(text),
                    disable_web_page_preview=True,
                    reply_to_message_id=post,
                )
                dl_id = int(dl.id)
                await save_channel(anime_id, post, dl_id, episodes)
            else:
                await app.edit_message_text(app.INDEX_CHANNEL_ID, dl_id, EPITEXT.format(text), disable_web_page_preview=True)

        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(text="Info", url=f"https://t.me/{INDEX_CHANNEL_USERNAME}/{dl_id - 1}"),
                    InlineKeyboardButton(text="Comments", url=f"https://t.me/{INDEX_CHANNEL_USERNAME}/{dl_id}?thread={dl_id}")
                ]
            ]
        )
        await app.edit_message_reply_markup(app.UPLOADS_CHANNEL_ID, video_id, reply_markup=buttons)
    except KeyError as e:
        logger.error(f"KeyError in channel_handler: {e}")
        logger.error(f"Anime ID: {anime_id}, Episodes: {json.dumps(episodes, indent=2)}, Post: {post}, DL ID: {dl_id}")
    except Exception as e:
        logger.error(f"Error in channel_handler: {e}")
        logger.error(f"Anime ID: {anime_id}, Episodes: {json.dumps(episodes, indent=2)}, Post: {post}, DL ID: {dl_id}")

def generate_episodes_text(episodes):
    text = ""
    for ep, data in episodes.items():
        line = f"➤ **Episode {ep}** : " + " | ".join([f"[{q}](https://t.me/{UPLOADS_CHANNEL_USERNAME}/{v})" for q, v in data]) + "\n"
        text += line
    return text


def generate_episodes_text(episodes):
    text = ""
    for ep, data in episodes.items():
        line = f"➤ **Episode {ep}** : " + " | ".join([f"[{q}](https://t.me/{UPLOADS_CHANNEL_USERNAME}/{v})" for q, v in data]) + "\n"
        text += line
    return text

EPITEXT = """
🔰 **Episodes :**

{}
"""

async def tg_handler(appp):
    global app
    app = appp
    queue = app.queue

    while True:
        if queue:
            i = queue[0]
            logger.info(f"Processing: {i}")
            try:
                episode_url = f"https://api3.kajmax.workers.dev/download/{i}"
                data = await fetch_episode_links(episode_url)

                if data:
                    dlinks = data.get("results", {})
                    for q, l in dlinks.items():
                        if await is_quality_uploaded(i, q) or await is_failed(f"{i}-{q}"):
                            continue
                        video_id, anime_id, name, ep_num = await start_uploading(app, q, l, i)
                        await app.update_status(f"Adding Links To Index Channel ({INDEX_CHANNEL_USERNAME})...")
                        await channel_handler(video_id, anime_id, name, ep_num, q)
                        await save_uploads(i, q)
                        await app.update_status(f"Sleeping for {SLEEP_TIME} seconds")
                        await asyncio.sleep(SLEEP_TIME)

                    for q in ["360p", "480p", "720p", "1080p"]:
                        if q not in dlinks:
                            await save_uploads(i, q)
                    await del_anime(i)
                    queue.pop(0)
                else:
                    logger.warning(f"Failed to fetch episode links for {i}")
                    await asyncio.sleep(SLEEP_TIME)
            except Exception as e:
                logger.error(f"Error processing {i}: {e}")
                await del_anime(i)
                await add_to_failed(f"{i}-{q}")
                queue.pop(0)
        else:
            if "Idle..." not in app.status.text:
                await app.update_status("Idle...")
            await asyncio.sleep(SLEEP_TIME)
