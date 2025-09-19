import requests
import lxml.etree as ET

# Originalfeed (Webnode)
SOURCE_FEED = "https://www.lampster.se/rss/pf-google_nok-no.xml"
# Utfil som ska publiceras på GitHub Pages
OUTPUT_FILE = "norsk-feed.xml"

# Valutakonvertering SEK -> NOK
CONVERSION_RATE = 1.3375

def main():
    # Hämta originalfeed
    resp = requests.get(SOURCE_FEED)
    resp.raise_for_status()
    xml = ET.fromstring(resp.content)

    # Namespacehantering (Webnode använder ns0 istället för g ibland)
    ns = {"g": "http://base.google.com/ns/1.0"}

    # Skapa nytt RSS-dokument
    rss = ET.Element("rss", version="2.0", nsmap={"g": "http://base.google.com/ns/1.0"})
    channel = ET.SubElement(rss, "channel")

    # Kopiera över huvudinfo från originalet
    for tag in ["title", "link", "description"]:
        el = xml.find(f"./channel/{tag}")
        if el is not None:
            ET.SubElement(channel, tag).text = el.text

    # Gå igenom alla produkter
    for item in xml.findall("./channel/item"):
        new_item = ET.SubElement(channel, "item")

        # id
        gid = item.find("g:id", ns)
        if gid is not None:
            ET.SubElement(new_item, "{http://base.google.com/ns/1.0}id").text = gid.text
            mpn = ET.SubElement(new_item, "{http://base.google.com/ns/1.0}mpn")
            mpn.text = gid.text

        # title
        title = item.find("title")
        if title is not None:
            ET.SubElement(new_item, "{http://base.google.com/ns/1.0}title").text = title.text

        # description
        desc = item.find("description")
        if desc is not None:
            ET.SubElement(new_item, "{http://base.google.com/ns/1.0}description").text = desc.text

        # link
        link = item.find("link")
        if link is not None:
            ET.SubElement(new_item, "{http://base.google.com/ns/1.0}link").text = link.text

        # image_link
        img = item.find("g:image_link", ns)
        if img is not None:
            ET.SubElement(new_item, "{http://base.google.com/ns/1.0}image_link").text = img.text

        # availability
        avail = item.find("g:availability", ns)
        if avail is not None:
            ET.SubElement(new_item, "{http://base.google.com/ns/1.0}availability").text = avail.text

        # product_type
        ptype = item.find("g:product_type", ns)
        if ptype is not None:
            ET.SubElement(new_item, "{http://base.google.com/ns/1.0}product_type").text = ptype.text

        # price (konverterad till NOK)
        price = item.find("g:price", ns)
        if price is not None:
            try:
                amount, currency = price.text.split()
                nok_price = float(amount) * CONVERSION_RATE
                ET.SubElement(new_item, "{http://base.google.com/ns/1.0}price").text = f"{nok_price:.2f} NOK"
            except Exception as e:
                print("Kunde inte konvertera pris:", e)

        # Extra fält
        ET.SubElement(new_item, "{http://base.google.com/ns/1.0}condition").text = "new"
        ET.SubElement(new_item, "{http://base.google.com/ns/1.0}brand").text = "Lampster"

    # Spara fil
    tree = ET.ElementTree(rss)
    tree.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True, pretty_print=True)

if __name__ == "__main__":
    main()
