import discord
from discord.ext import commands
import requests
from bs4 import BeautifulSoup

import random, string

import config, discord_token

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

client = discord.Client(intents=intents)

def get_shop_hours():
    r = requests.get(config.SHOP_HOURS_URL)
    soup = BeautifulSoup(r.text, 'html.parser')
    shop_hours = soup.find(id="shophours")

    hours_dict = {}

    for tr in shop_hours.find_all('tr'):
        td = tr.find_all("td")
        hours_dict[td[0].text] = td[1].text

    markdown_string = f'```\nCurrent Shop Hours\n=====\n'

    for k,v in hours_dict.items():
        spaces = ""
        s = 11 - (len(k) + 1)
        for x in range(s):
            spaces = spaces + " "

        markdown_string = markdown_string + f'{k}:{spaces}{v}\n'

    markdown_string = markdown_string + f'\n5967 Harrison Dr\nLas Vegas, NV, 89120\n```'

    return(markdown_string)


@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    m = message.content.upper()
    m = m.translate(str.maketrans('', '', string.punctuation))
    print(m)

    for phrase in config.PHRASES:
        if m == phrase:
            await message.channel.send(get_shop_hours())

# client.run(discord_token.TOKEN)

print(get_shop_hours())