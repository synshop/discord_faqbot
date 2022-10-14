import discord
from discord.ext import commands
import random, string

import config

token = config.TOKEN

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

client = discord.Client(intents=intents)

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
            await message.channel.send(config.SHOP_HOURS)

client.run(token)