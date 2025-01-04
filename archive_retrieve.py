import paho.mqtt.subscribe as subscribe
import json, ssl, config, requests, sqlite3, pytz, av, time, PIL
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from printer_config import PRINTERS

db_file = "printers.sqlite"
printer_table = "print_status"

def get_database_handle():

    create_table_statement = """CREATE TABLE IF NOT EXISTS print_status (
        id INTEGER PRIMARY KEY,
        date DATETIME NOT NULL,  
        printer text NOT NULL, 
        printer_id text NOT NULL, 
        state text NOT NULL, 
        job text, 
        mins text,
        task_id text,
        image BLOB
    );"""

    try:
        with sqlite3.connect(
                db_file,
                detect_types=sqlite3.PARSE_DECLTYPES |
                sqlite3.PARSE_COLNAMES) as database:
            cursor = database.cursor()
            cursor.execute(create_table_statement)
            database.commit()
    except sqlite3.OperationalError as e:
        print("Failed to open database", db_file, ". Error is:", e)
        exit(1)

    return database

# Thanks https://github.com/Cacsjep/pyrtsputils/blob/main/snapshot_generator.py
def save_image(ip, password):
    url = "rtsps://bblp:" + password + "@" + ip + ":322/streaming/live/1"
    video = av.open(url, 'r')
    for packet in video.demux():
        for frame in packet.decode():
            frame.to_image().save(f'/tmp/{ip}.jpg')
            video.close()
            return


def save_printer_status(status, database):
    time_zone = pytz.timezone('US/Pacific')
    datetime = datetime.now(time_zone)
    sql = '''
        INSERT INTO 
        print_status(date, printer, printer_id, state, job, mins, task_id)
        VALUES
        (?,?,?,?,?,?,?)
    '''
    row = (
        datetime, status["name"], status["printer_id"], status["state"],
        status["job"], status["mins"], status["task_id"]
    )
    cursor = database.cursor()
    # todo - fix this error:
    #  archive_retrieve.py:63: DeprecationWarning: The default datetime adapter is deprecated as of Python 3.12; see the sqlite3 documentation for suggested replacement recipes
    cursor.execute(sql, row)

    # commit the changes
    database.commit()

    # get the id of the last inserted row
    return cursor.lastrowid


def get_printer_status(printer, printer_id):
    auth = {"username": printer["username"], "password": printer["access_code"]}
    tls = ssl._create_unverified_context()
    status = {}
    try:
        msg = subscribe.simple(
            topics=printer["topic_name"],
            hostname=printer["ip"],
            port=printer["port"],
            auth=auth,
            tls=tls
        )
        printer_object = json.loads(msg.payload)

        status["name"] = printer["name"]
        status["printer_id"] = printer_id
        status["state"] = printer_object["print"]["gcode_state"]
        status["job"] = printer_object["print"]["subtask_name"]
        status["mins"] = printer_object["print"]["mc_remaining_time"]
        status["task_id"] = printer_object["print"]["task_id"]
    except Exception as e:
        print(f'Failed getting status for {printer["name"]} ({printer["ip"]}:{printer["port"]})', e)

    return status


def loop_over_printers():
    database = get_database_handle()

    for printer_id in PRINTERS:
        printer = PRINTERS[printer_id]
        status = get_printer_status(printer, printer_id)
        save_printer_status(status, database)
        save_image(printer["ip"], printer["access_code"])

    database.close()


def get_shop_hours():
    r = requests.get(config.SHOP_HOURS_URL)
    soup = BeautifulSoup(r.text, 'html.parser')
    shop_hours = soup.find(id="shophours")

    hours_dict = {}

    for tr in shop_hours.find_all('tr'):
        td = tr.find_all("td")
        hours_dict[td[0].text] = td[1].text

    markdown_string = f'```\nCurrent Shop Hours (fetched from https://synshop.org/hours) \n===\n'

    for k, v in hours_dict.items():
        spaces = ""
        s = 11 - (len(k) + 1)
        for x in range(s):
            spaces = spaces + " "

        markdown_string = markdown_string + f'{k}:{spaces}{v}\n'

    markdown_string = markdown_string + f'\n{config.SHOP_ADDRESS}\n'
    markdown_string = markdown_string + f'\n{config.MEMBERSHIP_NOTICE}\n```'

    return markdown_string


loop_over_printers()
# print(get_shop_hours())