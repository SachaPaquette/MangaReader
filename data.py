import json
import os
import zipfile

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

def create_cbz(image_data, cbz_filename):
    with zipfile.ZipFile(cbz_filename, 'w', zipfile.ZIP_DEFLATED) as cbz:
        for img_name, img_content in image_data:
            cbz.writestr(img_name, img_content)
    return f"Created {cbz_filename}"