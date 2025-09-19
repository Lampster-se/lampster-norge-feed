import requests
import lxml.etree as ET
from decimal import Decimal, ROUND_HALF_UP
import os
import math

SOURCE_URL = "https://www.lampster.se/rss/pf-google_nok-no.xml"
OUTPUT_DIR = "lampster-norge-feed"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "norsk-feed.xml")
CONVERSION_RATE = Decimal("1.3375")  # SEK → NOK

os.makedirs(OUTPUT_DIR, exist_ok=True)

resp = requests.get(SOURCE_URL)
resp.raise_for_status()

parser = ET.XMLParser(recover=True)
tree = ET.fromstring(resp.content, parser=parser)

G_NS = "http://base.google.com/ns/1.0"
ns = {"g": G_NS}

rss = ET.Element("rss", version="2.0", nsmap={"g": G_NS})
channel = ET.SubElement(rss, "channel")

orig_channel = tree.find("channel")
for tag in ["title", "link", "description"]:
    elem = orig_channel.find(tag)
    if elem is not None and elem.text:
        ET.SubElement(channel, tag).text = elem.text

# Frakt: 99 SEK → 133 NOK
SEK_SHIPPING = Decimal("99")
NOK_SHIPPING = (SEK_SHIPPING * CONVERSION_RATE).to_integral_value(rounding=ROUND_HALF_UP)  # rundar till heltal

DEFAULT_SHIPPING = {
    "country": "NO",
    "service": "Standard",
    "price": f"{NOK_SHIPPING} NOK"
}

for item in orig_channel.findall("item"):
    product_type_elem = item.find("g:product_type", ns)
    if product_type_elem is None or "Norsk" not in (product_type_elem.text or ""):
        continue

    new_item = ET.SubElement(channel, "item")

    for tag in ["id", "title", "description", "link",
                "image_link", "availability", "product_type", "price"]:
        elem = item.find(f"g:{tag}", ns)
        text = elem.text if elem is not None else None

        # Konvertera pris
        if tag == "price":
            if text:
                try:
                    value, currency = text.split()
                    nok_value = (Decimal(value) * CONVERSION_RATE).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    text = f"{nok_value} NOK"
                except:
                    text = "0.00 NOK"
            else:
                text = "0.00 NOK"

        ET.SubElement(new_item, f"{{{G_NS}}}{tag}").text = text or "N/A"

    # Lägg till fraktinformation
    shipping_elem = ET.SubElement(new_item, f"{{{G_NS}}}shipping")
    for key, value in DEFAULT_SHIPPING.items():
        ET.SubElement(shipping_elem, f"{{{G_NS}}}{key}").text = value

# Spara fil
tree_out = ET.ElementTree(rss)
tree_out.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True, pretty_print=True)
print(f"Klar! Fil sparad som {OUTPUT_FILE}")
