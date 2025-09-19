import requests
from lxml import etree
import re

# Källa (Webnode norska feed)
URL = "https://www.lampster.se/rss/pf-google_nok-no.xml"
FAKTOR = 1.3375  # SEK -> NOK

NS_G = "http://base.google.com/ns/1.0"
NS = {"g": NS_G}

def get_text_ns_or_plain(item, tag):
    """Försök hämta text från g:tag eller plain <tag>"""
    el = item.find(f"g:{tag}", namespaces=NS)
    if el is None:
        el = item.find(tag)
    if el is None:
        return None
    return el.text

def extract_price_as_number(price_text):
    """Plocka ut sifferdelen ur prissträngen."""
    if not price_text:
        return None
    m = re.search(r"([\d\.,]+)", price_text)
    if not m:
        return None
    return float(m.group(1).replace(",", "."))

def copy_known_tags(item, new_item, tags):
    for tag in tags:
        txt = get_text_ns_or_plain(item, tag)
        if txt is not None and txt.strip() != "":
            child = etree.SubElement(new_item, f"{{{NS_G}}}{tag}")
            child.text = txt

def main():
    resp = requests.get(URL, timeout=30)
    resp.raise_for_status()
    root = etree.fromstring(resp.content)

    # Ny RSS med g: som namespace
    rss = etree.Element("rss", nsmap={"g": NS_G}, version="2.0")
    channel = etree.SubElement(rss, "channel")

    # Loop items
    for item in root.xpath("//item"):
        # Hitta produktkategori (g:product_type eller product_type)
        pt_text = get_text_ns_or_plain(item, "product_type") or ""
        if "Norsk" not in pt_text:
            continue

        new_item = etree.SubElement(channel, "item")

        # Kopiera standardfält (id, title, description, link, image_link ...)
        standard_tags = [
            "id","title","description","link","image_link",
            "availability","brand","gtin","mpn","condition","product_type"
        ]
        copy_known_tags(item, new_item, standard_tags)

        # Pris: hantera konvertering från SEK -> NOK (om möjligt)
        price_text = get_text_ns_or_plain(item, "price")
        if price_text:
            val = extract_price_as_number(price_text)
            if val is not None:
                nok = round(val * FAKTOR, 2)
                p = etree.SubElement(new_item, f"{{{NS_G}}}price")
                p.text = f"{nok} NOK"
            else:
                # fallback: kopiera originaltext
                p = etree.SubElement(new_item, f"{{{NS_G}}}price")
                p.text = price_text

        # Kopiera övriga element från originalitem (så vi inte missar custom labels etc.)
        # Vi undviker att duplicera redan kopierade standard_tags.
        copied = set(standard_tags + ["price"])
        for child in item:
            q = etree.QName(child.tag)
            local = q.localname
            if local in copied:
                continue
            # Ignorera tomma element
            if child.text is None or child.text.strip() == "":
                continue
            # Skriv ut som g:localname så Google ser dem
            etree.SubElement(new_item, f"{{{NS_G}}}{local}").text = child.text

    # Skriv fil
    xml = etree.tostring(rss, pretty_print=True, xml_declaration=True, encoding="utf-8")
    with open("norsk-feed.xml", "wb") as f:
        f.write(xml)
    print("norsk-feed.xml skapad")

if __name__ == "__main__":
    main()
