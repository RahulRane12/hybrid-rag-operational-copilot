"""
Synthetic Data Generation Engine for Root-Cause Diagnostic Copilot.
Generates realistic e-commerce operational logistics and customer sentiment datasets:
- Structured Orders, Fulfillments, Carrier Latencies, and Returns
- Unstructured Customer Support Tickets and Post-Purchase Reviews
- Ground-truth root causes including Catalog Measurement Errors, Carrier Transit Delays,
  and Component Quality Defects.
"""

import sqlite3
import random
from datetime import datetime, timedelta
import os
from db_engine import init_db, get_db_connection, DB_PATH

random.seed(42)

SKUS_DATA = [
    {
        "sku_id": "SKU-APP-849",
        "name": "Summit-Shield Men's All-Weather Parka",
        "category": "Apparel & Outerwear",
        "price": 240.0,
        "cogs": 85.0,
        "baseline_return_threshold": 0.08,
        "catalog_specs": "Chest: S(38\"), M(40\"), L(42\"), XL(44\"); Sleeve Length: 34\"; Relaxed Fit; Waterproof 10k",
        "supplier": "NordicWeave Textiles Co.",
        "issue_profile": "CATALOG_MEASUREMENT_ERROR"
    },
    {
        "sku_id": "SKU-FURN-302",
        "name": "ErgoComfort Mesh Executive Task Chair",
        "category": "Office Furniture",
        "price": 289.0,
        "cogs": 110.0,
        "baseline_return_threshold": 0.06,
        "catalog_specs": "Dimensions: 26\"W x 24\"D x 42\"H; Max Weight: 300 lbs; Assembly Required; 5-Caster Base",
        "supplier": "Apex Furnishings Ltd.",
        "issue_profile": "TRANSIT_DELAY_LOGISTICS"
    },
    {
        "sku_id": "SKU-ELEC-119",
        "name": "AeroSound Pro ANC Wireless Earbuds",
        "category": "Consumer Electronics",
        "price": 149.0,
        "cogs": 48.0,
        "baseline_return_threshold": 0.05,
        "catalog_specs": "Bluetooth 5.3; ANC Active Noise Cancelling; Battery: 8hr earbud / 24hr case; IPX5 Waterproof",
        "supplier": "SonicWave Tech Shenzhen",
        "issue_profile": "HARDWARE_DEFECT"
    },
    {
        "sku_id": "SKU-TECH-620",
        "name": "UltraSpeed 100W Multi-Port GaN Wall Charger",
        "category": "Electronics & Accessories",
        "price": 64.0,
        "cogs": 18.0,
        "baseline_return_threshold": 0.04,
        "catalog_specs": "100W Total Output; 2x USB-C, 1x USB-A; Includes 2m 100W Braided USB-C Cable",
        "supplier": "PowerGrid Innovations",
        "issue_profile": "CATALOG_SPEC_MISMATCH"
    },
    {
        "sku_id": "SKU-HOME-504",
        "name": "Artisan Damascus 8-Inch Chef Knife",
        "category": "Kitchen & Dining",
        "price": 115.0,
        "cogs": 38.0,
        "baseline_return_threshold": 0.04,
        "catalog_specs": "67-Layer VG-10 Damascus Steel; Pakkawood Handle; 15-degree edge angle; Weight: 240g",
        "supplier": "Kyoto Blade Crafters",
        "issue_profile": "HEALTHY_BASELINE"
    },
    {
        "sku_id": "SKU-FIT-210",
        "name": "HydroGrip Insulated Stainless Water Bottle 32oz",
        "category": "Sports & Fitness",
        "price": 38.0,
        "cogs": 11.0,
        "baseline_return_threshold": 0.03,
        "catalog_specs": "Double-wall vacuum insulation; 32oz (950ml); Leak-proof straw lid; BPA-free 18/8 steel",
        "supplier": "Vanguard Gear LLC",
        "issue_profile": "HEALTHY_BASELINE"
    },
    {
        "sku_id": "SKU-APP-102",
        "name": "Classic Everyday Supima Cotton Crew Tee",
        "category": "Apparel & Outerwear",
        "price": 32.0,
        "cogs": 9.5,
        "baseline_return_threshold": 0.07,
        "catalog_specs": "100% Long-Staple Supima Cotton; Pre-shrunk; Standard Regular Fit; Crewneck",
        "supplier": "PimaLoft Mills",
        "issue_profile": "HEALTHY_BASELINE"
    },
    {
        "sku_id": "SKU-FOOT-405",
        "name": "TrailStrider Vibram All-Terrain Running Shoes",
        "category": "Footwear",
        "price": 135.0,
        "cogs": 45.0,
        "baseline_return_threshold": 0.09,
        "catalog_specs": "Vibram Megagrip Lug Sole; Breathable Mesh Upper; Drop: 4mm; Weight: 290g",
        "supplier": "Alpine Trek Footwear",
        "issue_profile": "HEALTHY_BASELINE"
    }
]

CARRIERS = ["ApexLogistics", "SwiftFreight", "NationalExpress", "BlueDart Overnight"]
HUBS = ["Chicago Hub 1", "Dallas Central Hub", "Newark Inland Hub", "Reno Fulfillment Hub"]
CITIES = [
    ("Atlanta", "GA"),
    ("New York", "NY"),
    ("Los Angeles", "CA"),
    ("Dallas", "TX"),
    ("Chicago", "IL"),
    ("Seattle", "WA"),
    ("Denver", "CO"),
    ("Miami", "FL")
]

# Domain-specific text templates for realistic unstructured logs
CATALOG_SIZING_TICKETS = [
    "The chest measurement is totally incorrect! Your size chart says Large has a 42 inch chest, but my tailor measured this at 37 inches. I can't even zip it up.",
    "Catalog measurement error. Tag says XL, but it fits like a tight Medium. The armholes and sleeve length are 3 inches shorter than the catalog specs.",
    "Returned because the size chart on the website is completely inaccurate. The product description says relaxed fit, but it feels two sizes smaller.",
    "Chest sizing discrepancy! Ordered according to the sizing guide table, but the garment received is 4 inches smaller around the torso.",
    "Please update your catalog specs! Sizing is mislabeled. Waist and chest are cut way narrower than described in the product specs.",
    "Inaccurate measurements on the product page. Jacket sleeves are too tight and short. Had to return and demand a refund."
]

CATALOG_SIZING_REVIEWS = [
    (1, "Size chart is completely wrong!", "Do not trust the sizing chart on the product page. I ordered a Large (stated 42 inch chest) and it measured barely 37.5 inches. Serious catalog specification error."),
    (2, "Way too small - catalog error", "Nice material but sizing is cut 2 sizes smaller than the size table indicates. Sizing chart needs immediate correction by the catalog team."),
    (1, "Inaccurate dimensions listed", "Arms are 3 inches shorter than listed in product description specifications. Returning today for refund.")
]

TRANSIT_DELAY_TICKETS = [
    "Shipment was delayed by 6 days past the promised delivery date. The package arrived with torn outer carton and internal components dented.",
    "Carrier ApexLogistics sat on this package in Chicago for 5 business days without scan updates. Arrived way too late for my scheduled installation.",
    "Excessive transit latency! Order took 11 days instead of 3 days. When it finally arrived, the box was battered and pieces were missing.",
    "Transit delay caused me to miss my deadline. Package sat in transit for over a week. Returning item as no longer needed.",
    "Carrier tracking stopped updating for 4 days. Delivery latency is unacceptable. Arrived damaged due to rough courier handling."
]

TRANSIT_DELAY_REVIEWS = [
    (1, "Late delivery and damaged box", "Shipped via ApexLogistics and was delayed by almost a full week past estimated date. The chair arrived with a cracked plastic casing."),
    (2, "Transit latency ruined experience", "Took 9 days to arrive. Delivery was stalled at the transit hub for 4 days. Product itself is okay, but delivery logistics were a disaster.")
]

HARDWARE_DEFECT_TICKETS = [
    "Left earbud will not hold a charge for more than 20 minutes. Seems like a bad battery cell from the production batch.",
    "Right earbud disconnects intermittently, and audio balance is heavily skewed to the left. Factory defect.",
    "ANC noise cancellation produces a loud buzzing squeal in the left earbud. Defective hardware component."
]

HARDWARE_DEFECT_REVIEWS = [
    (1, "Left earbud dead on arrival", "Worked for two days then left earbud completely stopped taking charge. Clear quality control issue in manufacturing batch."),
    (2, "Hardware defect after 1 week", "Audio keeps crackling and microphone failed during calls. Returning for warranty refund.")
]

CATALOG_SPEC_MISMATCH_TICKETS = [
    "Catalog listing says 'Includes 2m 100W Braided Cable' right in the specs, but inside the box there is only the wall plug! Missing cable.",
    "The product page description clearly claims a 2-meter USB-C cable is included. Mine arrived without it. False advertising or catalog description error?",
    "Where is the cable advertised in the catalog bullet points? Disappointed to open the package and find only the charger brick."
]

CATALOG_SPEC_MISMATCH_REVIEWS = [
    (2, "Missing advertised braided cable", "Product description states 2m 100W cable included. Product box received does not include any cable. Catalog team should revise product page."),
    (2, "Inaccurate product specification", "Great charging brick, but minus 3 stars because the listing promises an included cable that was not in the packaging.")
]

HEALTHY_TICKETS = [
    "Quick question on recommended cleaning care instructions for the blade.",
    "Can this water bottle be safely cleaned in the dishwasher on high heat?",
    "Does the warranty cover accidental drops, or standard manufacturing defects?"
]

HEALTHY_REVIEWS = [
    (5, "Exceptional craftsmanship and razor sharp", "Exceeded expectations. Perfectly balanced, slice tomatoes paper-thin. Delivered right on time in 2 days!"),
    (5, "Best water bottle I've owned", "Keeps ice solid for 24+ hours even in hot car. No leaks whatsoever. Super fast delivery."),
    (4, "Great quality cotton tee", "Soft, comfortable, held up nicely through 3 wash cycles without shrinking. True to size.")
]


def generate_seed_data(num_orders: int = 1500) -> None:
    """Populates operational database with realistic orders, fulfillments, returns, tickets, and reviews."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Clear existing data
    cursor.execute("DELETE FROM reviews;")
    cursor.execute("DELETE FROM customer_tickets;")
    cursor.execute("DELETE FROM returns;")
    cursor.execute("DELETE FROM fulfillments;")
    cursor.execute("DELETE FROM orders;")
    cursor.execute("DELETE FROM skus;")

    # 1. Insert SKUs
    for sku in SKUS_DATA:
        cursor.execute("""
        INSERT INTO skus (sku_id, name, category, price, cogs, baseline_return_threshold, catalog_specs, supplier, launch_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            sku["sku_id"], sku["name"], sku["category"], sku["price"],
            sku["cogs"], sku["baseline_return_threshold"], sku["catalog_specs"],
            sku["supplier"], "2026-01-15"
        ))

    base_date = datetime(2026, 7, 1)

    order_counter = 100000
    ticket_counter = 50000
    review_counter = 80000
    return_counter = 20000

    for _ in range(num_orders):
        order_counter += 1
        order_id = f"ORD-{order_counter}"
        customer_id = f"CUST-{random.randint(1000, 9999)}"
        
        # Pick SKU with realistic volume weights
        sku = random.choice(SKUS_DATA)
        sku_id = sku["sku_id"]
        profile = sku["issue_profile"]

        order_offset = random.randint(0, 90)
        order_time = base_date + timedelta(days=order_offset, hours=random.randint(8, 20))
        order_date_str = order_time.strftime("%Y-%m-%d %H:%M:%S")

        qty = 1 if sku["price"] > 100 else random.choice([1, 1, 2])
        gmv = sku["price"] * qty

        # Carriers & Routes
        if profile == "TRANSIT_DELAY_LOGISTICS" and random.random() < 0.65:
            carrier = "ApexLogistics"
            origin_hub = "Chicago Hub 1"
            dest_city, dest_state = "Atlanta", "GA"
        else:
            carrier = random.choice(CARRIERS)
            origin_hub = random.choice(HUBS)
            dest_city, dest_state = random.choice(CITIES)

        cursor.execute("""
        INSERT INTO orders (order_id, customer_id, sku_id, order_date, unit_price, quantity, gmv, carrier, origin_hub, destination_city, destination_state)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (order_id, customer_id, sku_id, order_date_str, sku["price"], qty, gmv, carrier, origin_hub, dest_city, dest_state))

        # Fulfillments & Transit Latency
        dispatched_time = order_time + timedelta(hours=random.randint(4, 24))
        target_days = 3 if carrier in ["NationalExpress", "BlueDart Overnight"] else 5

        # Check for transit latency anomaly
        if profile == "TRANSIT_DELAY_LOGISTICS" and carrier == "ApexLogistics":
            # Significant transit latency injection
            actual_days = target_days + random.uniform(3.5, 7.8)
            transit_latency = actual_days - target_days
            transit_status = "TRANSIT_DELAY"
        elif random.random() < 0.08:
            # Random minor carrier delay
            actual_days = target_days + random.uniform(1.2, 3.0)
            transit_latency = actual_days - target_days
            transit_status = "TRANSIT_DELAY"
        else:
            actual_days = max(1.0, target_days - random.uniform(0.1, 1.5))
            transit_latency = max(0.0, actual_days - target_days)
            transit_status = "DELIVERED"

        delivered_time = dispatched_time + timedelta(days=actual_days)

        cursor.execute("""
        INSERT INTO fulfillments (order_id, dispatched_date, delivered_date, target_transit_days, actual_transit_days, transit_latency_days, transit_status)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (order_id, dispatched_time.strftime("%Y-%m-%d %H:%M:%S"), delivered_time.strftime("%Y-%m-%d %H:%M:%S"), target_days, round(actual_days, 2), round(transit_latency, 2), transit_status))

        # Determine Returns probability based on SKU issue profile
        is_returned = False
        return_reason = ""
        customer_comment = ""

        if profile == "CATALOG_MEASUREMENT_ERROR":
            # High return rate ~35-38% due to sizing error
            if random.random() < 0.36:
                is_returned = True
                return_reason = "SIZE_FIT"
                customer_comment = random.choice(CATALOG_SIZING_TICKETS)
        elif profile == "TRANSIT_DELAY_LOGISTICS":
            # Return rate higher when delayed ~25-30%
            if transit_status == "TRANSIT_DELAY" and random.random() < 0.32:
                is_returned = True
                return_reason = random.choice(["TRANSIT_DAMAGE", "LATE_DELIVERY"])
                customer_comment = random.choice(TRANSIT_DELAY_TICKETS)
            elif random.random() < 0.05:
                is_returned = True
                return_reason = "BUYERS_REMORSE"
        elif profile == "HARDWARE_DEFECT":
            # High return rate ~22%
            if random.random() < 0.23:
                is_returned = True
                return_reason = "QUALITY_DEFECT"
                customer_comment = random.choice(HARDWARE_DEFECT_TICKETS)
        elif profile == "CATALOG_SPEC_MISMATCH":
            # Return rate ~18%
            if random.random() < 0.18:
                is_returned = True
                return_reason = "NOT_AS_DESCRIBED"
                customer_comment = random.choice(CATALOG_SPEC_MISMATCH_TICKETS)
        else:
            # Baseline healthy return rate (~3-5%)
            if random.random() < 0.04:
                is_returned = True
                return_reason = random.choice(["BUYERS_REMORSE", "SIZE_FIT"])
                customer_comment = "Decided to change color or no longer required."

        if is_returned:
            return_counter += 1
            ret_id = f"RET-{return_counter}"
            ret_date = delivered_time + timedelta(days=random.randint(1, 14))
            cursor.execute("""
            INSERT INTO returns (return_id, order_id, sku_id, return_date, refund_amount, return_reason_code, customer_comment)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (ret_id, order_id, sku_id, ret_date.strftime("%Y-%m-%d %H:%M:%S"), gmv, return_reason, customer_comment))

            # Automatically log a customer support ticket for this return
            ticket_counter += 1
            tick_id = f"TICK-{ticket_counter}"
            sentiment_score = -0.75 if return_reason in ["SIZE_FIT", "QUALITY_DEFECT", "LATE_DELIVERY"] else -0.3
            cursor.execute("""
            INSERT INTO customer_tickets (ticket_id, order_id, sku_id, created_at, channel, raw_text, sentiment_score, sentiment_label, tagged_issue_category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (tick_id, order_id, sku_id, (delivered_time + timedelta(hours=random.randint(2, 48))).strftime("%Y-%m-%d %H:%M:%S"),
                  random.choice(["Chat", "Email", "Voice"]), customer_comment, sentiment_score, "NEGATIVE", return_reason))

        # Randomly generate Post-Delivery Customer Reviews (~30% of orders leave reviews)
        if random.random() < 0.32:
            review_counter += 1
            rev_id = f"REV-{review_counter}"
            rev_date = delivered_time + timedelta(days=random.randint(2, 20))

            if profile == "CATALOG_MEASUREMENT_ERROR" and random.random() < 0.70:
                rating, title, body = random.choice(CATALOG_SIZING_REVIEWS)
            elif profile == "TRANSIT_DELAY_LOGISTICS" and transit_status == "TRANSIT_DELAY" and random.random() < 0.65:
                rating, title, body = random.choice(TRANSIT_DELAY_REVIEWS)
            elif profile == "HARDWARE_DEFECT" and random.random() < 0.60:
                rating, title, body = random.choice(HARDWARE_DEFECT_REVIEWS)
            elif profile == "CATALOG_SPEC_MISMATCH" and random.random() < 0.55:
                rating, title, body = random.choice(CATALOG_SPEC_MISMATCH_REVIEWS)
            else:
                rating, title, body = random.choice(HEALTHY_REVIEWS)

            cursor.execute("""
            INSERT INTO reviews (review_id, sku_id, order_id, rating, review_title, review_text, review_date)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (rev_id, sku_id, order_id, rating, title, body, rev_date.strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()
    conn.close()
    print(f"Operational database successfully seeded with {num_orders} orders at {DB_PATH}")


if __name__ == "__main__":
    generate_seed_data()
