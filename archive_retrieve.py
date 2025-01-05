import paho.mqtt.subscribe as subscribe
import json, ssl, sqlite3, av, hashlib

db_file = "printers.sqlite"
printer_table = "print_status"

def get_database_handle():
    create_table_statement = """CREATE TABLE IF NOT EXISTS print_status (
        id text PRIMARY KEY,
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


def get_id(status):
    return hashlib.md5(
        status["name"].encode() +
        status["job"].encode() +
        status["printer_id"].encode()
    ).hexdigest()


def get_by_id(id, database):
    search_sql = '''
        SELECT      
            id, date, printer, printer_id, state, job, mins, task_id
        FROM print_status 
        WHERE id = ?
    '''
    search = (id,)
    cursor = database.cursor()
    cursor.execute(search_sql, search)
    found = cursor.fetchone()
    return found


def save_printer_status(status, database):
    save_sql = '''
        INSERT INTO 
        print_status(id, date, printer, printer_id, state, job, mins, task_id)
        VALUES
        (?, CURRENT_TIMESTAMP, ?,?,?,?,?,?)        
        ON CONFLICT(id) 
        DO UPDATE SET 
        date = excluded.date, state = excluded.state, mins = excluded.mins;
    '''
    row = (
        get_id(status), status["name"], status["printer_id"], status["state"],
        status["job"], status["mins"], status["task_id"]
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
    except Exception as e:
        print(f'Failed getting status for {printer["name"]} ({printer["ip"]}:{printer["port"]})', e)

    return status


