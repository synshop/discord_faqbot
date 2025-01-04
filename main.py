import discord
import requests, string
from bs4 import BeautifulSoup

import paho.mqtt.subscribe as subscribe

import json, ssl
import config, discord_token

from printer_config import PRINTERS

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

client = discord.Client(intents=intents)

def get_printer_status():
    
    # thanks https://plainenglish.io/blog/send-an-embed-with-a-discord-bot-in-python
    embedInner = discord.Embed(title="🖨 Printer Status 🖨",
                               color=0xFF5733)
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
        task_id = printer_object["print"]["task_id"]

        if state == "RUNNING":
            value = """`{0}`\n{1} Min Remain (ID {2})""".format(job, mins, task_id)
        else:
            value = "Idle"

        embedInner.add_field(name=name, value=value, inline=False)

    return embedInner

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

        markdown_string = markdown_string + f'{k}:{spaces}{v}\n'

    markdown_string = markdown_string + f'\n{config.SHOP_ADDRESS}\n'
    markdown_string = markdown_string + f'\n{config.MEMBERSHIP_NOTICE}\n```'

    return(markdown_string)


@client.event
async def on_ready():
    print(f'We have logged in as {client.user}.')
    print(f'Printer status keyword is {config.PRINTER_STATUS} and there are {len(config.PHRASES)} shop hour phrases.')

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    m = message.content.upper()
    m = m.translate(str.maketrans('', '', string.punctuation))

    if message.channel.name == config.PRINTER_CHANNEL and m == config.PRINTER_STATUS:
        await message.channel.send(embed=get_printer_status())

    for phrase in config.PHRASES:
        if phrase in m:
            print(f'matched on: {phrase}')
            await message.channel.send(get_shop_hours())
            break

client.run(discord_token.TOKEN)
