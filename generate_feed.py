import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import os

# URL till JSON eller API som ger produkterna
API_URL = "https://dinkalla.shop/api/products"

def fetch_products():
    try:
        resp = requests.get(API_URL)
        resp.raise_for_status()
        data = resp.json()
        print(f"Hämtade {len(data)} produkter totalt från API")
        return data
    except Exception as e:
        print(f"Fel vid hämtning av produkter: {e}")
        return []

def generate_xml(products):
    root = ET.Element("products")
    for p in products:
        # Lägg till debug utskrift
        print(f"Bearbetar produkt: {p.get('name')} ({p.get('id')})")
        
        product_el = ET.SubElement(root, "product")
        ET.SubElement(product_el, "id").text = str(p.get("id"))
        ET.SubElement(product_el, "name").text = p.get("name", "")
        ET.SubElement(product_el, "price").text = str(p.get("price", ""))
        ET.SubElement(product_el, "availability").text = p.get("availability", "")
        ET.SubElement(product_el, "url").text = p.get("url", "")
        ET.SubElement(product_el, "image").text = p.get("image", "")
        
        # Lägg till datum (för test)
        ET.SubElement(product_el, "date_added").text = p.get("date_added", datetime.now().isoformat())

    tree = ET.ElementTree(root)
    output_file = "feed.xml"
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"XML-fil genererad: {output_file} ({len(products)} produkter)")

def main():
    products = fetch_products()
    if not products:
        print("Inga produkter hämtade, skapar tom XML ändå.")
    generate_xml(products)

if __name__ == "__main__":
    main()
