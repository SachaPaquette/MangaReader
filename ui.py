import curses
from network import process_chapter
from utils import top_left_menu, get_root

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

def display_message(stdscr, message, start_row=0):
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