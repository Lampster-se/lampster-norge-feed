import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import os

API_URL = "https://dinkalla.shop/api/products"  # Uppdatera med din riktiga API

def fetch_products():
    try:
        resp = requests.get(API_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        print(f"Hämtade {len(data)} produkter från API")
        return data
    except Exception as e:
        print(f"Fel vid hämtning av produkter: {e}")
        return []

def generate_xml(products):
    # Root-element med tidsstämpel så filen alltid ändras
    root = ET.Element("products")
    root.set("generated_at", datetime.now().isoformat())

    if not products:
        print("Ingen produktdata, lägger till placeholder")
        p = ET.SubElement(root, "product")
        ET.SubElement(p, "id").text = "0"
        ET.SubElement(p, "name").text = "Ingen produkt"
        ET.SubElement(p, "price").text = "0"
        ET.SubElement(p, "availability").text = "out of stock"
        ET.SubElement(p, "url").text = ""
        ET.SubElement(p, "image").text = ""
    else:
        for p in products:
            prod_el = ET.SubElement(root, "product")
            ET.SubElement(prod_el, "id").text = str(p.get("id", ""))
            ET.SubElement(prod_el, "name").text = p.get("name", "")
            ET.SubElement(prod_el, "price").text = str(p.get("price", ""))
            ET.SubElement(prod_el, "availability").text = p.get("availability", "")
            ET.SubElement(prod_el, "url").text = p.get("url", "")
            ET.SubElement(prod_el, "image").text = p.get("image", "")
            ET.SubElement(prod_el, "date_added").text = p.get("date_added", datetime.now().isoformat())

    tree = ET.ElementTree(root)
    tree.write("feed.xml", encoding="utf-8", xml_declaration=True)
    print(f"XML genererad: feed.xml ({len(products)} produkter)")

def main():
    products = fetch_products()
    generate_xml(products)

if __name__ == "__main__":
    main()
