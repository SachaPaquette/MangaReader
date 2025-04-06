import re
import curses
import time
import tkinter as tk

def clean_filename(title):
    invalid_chars = r'[<>:"/\\|?*\x00-\x1F]'
    title = re.sub(invalid_chars, '', title)
    title = title.replace('–', '-').replace('’', "'").replace('“', '"').replace('”', '"')
    title = re.sub(r'\s+', '_', title.strip())
    return title

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

def get_root():
    return tk.Tk()