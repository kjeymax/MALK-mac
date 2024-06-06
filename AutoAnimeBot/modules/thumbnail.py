import cv2
import random
from bs4 import BeautifulSoup as bs
import requests
from PIL import Image, ImageOps, ImageFilter, ImageDraw, ImageFont
from string import ascii_uppercase, digits
import os
import asyncio
from config import CHANNEL_TITLE

MAX_RETRIES = 5
FONT_PATHS = {
    "font1": "assets/Roboto-Bold.ttf",
    "font2": "assets/Oswald-Regular.ttf",
    "font3": "assets/Raleway-Bold.ttf"
}

def get_screenshot(file):
    cap = cv2.VideoCapture(file)
    name = "./" + "".join(random.choices(ascii_uppercase + digits, k=10)) + ".jpg"
    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) - 1
        frame_num = random.randint(0, total_frames)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num - 1)
        res, frame = cap.read()
        if not res:
            raise ValueError("Could not read frame.")
        cv2.imwrite(name, frame)
    finally:
        cap.release()
    return name

def make_col():
    return (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

def truncate(text):
    words = text.split(" ")
    text1, text2 = "", ""
    pos = 0
    for word in words:
        if len(text1) + len(word) < 16 and pos == 0:
            text1 += " " + word
        elif len(text2) + len(word) < 16:
            pos = 1
            text2 += " " + word
    return text1.strip(), text2.strip()

async def fetch_url_content(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        print(f"Error fetching URL content: {e}")
        return None

async def get_cover(id):
    for attempt in range(MAX_RETRIES):
        url = f"https://anilist.co/anime/{id}"
        page_content = await fetch_url_content(url)
        if page_content is None:
            await asyncio.sleep(2)
            continue

        soup = bs(page_content, "html.parser")
        img_tag = soup.find("img", "cover")
        if img_tag:
            img_url = img_tag.get("src")
            img_content = await fetch_url_content(img_url)
            if img_content:
                fname = "./" + "".join(random.choices(ascii_uppercase + digits, k=10)) + ".jpg"
                with open(fname, "wb") as file:
                    file.write(img_content)
                return fname
        await asyncio.sleep(2)
    return "assets/c4UUTC4DAe.jpg"

def change_image_size(max_width, max_height, image):
    width_ratio = max_width / image.size[0]
    height_ratio = max_height / image.size[1]
    new_width = int(width_ratio * image.size[0])
    new_height = int(height_ratio * image.size[1])
    return image.resize((new_width, new_height))

async def generate_thumbnail(id, file, title, ep_num, size, dur):
    ss = get_screenshot(file)
    cc = await get_cover(id)
    border_color = make_col()

    image = Image.open(ss).convert("RGBA").resize((1280, 720))
    cover = Image.open(cc).convert("RGBA")
    cover = cover.resize((round((cover.width * 720) / cover.height), 720))

    mask = Image.new("L", cover.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon([(50, 0), (0, 720), (cover.width, 720), (cover.width, 0)], fill=255)
    cover = Image.composite(cover, Image.new("RGBA", cover.size, 0), mask)

    image_blur = image.filter(ImageFilter.GaussianBlur(10))
    image_blur = Image.blend(image_blur, Image.new("RGBA", (1280, 720), "black"), 0.5)
    image_blur.paste(cover, (1280 - cover.width, 0), cover)
    image_blur = ImageOps.expand(image_blur.convert("RGB"), 20, border_color)

    draw = ImageDraw.Draw(image_blur)
    draw.line([((1280 - cover.width) + 50, 0), ((1280 - cover.width) + 0, 720)], border_color, 20)

    fonts = {name: ImageFont.truetype(path, size) for name, path, size in [
        ("font1", FONT_PATHS["font1"], 70),
        ("font2", FONT_PATHS["font2"], 80),
        ("font3", FONT_PATHS["font3"], 50)
    ]}

    draw.text((150, 80), f"{CHANNEL_TITLE}", "white", fonts["font2"], stroke_width=5, stroke_fill="black")
    text1, text2 = truncate(title)
    draw.text((60, 230), text1, "white", fonts["font1"], stroke_width=5, stroke_fill="black")
    if text2:
        draw.text((60, 310), text2, "white", fonts["font1"], stroke_width=5, stroke_fill="black")
    draw.text((60, 420), f"Episode : {ep_num}", "white", fonts["font3"], stroke_width=2, stroke_fill="black")
    draw.text((60, 500), f"File Size : {size}", "white", fonts["font3"], stroke_width=2, stroke_fill="black")
    draw.text((60, 580), f"Duration : {dur}", "white", fonts["font3"], stroke_width=2, stroke_fill="black")

    thumb_path = "./downloads/" + "".join(random.choices(ascii_uppercase + digits, k=10)) + ".jpg"
    image_blur.save(thumb_path)

    os.remove(ss)
    if cc != "assets/c4UUTC4DAe.jpg":
        os.remove(cc)
    
    return thumb_path, 1280, 720
