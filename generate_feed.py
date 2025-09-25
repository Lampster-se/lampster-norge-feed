import requests
import xml.etree.ElementTree as ET
from datetime import datetime

def generate_feed():
    url = "https://www.lampster.se/rss/pf-google_nok-no.xml"
    response = requests.get(url)
    response.raise_for_status()

    tree = ET.ElementTree(ET.fromstring(response.content))
    root = tree.getroot()

    # Exempel: lägg in timestamp i <channel><lastBuildDate>
    channel = root.find("channel")
    if channel is not None:
        last_build = channel.find("lastBuildDate")
        now_str = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
        if last_build is None:
            last_build = ET.SubElement(channel, "lastBuildDate")
        last_build.text = now_str

    tree.write("norsk-feed.xml", encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    generate_feed()
