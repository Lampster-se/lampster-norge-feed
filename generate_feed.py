import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# Din källa, t.ex. RSS eller API
URL = "https://www.lampster.se/rss/pf-google_nok-no.xml"

def fetch_feed(url):
    resp = requests.get(url)
    resp.raise_for_status()  # Korrekt indenterad
    return resp.text

def generate_feed(xml_content):
    root = ET.fromstring(xml_content)
    items = []

    for item in root.findall(".//item"):
        title = item.find("title").text if item.find("title") is not None else ""
        link = item.find("link").text if item.find("link") is not None else ""
        pubDate = item.find("pubDate").text if item.find("pubDate") is not None else datetime.now().isoformat()

        items.append({
            "title": title,
            "link": link,
            "pubDate": pubDate
        })

    return items

def save_feed(items, filename="feed_output.xml"):
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
    xml_content = fetch_feed(URL)
    items = generate_feed(xml_content)
    save_feed(items)
    print(f"Feed saved with {len(items)} items.")
