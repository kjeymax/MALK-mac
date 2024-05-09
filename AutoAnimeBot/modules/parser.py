import asyncio
import requests
from AutoAnimeBot.core.log import LOGGER
from AutoAnimeBot.modules.schedule import update_schedule
from AutoAnimeBot.modules.db import get_animesdb, get_uploads, is_failed, save_animedb

logger = LOGGER("Parser")

class TechZApi:
    """
    Python wrapper

    - Base Url : api3.kajmax.workers.dev
    - Documentation : [Click Here](https://api3.kajmax.workers.dev/docs)
    """

    def __init__(self) -> None:
        self.base = "https://api-consumet-dlst3n16z-kjeymaxs-projects.vercel.app/anime/gogoanime"

    def get_recent_anime(self, page=1):
        """
        Get recent animes
        """
        data = requests.get(
            f"{self.base}/recent/{page}"
        ).json()
        return data["results"]

async def auto_parser(app):
    techz_api = TechZApi()  # Create an instance of your custom class

    while True:
        await app.update_status("Scrapping Animes...")

        data = techz_api.get_recent_anime()  # Call the method from your custom class
        saved = await get_animesdb()
        uploaded = await get_uploads()

        saved_anime = []
        for i in saved:
            saved_anime.append(i["id"])

        uanimes = {}
        for i in uploaded:
            if i["id"] not in uanimes:
                uanimes[i["id"]] = set()
            if i.get("q"):
                uanimes[i["id"]] = set(i["q"])

        pos = len(saved_anime) + 1
        for i in data:
            if i["id"] not in saved_anime:
                if i["id"] in uanimes:
                    if uanimes[i["id"]] == {"360p", "480p", "720p", "1080p"}:
                        continue

                id = i["id"]
                if not (await is_failed(id)):
                    await save_animedb(id, pos)
                    pos += 1

        saved = await get_animesdb()
        for i in saved:
            if i["id"] not in app.queue:
                app.queue.append(i["id"])
                logger.info(f'Saved To Queue --> {i["id"]}')

        await update_schedule(app)
        await app.update_status("Idle...")

        await asyncio.sleep(600)

# The rest of your code remains unchanged
