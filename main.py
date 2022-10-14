import discord
from discord.ext import commands
import random

import config

token = config.TOKEN

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

client = discord.Client(intents=intents)

bot = commands.Bot(command_prefix='?', description="hello", intents=intents)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@bot.command()
async def add(ctx, left: int, right: int):
    """Adds two numbers together."""
    await ctx.send(left + right)

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content == "what time does the shop open?":
        await message.channel.send('```Hello!```')

client.run(token)