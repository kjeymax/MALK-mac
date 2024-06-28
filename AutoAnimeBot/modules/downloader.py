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
    logger.info(f"Starting download for {title}")

    downloads_dir = "downloads"
    
    # Ensure downloads directory exists
    if os.path.exists(downloads_dir):
        shutil.rmtree(downloads_dir)
    os.makedirs(downloads_dir, exist_ok=True)

    file_path = os.path.join(downloads_dir, file_name)
    
    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': file_path,
            'noplaylist': True,
            'allow_multiple_video_streams': True,
            'allow_multiple_audio_streams': True,
            'concurrent_fragments': 4,  # Set the maximum number of concurrent fragments           
            'fragment_retries': 10,     # Number of times to retry downloading a fragment
            'hls_prefer_native': False, # Use ffmpeg instead of the native HLS downloader
            'progress_hooks': [lambda d: progress_text(d, message)],
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            total = info_dict.get('filesize', 0)

        logger.info(f"Successfully downloaded {title}")
        return file_path

    except yt_dlp.utils.DownloadError as e:
        logger.warning(f"Download error: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error: {e}")

    return None
