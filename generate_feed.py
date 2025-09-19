import requests
from lxml import etree

URL = "https://www.lampster.se/rss/pf-google_nok-no.xml"
FAKTOR = 1.3375
NS = {"g": "http://base.google.com/ns/1.0"}

resp = requests.get(URL, timeout=30)
resp.raise_for_status()
root = etree.fromstring(resp.content)

# Ny RSS med korrekt namespace-mappning (g:)
rss = etree.Element("rss", nsmap={"g": NS["g"]}, version="2.0")
channel = etree.SubElement(rss, "channel")

for item in root.xpath("//item"):
    pt = item.find("g:product_type", namespaces=NS)
    if pt is None or "Norsk" not in (pt.text or ""):
        continue

    new_item = etree.SubElement(channel, "item")

    # kopiera vanliga taggar (om de finns)
    for tag in ["id","title","description","link","image_link","availability","brand","gtin","mpn","product_type"]:
        el = item.find(f"g:{tag}", namespaces=NS)
        if el is not None and el.text:
            child = etree.SubElement(new_item, f"{{{NS['g']}}}{tag}")
            child.text = el.text

    # pris: konvertera SEK -> NOK
    price_el = item.find("g:price", namespaces=NS)
    if price_el is not None and price_el.text:
        try:
            val = price_el.text.split()[0].replace(",", ".")
            sek = float(val)
            nok = round(sek * FAKTOR, 2)
            p = etree.SubElement(new_item, f"{{{NS['g']}}}price")
            p.text = f"{nok} NOK"
        except Exception:
            p = etree.SubElement(new_item, f"{{{NS['g']}}}price")
            p.text = price_el.text

# skriv ut fil
xml = etree.tostring(rss, pretty_print=True, xml_declaration=True, encoding="utf-8")
with open("norsk-feed.xml", "wb") as f:
    f.write(xml)

print("norsk-feed.xml skapad")
