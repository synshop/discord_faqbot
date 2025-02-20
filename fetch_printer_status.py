import json, ssl

import paho.mqtt.subscribe as subscribe
from data.printer_config import PRINTERS

def get_printer_status():

    for p in PRINTERS:
        printer = PRINTERS[p]

        auth = {"username":printer["username"],"password":printer["access_code"]}
        tls = ssl._create_unverified_context()

        msg = subscribe.simple(topics=printer["topic_name"],hostname=printer["ip"],port=printer["port"],auth=auth,tls=tls)
        printer_object = json.loads(msg.payload)

        name = printer["name"]
        job = printer_object["print"]["subtask_name"]
        state = printer_object["print"]["gcode_state"]
        mins = printer_object["print"]["mc_remaining_time"]

        with open("./"+ name + ".json", "w") as my_file:
            my_file.write(json.dumps(printer_object, indent=4))

if __name__ == "__main__":
    get_printer_status()
