#!/usr/bin/env python3
"""
Hämtar live-feed från Webnode, filtrerar norsk-produkter,
konverterar priser till NOK och skriver XML.
Commitar automatiskt till GitHub repo så filen alltid uppdateras.
"""

import requests, lxml.etree as ET, os, time, re, tempfile, shutil, subprocess, sys
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

# ---------- inställningar ----------
SOURCE_BASE = "https://www.lampster.se/rss/pf-google_nok-no.xml"
OUTPUT_DIR = "lampster-norge-feed"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "norsk-feed.xml")

CONVERSION_RATE = Decimal("1.3375")  # SEK -> NOK
STANDARD_SEK_SHIPPING = Decimal("99")
FREE_SHIPPING_THRESHOLD = Decimal("735.00")  # NOK

FETCH_ATTEMPTS = 5
FETCH_DELAY_SECONDS = 2

G_NS = "http://base.google.com/ns/1.0"
ns = {"g": G_NS}

# ---------- helpers ----------
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
    if e is not None and e.text:
        return e.text.strip()
    e = item.find(localname)
    if e is not None and e.text:
        return e.text.strip()
    for c in item:
        if isinstance(c.tag, str) and c.tag.endswith(localname) and c.text:
            return c.text.strip()
    return None

# ---------- skapa output dir ----------
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------- hämta feed ----------
session = requests.Session()
headers = {"Cache-Control":"no-cache", "Pragma":"no-cache","Expires":"0","User-Agent":"Mozilla/5.0 (feed-updater)"}

resp = None
for attempt in range(1, FETCH_ATTEMPTS+1):
    cb = int(time.time())
    url = f"{SOURCE_BASE}?cb={cb}"
    print(f"[fetch] Attempt {attempt}/{FETCH_ATTEMPTS} -> {url}")
    try:
        resp = session.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        if "<item" in resp.text:
            print("[fetch] Feed fetched successfully")
            break
    except Exception as e:
        print(f"[fetch] Error: {e}")
    time.sleep(FETCH_DELAY_SECONDS)

if resp is None:
    print("[error] Could not fetch feed. Exiting.", file=sys.stderr)
    sys.exit(1)

# ---------- parse XML ----------
parser = ET.XMLParser(recover=True)
try:
    tree = ET.fromstring(resp.content, parser=parser)
except Exception as e:
    print(f"[error] XML parse error: {e}", file=sys.stderr)
    sys.exit(1)

rss = ET.Element("rss", version="2.0", nsmap={"g": G_NS})
channel = ET.SubElement(rss, "channel")
orig_channel = tree.find("channel")
if orig_channel is None:
    print("[error] Original feed has no <channel>", file=sys.stderr)
    sys.exit(1)

for tag in ("title","link","description"):
    t = orig_channel.find(tag)
    if t is not None and t.text:
        ET.SubElement(channel, tag).text = t.text

items = orig_channel.findall("item")
print(f"[info] Total items in source-feed: {len(items)}")

included_ids = []

NOK_STANDARD_SHIPPING = (STANDARD_SEK_SHIPPING*CONVERSION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

for item in items:
    product_type_text = find_child_text(item, "product_type", ns) or ""
    google_cat_text = find_child_text(item, "google_product_category", ns) or ""
    product_cat_combined = (product_type_text + " " + google_cat_text).strip().lower()
    if "norsk" not in product_cat_combined:
        continue

    new_item = ET.SubElement(channel, "item")
    pid = find_child_text(item, "id", ns) or find_child_text(item, "g:id", ns) or "unknown"
    included_ids.append(pid)

    for tag in ("id","title","description","link","image_link","availability","product_type","price"):
        val = find_child_text(item, tag, ns)
        if tag=="price":
            if val:
                d = safe_decimal_from_str(val)
                if d is not None:
                    nok = (d*CONVERSION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    out_val = f"{nok:.2f} NOK"
                else:
                    out_val = f"{NOK_STANDARD_SHIPPING:.2f} NOK"
            else:
                out_val = f"{NOK_STANDARD_SHIPPING:.2f} NOK"
            ET.SubElement(new_item, f"{{{G_NS}}}{tag}").text = out_val
            continue
        ET.SubElement(new_item, f"{{{G_NS}}}{tag}").text = val if val else "N/A"

    shipping_elem = ET.SubElement(new_item, f"{{{G_NS}}}shipping")
    ET.SubElement(shipping_elem, f"{{{G_NS}}}country").text = "NO"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}service").text = "Standard"
    price_elem = find_child_text(new_item, "price", ns)
    price_val = safe_decimal_from_str(price_elem) or Decimal("0.00")
    shipping_price = Decimal("0.00") if price_val>=FREE_SHIPPING_THRESHOLD else NOK_STANDARD_SHIPPING
    ET.SubElement(shipping_elem, f"{{{G_NS}}}price").text = f"{shipping_price:.2f} NOK"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}min_handling_time").text="0"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}max_handling_time").text="1"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}min_transit_time").text="1"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}max_transit_time").text="9"

# ---------- skriv XML ----------
tmp_fd, tmp_path = tempfile.mkstemp(suffix=".xml", prefix="norsk-feed-", dir=OUTPUT_DIR)
os.close(tmp_fd)
try:
    tree_out = ET.ElementTree(rss)
    tree_out.write(tmp_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
    shutil.move(tmp_path, OUTPUT_FILE)
    print(f"[ok] XML skriven: {OUTPUT_FILE}")
except Exception as e:
    print(f"[error] Writing output failed: {e}", file=sys.stderr)
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    sys.exit(1)

# ---------- Git auto-commit with retry ----------
def git_commit_push(file_path, max_retries=3):
    for attempt in range(1,max_retries+1):
        try:
            subprocess.run(["git", "config", "--global", "user.name", "lampster-bot"], check=True)
            subprocess.run(["git", "config", "--global", "user.email", "bot@example.com"], check=True)
            subprocess.run(["git", "add", file_path], check=True)
            commit_msg = f"Auto-update norsk-feed.xml [{time.strftime('%Y-%m-%d %H:%M:%S')}]"
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            subprocess.run(["git", "push"], check=True)
            print("[ok] Git push succeeded")
            return
        except subprocess.CalledProcessError as e:
            print(f"[warn] Git push attempt {attempt} failed: {e}")
            time.sleep(5)
    print("[error] Git push failed after retries")

git_commit_push(OUTPUT_FILE)

sys.exit(0)
if orig_channel is None:
    print("[error] Original feed has no <channel>", file=sys.stderr)
    sys.exit(1)

for tag in ("title","link","description"):
    t = orig_channel.find(tag)
    if t is not None and t.text:
        ET.SubElement(channel, tag).text = t.text

items = orig_channel.findall("item")
print(f"[info] Totalt items i source-feed: {len(items)}")

included_ids = []
included_titles = []

NOK_STANDARD_SHIPPING = (STANDARD_SEK_SHIPPING*CONVERSION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

for item in items:
    product_type_text = find_child_text(item, "product_type", ns) or ""
    google_cat_text = find_child_text(item, "google_product_category", ns) or ""
    product_cat_combined = (product_type_text + " " + google_cat_text).strip().lower()

    if "norsk" not in product_cat_combined:
        continue

    new_item = ET.SubElement(channel, "item")
    pid = find_child_text(item, "id", ns) or find_child_text(item, "g:id", ns) or "unknown"
    title_text = find_child_text(item, "title", ns) or "no-title"
    included_ids.append(pid)
    included_titles.append(title_text)

    for tag in ("id","title","description","link","image_link","availability","product_type","price"):
        val = find_child_text(item, tag, ns)
        if tag=="price":
            if val:
                d = safe_decimal_from_str(val)
                if d is not None:
                    nok = (d*CONVERSION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    out_val = f"{nok:.2f} NOK"
                else:
                    out_val = f"{NOK_STANDARD_SHIPPING:.2f} NOK"
            else:
                out_val = f"{NOK_STANDARD_SHIPPING:.2f} NOK"
            ET.SubElement(new_item, f"{{{G_NS}}}{tag}").text = out_val
            continue
        ET.SubElement(new_item, f"{{{G_NS}}}{tag}").text = val if val else "N/A"

    # frakt
    shipping_elem = ET.SubElement(new_item, f"{{{G_NS}}}shipping")
    ET.SubElement(shipping_elem, f"{{{G_NS}}}country").text = "NO"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}service").text = "Standard"
    price_elem = find_child_text(new_item, "price", ns)
    price_val = safe_decimal_from_str(price_elem) or Decimal("0.00")
    shipping_price = Decimal("0.00") if price_val>=FREE_SHIPPING_THRESHOLD else NOK_STANDARD_SHIPPING
    ET.SubElement(shipping_elem, f"{{{G_NS}}}price").text = f"{shipping_price:.2f} NOK"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}min_handling_time").text="0"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}max_handling_time").text="1"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}min_transit_time").text="1"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}max_transit_time").text="9"

print(f"[info] Inkluderade produkter: {len(included_ids)}")

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

# ---------- auto-commit to Git ----------
try:
    subprocess.run(["git", "config", "--global", "user.name", "lampster-bot"], check=True)
    subprocess.run(["git", "config", "--global", "user.email", "bot@example.com"], check=True)
    subprocess.run(["git", "add", OUTPUT_FILE], check=True)
    commit_msg = f"Auto-update norsk-feed.xml [{time.strftime('%Y-%m-%d %H:%M:%S')}]"
    subprocess.run(["git", "commit", "-m", commit_msg], check=True)
    subprocess.run(["git", "push"], check=True)
    print("[ok] Auto-push to GitHub complete")
except subprocess.CalledProcessError as e:
    print(f"[warn] Git commit/push failed: {e}")

sys.exit(0)
