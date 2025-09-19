import requests
import lxml.etree as ET
from decimal import Decimal, ROUND_HALF_UP
import os

# URL till originalfeeden
SOURCE_URL = "https://www.lampster.se/rss/pf-google_nok-no.xml"
OUTPUT_DIR = "lampster-norge-feed"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "norsk-feed.xml")
CONVERSION_RATE = Decimal("1.3375")  # SEK → NOK med påslag

# Skapa mappen om den inte finns
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Ladda ner originalfeeden
resp = requests.get(SOURCE_URL)
resp.raise_for_status()

# Parse XML
parser = ET.XMLParser(recover=True)
tree = ET.fromstring(resp.content, parser=parser)

# Namespace
G_NS = "http://base.google.com/ns/1.0"
ns = {"g": G_NS}

# Skapa ny RSS-root med namespace
rss = ET.Element("rss", version="2.0", nsmap={"g": G_NS})
channel = ET.SubElement(rss, "channel")

# Kopiera över channel-info från originalet
orig_channel = tree.find("channel")
for tag in ["title", "link", "description"]:
    elem = orig_channel.find(tag)
    if elem is not None and elem.text:
        ET.SubElement(channel, tag).text = elem.text

# Gå igenom alla produkter
for item in orig_channel.findall("item"):
    product_type_elem = item.find("g:product_type", ns)
    if product_type_elem is None or "Norsk" not in (product_type_elem.text or ""):
        continue  # hoppa över om inte norsk kategori

    new_item = ET.SubElement(channel, "item")

    # Kopiera över viktiga fält
    for tag in ["id", "title", "description", "link",
                "image_link", "availability", "product_type", "price"]:
        elem = item.find(f"g:{tag}", ns)
        text = elem.text if elem is not None else None

        # Konvertera pris till NOK
        if tag == "price":
            if text:
                try:
                    value, currency = text.split()
                    nok_value = (Decimal(value) * CONVERSION_RATE).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    text = f"{nok_value} NOK"
                except Exception as e:
                    print(f"Fel vid pris-konvertering: {e}")
                    text = "0.00 NOK"
            else:
                text = "0.00 NOK"

        ET.SubElement(new_item, f"{{{G_NS}}}{tag}").text = text or "N/A"

# Spara till fil
tree_out = ET.ElementTree(rss)
tree_out.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True, pretty_print=True)

print(f"Klar! Fil sparad som {OUTPUT_FILE}")
