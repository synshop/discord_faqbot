import os
from time import sleep
from data.printer_config import PRINTERS
import fdmprinting.archive_retrieve as ar

while True:
    print("Loop starting")
    database = ar.get_database_handle()
    for printer_id in PRINTERS:
        printer = PRINTERS[printer_id]
        printer_str = printer["name"] + " (" + printer_id + " " + printer["ip"] + ")"

        current_status = ar.get_status_from_mqtt(printer, printer_id)
        job_hash = ar.get_job_hash(current_status)
        if job_hash is None:
            print(printer_str + " Error: job_hash or current_status was empty, skipping")
            continue

        prior_status = ar.get_by_job_hash(job_hash, database)
        if prior_status is None:
            p_mins = -1
        else:
            p_mins = int(prior_status["mins"])
        c_mins = int(current_status["mins"])

        if (prior_status is None or
                prior_status["state"] != current_status["state"] or
                c_mins != p_mins):
            image_path = ar.save_image(printer)
            current_status["image_path"] = image_path
            ar.save_printer_status(current_status, database)
            os.remove(image_path)
            print(printer_str + " changed, wrote to DB")
        else:
            print(printer_str + " unchanged, no DB updates")

    database.close()
    print("Loop complete")
    sleep(60)