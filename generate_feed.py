import requests
import lxml.etree as ET
from decimal import Decimal, ROUND_HALF_UP
import os

# Webnode feed (källa)
SOURCE_URL = "https://www.lampster.se/rss/pf-google_nok-no.xml"

# Målfil (GitHub Pages)
OUTPUT_DIR = "lampster-norge-feed"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "norsk-feed.xml")

# Omräkning SEK → NOK
CONVERSION_RATE = Decimal("1.3375")
STANDARD_SEK_SHIPPING = 99
FREE_SHIPPING_THRESHOLD = Decimal("735.00")  # NOK

# Skapa output-mapp
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Hämta live feed
resp = requests.get(SOURCE_URL, timeout=30)
resp.raise_for_status()

parser = ET.XMLParser(recover=True)
tree = ET.fromstring(resp.content, parser=parser)

# Namespaces
G_NS = "http://base.google.com/ns/1.0"
ns = {"g": G_NS}

# Ny RSS-root
rss = ET.Element("rss", version="2.0", nsmap={"g": G_NS})
channel = ET.SubElement(rss, "channel")

# Kopiera över metadata
orig_channel = tree.find("channel")
for tag in ["title", "link", "description"]:
    elem = orig_channel.find(tag)
    if elem is not None and elem.text:
        ET.SubElement(channel, tag).text = elem.text

# Konvertera frakt SEK → NOK
NOK_STANDARD_SHIPPING = (
    Decimal(STANDARD_SEK_SHIPPING) * CONVERSION_RATE
).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

# Bygg produktlista
for item in orig_channel.findall("item"):
    product_type_elem = item.find("g:product_type", ns)
    text_product_type = (
        product_type_elem.text or ""
    ).lower() if product_type_elem is not None else ""

    # Endast produkter i kategori "norsk"
    if "norsk" not in text_product_type:
        continue

    new_item = ET.SubElement(channel, "item")

    # Kopiera fält
    for tag in [
        "id", "title", "description", "link", "image_link",
        "availability", "product_type", "price"
    ]:
        elem = item.find(f"g:{tag}", ns)
        text = elem.text if elem is not None else None

        if tag == "price" and text:
            try:
                value, currency = text.split()
                nok_value = (
                    Decimal(value) * CONVERSION_RATE
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                text = f"{nok_value:.2f} NOK"
            except Exception:
                text = f"{NOK_STANDARD_SHIPPING:.2f} NOK"
        elif tag == "price":
            text = f"{NOK_STANDARD_SHIPPING:.2f} NOK"

        ET.SubElement(new_item, f"{{{G_NS}}}{tag}").text = text or "N/A"

    # Fraktinformation
    shipping_elem = ET.SubElement(new_item, f"{{{G_NS}}}shipping")
    ET.SubElement(shipping_elem, f"{{{G_NS}}}country").text = "NO"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}service").text = "Standard"

    price_elem = new_item.find(f"{{{G_NS}}}price")
    price_value = Decimal(price_elem.text.split()[0])
    shipping_price = (
        Decimal("0.00") if price_value >= FREE_SHIPPING_THRESHOLD else NOK_STANDARD_SHIPPING
    )
    ET.SubElement(shipping_elem, f"{{{G_NS}}}price").text = f"{shipping_price:.2f} NOK"

    # Hanteringstid: 0–1 arbetsdagar
    ET.SubElement(shipping_elem, f"{{{G_NS}}}min_handling_time").text = "0"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}max_handling_time").text = "1"

    # Leveranstid: 1–9 arbetsdagar
    ET.SubElement(shipping_elem, f"{{{G_NS}}}min_transit_time").text = "1"
    ET.SubElement(shipping_elem, f"{{{G_NS}}}max_transit_time").text = "9"

# Spara feeden
tree_out = ET.ElementTree(rss)
tree_out.write(
    OUTPUT_FILE, encoding="utf-8", xml_declaration=True, pretty_print=True
)

print(f"Klar! Feed sparad som {OUTPUT_FILE}")
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
