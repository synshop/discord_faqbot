import paho.mqtt.subscribe as subscribe
import json, ssl, config, requests, sqlite3, datetime
from bs4 import BeautifulSoup
from printer_config import PRINTERS

db_file = "printers.sqlite"
printer_table = "print_status"

def get_database_handle():

    create_table_statement = """CREATE TABLE IF NOT EXISTS print_status (
        id INTEGER PRIMARY KEY,
        date TIMESTAMP,  
        printer text NOT NULL, 
        printer_id text NOT NULL, 
        state text NOT NULL, 
        raw_object text NOT NULL,
        job text, 
        mins text
    );"""
    try:
        with sqlite3.connect(db_file) as database:
            cursor = database.cursor()
            cursor.execute(create_table_statement)
            database.commit()
    except sqlite3.OperationalError as e:
        print("Failed to open database", db_file, ". Error is:", e)

    return database


def save_printer_status(printer, printer_id, state, raw_object, job, mins, database):
    currentDateTime = datetime.datetime.now()
    sql = '''INSERT INTO print_status(date, printer, printer_id, state, raw_object, job, mins)
             VALUES(?,?,?,?,?,?,?) '''

    row = (
        currentDateTime,
        printer,
        printer_id,
        state,
        str(raw_object),
        job,
        mins
    )
    cursor = database.cursor()
    # print(row)
    cursor.execute(sql, row)

    # commit the changes
    database.commit()

    # get the id of the last inserted row
    return cursor.lastrowid


def get_printer_status():
    status = ""
    database = get_database_handle()

    for printer_id in PRINTERS:
        printer = PRINTERS[printer_id]

        auth = {"username": printer["username"], "password": printer["access_code"]}
        tls = ssl._create_unverified_context()

        msg = subscribe.simple(topics=printer["topic_name"], hostname=printer["ip"], port=printer["port"], auth=auth,
                               tls=tls)
        printer_object = json.loads(msg.payload)

        name = printer["name"]
        job = printer_object["print"]["subtask_name"]
        state = printer_object["print"]["gcode_state"]
        mins = printer_object["print"]["mc_remaining_time"]

        save_printer_status(name, printer_id, state, printer_object, job, mins, database)

        # print(name, state, mins, job, printer_id)

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


get_printer_status()
# print(get_shop_hours())