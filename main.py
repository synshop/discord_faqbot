import string, discord

import fdmprinting.archive_retrieve as ar
from general import shop_hours
from data import config, discord_token

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'We have logged in as the {client.user}.')
    print(f'Printer status keyword is {config.PRINTER_STATUS} and there are {len(config.PHRASES)} shop hour phrases.')

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    m = message.content.upper()
    m = m.translate(str.maketrans('', '', string.punctuation))

    if message.channel.name == config.PRINTER_CHANNEL and m == config.PRINTER_STATUS:
        await ar.send_printer_status(message)

    for phrase in config.PHRASES:
        if phrase in m:
            print(f'matched on: {phrase}')
            await message.channel.send(shop_hours.get_shop_hours())
            break

client.run(discord_token.TOKEN)
