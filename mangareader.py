import curses
import sys
from ui import MenuOptions, display_message
from data import load_read_list
from network import search_manga, continue_reading, process_chapter
from viewer import MangaViewer
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

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

                current_chapter = chapters[current_index]
                current_cbz, message = process_chapter(current_chapter, series_name, cookies, stdscr)

                display_message(stdscr, message)
                if current_cbz:
                    curses.endwin()  
                    try:
                        app = QApplication(sys.argv)
                        viewer = MangaViewer(current_cbz, chapters, current_index, series_name, cookies, stdscr)
                        viewer.showMaximized()
                        sys.exit(app.exec_())
                    except Exception as e:
                        print(f"Viewer error: {e}")
                        display_message(stdscr, f"Viewer error: {e}. Press any key to continue.")
                        stdscr.getch()
                    finally:
                        stdscr = curses.initscr()
                        stdscr.keypad(True)
                        stdscr.refresh()

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
            break

if __name__ == "__main__":
    curses.wrapper(main)
