import json, ssl, sqlite3, hashlib, os, subprocess, discord, paho.mqtt.subscribe as subscribe

from data import config
from data.printer_config import PRINTERS
from .const_print_errors import PRINT_ERROR_ERRORS

db_file = "data/printers.sqlite"
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
        print("Failed to capture image from ", printer["ip"], " Error:", e)
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
        status["raw_json"] = json.dumps(printer_object)
    except Exception as e:
        print(f'Failed getting status for {printer["name"]} ({printer["ip"]}:{printer["port"]})', e)

    return status


def get_status_msg(status):
    clean_json = json.loads(status["raw_json"])
    fail_reason = int(clean_json["print"]["fail_reason"])

    if fail_reason != 0:
        # Convert the python hex output to match the 
        # fixed width format of const_print_errors.py
        hex_code = f'{fail_reason:x}'
        if len(hex_code) == 7: hex_code = "0" + str(hex_code)
        
        for key, value in PRINT_ERROR_ERRORS.items():
            if hex_code.upper() == key:
                return "\n\n**" + value + "**\n\n"
  
    return "\n\n"


# thanks https://plainenglish.io/blog/send-an-embed-with-a-discord-bot-in-python
async def send_printer_status(message):
    database = get_database_handle()

    for printer_id in PRINTERS:
        status = get_status_from_db(printer_id, database)
        if status is not False and status is not None:
            printer = status["printer"]
            embed = discord.Embed(
                title="🖨 " + printer + ": " + status["state"].title(),
                color=0xFF5733
            )

            value = ("""`{0}`\n{1} Min Remain{2}_{3}_""".
                     format(status["job"], status["mins"], get_status_msg(status), status["dateLocal"]))
                
            image_path  = "/tmp/" + status["job_hash"] + ".jpg"
            with open(image_path, 'wb') as file: # todo - avoid writing to disk
                file.write(status["image"])
            file = discord.File(image_path, filename="printer.jpg")
            embed.set_image(url="attachment://printer.jpg")
        else:
            embed = discord.Embed(
                title="🖨 " + PRINTERS[printer_id]["name"] + ": Error",
                color=0xFF5733
            )
            value = "Failed to query DB for printer " + printer_id
            file = None
            image_path = None
            printer = ""

        embed.add_field(name="", value=value, inline=False)
        await message.channel.send(embed=embed, file=file)

        if image_path is not None:
            os.remove(image_path)

    database.close()



