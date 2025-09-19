import requests
from lxml import etree

URL = "https://www.lampster.se/rss/pf-google_nok-no.xml"
FAKTOR = 1.3375

response = requests.get(URL)
tree = etree.fromstring(response.content)

ns = {"g": "http://base.google.com/ns/1.0"}

for item in tree.xpath("//item"):
    price_elem = item.find("g:price", ns)
    if price_elem is not None:
        price_text = price_elem.text.split(" ")[0]
        currency = price_elem.text.split(" ")[1]
        sek_price = float(price_text.replace(",", "."))
        nok_price = round(sek_price * FAKTOR, 2)
        price_elem.text = f"{nok_price} NOK"

with open("norsk-feed.xml", "wb") as f:
    f.write(etree.tostring(tree, pretty_print=True, encoding="UTF-8"))
