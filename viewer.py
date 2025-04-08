import sys
import zipfile
from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QToolBar, QAction
from PyQt5.QtGui import QPixmap, QKeyEvent
from PyQt5.QtCore import Qt
from data import load_read_list, save_read_list, add_to_read_list, update_current_position, create_cbz
class ViewerConfig:
    BACKGROUND_COLOR = "#2b2b2b"  
    TEXT_COLOR = "#ffffff"        
    MANHWA_WIDTH_THRESHOLD = 300  
    SCROLL_INCREMENT = 50         
    MIN_WINDOW_SIZE = 100         
    MANHWA_AUTO_ZOOM = 5.0        

class MangaViewer(QMainWindow):
    def __init__(self, cbz_filename, chapters, current_index, series_name, cookies, stdscr):
        super().__init__()
        self.setWindowTitle("Manga Viewer - PyQt5 Integration")
        self.setGeometry(100, 100, 800, 600)

        self.chapters = chapters
        self.current_index = current_index
        self.series_name = series_name
        self.cookies = cookies
        self.stdscr = stdscr
        self.cbz_filename = cbz_filename
        self.current_page = 0
        self.full_size_mode = False
        self.chapter_images = []
        self.current_image_index = 0
        self.scroll_locked = False 
        self.view = QGraphicsView(self)
        self.scene = QGraphicsScene(self)
        self.view.setScene(self.scene)
        self.setCentralWidget(self.view)
        self.view.setFocusPolicy(Qt.StrongFocus)
        self._create_actions()
        self._create_toolbar()
        self.load_chapter(cbz_filename)

        self.view.setFocus()
        self.view.setStyleSheet(f"background-color: {ViewerConfig.BACKGROUND_COLOR};")

        self.view.verticalScrollBar().valueChanged.connect(self.check_scroll_position)
    def check_scroll_position(self):
        vertical_scroll_bar = self.view.verticalScrollBar()
        max_value = vertical_scroll_bar.maximum()
        current_value = vertical_scroll_bar.value()
        threshold = max_value - 10

        if current_value >= threshold and not self.scroll_locked:
            self.scroll_locked = True
            self.next_page()

    def _create_actions(self):
        self.toggle_action = QAction("Toggle Full-Size", self)
        self.toggle_action.triggered.connect(self.toggle_full_size)

    def _create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        toolbar.addAction(self.toggle_action)

    def load_chapter(self, chapter_info, append=False):
        """Load chapter images and optionally append to the current scene."""
        if isinstance(chapter_info, dict):
            cbz_filename = chapter_info.get("cbz_filename")
        else:
            cbz_filename = chapter_info

        if cbz_filename is None:
            print("Error: Cannot load chapter because cbz_filename is None.")
            return

        try:
            with zipfile.ZipFile(cbz_filename, 'r') as zf:
                images = sorted(
                    [f for f in zf.namelist() if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
                )

                if not append:
                    self.scene.clear()
                    self.current_image_index = 0
                else:
                    self.current_image_index = 0 

                self.chapter_images = images
                self.cbz_file = cbz_filename
                self.display_image_from_cbz(append=append)

        except Exception as e:
            print(f"Failed to load chapter: {e}")

    def display_image_from_cbz(self, append=False):
        if not self.chapter_images:
            print("No images found in chapter.")
            return

        try:
            with zipfile.ZipFile(self.cbz_file, 'r') as zf:
                while self.current_image_index < len(self.chapter_images):
                    image_name = self.chapter_images[self.current_image_index]
                    with zf.open(image_name) as file:
                        image_data = file.read()
                    pixmap = QPixmap()
                    pixmap.loadFromData(image_data)
                    y_offset = self.scene.itemsBoundingRect().bottom() if self.scene.items() else 0
                    item = QGraphicsPixmapItem(pixmap)
                    item.setPos(0, y_offset)
                    self.scene.addItem(item)

                    self.current_image_index += 1

                    if not append:
                        break 

            self.scroll_locked = False

        except Exception as e:
            print(f"Error displaying image: {e}")

    def load_cbz_image(self, filename):
        """Extract and load the first image from a CBZ file."""
        try:
            if not filename or isinstance(filename, dict):
                raise ValueError("Invalid file type: Expected a file path, got None or dict.")
            
            with zipfile.ZipFile(filename, 'r') as zf:
                image_files = [f for f in zf.namelist() if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
                if not image_files:
                    return None
                image_files.sort()
                with zf.open(image_files[0]) as file:
                    data = file.read()
                    return data
        except Exception as e:
            print(f"Error reading CBZ file: {e}")
            return None

    def fitInView(self):
        """Fit the image into the window."""
        rect = self.pixmap_item.boundingRect()
        self.view.fitInView(rect, Qt.KeepAspectRatio)

    def toggle_full_size(self):
        """Toggle full-size or fit-to-window mode."""
        self.full_size_mode = not self.full_size_mode
        if self.full_size_mode:
            self.view.resetTransform()
            self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        else:
            self.fitInView()

    def keyPressEvent(self, event):
        """Handle key press events for navigation."""
        if event.key() == Qt.Key_Left:
            self.prev_page()
        elif event.key() == Qt.Key_Right:
            self.next_page()
        elif event.key() == Qt.Key_Up:
            self.scroll_up()
        elif event.key() == Qt.Key_Down:
            self.scroll_down()
        else:
            super().keyPressEvent(event)

    def next_page(self):
        if self.current_image_index < len(self.chapter_images):
            self.view.verticalScrollBar().valueChanged.disconnect(self.check_scroll_position)
            self.display_image_from_cbz()  
            self.view.verticalScrollBar().valueChanged.connect(self.check_scroll_position)
            current_chapter = self.chapters[self.current_index]["number"]
            new_page = self.current_image_index + 1  
            update_current_position(self.series_name, current_chapter, new_page)
        else:
            if self.current_index < len(self.chapters) - 1:
                current_chapter = self.chapters[self.current_index]["number"]
                add_to_read_list(self.series_name, current_chapter)
                self.current_index += 1
                next_chapter = self.chapters[self.current_index]
                self.load_chapter(next_chapter, append=True)
                update_current_position(self.series_name, next_chapter["number"], 1)
            else:
                print("No more chapters available.")



    def prev_page(self):
        if self.current_image_index > 0:
            self.view.verticalScrollBar().valueChanged.disconnect(self.check_scroll_position)
            self.current_image_index -= 1
            self.display_image_from_cbz()
            self.view.verticalScrollBar().valueChanged.connect(self.check_scroll_position)
            current_chapter = self.chapters[self.current_index]["number"]
            new_page = self.current_image_index + 1  
            update_current_position(self.series_name, current_chapter, new_page)
        else:
            if self.current_index > 0:
                self.current_index -= 1
                prev_chapter = self.chapters[self.current_index]
                self.load_chapter(prev_chapter) 
                update_current_position(self.series_name, prev_chapter["number"], 1)
            else:
                print("No previous chapters available.")

    def scroll_up(self):
        """Scroll up the current page."""
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().value() - ViewerConfig.SCROLL_INCREMENT)

    def scroll_down(self):
        """Scroll down the current page."""
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().value() + ViewerConfig.SCROLL_INCREMENT)
