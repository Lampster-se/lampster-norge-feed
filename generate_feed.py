import requests
import lxml.etree as ET
from decimal import Decimal, ROUND_HALF_UP
import os

SOURCE_URL = "https://www.lampster.se/rss/pf-google_nok-no.xml"
OUTPUT_DIR = "lampster-norge-feed"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "norsk-feed.xml")
CONVERSION_RATE = Decimal("1.3375")  # SEK → NOK
STANDARD_SEK_SHIPPING = 99
FREE_SHIPPING_THRESHOLD = Decimal("735.00")  # NOK

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Hämta live feed
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

# Konvertera standardfrakt
NOK_STANDARD_SHIPPING = (Decimal(STANDARD_SEK_SHIPPING) * CONVERSION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

for item in orig_channel.findall("item"):
    product_type_elem = item.find("g:product_type", ns)
    text_product_type = (product_type_elem.text or "").lower() if product_type_elem is not None else ""
    if "norsk" not in text_product_type:
        continue

    new_item = ET.SubElement(channel, "item")

    # Kopiera fält och konvertera pris
    for tag in ["id", "title", "description", "link", "image_link", "availability", "product_type", "price"]:
        elem = item.find(f"g:{tag}", ns)
        text = elem.text if elem is not None else None

        if tag == "price" and text:
            try:
                value, currency = text.split()
                nok_value = (Decimal(value) * CONVERSION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                text = f"{nok_value:.2f} NOK"
            except:
                text = f"{NOK_STANDARD_SHIPPING:.2f} NOK"
        elif tag == "price":
            text = f"{NOK_STANDARD_SHIPPING:.2f} NOK"

        ET.SubElement(new_item, f"{{{G_NS}}}{tag}").text = text or "N/A"

    # Frakt
    shipping_elem = ET.SubElement(new_item, f"{{{G_NS}}}shipping")
    ET.SubElement(shipping_elem, f"{{{G_NS}}}country").text = "NO"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}service").text = "Standard"

    price_elem = new_item.find(f"{{{G_NS}}}price")
    price_value = Decimal(price_elem.text.split()[0])
    shipping_price = Decimal("0.00") if price_value >= FREE_SHIPPING_THRESHOLD else NOK_STANDARD_SHIPPING
    ET.SubElement(shipping_elem, f"{{{G_NS}}}price").text = f"{shipping_price:.2f} NOK"

    # Hanteringstid 0-1 arbetsdagar
    ET.SubElement(shipping_elem, f"{{{G_NS}}}min_handling_time").text = "0"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}max_handling_time").text = "1"

    # Leveranstid 1-9 arbetsdagar
    ET.SubElement(shipping_elem, f"{{{G_NS}}}min_transit_time").text = "1"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}max_transit_time").text = "9"

# Spara fil
tree_out = ET.ElementTree(rss)
tree_out.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True, pretty_print=True)
print(f"Klar! Fil sparad som {OUTPUT_FILE}")
G_NS = "http://base.google.com/ns/1.0"
ns = {"g": G_NS}

rss = ET.Element("rss", version="2.0", nsmap={"g": G_NS})
channel = ET.SubElement(rss, "channel")

orig_channel = tree.find("channel")
for tag in ["title", "link", "description"]:
    elem = orig_channel.find(tag)
    if elem is not None and elem.text:
        ET.SubElement(channel, tag).text = elem.text

# Konvertera standardfrakt
NOK_STANDARD_SHIPPING = (Decimal(STANDARD_SEK_SHIPPING) * CONVERSION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

for item in orig_channel.findall("item"):
    product_type_elem = item.find("g:product_type", ns)
    text_product_type = (product_type_elem.text or "").lower() if product_type_elem is not None else ""
    if "norsk" not in text_product_type:
        continue

    new_item = ET.SubElement(channel, "item")

    # Kopiera fält och konvertera pris
    for tag in ["id", "title", "description", "link", "image_link", "availability", "product_type", "price"]:
        elem = item.find(f"g:{tag}", ns)
        text = elem.text if elem is not None else None

        if tag == "price" and text:
            try:
                value, currency = text.split()
                nok_value = (Decimal(value) * CONVERSION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                text = f"{nok_value:.2f} NOK"
            except:
                text = f"{NOK_STANDARD_SHIPPING:.2f} NOK"
        elif tag == "price":
            text = f"{NOK_STANDARD_SHIPPING:.2f} NOK"

        ET.SubElement(new_item, f"{{{G_NS}}}{tag}").text = text or "N/A"

    # Frakt
    shipping_elem = ET.SubElement(new_item, f"{{{G_NS}}}shipping")
    ET.SubElement(shipping_elem, f"{{{G_NS}}}country").text = "NO"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}service").text = "Standard"

    price_elem = new_item.find(f"{{{G_NS}}}price")
    price_value = Decimal(price_elem.text.split()[0])
    shipping_price = Decimal("0.00") if price_value >= FREE_SHIPPING_THRESHOLD else NOK_STANDARD_SHIPPING
    ET.SubElement(shipping_elem, f"{{{G_NS}}}price").text = f"{shipping_price:.2f} NOK"

    # Hanteringstid 0-1 arbetsdagar
    ET.SubElement(shipping_elem, f"{{{G_NS}}}min_handling_time").text = "0"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}max_handling_time").text = "1"

    # Leveranstid 1-9 arbetsdagar
    ET.SubElement(shipping_elem, f"{{{G_NS}}}min_transit_time").text = "1"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}max_transit_time").tex
