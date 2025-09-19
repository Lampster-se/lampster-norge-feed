import requests
import xml.etree.ElementTree as ET

# Din norska feed från Webnode
URL = "https://www.lampster.se/rss/pf-google_nok-no.xml"

# Hämta feed
r = requests.get(URL)
r.raise_for_status()

root = ET.fromstring(r.content)

# Namespace fix
ns = {"g": "http://base.google.com/ns/1.0"}

# Bygg ny RSS
rss = ET.Element("rss", {
    "xmlns:g": "http://base.google.com/ns/1.0",
    "version": "2.0"
})
channel = ET.SubElement(rss, "channel")

for item in root.findall(".//item"):
    # Bara produkter märkta "Norsk"
    pt = item.find("g:product_type", ns)
    if pt is None or "Norsk" not in pt.text:
        continue

    new_item = ET.SubElement(channel, "item")

    # Kopiera id, titel, beskrivning, etc.
    for tag in ["id", "title", "description", "link", "image_link", "availability", "brand", "gtin"]:
        el = item.find(f"g:{tag}", ns)
        if el is not None:
            new = ET.SubElement(new_item, f"g:{tag}")
            new.text = el.text

    # Pris konvertering SEK -> NOK (med 1,3375 påslag)
    price = item.find("g:price", ns)
    if price is not None:
        try:
            value, currency = price.text.split()
            sek = float(value)
            nok = round(sek * 1.3375, 2)
            new_price = ET.SubElement(new_item, "g:price")
            new_price.text = f"{nok} NOK"
        except Exception as e:
            print("Kunde inte konvertera pris:", price.text, e)

# Skriv fil
ET.ElementTree(rss).write("norsk-feed.xml", encoding="utf-8", xml_declaration=True)
