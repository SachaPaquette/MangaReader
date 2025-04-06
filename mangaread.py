import math
import time
from tkinter import messagebox
import requests
import os
import zipfile
import shutil
import tkinter as tk
from PIL import Image, ImageTk
from bs4 import BeautifulSoup
import re
from threading import Thread
from io import BytesIO
import tempfile
import curses
import json
import concurrent.futures

SESSION = requests.Session()

class MenuOptions:
    def __init__(self):
        self.options = ["Search for Manga", "Continue Reading", "Exit"]

    def display_menu(self, stdscr):
        curses.curs_set(0)
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
        stdscr.keypad(True)
        current_row = 0

        while True:
            stdscr.clear()
            h, w = stdscr.getmaxyx()
            for idx, option in enumerate(self.options):
                x = w // 2 - len(option) // 2
                y = h // 2 - len(self.options) // 2 + idx
                if idx == current_row:
                    stdscr.attron(curses.color_pair(1))
                    stdscr.addstr(y, x, option)
                    stdscr.attroff(curses.color_pair(1))
                else:
                    stdscr.addstr(y, x, option)
            stdscr.refresh()

            key = stdscr.getch()
            if key == ord('q'):
                return None
            if key == curses.KEY_UP and current_row > 0:
                current_row -= 1
            elif key == curses.KEY_DOWN and current_row < len(self.options) - 1:
                current_row += 1
            elif key in [10, 13, curses.KEY_RIGHT]:
                return current_row

    def get_choice(self, stdscr):
        return self.display_menu(stdscr)

    def Exit(self):
        exit(0)

def top_left_menu(stdscr, options, prompt):
    curses.curs_set(0)
    curses.start_color()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
    stdscr.keypad(True)
    current_row = 0
    scroll_offset = 0
    stdscr.clear()

    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        max_display = h - 2

        if h > 0:
            stdscr.addnstr(0, 0, prompt, w)

        visible_start = scroll_offset
        visible_end = min(scroll_offset + max_display, len(options))
        visible_options = options[visible_start:visible_end]

        for idx, option in enumerate(visible_options):
            y = 1 + idx
            x = 0
            max_width = w - x
            if y < h:
                truncated_option = option[:max_width - 1] if len(option) >= max_width else option
                if visible_start + idx == current_row:
                    stdscr.attron(curses.color_pair(1))
                    stdscr.addnstr(y, x, truncated_option, max_width)
                    stdscr.attroff(curses.color_pair(1))
                else:
                    stdscr.addnstr(y, x, truncated_option, max_width)

        stdscr.refresh()
        key = stdscr.getch()
        if key == ord('q'):
            stdscr.clear()
            stdscr.addstr(0, 0, "Exiting menu...")
            stdscr.refresh()
            time.sleep(1)
            return None
        if key == curses.KEY_UP:
            if current_row > 0:
                current_row -= 1
                if current_row < scroll_offset:
                    scroll_offset -= 1
        elif key == curses.KEY_DOWN:
            if current_row < len(options) - 1:
                current_row += 1
                if current_row >= scroll_offset + max_display:
                    scroll_offset += 1
        elif key == curses.KEY_ENTER or key in [10, 13] or key == curses.KEY_RIGHT:
            stdscr.clear()
            stdscr.keypad(False)
            return current_row

def load_read_list():
    try:
        with open("read_list.json", "r") as f:
            data = json.load(f)
            for series in list(data.keys()):
                if isinstance(data[series], list):
                    data[series] = {"read": data[series], "current": {"chapter": None, "page": None}}
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_read_list(read_list):
    with open("read_list.json", "w") as f:
        json.dump(read_list, f, indent=4)

def add_to_read_list(series_name, chapter_number):
    read_list = load_read_list()
    if series_name not in read_list:
        read_list[series_name] = {"read": [], "current": {"chapter": None, "page": None}}
    if chapter_number not in read_list[series_name]["read"]:
        read_list[series_name]["read"].append(chapter_number)
        read_list[series_name]["read"].sort()
    save_read_list(read_list)

def update_current_position(series_name, chapter_number, page_number):
    read_list = load_read_list()
    if series_name not in read_list:
        read_list[series_name] = {"read": [], "current": {"chapter": None, "page": None}}
    read_list[series_name]["current"]["chapter"] = chapter_number
    read_list[series_name]["current"]["page"] = str(page_number)
    save_read_list(read_list)

def get_image_urls(chapter_url, cookies):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = SESSION.get(chapter_url, headers=headers, cookies=cookies)
    if response.status_code != 200:
        return [], f"Failed to retrieve chapter page. Status code: {response.status_code}"
    soup = BeautifulSoup(response.text, "html.parser")
    image_tags = soup.find_all("img", class_="wp-manga-chapter-img")
    image_urls = [img["src"] for img in image_tags if "src" in img.attrs]
    return image_urls, None

def download_images(image_urls, cookies, stdscr):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0',
        'Accept': 'image/avif,image/webp,image/png,image/svg+xml,image/*;q=0.8,*/*;q=0.5',
        'Accept-Language': 'en-CA,en-US;q=0.7,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
    }
    image_data = []
    messages = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {
            executor.submit(SESSION.get, url, headers=headers, cookies=cookies, stream=True): (idx, url)
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

def create_cbz(image_data, cbz_filename):
    with zipfile.ZipFile(cbz_filename, 'w', zipfile.ZIP_DEFLATED) as cbz:
        for img_name, img_content in image_data:
            cbz.writestr(img_name, img_content)
    return f"Created {cbz_filename}"

def clean_filename(title):
    invalid_chars = r'[<>:"/\\|?*\x00-\x1F]'
    title = re.sub(invalid_chars, '', title)
    title = title.replace('–', '-').replace('’', "'").replace('“', '"').replace('”', '"')
    title = re.sub(r'\s+', '_', title.strip())
    return title

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
        short_messages = [msg[:100] for msg in download_messages]  
        return cbz_filename, f"{message}\nFound {len(image_urls)} images\n" + "\n".join(short_messages) + f"\n{cbz_message}"
    else:
        return None, "No images found."

def download_next_chapter(chapter, series_name, cookies, stdscr):
    return process_chapter(chapter, series_name, cookies, stdscr)

class MangaViewer:
    def __init__(self, root, cbz_filename, chapters, current_index, series_name, cookies, stdscr):
        self.root = root
        self.root.title(f"Manga Viewer - {os.path.basename(cbz_filename)}")
        self.root.configure(bg="#2b2b2b")
        self.chapters = chapters
        self.current_index = current_index
        self.series_name = series_name
        self.cookies = cookies
        self.next_cbz = None
        self.stdscr = stdscr
        self.read = False
        self.download_thread = None 

        self.images = []
        try:
            with zipfile.ZipFile(cbz_filename, 'r') as cbz:
                for file_info in sorted(cbz.infolist(), key=lambda x: x.filename):
                    with cbz.open(file_info) as file:
                        img = Image.open(BytesIO(file.read()))
                        img.thumbnail((800, 1200), Image.Resampling.LANCZOS)
                        self.images.append(ImageTk.PhotoImage(img))
        except (zipfile.BadZipFile, IOError) as e:
            self.stdscr.addstr(f"Error opening {cbz_filename}: {e}\n")
            self.stdscr.refresh()
            self.images = []

        if not self.images:
            self.stdscr.addstr(f"No valid images in {cbz_filename}. Re-downloading...\n")
            self.stdscr.refresh()
            os.remove(cbz_filename)
            new_cbz, message = process_chapter(self.chapters[self.current_index], self.series_name, self.cookies, self.stdscr)
            self.stdscr.addstr(message + "\n")
            self.stdscr.refresh()
            if new_cbz and os.path.getsize(new_cbz) > 1024:
                with zipfile.ZipFile(new_cbz, 'r') as cbz:
                    for file_info in sorted(cbz.infolist(), key=lambda x: x.filename):
                        with cbz.open(file_info) as file:
                            img = Image.open(BytesIO(file.read()))
                            img.thumbnail((800, 1200), Image.Resampling.LANCZOS)
                            self.images.append(ImageTk.PhotoImage(img))
            else:
                self.stdscr.addstr("Failed to re-download a valid chapter. ClosingI Closing viewer.\n")
                self.stdscr.refresh()
                self.root.destroy()
                return

        self.current_page = 0
        self.total_pages = len(self.images)

        read_list = load_read_list()
        if self.series_name in read_list:
            current_data = read_list[self.series_name].get("current", {})
            if current_data and current_data.get("chapter") == self.chapters[self.current_index]["number"]:
                last_page = int(current_data.get("page", "0")) - 1
                if 0 <= last_page < self.total_pages:
                    self.current_page = last_page

        self.label = tk.Label(root, image=self.images[self.current_page], bg="#2b2b2b")
        self.label.pack()

        self.page_label = tk.Label(root, text=f"Page {self.current_page + 1} of {self.total_pages}", bg="#2b2b2b", fg="#ffffff")
        self.page_label.pack()

        self.prev_button = tk.Button(root, text="Previous", command=self.prev_page, bg="#404040", fg="#ffffff", activebackground="#505050")
        self.prev_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.next_button = tk.Button(root, text="Next", command=self.next_page, bg="#404040", fg="#ffffff", activebackground="#505050")
        self.next_button.pack(side=tk.RIGHT, padx=5, pady=5)

        self.next_chapter_button = tk.Button(root, text="Next Chapter", command=self.next_chapter, bg="#404040", fg="#ffffff", activebackground="#505050")
        self.next_chapter_button.pack(side=tk.BOTTOM, pady=5)

        self.root.bind("<Left>", lambda e: self.prev_page())
        self.root.bind("<Right>", lambda e: self.next_page())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        if self.current_index + 1 < len(self.chapters):
            self.start_next_download()

        self.update_current()

    def start_next_download(self):
        if self.current_index + 1 < len(self.chapters):
            next_chapter = self.chapters[self.current_index + 1]
            next_cbz = f"{self.series_name}_Chapter_{next_chapter['number']}.cbz"
            if not os.path.exists(next_cbz) or os.path.getsize(next_cbz) <= 1024:
                self.stdscr.addstr(f"Starting background download for {next_chapter['text']}...\n")
                self.stdscr.refresh()
                self.download_thread = Thread(target=self.download_next)
                self.download_thread.start()

    def download_next(self):
        try:
            next_chapter = self.chapters[self.current_index + 1]
            self.next_cbz, message = download_next_chapter(next_chapter, self.series_name, self.cookies, self.stdscr)
            self.stdscr.addstr(message + "\nDownload complete.\n")
            self.stdscr.refresh()
        except Exception as e:
            self.stdscr.addstr(f"Background download failed: {str(e)}\n")
            self.stdscr.refresh()

    def update_page(self):
        self.label.config(image=self.images[self.current_page])
        self.page_label.config(text=f"Page {self.current_page + 1} of {self.total_pages}")
        self.prev_button.config(state=tk.NORMAL if self.current_page > 0 else tk.DISABLED)
        self.next_button.config(state=tk.NORMAL if self.current_page < self.total_pages - 1 else tk.DISABLED)
        self.next_chapter_button.config(state=tk.NORMAL if self.current_index + 1 < len(self.chapters) else tk.DISABLED)
        self.update_current()

    def update_current(self):
        chapter_number = self.chapters[self.current_index]['number']
        update_current_position(self.series_name, chapter_number, self.current_page + 1)

    def mark_as_read(self):
        if not self.read and self.current_page == self.total_pages - 1:
            chapter_number = self.chapters[self.current_index]['number']
            add_to_read_list(self.series_name, chapter_number)
            self.stdscr.addstr(f"Marked {self.series_name} Chapter {chapter_number} as read.\n")
            self.stdscr.refresh()
            self.read = True

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_page()
        elif self.current_index > 0:
            prev_cbz = f"{self.series_name}_Chapter_{self.chapters[self.current_index - 1]['number']}.cbz"
            if os.path.exists(prev_cbz):
                self.current_index -= 1
                self.root.destroy()
                new_root = tk.Tk()
                MangaViewer(new_root, prev_cbz, self.chapters, self.current_index, self.series_name, self.cookies, self.stdscr)
                new_root.mainloop()

    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_page()
            self.mark_as_read()
        elif self.current_index + 1 < len(self.chapters):
            self.mark_as_read()
            next_cbz = f"{self.series_name}_Chapter_{self.chapters[self.current_index + 1]['number']}.cbz"
            
            if self.download_thread and self.download_thread.is_alive():
                self.root.title("Manga Viewer - Downloading next chapter...")
                self.download_thread.join()  
            
            if os.path.exists(next_cbz) and os.path.getsize(next_cbz) > 1024:
                self.current_index += 1
                self.root.destroy()
                new_root = tk.Tk()
                MangaViewer(new_root, next_cbz, self.chapters, self.current_index, self.series_name, self.cookies, self.stdscr)
                new_root.mainloop()
            else:
                messagebox.showwarning("Next Chapter Not Ready", "The next chapter is not yet downloaded or is invalid. Please wait and try again.")

    def next_chapter(self):
        if self.current_index + 1 >= len(self.chapters):
            messagebox.showinfo("End of Series", "You have reached the end of the series.")
            return
        
        self.mark_as_read()
        next_cbz = f"{self.series_name}_Chapter_{self.chapters[self.current_index + 1]['number']}.cbz"
        
        if self.download_thread and self.download_thread.is_alive():
            self.root.title("Manga Viewer - Downloading next chapter...")
            self.download_thread.join()
        
        if os.path.exists(next_cbz) and os.path.getsize(next_cbz) > 1024:
            self.current_index += 1
            self.root.destroy()
            new_root = tk.Tk()
            MangaViewer(new_root, next_cbz, self.chapters, self.current_index, self.series_name, self.cookies, self.stdscr)
            new_root.mainloop()
        else:
            messagebox.showwarning("Error", "Next chapter not ready or invalid. Please try again later.")

    def on_close(self):
        if self.current_page == self.total_pages - 1:
            self.mark_as_read()
        self.update_current()
        self.root.destroy()

def search_manga(stdscr):
    stdscr.clear()
    stdscr.addstr(0, 0, "Enter manga name: ")
    stdscr.refresh()
    curses.echo()
    manga_name = stdscr.getstr(1, 0, 50).decode('utf-8').strip()
    curses.noecho()

    url = f"https://www.mangaread.org/manga/?s={manga_name.replace(' ', '+')}&post_type=wp-manga"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = SESSION.get(url, headers=headers)
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
        title_tag = manga.find("h3", class_="h4").find("a")
        title = title_tag.text.strip() if title_tag else "Unknown Title"
        manga_url = title_tag["href"] if title_tag else "No URL"
        status_tag = manga.find("div", class_="post-content_item mg_status").find("div", class_="summary-content")
        status = status_tag.text.strip() if status_tag else "Unknown Status"
        latest_chapter_tag = manga.find("div", class_="meta-item latest-chap").find("span", class_="font-meta chapter").find("a")
        latest_chapter_text = latest_chapter_tag.text.strip() if latest_chapter_tag else "No Chapter"
        latest_chapter_match = re.search(r'Chapter (\d+)', latest_chapter_text)
        latest_chapter_number = latest_chapter_match.group(1) if latest_chapter_match else "Unknown"
        update_time_tag = manga.find("div", class_="meta-item post-on").find("span", class_="font-meta")
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

    response = SESSION.get(chosen_manga["url"], headers=headers)
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
        chapters.append({"text": chapter_text, "url": chapter_url, "number": chapter_number})
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

    url = f"https://www.mangaread.org/manga/?s={series_name.replace('_', '+')}&post_type=wp-manga"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
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

    manga_url = manga_list[0].find("h3", class_="h4").find("a")["href"]
    response = requests.get(manga_url, headers=headers)
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
        chapters.append({"text": chapter_text, "url": chapter_url, "number": chapter_number_from_url})

    chapters.sort(key=lambda x: int(x["number"]) if x["number"] != "Unknown" else 0)

    current_index = next((i for i, ch in enumerate(chapters) if ch["number"] == chapter_number), 0)
    current_chapter = chapters[current_index]
    stdscr.clear()
    stdscr.refresh()
    current_cbz, message = process_chapter(current_chapter, series_name, response.cookies, stdscr)
    stdscr.addstr(0, 0, message)
    stdscr.refresh()
    time.sleep(2)

    if current_cbz:
        root = tk.Tk()
        viewer = MangaViewer(root, current_cbz, chapters, current_index, series_name, response.cookies, stdscr)
        root.mainloop()
    else:
        stdscr.getch()

def display_message(stdscr, message, start_row=0):
    """Safely display a message within terminal bounds."""
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    row = start_row
    for line in message.split('\n'):
        if row >= h:  
            break
        truncated_line = line[:w - 1] if len(line) >= w else line
        try:
            stdscr.addnstr(row, 0, truncated_line, w - 1)
        except curses.error:
            stdscr.addstr(row, 0, "Display error occurred")
            break
        row += 1
    stdscr.refresh()
    return row

def main(stdscr):
    menu = MenuOptions()
    while True:
        choice = menu.get_choice(stdscr)
        if choice == 0:  
            try:
                series_name, chapters, current_index, cookies = search_manga(stdscr)
                if not (series_name and chapters):
                    display_message(stdscr, "Search failed. Press any key to continue.")
                    stdscr.getch()
                    continue

                display_message(stdscr, f"Processing {series_name}...")
                time.sleep(1)
                current_chapter = chapters[current_index]
                current_cbz, message = process_chapter(current_chapter, series_name, cookies, stdscr)

                display_message(stdscr, message)
                time.sleep(1)

                if current_cbz:
                    row = display_message(stdscr, "Launching viewer...")
                    curses.endwin()
                    try:
                        root = tk.Tk()
                        viewer = MangaViewer(root, current_cbz, chapters, current_index, series_name, cookies, stdscr)
                        root.mainloop()
                    except Exception as e:
                        print(f"Viewer error: {e}") 
                    finally:
                        stdscr = curses.initscr()
                        stdscr.keypad(True)
                        stdscr.refresh()
                        display_message(stdscr, "Returned to menu. Press any key to continue.")
                        stdscr.getch()
                else:
                    display_message(stdscr, "Failed to create CBZ. Press any key to continue.")
                    stdscr.getch()
            except Exception as e:
                display_message(stdscr, f"Error: {str(e)}. Press any key to continue.")
                stdscr.getch()
        elif choice == 1:  
            continue_reading(stdscr)
        elif choice == 2:  
            menu.Exit()
            
if __name__ == "__main__":
    curses.wrapper(main)