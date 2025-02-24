import requests
from bs4 import BeautifulSoup

from data import config

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

        markdown_string += f'{k}:{spaces}{v}\n'

    markdown_string += f'\n{config.SHOP_ADDRESS}\n'
    markdown_string += f'\n{config.MEMBERSHIP_NOTICE}\n```'

    return markdown_string