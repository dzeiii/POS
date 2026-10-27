"""Gulps & Grubs menu catalog used by the existing POS application.
All prices are integer centavos. No separate application or non-Python language is used.
"""

MENU_ITEMS = []

def add(code, name, category, price, sizes=None, options=None):
    MENU_ITEMS.append({
        "code": code, "name": name, "category": category,
        "price_cents": int(price * 100),
        "sizes": {int(k): int(v * 100) for k, v in (sizes or {}).items()},
        "options": options or {},
    })

MILKSHAKE_FLAVORS = ["Chocolate Kisses", "Cookies N Cream", "Strawberry", "Buco", "Avocado", "Mango", "Melon", "Coffee Crumble", "Buko Pandan"]
MILKTEA_FLAVORS = ["Wintermelon", "Okinawa", "Caramel Sugar"]
LEMONADE_FLAVORS = ["Blue", "Lychee", "Cucumber", "Lemon", "Honey Lemon"]
FRIES_FLAVORS = ["Sour Cream", "Cheese", "Barbecue", "Butter Cheese", "Chili Barbecue", "Plain"]

for i, flavor in enumerate(MILKSHAKE_FLAVORS, 1):
    add(f"GUL-MS-{i:02d}", f"Milkshake - {flavor}", "GULPS - Milkshake", 35, {12: 35, 16: 45}, {"Sinkers": ["Nata", "Pearl (Sago)", "None"]})
for i, flavor in enumerate(MILKTEA_FLAVORS, 1):
    add(f"GUL-MT-{i:02d}", f"Milktea - {flavor}", "GULPS - Milktea", 39, {12: 39, 16: 49}, {"Sinkers": ["Pearl (Sago)", "None"]})

for code, name, sizes in [
    ("GUL-FL-COKE", "Coke Float", {8: 20, 12: 30, 16: 40}),
    ("GUL-FL-CHUCKIE", "Chuckie Float", {8: 35, 12: 45}),
    ("GUL-FL-MILO", "Milo Float", {8: 40, 12: 50}),
    ("GUL-FL-DUTCH", "Dutchmill Float", {8: 30, 12: 40}),
    ("GUL-FL-COFFEE", "Coffee Float", {12: 40, 16: 50}),
]:
    add(code, name, "GULPS - Floats", next(iter(sizes.values())), sizes)
for i, flavor in enumerate(LEMONADE_FLAVORS, 1):
    add(f"GUL-LEM-{i:02d}", f"Lemonade - {flavor}", "GULPS - Lemonades", 25, {12: 25, 16: 35}, {"Sinkers": ["Rainbow Jelly", "None"]})
for i, flavor in enumerate(LEMONADE_FLAVORS, 1):
    add(f"GUL-SLU-{i:02d}", f"Lemonade Slushie - {flavor}", "GULPS - Lemonade Slushie", 30, {12: 30, 16: 40}, {"Sinkers": ["Nata", "None"]})
add("GUL-COF-ICE", "Iced Coffee", "GULPS - Coffee", 30, {12: 30, 16: 40})
add("GUL-COF-SLU", "Coffee Slushie", "GULPS - Coffee", 35, {12: 35, 16: 45})

# GRUBS - Streetfoods
for code, name, price in [
    ("GRB-FISHBALL", "Fishball (6 pcs)", 5), ("GRB-KIKIAM", "Kikiam (5 pcs)", 10),
    ("GRB-SQUIDBALL", "Squidball (3 pcs)", 10), ("GRB-KWEK", "Kwek Kwek (1 pc)", 5),
    ("GRB-HOTDOG", "Hotdog (5 pcs)", 20), ("GRB-BREADROLL", "Breadroll", 12),
    ("GRB-CHEESESTK", "Cheese Sticks (4 pcs)", 20), ("GRB-TURON", "Turones with Syrup (4 pcs)", 20),
    ("GRB-LUMPIA", "Lumpiang Gulay", 15),
]: add(code, name, "GRUBS - Streetfoods", price)
add("GRB-FRIES", "French Fries", "GRUBS - Streetfoods", 35, options={"Fries Flavor": FRIES_FLAVORS})

for code, name, price in [
    ("GRB-WAFFLE", "Round Waffle", 10), ("GRB-WAFFLE-ICE", "Round Waffle with Ice Cream", 20),
    ("GRB-MESSY-DONUT", "Messy Donut", 20), ("GRB-HOTDOG-WAFFLE", "Hotdog Waffle", 15),
]: add(code, name, "GRUBS - Donut and Waffles", price)
add("GRB-SIOMAI-3", "Siomai (3 pcs)", "GRUBS - Dim Sum", 20)
add("GRB-SIOMAI-1", "Siomai (1 pc)", "GRUBS - Dim Sum", 7)
add("GRB-SIOPAO", "Mini Siopao", "GRUBS - Dim Sum", 15)
add("OTH-LEM-YAKULT", "Lemonade Yakult", "GRUBS - Others", 55, {16: 55}, {"Lemonade Flavor": LEMONADE_FLAVORS})
add("OTH-ISK-12", "Iskrambol B1T1", "GRUBS - Others", 35, {12: 35, 16: 65})
add("OTH-KERI", "Keri Mo Yan Combo", "GRUBS - Others", 60, options={"Lemonade Flavor": LEMONADE_FLAVORS, "Fries Flavor": FRIES_FLAVORS})
add("OTH-MALLOW", "Marshmallow Solo (7 pcs)", "GRUBS - Others", 10, options={"Syrup": ["Chocolate", "Strawberry", "Caramel", "None"], "Sprinkles": ["With sprinkles", "No sprinkles"]})
add("OTH-BREADSTICKS", "Breadsticks Solo (12 pcs)", "GRUBS - Others", 10, options={"Syrup": ["Chocolate", "Strawberry", "Caramel", "None"], "Sprinkles": ["With sprinkles", "No sprinkles"]})
add("OTH-MARSH-COMBO", "Marsh-Sticks Combo (4 marshmallows + 5 breadsticks)", "GRUBS - Others", 10, options={"Syrup": ["Chocolate", "Strawberry", "Caramel", "None"], "Sprinkles": ["With sprinkles", "No sprinkles"]})

MENU_CATEGORIES = sorted({item["category"] for item in MENU_ITEMS})


def menu_options_for(product):
    """Return option fields for a menu product, or no options for custom products."""
    code = str(product.get("code", "")).upper()
    for item in MENU_ITEMS:
        if item["code"] == code:
            return item["options"]
    return {}
