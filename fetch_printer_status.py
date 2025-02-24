import json
from data.printer_config import PRINTERS
import fdmprinting.archive_retrieve as ar

def get_printer_status():

    for p in PRINTERS:
        printer = PRINTERS[p]
        printer_object = ar.get_status_from_mqtt(printer, printer["name"])
        clean_json = ar.clean_raw_json(printer_object["raw_json"])

        with open("./"+ printer["name"] + ".json", "w") as my_file:
            my_file.write(json.dumps(clean_json, indent=4))

if __name__ == "__main__":
    get_printer_status()
