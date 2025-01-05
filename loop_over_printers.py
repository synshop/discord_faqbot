import archive_retrieve as ar
from printer_config import PRINTERS

print("Loop starting")
database = ar.get_database_handle()

for printer_id in PRINTERS:
    printer = PRINTERS[printer_id]
    print("Looping " + printer["name"] + " (" + printer_id + " " + printer["ip"] + ")")
    status = ar.get_status_from_mqtt(printer, printer_id)
    ar.save_printer_status(status, database)
    ar. save_image(printer["ip"], printer["access_code"])

database.close()
print("Loop complete")