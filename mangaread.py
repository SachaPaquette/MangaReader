import math
import time
import requests
import json
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

def get_image_urls(chapter_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(chapter_url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to retrieve chapter page. Status code: {response.status_code}")
        return []
    
    soup = BeautifulSoup(response.text, "html.parser")
    image_tags = soup.find_all("img", class_="wp-manga-chapter-img")
    image_urls = [img["src"] for img in image_tags if "src" in img.attrs]
    return image_urls

def download_images(image_urls, download_folder, cookies):
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0',
        'Accept': 'image/avif,image/webp,image/png,image/svg+xml,image/*;q=0.8,*/*;q=0.5',
        'Accept-Language': 'en-CA,en-US;q=0.7,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
    }
    for index, url in enumerate(image_urls):
        try:
            response = requests.get(url, headers=headers, cookies=cookies, stream=True)
            if response.status_code == 200:
                img_name = f"image_{index + 1:03d}.jpg"
                img_path = os.path.join(download_folder, img_name)
                with open(img_path, 'wb') as img_file:
                    for chunk in response.iter_content(chunk_size=8192):
                        img_file.write(chunk)
                print(f"Downloaded: {img_name}")
            else:
                print(f"Failed to download {url} - Status code {response.status_code}")
        except Exception as e:
            print(f"Failed to download {url}: {e}")

def create_cbz(images_folder, cbz_filename):
    with zipfile.ZipFile(cbz_filename, 'w', zipfile.ZIP_DEFLATED) as cbz:
        for img_file in sorted(os.listdir(images_folder)):
            img_path = os.path.join(images_folder, img_file)
            if os.path.isfile(img_path):
                cbz.write(img_path, os.path.basename(img_path))
    print(f"Created {cbz_filename}")

def clean_filename(title):
    invalid_chars = r'[<>:"/\\|?*\x00-\x1F]'
    title = re.sub(invalid_chars, '', title)
    title = title.replace('–', '-').replace('’', "'").replace('“', '"').replace('”', '"')
    title = re.sub(r'\s+', '_', title.strip())
    return title

def process_chapter(chapter, series_name, cookies, download_folder=None):
    cbz_filename = f"{series_name}_Chapter_{chapter['number']}.cbz"
    
    if os.path.exists(cbz_filename):
        file_size = os.path.getsize(cbz_filename)
        if file_size > 1024:
            print(f"\nUsing existing file: {cbz_filename}")
            return cbz_filename
        else:
            print(f"\nExisting file {cbz_filename} is too small ({file_size} bytes), re-downloading...")
            os.remove(cbz_filename)
    
    chapter_url = chapter["url"]
    chapter_number = chapter["number"]
    print(f"\nFetching images from: {chapter['text']} ({chapter_url})")
    
    image_urls = get_image_urls(chapter_url)
    if image_urls:
        if download_folder is None:
            download_folder = tempfile.mkdtemp(prefix=f"manga_{chapter_number}_")
        else:
            if os.path.exists(download_folder):
                for _ in range(5):  
                    try:
                        shutil.rmtree(download_folder)
                        break
                    except PermissionError:
                        print(f"Waiting to delete {download_folder} due to file lock...")
                        time.sleep(1)
                else:
                    print(f"Failed to delete {download_folder}. Using a new temp folder.")
                    download_folder = tempfile.mkdtemp(prefix=f"manga_{chapter_number}_")
        
        download_images(image_urls, download_folder, cookies)
        create_cbz(download_folder, cbz_filename)
        
        for _ in range(5):
            try:
                shutil.rmtree(download_folder)
                break
            except PermissionError:
                print(f"Waiting to delete {download_folder} due to file lock...")
                time.sleep(1)
        else:
            print(f"Failed to delete {download_folder}. It will remain on disk.")
        
        file_size = os.path.getsize(cbz_filename)
        if file_size <= 1024:
            print(f"Downloaded file {cbz_filename} is too small ({file_size} bytes), likely corrupt.")
            os.remove(cbz_filename)
            return None
        return cbz_filename
    else:
        print("No images found.")
        return None

def download_next_chapter(chapter, series_name, cookies):
    download_folder = tempfile.mkdtemp(prefix=f"manga_next_{chapter['number']}_")
    return process_chapter(chapter, series_name, cookies, download_folder=download_folder)

class MangaViewer:
    def __init__(self, root, cbz_filename, chapters, current_index, series_name, cookies):
        self.root = root
        self.root.title(f"Manga Viewer - {os.path.basename(cbz_filename)}")
        self.root.configure(bg="#2b2b2b")  
        self.chapters = chapters
        self.current_index = current_index
        self.series_name = series_name
        self.cookies = cookies
        self.next_cbz = None

        self.images = []
        try:
            with zipfile.ZipFile(cbz_filename, 'r') as cbz:
                for file_info in sorted(cbz.infolist(), key=lambda x: x.filename):
                    with cbz.open(file_info) as file:
                        img = Image.open(BytesIO(file.read()))
                        img.thumbnail((800, 1200), Image.Resampling.LANCZOS)
                        self.images.append(ImageTk.PhotoImage(img))
        except (zipfile.BadZipFile, IOError) as e:
            print(f"Error opening {cbz_filename}: {e}")
            self.images = [] 

        if not self.images:
            print(f"No valid images found in {cbz_filename}. Re-downloading chapter...")
            os.remove(cbz_filename)
            new_cbz = process_chapter(self.chapters[self.current_index], self.series_name, self.cookies)
            if new_cbz and os.path.getsize(new_cbz) > 1024:
                with zipfile.ZipFile(new_cbz, 'r') as cbz:
                    for file_info in sorted(cbz.infolist(), key=lambda x: x.filename):
                        with cbz.open(file_info) as file:
                            img = Image.open(BytesIO(file.read()))
                            img.thumbnail((800, 1200), Image.Resampling.LANCZOS)
                            self.images.append(ImageTk.PhotoImage(img))
            else:
                print("Failed to re-download a valid chapter. Closing viewer.")
                self.root.destroy()
                return

        self.current_page = 0
        self.total_pages = len(self.images)

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

        if self.current_index + 1 < len(self.chapters):
            next_cbz = f"{self.series_name}_Chapter_{self.chapters[self.current_index + 1]['number']}.cbz"
            if not os.path.exists(next_cbz) or os.path.getsize(next_cbz) <= 1024:
                self.start_next_download()

    def start_next_download(self):
        next_chapter = self.chapters[self.current_index + 1]
        print(f"Starting background download for {next_chapter['text']}...")
        self.download_thread = Thread(target=self.download_next)
        self.download_thread.start()

    def download_next(self):
        next_chapter = self.chapters[self.current_index + 1]
        self.next_cbz = download_next_chapter(next_chapter, self.series_name, self.cookies)

    def update_page(self):
        self.label.config(image=self.images[self.current_page])
        self.page_label.config(text=f"Page {self.current_page + 1} of {self.total_pages}")
        self.prev_button.config(state=tk.NORMAL if self.current_page > 0 else tk.DISABLED)
        self.next_button.config(state=tk.NORMAL if self.current_page < self.total_pages - 1 else tk.DISABLED)
        self.next_chapter_button.config(state=tk.NORMAL if self.current_index + 1 < len(self.chapters) else tk.DISABLED)

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
                viewer = MangaViewer(new_root, prev_cbz, self.chapters, self.current_index, self.series_name, self.cookies)
                new_root.mainloop()

    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_page()
        elif self.current_index + 1 < len(self.chapters): 
            next_cbz = f"{self.series_name}_Chapter_{self.chapters[self.current_index + 1]['number']}.cbz"
            if os.path.exists(next_cbz) and os.path.getsize(next_cbz) > 1024:
                self.current_index += 1
                self.root.destroy()
                new_root = tk.Tk()
                viewer = MangaViewer(new_root, next_cbz, self.chapters, self.current_index, self.series_name, self.cookies)
                new_root.mainloop()

    def next_chapter(self):
        if self.current_index + 1 < len(self.chapters):
            next_cbz = f"{self.series_name}_Chapter_{self.chapters[self.current_index + 1]['number']}.cbz"
            if os.path.exists(next_cbz) and os.path.getsize(next_cbz) > 1024:
                self.current_index += 1
                self.root.destroy()
                new_root = tk.Tk()
                viewer = MangaViewer(new_root, next_cbz, self.chapters, self.current_index, self.series_name, self.cookies)
                new_root.mainloop()
            else:
                self.download_thread.join()  
                if self.next_cbz and os.path.exists(self.next_cbz) and os.path.getsize(self.next_cbz) > 1024:
                    self.current_index += 1
                    self.root.destroy()
                    new_root = tk.Tk()
                    viewer = MangaViewer(new_root, self.next_cbz, self.chapters, self.current_index, self.series_name, self.cookies)
                    new_root.mainloop()
                else:
                    print("Next chapter not ready or invalid. Please try again.")

def search_manga(query):
    url = f"https://www.mangaread.org/manga/?s={query.replace(' ', '+')}&post_type=wp-manga"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to retrieve data. Status code: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    print("Searching for manga...")
    manga_list = soup.select(".row.c-tabs-item__content")
    if not manga_list:
        print("No manga found in the search results.")
        return

    manga_data = []
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

        print(f"{index + 1}. Title: {title}")
        print(f"   Status: {status}")
        print(f"   Latest Chapter: {latest_chapter_text} (Chapter {latest_chapter_number})")
        print(f"   Update Time: {update_time}")
        print("-" * 50)

    if manga_data:
        choice = int(input("Enter the number of the manga you want to choose: ")) - 1
        if 0 <= choice < len(manga_data):
            chosen_manga = manga_data[choice]
            print(f"You chose: {chosen_manga['title']}")
            print(f"URL: {chosen_manga['url']}")
            print(f"Status: {chosen_manga['status']}")
            print(f"Latest Chapter: {chosen_manga['latest_chapter_text']} (Chapter {chosen_manga['latest_chapter_number']})")

            response = requests.get(chosen_manga["url"], headers=headers)
            if response.status_code != 200:
                print(f"Failed to retrieve manga page. Status code: {response.status_code}")
                return

            soup = BeautifulSoup(response.text, "html.parser")
            chapter_tags = soup.select(".wp-manga-chapter a")
            if not chapter_tags:
                print("No chapters found on the manga page.")
                return

            chapters = []
            for tag in chapter_tags:
                chapter_text = tag.text.strip()
                chapter_url = tag["href"]
                chapter_match = re.search(r'chapter-(\d+)', chapter_url)
                chapter_number = chapter_match.group(1) if chapter_match else "Unknown"
                chapters.append({"text": chapter_text, "url": chapter_url, "number": chapter_number})

            chapters.sort(key=lambda x: int(x["number"]) if x["number"] != "Unknown" else 0)

            print("Chapters:")
            for index, chapter in enumerate(chapters):
                print(f"{index + 1}. {chapter['text']} (Chapter {chapter['number']})")

            choice = int(input("Enter the number of the chapter to start from: ")) - 1
            if 0 <= choice < len(chapters):
                series_name = clean_filename(chosen_manga['title'])
                current_index = choice

                current_chapter = chapters[current_index]
                current_cbz = process_chapter(current_chapter, series_name, response.cookies)
                if not current_cbz:
                    return

                root = tk.Tk()
                viewer = MangaViewer(root, current_cbz, chapters, current_index, series_name, response.cookies)
                root.mainloop()
            else:
                print("Invalid chapter choice.")
        else:
            print("Invalid manga choice.")
    else:
        print("No manga found.")

if __name__ == "__main__":
    manga_name = input("Enter manga name: ")
    search_manga(manga_name)