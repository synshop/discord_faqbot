from bs4 import BeautifulSoup
from printer_config import PRINTERS
import config, discord_token, requests, string, discord, os, archive_retrieve as ar


intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

client = discord.Client(intents=intents)

async def send_printer_status(message):
    # thanks https://plainenglish.io/blog/send-an-embed-with-a-discord-bot-in-python
    database = ar.get_database_handle()

    for printer_id in PRINTERS:
        status = ar.get_status_from_db(printer_id, database)
        if status is not False:
            printer = status["printer"]
            embed = discord.Embed(
                title="🖨 " + printer + ": " + status["state"].title(),
                color=0xFF5733
            )

            value = (
                """`{0}`\n{1} Min Remain""".
                     format(status["job"], status["mins"])
            )

            # todo - avoid writing to disk in /tmp
            image_path  = "/tmp/" + status["job_hash"] + ".jpg"
            with open(image_path, 'wb') as file:
                file.write(status["image"])
            file = discord.File(image_path, filename="printer.jpg")
            embed.set_image(url="attachment://printer.jpg")
        else:
            value = "Failed to get status for printer " + printer_id
            file = None
            image_path = None
            printer = None


        embed.add_field(name=printer, value=value, inline=False)
        await message.channel.send(embed=embed, file=file)
        if image_path is not None:
            os.remove(image_path)

    database.close()


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
        await send_printer_status(message)

    for phrase in config.PHRASES:
        if phrase in m:
            print(f'matched on: {phrase}')
            await message.channel.send(get_shop_hours())
            break

client.run(discord_token.TOKEN)
