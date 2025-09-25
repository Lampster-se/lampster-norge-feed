import requests
import xml.etree.ElementTree as ET
from datetime import datetime

URL = "https://www.lampster.se/rss/pf-google_nok-no.xml"
OUTPUT_FILE = "feed_output.xml"

def fetch_feed(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.text

def parse_feed(xml_content):
    root = ET.fromstring(xml_content)
    items = []

    for item in root.findall(".//item"):
        title = item.findtext("title", default="")
        link = item.findtext("link", default="")
        pubDate = item.findtext("pubDate", default=datetime.now().isoformat())
        items.append({"title": title, "link": link, "pubDate": pubDate})

    return items

def save_feed(items, filename):
    root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(root, "channel")

    for item in items:
        item_elem = ET.SubElement(channel, "item")
        ET.SubElement(item_elem, "title").text = item["title"]
        ET.SubElement(item_elem, "link").text = item["link"]
        ET.SubElement(item_elem, "pubDate").text = item["pubDate"]

    tree = ET.ElementTree(root)
    tree.write(filename, encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    xml_data = fetch_feed(URL)
    items = parse_feed(xml_data)
    save_feed(items, OUTPUT_FILE)
    print(f"Feed generated with {len(items)} items and saved to {OUTPUT_FILE}.")
