import tkinter as tk
from PIL import Image, ImageTk
from threading import Thread
from io import BytesIO
import os
import zipfile
from data import load_read_list, update_current_position, add_to_read_list

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
        self.messages = [] 

        self.label = tk.Label(root, bg="#2b2b2b")
        self.label.pack()

        self.page_label = tk.Label(root, text="", bg="#2b2b2b", fg="#ffffff")
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

        self.load_chapter(cbz_filename)

        if self.current_index + 1 < len(self.chapters):
            self.start_next_download()

    def load_chapter(self, cbz_filename):
        """Load images and update UI for a given chapter."""
        self.images = []
        try:
            with zipfile.ZipFile(cbz_filename, 'r') as cbz:
                for file_info in sorted(cbz.infolist(), key=lambda x: x.filename):
                    with cbz.open(file_info) as file:
                        img = Image.open(BytesIO(file.read()))
                        img.thumbnail((800, 1200), Image.Resampling.LANCZOS)
                        self.images.append(ImageTk.PhotoImage(img))
        except (zipfile.BadZipFile, IOError) as e:
            self.messages.append(f"Error opening {cbz_filename}: {e}")

        if not self.images:
            self.messages.append(f"No valid images in {cbz_filename}. Re-downloading...")
            os.remove(cbz_filename)
            from network import process_chapter
            new_cbz, message = process_chapter(self.chapters[self.current_index], self.series_name, self.cookies, self.stdscr)
            self.messages.append(message)
            if new_cbz and os.path.getsize(new_cbz) > 1024:
                with zipfile.ZipFile(new_cbz, 'r') as cbz:
                    for file_info in sorted(cbz.infolist(), key=lambda x: x.filename):
                        with cbz.open(file_info) as file:
                            img = Image.open(BytesIO(file.read()))
                            img.thumbnail((800, 1200), Image.Resampling.LANCZOS)
                            self.images.append(ImageTk.PhotoImage(img))
            else:
                self.messages.append("Failed to re-download a valid chapter. Closing viewer.")
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

        self.root.title(f"Manga Viewer - {os.path.basename(cbz_filename)}")
        self.label.config(image=self.images[self.current_page])
        self.update_page()

    def start_next_download(self):
        if self.current_index + 1 < len(self.chapters):
            next_chapter = self.chapters[self.current_index + 1]
            next_cbz = f"{self.series_name}_Chapter_{next_chapter['number']}.cbz"
            if not os.path.exists(next_cbz) or os.path.getsize(next_cbz) <= 1024:
                self.messages.append(f"Starting background download for {next_chapter['text']}...")
                self.download_thread = Thread(target=self.download_next)
                self.download_thread.start()

    def download_next(self):
        from network import process_chapter
        try:
            next_chapter = self.chapters[self.current_index + 1]
            self.next_cbz, message = process_chapter(next_chapter, self.series_name, self.cookies, self.stdscr)
            self.messages.append(f"{message}\nDownload complete.")
        except Exception as e:
            self.messages.append(f"Background download failed: {str(e)}")

    def update_page(self):
        self.page_label.config(text=f"Page {self.current_page + 1} of {self.total_pages}")
        self.prev_button.config(state=tk.NORMAL if self.current_page > 0 or self.current_index > 0 else tk.DISABLED)
        self.next_button.config(state=tk.NORMAL if self.current_page < self.total_pages - 1 or self.current_index + 1 < len(self.chapters) else tk.DISABLED)
        self.next_chapter_button.config(state=tk.NORMAL if self.current_index + 1 < len(self.chapters) else tk.DISABLED)
        self.update_current()

    def update_current(self):
        chapter_number = self.chapters[self.current_index]['number']
        update_current_position(self.series_name, chapter_number, self.current_page + 1)

    def mark_as_read(self):
        if not self.read and self.current_page == self.total_pages - 1:
            chapter_number = self.chapters[self.current_index]['number']
            add_to_read_list(self.series_name, chapter_number)
            self.messages.append(f"Marked {self.series_name} Chapter {chapter_number} as read.")
            self.read = True

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.label.config(image=self.images[self.current_page])
            self.update_page()
        elif self.current_index > 0:
            self.current_index -= 1
            prev_cbz = f"{self.series_name}_Chapter_{self.chapters[self.current_index]['number']}.cbz"
            if os.path.exists(prev_cbz):
                self.load_chapter(prev_cbz)
            else:
                self.messages.append(f"Previous chapter {prev_cbz} not found.")

    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.label.config(image=self.images[self.current_page])
            self.update_page()
            self.mark_as_read()
        elif self.current_index + 1 < len(self.chapters):
            self.mark_as_read()
            self.current_index += 1
            next_cbz = f"{self.series_name}_Chapter_{self.chapters[self.current_index]['number']}.cbz"
            if self.download_thread and self.download_thread.is_alive():
                self.root.title("Manga Viewer - Downloading next chapter...")
                self.download_thread.join()
            if os.path.exists(next_cbz) and os.path.getsize(next_cbz) > 1024:
                self.load_chapter(next_cbz)
                if self.current_index + 1 < len(self.chapters):
                    self.start_next_download()
            else:
                self.messages.append("The next chapter is not yet downloaded or is invalid. Please wait and try again.")
                self.current_index -= 1 

    def next_chapter(self):
        if self.current_index + 1 >= len(self.chapters):
            self.messages.append("You have reached the end of the series.")
            return
        self.mark_as_read()
        self.current_index += 1
        next_cbz = f"{self.series_name}_Chapter_{self.chapters[self.current_index]['number']}.cbz"
        if self.download_thread and self.download_thread.is_alive():
            self.root.title("Manga Viewer - Downloading next chapter...")
            self.download_thread.join()
        if os.path.exists(next_cbz) and os.path.getsize(next_cbz) > 1024:
            self.load_chapter(next_cbz)
            if self.current_index + 1 < len(self.chapters):
                self.start_next_download()
        else:
            self.messages.append("Next chapter not ready or invalid. Please try again later.")
            self.current_index -= 1  

    def on_close(self):
        if self.current_page == self.total_pages - 1:
            self.mark_as_read()
        self.update_current()
        self.root.destroy()

    def get_messages(self):
        """Return stored messages for display later."""
        return self.messages