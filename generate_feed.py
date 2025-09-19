import requests
import lxml.etree as ET
from decimal import Decimal, ROUND_HALF_UP

# URL till originalfeeden
SOURCE_URL = "https://www.lampster.se/rss/pf-google_nok-no.xml"
OUTPUT_FILE = "norsk-feed.xml"
CONVERSION_RATE = Decimal("1.3375")  # SEK → NOK med påslag

# Ladda ner originalfeeden
resp = requests.get(SOURCE_URL)
resp.raise_for_status()

# Parse XML
parser = ET.XMLParser(recover=True)
tree = ET.fromstring(resp.content, parser=parser)

# Namnrymder
ns = {"g": "http://base.google.com/ns/1.0"}

# Skapa ny RSS-root
rss = ET.Element("rss", {
    "version": "2.0",
    "xmlns:g": "http://base.google.com/ns/1.0"
})
channel = ET.SubElement(rss, "channel")

# Kopiera över channel-info från originalet
orig_channel = tree.find("channel")
for tag in ["title", "link", "description"]:
    elem = orig_channel.find(tag)
    if elem is not None:
        ET.SubElement(channel, tag).text = elem.text

# Gå igenom alla produkter
for item in orig_channel.findall("item"):
    product_type = item.find("g:product_type", ns)
    if product_type is None or "Norsk" not in (product_type.text or ""):
        continue  # hoppa över om inte norsk kategori

    new_item = ET.SubElement(channel, "item")

    # Kopiera över viktiga fält
    for tag in ["g:id", "g:title", "g:description", "g:link",
                "g:image_link", "g:availability", "g:product_type"]:
        elem = item.find(tag, ns)
        if elem is not None and elem.text:
            ET.SubElement(new_item, tag).text = elem.text

    # Pris (konverterat)
    price_elem = item.find("g:price", ns)
    if price_elem is not None and price_elem.text:
        try:
            value, currency = price_elem.text.split()
            nok_value = (Decimal(value) * CONVERSION_RATE).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            ET.SubElement(new_item, "g:price").text = f"{nok_value} NOK"
        except Exception as e:
            print(f"Fel vid pris-konvertering: {e}")

# Spara till fil
tree_out = ET.ElementTree(rss)
tree_out.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True, pretty_print=True)

print(f"Klar! Fil sparad som {OUTPUT_FILE}")
