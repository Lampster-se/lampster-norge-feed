#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import re
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom

# 1. Hämta RSS-flödet med cache-bust (tidsstämpel)
url = "https://www.lampster.se/rss/pf-google_nok-no.xml"
params = {"t": str(int(time.time()))}
response = requests.get(url, params=params, headers={"Cache-Control": "no-cache"})
response.raise_for_status()
rss_text = response.content

# 2. Parse original RSS
root = ET.fromstring(rss_text)

# 3. Skapa nytt RSS-träd med Google Merchant-namespace
ET.register_namespace('g', 'http://base.google.com/ns/1.0')
newrss = ET.Element('rss', {"version": "2.0", "xmlns:g": "http://base.google.com/ns/1.0"})
channel = ET.SubElement(newrss, 'channel')
ET.SubElement(channel, 'title').text = 'Lampster Norge - Norsk produktfeed'
ET.SubElement(channel, 'link').text = 'https://www.lampster.se'
ET.SubElement(channel, 'description').text = 'Produktfeed för Lampster Norge (finns för Google Merchant).'

# 4. Iterera över alla produkter i originalflödet
for item in root.findall('.//item'):
    # Läs textinnehållet i product_type och google_product_category (om de finns)
    prod_type = item.findtext('product_type', default='').lower()
    google_cat = item.findtext('google_product_category', default='').lower()
    # Filtrera: endast produkter med "norsk" i fältet
    if 'norsk' not in prod_type and 'norsk' not in google_cat:
        continue

    # Hämta nödvändiga fält (hantera ev. saknade värden)
    prod_id   = item.findtext('id', default='').strip()
    title     = item.findtext('title', default='').strip()
    desc      = item.findtext('description', default='').strip()
    link      = item.findtext('link', default='').strip()
    image     = item.findtext('image_link', default='').strip() or item.findtext('image_url', default='').strip()
    condition = item.findtext('condition', default='').strip() or item.findtext('condition', default='').strip()
    availability = item.findtext('availability', default='').strip()
    # Läs pris (förväntas i SEK i original), ta bort icke-numeriska tecken
    price_text = item.findtext('price', default='0').strip()
    price_num = float(re.sub(r'[^\d,\.]', '', price_text).replace(',', '.')) if price_text else 0.0
    price_nok = price_num * 1.3375

    # Bestäm fraktpris: gratis om över 735 NOK, annars 99 SEK → NOK
    if price_nok > 735:
        shipping_nok = 0.00
    else:
        shipping_nok = 99.00 * 1.3375

    # 5. Bygg nytt <item> i newrss
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

    # Sätt det nya priset i NOK
    ET.SubElement(new_item, '{http://base.google.com/ns/1.0}price').text = f"{price_nok:.2f} NOK"

    # Lägg till fraktinfo enligt Google-formatet:contentReference[oaicite:3]{index=3}
    shipping = ET.SubElement(new_item, '{http://base.google.com/ns/1.0}shipping')
    ET.SubElement(shipping, '{http://base.google.com/ns/1.0}country').text = 'NO'
    ET.SubElement(shipping, '{http://base.google.com/ns/1.0}service').text = 'Standard'
    ET.SubElement(shipping, '{http://base.google.com/ns/1.0}price').text = f"{shipping_nok:.2f} NOK"

    # Ta med product_type och google_product_category om det finns
    if prod_type:
        ET.SubElement(new_item, '{http://base.google.com/ns/1.0}product_type').text = prod_type
    if google_cat:
        ET.SubElement(new_item, '{http://base.google.com/ns/1.0}google_product_category').text = google_cat

# 6. Skriv ut det nya RSS-flödet som XML-fil
raw_xml = ET.tostring(newrss, encoding='utf-8')
# Gör XML-utformatning mer läsbar
parsed = minidom.parseString(raw_xml)
pretty_xml = parsed.toprettyxml(indent="  ", encoding='utf-8')
with open('norsk-feed.xml', 'wb') as f:
    f.write(pretty_xml)
