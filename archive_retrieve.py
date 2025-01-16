import json, ssl, sqlite3, hashlib, os, requests, subprocess, config, discord, paho.mqtt.subscribe as subscribe
from bs4 import BeautifulSoup
from printer_config import PRINTERS

db_file = "printers.sqlite"
printer_table = "print_status"

def get_database_handle():
    create_table_statement = """
        CREATE TABLE IF NOT EXISTS print_status (
            job_hash text PRIMARY KEY,
            date DATETIME NOT NULL,
            printer text NOT NULL,
            printer_id text NOT NULL,
            state text NOT NULL,
            job text,
            mins text,
            task_id text,
            image BLOB,
            raw_json text,
            owner text
        );
    """
    create_idx_printer_date = """
        CREATE INDEX IF NOT EXISTS  idx_printer_date
        ON print_status (printer_id);
    """

    try:
        with sqlite3.connect(
                db_file,
                detect_types=sqlite3.PARSE_DECLTYPES |
                sqlite3.PARSE_COLNAMES) as database:
            cursor = database.cursor()
            cursor.execute(create_table_statement)
            database.commit()
            cursor.execute(create_idx_printer_date)
            database.commit()
    except sqlite3.OperationalError as e:
        print("Failed to open database", db_file, ". Error is:", e)
        exit(1)

    database.row_factory = sqlite3.Row
    return database


# Thanks https://github.com/Cacsjep/pyrtsputils/blob/main/snapshot_generator.py
def save_image(printer):
    url = "rtsps://bblp:" + printer["access_code"] + "@" + printer["ip"] + ":322/streaming/live/1"
    path = '/tmp/' + printer["ip"] + '.jpg'
    shell = config.FFMPEG + " -loglevel fatal -y -i " + url + " -vframes 1 " + path

    try:
        subprocess.run(shell, shell=True)
        return path
    except Exception as e:
        print("Failed to capture image from " + printer["ip"] + " Error:" + e)
        return None

def get_job_hash(status):
    # thanks https://stackoverflow.com/a/3845371
    if status and "name" in status and "job" in status and "printer_id" in status:
        return hashlib.md5(
            status["name"].encode() +
            status["job"].encode() +
            status["printer_id"].encode()
        ).hexdigest()
    else:
        return None


def get_by_job_hash(job_hash, database):
    try:
        search_sql = '''
            SELECT *
            FROM print_status
            WHERE job_hash = ?
        '''
        search = (job_hash, )
        cursor = database.cursor()
        cursor.execute(search_sql, search)
        found = cursor.fetchone()
        return found
    except sqlite3.OperationalError as e:
        print("Failed to get job by hash from db for ", job_hash, ". Error is:", e)
        result = False


def get_status_from_db(printer_id, database):
    try:
        get_sql = '''
            SELECT 
                strftime('%Y-%m-%d %I:%M%p',datetime(date,'localtime')) dateLocal, 
                *
            FROM print_status
            WHERE printer_id = ?
            ORDER BY date DESC
            LIMIT 1;
        '''
        search = (printer_id, )
        cursor = database.cursor()
        cursor.execute(get_sql, search)
        printers = cursor.fetchone()
        return printers
    except sqlite3.OperationalError as e:
        print("Failed to get printer status from db for ", printer_id, ". Error is:", e)
        result = False

def save_printer_status(status, database):
    save_sql = '''
        INSERT INTO 
        print_status(job_hash, date, printer, printer_id, state, job, mins, task_id, raw_json, image)
        VALUES
        (?, CURRENT_TIMESTAMP, ?,?,?,?,?,?,?,?)
        ON CONFLICT(job_hash) 
        DO UPDATE SET 
        date = excluded.date, state = excluded.state, mins = excluded.mins, 
        raw_json = excluded.raw_json, image = excluded.image;
    '''
    path = status["image_path"]
    if path is not None and os.path.exists(path):
        with open(path, 'rb') as file:
            image = file.read()
    else:
        image = None

    row = (
        get_job_hash(status), status["name"], status["printer_id"], status["state"],
        status["job"], status["mins"], status["task_id"], status["raw_json"], image
    )
    try:
        cursor = database.cursor()
        cursor.execute(save_sql, row)
        database.commit()
        result = True
    except sqlite3.OperationalError as e:
        print("Failed to save printer status", db_file, ". Error is:", e)
        result = False
    return result


def get_status_from_mqtt(printer, printer_id):
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
        status["raw_json"] = str(printer_object)
    except Exception as e:
        print(f'Failed getting status for {printer["name"]} ({printer["ip"]}:{printer["port"]})', e)

    return status


# thanks https://plainenglish.io/blog/send-an-embed-with-a-discord-bot-in-python
async def send_printer_status(message):
    database = get_database_handle()

    for printer_id in PRINTERS:
        status = get_status_from_db(printer_id, database)
        if status is not False:
            printer = status["printer"]
            embed = discord.Embed(
                title="🖨 " + printer + ": " + status["state"].title(),
                color=0xFF5733
            )

            value = ("""`{0}`\n{1} Min Remain\n\n_{2}_""".
                     format(status["job"], status["mins"], status["dateLocal"]))
            image_path  = "/tmp/" + status["job_hash"] + ".jpg"
            with open(image_path, 'wb') as file: # todo - avoid writing to disk
                file.write(status["image"])
            file = discord.File(image_path, filename="printer.jpg")
            embed.set_thumbnail(url="attachment://printer.jpg")
        else:
            value = "Failed to get status for printer " + printer_id
            file = None
            image_path = None
            printer = None

        embed.add_field(name=printer, value=value, inline=False)
        await message.channel.send(embed=embed, file=file)
        if image_path is not None:
            os.remove(image_path)

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

    for k,v in hours_dict.items():
        spaces = ""
        s = 11 - (len(k) + 1)
        for x in range(s):
            spaces = spaces + " "

        markdown_string += f'{k}:{spaces}{v}\n'

    markdown_string += f'\n{config.SHOP_ADDRESS}\n'
    markdown_string += f'\n{config.MEMBERSHIP_NOTICE}\n```'

    return markdown_string
