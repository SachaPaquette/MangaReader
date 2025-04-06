import curses
from ui import MenuOptions, display_message
from data import load_read_list
from network import search_manga, continue_reading, process_chapter
from viewer import MangaViewer
import tkinter as tk

def main(stdscr):
    menu = MenuOptions()
    while True:
        choice = menu.get_choice(stdscr)
        if choice == 0:  # Search for Manga
            try:
                series_name, chapters, current_index, cookies = search_manga(stdscr)
                if not (series_name and chapters):
                    display_message(stdscr, "Search failed. Press any key to continue.")
                    stdscr.getch()
                    continue

                display_message(stdscr, f"Processing {series_name}...")
                current_chapter = chapters[current_index]
                current_cbz, message = process_chapter(current_chapter, series_name, cookies, stdscr)

                display_message(stdscr, message)
                if current_cbz:
                    row = display_message(stdscr, "Launching viewer...")
                    curses.endwin()
                    try:
                        root = tk.Tk()
                        viewer = MangaViewer(root, current_cbz, chapters, current_index, series_name, cookies, stdscr)
                        root.mainloop()
                        messages = viewer.get_messages()
                    except Exception as e:
                        print(f"Viewer error: {e}")
                        messages = [f"Viewer error: {e}"]
                    finally:
                        stdscr = curses.initscr()
                        stdscr.keypad(True)
                        stdscr.refresh()
                        full_message = "\n".join(messages) + "\nReturned to menu. Press any key to continue."
                        display_message(stdscr, full_message)
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