#KMAC coding
import os
import shutil
import time
import aiofiles
import yt_dlp
from pyrogram.types import Message
from AutoAnimeBot.core.log import LOGGER
from AutoAnimeBot.modules.progress import progress_text

logger = LOGGER("Downloader")

async def downloader(message: Message, url: str, title: str, file_name: str):
    logger.info(f"Downloading {title}")

    try:
        shutil.rmtree("downloads")
    except FileNotFoundError:
        pass

    if not os.path.exists("downloads"):
        os.mkdir("downloads")

    file_path = f"downloads/{file_name}"

    t1 = time.time()
    dcount = 1  # Downloaded count in 10 sec

    try:
        ydl_opts = {
              'format': 'best',
              'outtmpl': file_path,
              'noplaylist': True,
              'downloader': 'ffmpeg',
              'fragment_retries': 10,  # Number of times to retry downloading a fragment
              'hls_prefer_native': False,  # Use ffmpeg instead of the native HLS downloader
              'external_downloader_args': ['--hls-use-mpegts'],  # Use mpegts format for HLS
}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            total = info_dict.get('filesize', 0)

        logger.info(f"Downloaded {title}")
        return file_path

    except yt_dlp.utils.DownloadError as e:
        logger.warning(str(e))
    except Exception as e:
        logger.warning(str(e))
    
    return None
