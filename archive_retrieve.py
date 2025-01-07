import paho.mqtt.subscribe as subscribe
import json, ssl, sqlite3, av, hashlib, os

db_file = "printers.sqlite"
printer_table = "print_status"

def get_database_handle():
    create_table_statement = """CREATE TABLE IF NOT EXISTS print_status (
        job_hash text PRIMARY KEY,
        date DATETIME NOT NULL,  
        printer text NOT NULL, 
        printer_id text NOT NULL, 
        state text NOT NULL, 
        job text, 
        mins text,
        task_id text,
        image BLOB,
        raw_json text
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

    database.row_factory = sqlite3.Row
    return database


# Thanks https://github.com/Cacsjep/pyrtsputils/blob/main/snapshot_generator.py
def save_image(printer):
    url = "rtsps://bblp:" + printer["access_code"] + "@" + printer["ip"] + ":322/streaming/live/1"
    video = av.open(url, 'r')
    path = '/tmp/' + printer["ip"] + '.jpg'
    try:
        for packet in video.demux():
            for frame in packet.decode():
                frame.to_image().save(path)
                video.close()
                return path
    except Exception as e:
        print("Failed to capture image from " + printer["ip"] + " Error:" + e)
        return None

def get_job_hash(status):
    return hashlib.md5(
        status["name"].encode() +
        status["job"].encode() +
        status["printer_id"].encode()
    ).hexdigest()
# todo - protect against job not being set some how?!
#
# Loop starting
# Replicator 1 (3DP-00M-748 10.0.40.126) unchanged, no DB updates
# Failed getting status for Replicator A (10.0.40.228:8883) 'gcode_state'
# Traceback (most recent call last):
#   File "/home/mrjones/Documents/discord_faqbot/loop_over_printers.py", line 12, in <module>
#     job_hash = ar.get_job_hash(current_status)
#   File "/home/mrjones/Documents/discord_faqbot/archive_retrieve.py", line 55, in get_job_hash
#     status["job"].encode() +
#     ~~~~~~^^^^^^^
# KeyError: 'job'
# (venv) FAIL

def get_by_job_hash(job_hash, database):
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

# todo - this should more intelligently get 3 printers, not last 3 rows, as that might get out of sync
def get_status_from_db(database):
    get_sql = '''
        SELECT *
        FROM print_status 
        ORDER BY date DESC
        LIMIT 3;
    '''
    cursor = database.cursor()
    cursor.execute(get_sql)
    printers = cursor.fetchall()
    return printers


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


