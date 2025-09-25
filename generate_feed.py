#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import re
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path

# Skapa build-katalog för output
output_dir = Path("build")
output_dir.mkdir(exist_ok=True)

# 1. Hämta RSS-flödet (med cache-busting)
url = "https://www.lampster.se/rss/pf-google_nok-no.xml"
params = {"t": str(int(time.time()))}
response = requests.get(url, params=params, headers={"Cache-Control": "no-cache"})
response.raise_for_status()
rss_text = response.content

# 2. Parse original RSS
root = ET.fromstring(rss_text)

# 3. Skapa nytt RSS-träd
ET.register_namespace('g', 'http://base.google.com/ns/1.0')
newrss = ET.Element('rss', {"version": "2.0", "xmlns:g": "http://base.google.com/ns/1.0"})
channel = ET.SubElement(newrss, 'channel')
ET.SubElement(channel, 'title').text = 'Lampster Norge - Norsk produktfeed'
ET.SubElement(channel, 'link').text = 'https://www.lampster.se'
ET.SubElement(channel, 'description').text = 'Produktfeed för Lampster Norge (Google Merchant).'

# 4. Iterera produkter
for item in root.findall('.//item'):
    prod_type = (item.findtext('product_type') or '').lower()
    google_cat = (item.findtext('google_product_category') or '').lower()
    if 'norsk' not in prod_type and 'norsk' not in google_cat:
        continue

    prod_id   = (item.findtext('id') or '').strip()
    title     = (item.findtext('title') or '').strip()
    desc      = (item.findtext('description') or '').strip()
    link      = (item.findtext('link') or '').strip()
    image     = (item.findtext('image_link') or item.findtext('image_url') or '').strip()
    condition = (item.findtext('condition') or '').strip()
    availability = (item.findtext('availability') or '').strip()
    price_text = (item.findtext('price') or '0').strip()
    price_num = float(re.sub(r'[^\d,\.]', '', price_text).replace(',', '.')) if price_text else 0.0
    price_nok = price_num * 1.3375

    if price_nok > 735:
        shipping_nok = 0.00
    else:
        shipping_nok = 99.00 * 1.3375

    new_item = ET.SubElement(channel, 'item')
    ET.SubElement(new_item, '{http://base.google.com/ns/1.0}id').text = prod_id
    ET.SubElement(new_item, '{http://base.google.com/ns/1.0}title').text = title
    ET.SubElement(new_item, '{http://base.google.com/ns/1.0}description').text = desc
    ET.SubElement(new_item, '{http://base.google.com/ns/1.0}link').text = link
    if image:
        ET.SubElement(new_item, '{http://base.google.com/ns/1.0}image_link').text = image
    if condition:
        ET.SubElement(new_item, '{http://base.google.com/ns/1.0}condition').text = condition
    if availability:
        ET.SubElement(new_item, '{http://base.google.com/ns/1.0}availability').text = availability
    ET.SubElement(new_item, '{http://base.google.com/ns/1.0}price').text = f"{price_nok:.2f} NOK"

    shipping = ET.SubElement(new_item, '{http://base.google.com/ns/1.0}shipping')
    ET.SubElement(shipping, '{http://base.google.com/ns/1.0}country').text = 'NO'
    ET.SubElement(shipping, '{http://base.google.com/ns/1.0}service').text = 'Standard'
    ET.SubElement(shipping, '{http://base.google.com/ns/1.0}price').text = f"{shipping_nok:.2f} NOK"

    if prod_type:
        ET.SubElement(new_item, '{http://base.google.com/ns/1.0}product_type').text = prod_type
    if google_cat:
        ET.SubElement(new_item, '{http://base.google.com/ns/1.0}google_product_category').text = google_cat

# 5. Skriv ut
raw_xml = ET.tostring(newrss, encoding='utf-8')
parsed = minidom.parseString(raw_xml)
pretty_xml = parsed.toprettyxml(indent="  ", encoding='utf-8')

out_file = output_dir / "norsk-feed.xml"
with open(out_file, 'wb') as f:
    f.write(pretty_xml)

print(f"✅ Skapade {out_file}")
