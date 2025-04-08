import requests
from bs4 import BeautifulSoup
import re
import time
import concurrent.futures
import os
from data import load_read_list, create_cbz
from utils import clean_filename, top_left_menu, get_root
from viewer import MangaViewer
import curses

class NetworkConfig:
    BASE_URL = "https://www.mangaread.org/manga/"
    SEARCH_SUFFIX = "?s="
    POST_TYPE_SUFFIX = "&post_type=wp-manga"
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    IMAGE_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0',
        'Accept': 'image/avif,image/webp,image/png,image/svg+xml,image/*;q=0.8,*/*;q=0.5',
        'Accept-Language': 'en-CA,en-US;q=0.7,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
    }
    MAX_WORKERS = 5
    MIN_FILE_SIZE = 1024

CONFIG = NetworkConfig()
SESSION = requests.Session()

def get_image_urls(chapter_url, cookies, retries=3, delay=2):
    for attempt in range(retries):
        try:
            response = SESSION.get(chapter_url, headers=CONFIG.DEFAULT_HEADERS, cookies=cookies, timeout=10)
            response.raise_for_status() 
            soup = BeautifulSoup(response.text, "html.parser")
            image_tags = soup.find_all("img", class_="wp-manga-chapter-img")
            image_urls = [img["src"] for img in image_tags if "src" in img.attrs]
            return image_urls, None
        except requests.RequestException as e:
            error_msg = f"Attempt {attempt + 1}/{retries} failed: {str(e)}"
            if attempt + 1 == retries:
                return [], f"Failed to retrieve chapter page after {retries} attempts: {error_msg}"
            time.sleep(delay)

def download_images(image_urls, cookies, stdscr):
    image_data = []
    messages = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {
            executor.submit(SESSION.get, url, headers=CONFIG.IMAGE_HEADERS, cookies=cookies, stream=True): (idx, url)
            for idx, url in enumerate(image_urls)
        }
        for future in concurrent.futures.as_completed(future_to_url):
            idx, url = future_to_url[future]
            try:
                response = future.result()
                if response.status_code == 200:
                    img_name = f"image_{idx + 1:03d}.jpg"
                    image_data.append((img_name, response.content))
                    messages.append(f"Fetched: {img_name}")
                else:
                    messages.append(f"Failed to fetch {url} - Status code {response.status_code}")
            except Exception as e:
                messages.append(f"Failed to fetch {url}: {e}")

    return image_data, messages

def process_chapter(chapter, series_name, cookies, stdscr):
    cbz_filename = f"{series_name}_Chapter_{chapter['number']}.cbz"
    
    if os.path.exists(cbz_filename):
        file_size = os.path.getsize(cbz_filename)
        if file_size > 1024:
            return cbz_filename, f"Using existing file: {cbz_filename}"
        else:
            os.remove(cbz_filename)
            stdscr.addstr(0, 0, f"Existing file {cbz_filename} too small, re-fetching...")
            stdscr.refresh()
    
    chapter_url = chapter["url"]
    message = f"Fetching images from: {chapter['text']}"
    stdscr.addstr(1, 0, message)
    stdscr.refresh()

    image_urls, error = get_image_urls(chapter_url, cookies)
    if error:
        return None, f"Error: {error}"
    if image_urls:
        stdscr.addstr(2, 0, f"Found {len(image_urls)} images")
        stdscr.refresh()
        image_data, download_messages = download_images(image_urls, cookies, stdscr)
        if not image_data:
            return None, "No images fetched successfully."
        cbz_message = create_cbz(image_data, cbz_filename)
        
        file_size = os.path.getsize(cbz_filename)
        if file_size <= 1024:
            os.remove(cbz_filename)
            return None, f"File {cbz_filename} too small ({file_size} bytes), likely corrupt."
        return cbz_filename, ""
    else:
        return None, "No images found."

def search_manga(stdscr):
    stdscr.clear()
    stdscr.addstr(0, 0, "Enter manga name: ")
    stdscr.refresh()
    curses.echo()
    manga_name = stdscr.getstr(1, 0, 50).decode('utf-8').strip()
    curses.noecho()

    if not manga_name:
        stdscr.addstr(2, 0, "Manga name cannot be empty.")
        stdscr.refresh()
        stdscr.getch()
        return None, None, None, None

    url = f"{CONFIG.BASE_URL}{CONFIG.SEARCH_SUFFIX}{'+'.join(manga_name.split())}{CONFIG.POST_TYPE_SUFFIX}"

    response = SESSION.get(url, headers=CONFIG.DEFAULT_HEADERS)
    if response.status_code != 200:
        stdscr.addstr(2, 0, f"Failed to retrieve data. Status code: {response.status_code}")
        stdscr.refresh()
        stdscr.getch()
        return None, None, None, None

    soup = BeautifulSoup(response.text, "html.parser")
    stdscr.addstr(2, 0, "Searching for manga...\n")
    stdscr.refresh()
    manga_list = soup.select(".row.c-tabs-item__content")
    if not manga_list:
        stdscr.addstr(3, 0, "No manga found in the search results.")
        stdscr.refresh()
        stdscr.getch()
        return None, None, None, None

    manga_data = []
    manga_options = []
    for index, manga in enumerate(manga_list):
        h3_tag = manga.find("h3", class_="h4")
        title_tag = h3_tag.find("a") if h3_tag else None
        title = title_tag.text.strip() if title_tag else "Unknown Title"
        manga_url = title_tag["href"] if title_tag else "No URL"
        status_div = manga.find("div", class_="post-content_item mg_status")
        status_tag = status_div.find("div", class_="summary-content") if status_div else None
        status = status_tag.text.strip() if status_tag else "Unknown Status"
        latest_div = manga.find("div", class_="meta-item latest-chap")
        chapter_span = latest_div.find("span", class_="font-meta chapter") if latest_div else None
        latest_chapter_tag = chapter_span.find("a") if chapter_span else None
        latest_chapter_text = latest_chapter_tag.text.strip() if latest_chapter_tag else "No Chapter"
        latest_chapter_match = re.search(r'Chapter (\d+)', latest_chapter_text)
        latest_chapter_number = latest_chapter_match.group(1) if latest_chapter_match else "Unknown"
        update_div = manga.find("div", class_="meta-item post-on")
        update_time_tag = update_div.find("span", class_="font-meta") if update_div else None
        update_time = update_time_tag.text.strip() if update_time_tag else "Unknown Date"

        manga_data.append({
            "title": title,
            "url": manga_url,
            "status": status,
            "latest_chapter_number": latest_chapter_number,
            "latest_chapter_text": latest_chapter_text,
            "update_time": update_time
        })
        manga_options.append(f"{index + 1}. {title} - {status} - Latest: {latest_chapter_text} ({update_time})")

    choice = top_left_menu(stdscr, manga_options, "Select a manga:")
    if choice is None or choice < 0 or choice >= len(manga_data):
        stdscr.clear()
        stdscr.addstr(0, 0, "Invalid manga choice.")
        stdscr.refresh()
        stdscr.getch()
        return None, None, None, None

    chosen_manga = manga_data[choice]
    stdscr.clear()
    stdscr.addstr(0, 0, f"You chose: {chosen_manga['title']}")
    stdscr.addstr(1, 0, f"URL: {chosen_manga['url']}")
    stdscr.addstr(2, 0, f"Status: {chosen_manga['status']}")
    stdscr.addstr(3, 0, f"Latest Chapter: {chosen_manga['latest_chapter_text']} (Chapter {chosen_manga['latest_chapter_number']})")
    stdscr.refresh()
    time.sleep(2)

    response = SESSION.get(chosen_manga["url"], headers=CONFIG.DEFAULT_HEADERS)
    if response.status_code != 200:
        stdscr.addstr(4, 0, f"Failed to retrieve manga page. Status code: {response.status_code}")
        stdscr.refresh()
        stdscr.getch()
        return None, None, None, None

    soup = BeautifulSoup(response.text, "html.parser")
    chapter_tags = soup.select(".wp-manga-chapter a")
    if not chapter_tags:
        stdscr.addstr(4, 0, "No chapters found on the manga page.")
        stdscr.refresh()
        stdscr.getch()
        return None, None, None, None

    chapters = []
    chapter_options = []
    for index, tag in enumerate(chapter_tags):
        chapter_text = tag.text.strip()
        chapter_url = tag["href"]
        chapter_match = re.search(r'chapter-(\d+)', chapter_url)
        chapter_number = chapter_match.group(1) if chapter_match else "Unknown"
        chapters.append({"text": chapter_text, "url": chapter_url, "number": chapter_number, "cbz_filename": f"{clean_filename(chosen_manga['title'])}_Chapter_{chapter_number}.cbz"})
        chapter_options.append(f"{chapter_text}")

    chapters.sort(key=lambda x: int(x["number"]) if x["number"] != "Unknown" else 0)
    chapter_options.sort(key=lambda x: int(re.search(r'Chapter (\d+)', x).group(1)) if re.search(r'Chapter (\d+)', x) else 0)

    choice = top_left_menu(stdscr, chapter_options, "Select a chapter to start from:")
    stdscr.addstr(5, 0, f"Chapter choice: {choice} (Selected: {chapter_options[choice] if choice is not None else 'None'})")
    stdscr.refresh()
    time.sleep(2)
    if choice is None or choice < 0 or choice >= len(chapters):
        stdscr.clear()
        stdscr.addstr(0, 0, "Invalid chapter choice.")
        stdscr.refresh()
        stdscr.getch()
        return None, None, None, None

    series_name = clean_filename(chosen_manga['title'])
    current_index = choice
    stdscr.addstr(6, 0, f"Returning: series_name={series_name}, current_index={current_index}")
    stdscr.refresh()
    time.sleep(2)
    return series_name, chapters, current_index, response.cookies

def continue_reading(stdscr):
    stdscr.clear()
    read_list = load_read_list()
    if not read_list:
        stdscr.addstr(0, 0, "No manga in your read list yet.")
        stdscr.refresh()
        stdscr.getch()
        return

    series_list = []
    series_options = []
    for index, (series, data) in enumerate(read_list.items()):
        current = data["current"]
        if current["chapter"]:
            series_list.append((series, current["chapter"]))
            series_options.append(f"{index + 1}. {series} - Chapter {current['chapter']}")

    if not series_list:
        stdscr.addstr(0, 0, "No series currently being read.")
        stdscr.refresh()
        stdscr.getch()
        return

    choice = top_left_menu(stdscr, series_options, "Continue Reading:")
    if choice is None or choice < 0 or choice >= len(series_list):
        stdscr.clear()
        stdscr.addstr(0, 0, "Invalid choice.")
        stdscr.refresh()
        stdscr.getch()
        return

    series_name, chapter_number = series_list[choice]
    stdscr.clear()
    stdscr.addstr(0, 0, f"Resuming {series_name} at Chapter {chapter_number}...")
    stdscr.refresh()
    time.sleep(1)

    url = f"{CONFIG.BASE_URL}{CONFIG.SEARCH_SUFFIX}{series_name.replace('_', '+')}{CONFIG.POST_TYPE_SUFFIX}"

    response = requests.get(url, headers=CONFIG.DEFAULT_HEADERS)
    if response.status_code != 200:
        stdscr.addstr(1, 0, f"Failed to retrieve manga data. Status code: {response.status_code}")
        stdscr.refresh()
        stdscr.getch()
        return

    soup = BeautifulSoup(response.text, "html.parser")
    manga_list = soup.select(".row.c-tabs-item__content")
    if not manga_list:
        stdscr.addstr(1, 0, "Manga not found.")
        stdscr.refresh()
        stdscr.getch()
        return

    first_manga = manga_list[0]
    h3_tag = first_manga.find("h3", class_="h4")
    manga_url_tag = h3_tag.find("a") if h3_tag else None
    if not manga_url_tag:
        stdscr.addstr(1, 0, "Failed to find manga URL in search results.")
        stdscr.refresh()
        stdscr.getch()
        return
    manga_url = manga_url_tag["href"]

    response = requests.get(manga_url, headers=CONFIG.DEFAULT_HEADERS)
    if response.status_code != 200:
        stdscr.addstr(1, 0, f"Failed to retrieve manga page. Status code: {response.status_code}")
        stdscr.refresh()
        stdscr.getch()
        return

    soup = BeautifulSoup(response.text, "html.parser")
    chapter_tags = soup.select(".wp-manga-chapter a")
    if not chapter_tags:
        stdscr.addstr(1, 0, "No chapters found.")
        stdscr.refresh()
        stdscr.getch()
        return

    chapters = []
    for tag in chapter_tags:
        chapter_text = tag.text.strip()
        chapter_url = tag["href"]
        chapter_match = re.search(r'chapter-(\d+)', chapter_url)
        chapter_number_from_url = chapter_match.group(1) if chapter_match else "Unknown"
        chapters.append({"text": chapter_text, "url": chapter_url, "number": chapter_number_from_url, "cbz_filename": f"{series_name}_Chapter_{chapter_number_from_url}.cbz"})
    for key, value in chapters:
        print(f"{key}: {value}")
    chapters.sort(key=lambda x: int(x["number"]) if x["number"] != "Unknown" else 0)

    current_index = next((i for i, ch in enumerate(chapters) if ch["number"] == chapter_number), 0)
    current_chapter = chapters[current_index]
    stdscr.clear()
    stdscr.refresh()
    current_cbz, message = process_chapter(current_chapter, series_name, response.cookies, stdscr)
    stdscr.addstr(0, 0, message)
    stdscr.refresh()

    if current_cbz:
        root = get_root()
        MangaViewer(root, current_cbz, chapters, current_index, series_name, response.cookies, stdscr)
        root.mainloop()
    else:
        stdscr.getch()