#!/usr/bin/env python3
"""
generate_feed.py
Hämtar live-feed från Webnode och skapar norsk Google Merchant RSS/Feed.
Skriver alltid till OUTPUT_FILE.
"""

import requests
import lxml.etree as ET
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import os
import time
import re
import tempfile
import shutil
import sys
import subprocess

# ---------- inställningar ----------
SOURCE_BASE = "https://www.lampster.se/rss/pf-google_nok-no.xml"
OUTPUT_DIR = "lampster-norge-feed"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "norsk-feed.xml")

CONVERSION_RATE = Decimal("1.3375")  # SEK -> NOK
STANDARD_SEK_SHIPPING = Decimal("99")
FREE_SHIPPING_THRESHOLD = Decimal("735.00")  # NOK

FETCH_ATTEMPTS = 5
FETCH_DELAY_SECONDS = 2

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------- hjälpfunktioner ----------
def safe_decimal_from_str(s):
    if not s:
        return None
    m = re.search(r"[-+]?[0-9\.,]+", s)
    if not m:
        return None
    num = m.group(0).replace(",", ".")
    try:
        return Decimal(num)
    except InvalidOperation:
        return None

def find_child_text(item, localname, ns):
    try:
        e = item.find(f"g:{localname}", ns)
    except Exception:
        e = None
    if e is not None and e.text is not None:
        return e.text.strip()
    e = item.find(localname)
    if e is not None and e.text is not None:
        return e.text.strip()
    for c in item:
        if isinstance(c.tag, str) and c.tag.endswith(localname):
            if c.text:
                return c.text.strip()
    return None

# ---------- hämta feed ----------
session = requests.Session()
headers = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
    "User-Agent": "Mozilla/5.0 (compatible; feed-updater/1.0)"
}

last_resp_text = None
for attempt in range(1, FETCH_ATTEMPTS + 1):
    cb = int(time.time())
    url = f"{SOURCE_BASE}?cb={cb}"
    print(f"[fetch] Attempt {attempt}/{FETCH_ATTEMPTS} -> {url}")
    try:
        resp = session.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        last_resp_text = resp.text
        if ("<item" in last_resp_text) and (("g:id" in last_resp_text) or ("<id>" in last_resp_text)):
            print("[fetch] OK - feed looks like RSS with items.")
            break
    except Exception as e:
        print(f"[fetch] Error fetching feed: {e}")
    time.sleep(FETCH_DELAY_SECONDS)
else:
    print("[error] Could not fetch feed.", file=sys.stderr)
    sys.exit(1)

# ---------- parse XML ----------
parser = ET.XMLParser(recover=True)
try:
    tree = ET.fromstring(resp.content, parser=parser)
except Exception as e:
    print(f"[error] XML parse error: {e}", file=sys.stderr)
    sys.exit(1)

G_NS = "http://base.google.com/ns/1.0"
ns = {"g": G_NS}

# ---------- build output RSS ----------
rss = ET.Element("rss", version="2.0", nsmap={"g": G_NS})
channel = ET.SubElement(rss, "channel")
orig_channel = tree.find("channel")
if orig_channel is None:
    print("[error] Original feed has no <channel>.", file=sys.stderr)
    sys.exit(1)

for tag in ("title", "link", "description"):
    t = orig_channel.find(tag)
    if t is not None and t.text:
        ET.SubElement(channel, tag).text = t.text

items = orig_channel.findall("item")
included_ids = []

NOK_STANDARD_SHIPPING = (STANDARD_SEK_SHIPPING * CONVERSION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

for item in items:
    product_type_text = find_child_text(item, "product_type", ns) or ""
    google_cat_text = find_child_text(item, "google_product_category", ns) or ""
    if "norsk" not in (product_type_text + " " + google_cat_text).lower():
        continue

    new_item = ET.SubElement(channel, "item")
    pid = find_child_text(item, "id", ns) or find_child_text(item, "g:id", ns) or "unknown"
    included_ids.append(pid)

    for tag in ("id", "title", "description", "link", "image_link", "availability", "product_type", "price"):
        val = find_child_text(item, tag, ns)
        if tag == "price":
            if val:
                d = safe_decimal_from_str(val)
                if d is not None:
                    nok = (d * CONVERSION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    val = f"{nok:.2f} NOK"
                else:
                    val = f"{NOK_STANDARD_SHIPPING:.2f} NOK"
            else:
                val = f"{NOK_STANDARD_SHIPPING:.2f} NOK"
            ET.SubElement(new_item, f"{{{G_NS}}}{tag}").text = val
            continue
        ET.SubElement(new_item, f"{{{G_NS}}}{tag}").text = val or "N/A"

    shipping_elem = ET.SubElement(new_item, f"{{{G_NS}}}shipping")
    ET.SubElement(shipping_elem, f"{{{G_NS}}}country").text = "NO"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}service").text = "Standard"

    price_elem = find_child_text(new_item, "price", ns)
    price_val = safe_decimal_from_str(price_elem) or Decimal("0.00")
    shipping_price = Decimal("0.00") if price_val >= FREE_SHIPPING_THRESHOLD else NOK_STANDARD_SHIPPING
    ET.SubElement(shipping_elem, f"{{{G_NS}}}price").text = f"{shipping_price:.2f} NOK"

    ET.SubElement(shipping_elem, f"{{{G_NS}}}min_handling_time").text = "0"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}max_handling_time").text = "1"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}min_transit_time").text = "1"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}max_transit_time").text = "9"

# ---------- write file ----------
tmp_fd, tmp_path = tempfile.mkstemp(suffix=".xml", prefix="norsk-feed-", dir=OUTPUT_DIR)
os.close(tmp_fd)
try:
    tree_out = ET.ElementTree(rss)
    tree_out.write(tmp_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
    shutil.move(tmp_path, OUTPUT_FILE)
    print(f"[ok] Skriven fil: {OUTPUT_FILE}")
except Exception as e:
    print(f"[error] Could not write XML: {e}", file=sys.stderr)
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    sys.exit(1)

# ---------- commit + push to generated-feed ----------
try:
    subprocess.run(["git", "config", "user.name", "github-actions"], check=True)
    subprocess.run(["git", "config", "user.email", "github-actions@github.com"], check=True)
    subprocess.run(["git", "checkout", "-B", "generated-feed"], check=True)
    subprocess.run(["git", "add", OUTPUT_FILE], check=True)
    subprocess.run(["git", "commit", "-m", "Update norsk-feed.xml via GitHub Actions"], check=True)
    subprocess.run(["git", "push", "--force", "origin", "generated-feed"], check=True)
    print("[ok] XML committed and pushed to generated-feed branch")
except subprocess.CalledProcessError as e:
    print(f"[warn] Could not push XML: {e}")

sys.exit(0)
