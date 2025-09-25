#!/usr/bin/env python3
"""
generate_feed.py
Hämtar live-feed från Webnode och skapar en norsk Google Merchant RSS/Feed.
Robust: försöker alltid cache-bust, försöker hitta taggar både med och utan namespace,
loggar vilka produkter som hittas och vilka som inkluderas i output.
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

# ---------- inställningar ----------
SOURCE_BASE = "https://www.lampster.se/rss/pf-google_nok-no.xml"
OUTPUT_DIR = "lampster-norge-feed"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "norsk-feed.xml")

CONVERSION_RATE = Decimal("1.3375")  # SEK -> NOK
STANDARD_SEK_SHIPPING = Decimal("99")
FREE_SHIPPING_THRESHOLD = Decimal("735.00")  # NOK

# max försök att hämta live-feed (cache-bust olika timestamp)
FETCH_ATTEMPTS = 5
FETCH_DELAY_SECONDS = 2

# ---------- hjälpfunktioner ----------
def safe_decimal_from_str(s):
    """Hämta första nummer i strängen och returnera Decimal (punkt decimal)."""
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
    """
    Försök hitta child med namn localname både med g: namespace och utan.
    Returnerar text eller None.
    """
    # försök namespaced
    try:
        e = item.find(f"g:{localname}", ns)
    except Exception:
        e = None
    if e is not None and e.text is not None:
        return e.text.strip()
    # försök utan namespace
    e = item.find(localname)
    if e is not None and e.text is not None:
        return e.text.strip()
    # fallback: sök alla children som slutar på localname
    for c in item:
        # child.tag kan vara "{uri}localname" eller "localname"
        if isinstance(c.tag, str) and c.tag.endswith(localname):
            if c.text:
                return c.text.strip()
    return None

def find_child_elem(item, localname, ns):
    """Returnerar element-objekt eller None, med samma strategi som find_child_text."""
    try:
        e = item.find(f"g:{localname}", ns)
    except Exception:
        e = None
    if e is not None:
        return e
    e = item.find(localname)
    if e is not None:
        return e
    for c in item:
        if isinstance(c.tag, str) and c.tag.endswith(localname):
            return c
    return None

# ---------- försök hämta feed med cache-bust ----------
os.makedirs(OUTPUT_DIR, exist_ok=True)

session = requests.Session()
headers = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
    "User-Agent": "Mozilla/5.0 (compatible; feed-updater/1.0)"
}

last_resp_text = None
resp = None
for attempt in range(1, FETCH_ATTEMPTS + 1):
    cb = int(time.time())
    url = f"{SOURCE_BASE}?cb={cb}"
    print(f"[fetch] Attempt {attempt}/{FETCH_ATTEMPTS} -> {url}")
    try:
        resp = session.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        last_resp_text = resp.text
        # basic sanity: must contain <item> and at least one occurrence of "g:id" or "<id>"
        if ("<item" in last_resp_text) and (("g:id" in last_resp_text) or ("<g:id" in last_resp_text) or ("<id>" in last_resp_text)):
            print("[fetch] OK - feed looks like RSS with items.")
            break
        else:
            print("[fetch] Warning: feed fetched but doesn't look like expected RSS (no <item>/<g:id>). Retrying...")
    except Exception as e:
        print(f"[fetch] Error fetching feed: {e}")
    time.sleep(FETCH_DELAY_SECONDS)

if resp is None:
    print("[error] Could not fetch feed from Webnode (no successful response). Exiting.", file=sys.stderr)
    sys.exit(1)

# ---------- parse XML ----------
parser = ET.XMLParser(recover=True)
try:
    tree = ET.fromstring(resp.content, parser=parser)
except Exception as e:
    print(f"[error] XML parse error: {e}", file=sys.stderr)
    sys.exit(1)

# ---------- namespace setup ----------
G_NS = "http://base.google.com/ns/1.0"
ns = {"g": G_NS}

# ---------- build output RSS ----------
rss = ET.Element("rss", version="2.0", nsmap={"g": G_NS})
channel = ET.SubElement(rss, "channel")

orig_channel = tree.find("channel")
if orig_channel is None:
    print("[error] Original feed has no <channel>. Exiting.", file=sys.stderr)
    sys.exit(1)

for tag in ("title", "link", "description"):
    t = orig_channel.find(tag)
    if t is not None and t.text:
        ET.SubElement(channel, tag).text = t.text

items = orig_channel.findall("item")
print(f"[info] Totalt items i source-feed: {len(items)}")

included_ids = []
included_titles = []

# prepare shipping constants
try:
    NOK_STANDARD_SHIPPING = (STANDARD_SEK_SHIPPING * CONVERSION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
except Exception:
    NOK_STANDARD_SHIPPING = (Decimal("99") * CONVERSION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

for item in items:
    # Hitta produktkategori: försök flera varianter
    product_type_text = find_child_text(item, "product_type", ns) or ""
    google_cat_text = find_child_text(item, "google_product_category", ns) or ""
    product_cat_combined = (product_type_text + " " + google_cat_text).strip().lower()

    # filter endast norska produkter
    if "norsk" not in product_cat_combined:
        continue

    # skapa item i nya kanalen
    new_item = ET.SubElement(channel, "item")

    # id/title för loggning
    pid = find_child_text(item, "id", ns) or find_child_text(item, "g:id", ns) or "unknown"
    title_text = find_child_text(item, "title", ns) or "no-title"
    included_ids.append(pid)
    included_titles.append(title_text)

    # kopiera fält (försöker namespaced g:tag först, sedan utan)
    for tag in ("id", "title", "description", "link", "image_link", "availability", "product_type", "price"):
        val = find_child_text(item, tag, ns)
        if tag == "price":
            if val:
                # hitta första nummer i strängen och konvertera
                d = safe_decimal_from_str(val)
                if d is not None:
                    nok = (d * CONVERSION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    out_val = f"{nok:.2f} NOK"
                else:
                    out_val = f"{NOK_STANDARD_SHIPPING:.2f} NOK"
            else:
                out_val = f"{NOK_STANDARD_SHIPPING:.2f} NOK"
            ET.SubElement(new_item, f"{{{G_NS}}}{tag}").text = out_val
            continue

        # vanliga fält
        if val:
            ET.SubElement(new_item, f"{{{G_NS}}}{tag}").text = val
        else:
            ET.SubElement(new_item, f"{{{G_NS}}}{tag}").text = "N/A"

    # frakt-element (NO)
    shipping_elem = ET.SubElement(new_item, f"{{{G_NS}}}shipping")
    ET.SubElement(shipping_elem, f"{{{G_NS}}}country").text = "NO"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}service").text = "Standard"

    # beräkna shipping price
    price_elem = find_child_text(new_item, "price", ns)
    price_val = safe_decimal_from_str(price_elem) or Decimal("0.00")
    shipping_price = Decimal("0.00") if price_val >= FREE_SHIPPING_THRESHOLD else NOK_STANDARD_SHIPPING
    ET.SubElement(shipping_elem, f"{{{G_NS}}}price").text = f"{shipping_price:.2f} NOK"

    # hanteringstid och leveranstid (arbetsdagar)
    ET.SubElement(shipping_elem, f"{{{G_NS}}}min_handling_time").text = "0"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}max_handling_time").text = "1"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}min_transit_time").text = "1"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}max_transit_time").text = "9"

# ---------- logging ----------
print(f"[info] Inkluderade produkter: {len(included_ids)}")
if included_ids:
    # lista max 200 IDs för att inte spamma loggen
    for i, pid in enumerate(included_ids[:200], start=1):
        t = included_titles[i-1] if i-1 < len(included_titles) else ""
        print(f" - {i}: id={pid} title={t}")

# ---------- skriv ut atomiskt ----------
tmp_fd, tmp_path = tempfile.mkstemp(suffix=".xml", prefix="norsk-feed-", dir=OUTPUT_DIR)
os.close(tmp_fd)
try:
    tree_out = ET.ElementTree(rss)
    tree_out.write(tmp_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
    shutil.move(tmp_path, OUTPUT_FILE)
    print(f"[ok] Skriven fil: {OUTPUT_FILE}")
except Exception as e:
    print(f"[error] Kunde inte skriva output: {e}", file=sys.stderr)
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    sys.exit(1)

# Exit-code depending on whether anything was included
if not included_ids:
    print("[warn] Ingen 'norsk' produkt hittades i feeden vid körningen. Kontrollera att feeden verkligen innehåller dem.")
    # exit 0 still (workflow can inspect logs), or exit non-zero to fail job? We'll print warn and exit 0:
    sys.exit(0)

sys.exit(0)
