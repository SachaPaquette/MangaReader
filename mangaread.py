import time
import requests
import json
import os
import zipfile
import shutil
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.chrome.options import Options

def setup_selenium():
    options = uc.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--log-level=3")
    options.add_argument("--no-sandbox")
    options.add_argument("--headless")
    options.add_argument("--disable-dev-shm-usage")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = uc.Chrome(options=options)
    return driver

def get_image_urls(manga_url):
    driver = setup_selenium()
    driver.get(manga_url)

    time.sleep(2)
    logs = driver.get_log("performance")
    image_urls = []

    for log in logs:
            msg = json.loads(log["message"])["message"]
            if msg["method"] == "Network.responseReceived":
                response = msg["params"]["response"]
                url = response["url"]
                if url.endswith(".jpg"): 
                    image_urls.append(url)

    driver.quit()
    return image_urls

def download_images(image_urls, download_folder, cookies):
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0',
        'Accept': 'image/avif,image/webp,image/png,image/svg+xml,image/*;q=0.8,*/*;q=0.5',
        'Accept-Language': 'en-CA,en-US;q=0.7,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Referer': 'https://chapmanganato.to/', 
    }

    for index, url in enumerate(image_urls):
        try:
            response = requests.get(url, headers=headers, cookies=cookies, stream=True)
            if response.status_code == 200:
                img_name = f"image_{index + 1}.jpg"
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
        for img_file in os.listdir(images_folder):
            img_path = os.path.join(images_folder, img_file)
            if os.path.isfile(img_path):
                cbz.write(img_path, os.path.basename(img_path))
    print(f"Created {cbz_filename}")

def search_manga(query):
    url = f"https://manganato.com/search/story/{query.replace(' ', '_')}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to retrieve data. Status code: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    manga_list = soup.find_all("div", class_="search-story-item")

    manga_data = []
    for index, manga in enumerate(manga_list):
        title_tag = manga.find("a", class_="item-title")
        title = title_tag.text if title_tag else "Unknown Title"
        manga_url = title_tag["href"] if title_tag else "No URL"
        author_tag = manga.find("span", class_="item-author")
        author = author_tag.text if author_tag else "Unknown Author"
        rating_tag = manga.find("em", class_="item-rate")
        rating = rating_tag.text if rating_tag else "No Rating"
        chapters = manga.find_all("a", class_="item-chapter")
        latest_chapters = [ch.text for ch in chapters[:2]]  

        manga_data.append({
            "title": title,
            "url": manga_url,
            "author": author,
            "rating": rating,
            "latest_chapters": latest_chapters
        })

        print(f"{index + 1}. Title: {title}")
        print(f"   URL: {manga_url}")
        print(f"   Author: {author}")
        print(f"   Rating: {rating}")
        print("   Latest Chapters:", ", ".join(latest_chapters))
        print("-" * 50)

    if manga_data:
        choice = int(input("Enter the number of the manga you want to choose: ")) - 1
        if 0 <= choice < len(manga_data):
            chosen_manga = manga_data[choice]
            print(f"You chose: {chosen_manga['title']}")
            print(f"URL: {chosen_manga['url']}")
            print(f"Author: {chosen_manga['author']}")
            print(f"Rating: {chosen_manga['rating']}")
            print("Latest Chapters:", ", ".join(chosen_manga['latest_chapters']))
            
            response = requests.get(chosen_manga["url"], headers=headers)
            if response.status_code != 200:
                print(f"Failed to retrieve data. Status code: {response.status_code}")
                return

            soup = BeautifulSoup(response.text, "html.parser")
            chapters = soup.find_all("a", class_="chapter-name text-nowrap")
            chapter_names = [chapter.text for chapter in chapters]
            print("Chapters:")
            for index, chapter in enumerate(chapter_names):
                print(f"{index + 1}. {chapter}")

            choice = int(input("Enter the number of the chapter: ")) - 1
            if 0 <= choice < len(chapters):
                chosen_chapter = chapters[choice]
                chapter_url = chosen_chapter["href"]
                print(f"\nFetching images from: {chosen_chapter.text} ({chapter_url})")
                image_urls = get_image_urls(chapter_url)

                if image_urls:
                    download_folder = "manga_images"
                    download_images(image_urls, download_folder, response.cookies)

                    cbz_filename = f"{chosen_manga['title'].replace(' ', '_')}_chapter_{choice + 1}.cbz"
                    create_cbz(download_folder, cbz_filename)

                    shutil.rmtree(download_folder)
                else:
                    print("No images found.")
            else:
                print("Invalid chapter choice.")
        else:
            print("Invalid manga choice.")
    else:
        print("No manga found.")

if __name__ == "__main__":
    manga_name = input("Enter manga name: ")
    search_manga(manga_name)
