import asyncio
import os
import requests
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
    is_voted,
    save_vote,
    is_uploaded,
)
from AutoAnimeBot.modules.downloader import downloader
from AutoAnimeBot.modules.anilist import get_anilist_data, get_anime_img, get_anime_name
from AutoAnimeBot.inline import button1
from config import (
    INDEX_CHANNEL_USERNAME,
    UPLOADS_CHANNEL_USERNAME,
    SLEEP_TIME,
)
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram import filters
from pyrogram.client import Client

logger = LOGGER("TgHandler")
app = Client


async def tg_handler(appp):
    global app
    app = appp
    queue = app.queue

    while True:
        if len(queue) != 0:
            try:
                i = queue[0]
                logger.info("Processing : " + i)

                # Fetch episode links
                episode_url = f"https://api3.kajmax.workers.dev/download/{i}"
                data = await fetch_episode_links(episode_url)

                if data:
                    dlinks = data.get("results", {})
                    for q, l in dlinks.items():
                        if await is_quality_uploaded(i, q):
                            continue
                        if await is_failed(f"{i}-{q}"):
                            continue

                        video_id, anime_id, name, ep_num = await start_uploading(
                            app, q, l, i
                        )

                        await app.update_status(
                            f"Adding Links To Index Channel ({INDEX_CHANNEL_USERNAME})..."
                        )
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
                    logger.warning("Failed to fetch episode links for", i)
                    await asyncio.sleep(SLEEP_TIME)  # Sleep and retry
            except Exception as e:
                logger.warning(str(e))
                await del_anime(i)
                await add_to_failed(f"{i}-{q}")
                queue.pop(0)
        else:
            if "Idle..." not in app.status.text:
                await app.update_status("Idle...")
                await asyncio.sleep(SLEEP_TIME)
            else:
                await asyncio.sleep(SLEEP_TIME)


async def fetch_episode_links(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logger.warning("Failed to fetch episode links:", response.status_code)
            return None
    except Exception as e:
        logger.warning("An error occurred while fetching episode links:", str(e))
        return None


async def start_uploading(app, q, eid):
    try:
        title = eid.replace("-", " ").title().strip() + f" - {q}"
        file_name = f"{title} [@{UPLOADS_CHANNEL_USERNAME}].mp4"

        anime = eid.split("-episode-")[0].replace("-", " ").title().strip()
        id, img, tit = await get_anime_img(anime)
        msg = await app.send_photo(app.UPLOADS_CHANNEL_ID, photo=img, caption=title)

        await app.update_status(f"Downloading {title}")
        file = await downloader(msg, title, file_name)

        await app.update_status(f"Uploading {title}")
        video_id = await upload_video(app, msg, file, id, tit, title, eid)

        return video_id, id, tit, eid.split("-episode-")[1]
    except Exception as e:
        logger.warning(str(e))
        try:
            await msg.delete()
        except:
            pass



EPITEXT = """
🔰 **Episodes :**

{}
"""

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
            episodes[ep_num].append((quality, video_id))
            await save_channel(anime_id, post, dl_id, episodes)

            text = ""
            for ep, data in episodes.items():
                line = f"➤ **Episode {ep}** : "
                for q, v in data:
                    line += f"[{q}](https://t.me/{UPLOADS_CHANNEL_USERNAME}/{v}) | "

                x = line[:-3] + "\n"

                if len(x) + len(text) > 4000:
                    dl = await app.send_message(
                        app.INDEX_CHANNEL_ID,
                        EPITEXT.format(x),
                        disable_web_page_preview=True,
                        reply_to_message_id=post,
                    )
                    dl_id = int(dl.id)
                    await save_channel(anime_id, post, dl_id, {ep: data})

                else:
                    text += x
                    await app.edit_message_text(
                        app.INDEX_CHANNEL_ID,
                        dl_id,
                        EPITEXT.format(text),
                        disable_web_page_preview=True,
                    )

        main_id = dl_id
        info_id = main_id - 1
        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="Info",
                        url=f"https://t.me/{INDEX_CHANNEL_USERNAME}/{info_id}",
                    ),
                    InlineKeyboardButton(
                        text="Comments",
                        url=f"https://t.me/{INDEX_CHANNEL_USERNAME}/{main_id}?thread={main_id}",
                    ),
                ]
            ]
        )
        await app.edit_message_reply_markup(
            app.UPLOADS_CHANNEL_ID, video_id, reply_markup=buttons
        )
    except Exception as e:
        logger.warning(str(e))
