import archive_retrieve as ar
from printer_config import PRINTERS

print("Loop starting")
database = ar.get_database_handle()

for printer_id in PRINTERS:
    printer = PRINTERS[printer_id]
    printer_str = printer["name"] + " (" + printer_id + " " + printer["ip"] + ")"

    current_status = ar.get_status_from_mqtt(printer, printer_id)
    prior_status = ar.get_by_job_hash(
        ar.get_job_hash(current_status),
        database
    )
    c_mins = int(current_status["mins"])
    if prior_status is not None:
        p_mins = int(prior_status["mins"])
    else:
        p_mins = -1

    if (prior_status is None or
            prior_status["state"] != current_status["state"] or
            c_mins != p_mins):
        ar.save_printer_status(current_status, database)
        ar.save_image(printer["ip"], printer["access_code"])
        print(printer_str + "  changed, wrote to DB")
    else:
        print(printer_str + " unchanged, no DB updates")

database.close()
print("Loop complete")