import fdmprinting.archive_retrieve as ar


def get_printer_status():
    for id in ar.PRINTERS:
        printer = ar.PRINTERS[id]
        file = printer["name"] + ".json"
        print("Writing " + file)
        printer_object = ar.get_status_from_mqtt(printer, id)
        printer_object["raw_json"] = ar.clean_raw_json(printer_object["raw_json"])
        with open(file, "w") as my_file:
            my_file.write(ar.json.dumps(printer_object, indent=4))
    print("Done")


if __name__ == "__main__":
    get_printer_status()
