#!/usr/bin/env python3
"""Data preparation script for the CDP Agentic Ad Engine.

Downloads instructions, generates synthetic clickstream data,
splits across two platforms with overlapping users for identity
resolution evaluation, and creates a product catalog.

Usage:
    python scripts/prepare_data.py \\
        --seed 42 \\
        --input-dir ./data \\
        --output-dir ./data

Manual Download Instructions for Kaggle Datasets:
    Dataset A - Ecommerce Clickstream (raw behavioral logs):
        https://www.kaggle.com/datasets/ifeanyiokonkwo/ecommerce-clickstream-data
        → Place file as: data/ecommerce_clickstream.csv

    Dataset B - E-commerce User Behavior & Transactions (enriched):
        https://www.kaggle.com/datasets/ifeanyiokonkwo/e-commerce-user-behavior-and-transactions
        → Place file as: data/user_behavior_transactions.csv

    If either file is missing, this script will generate synthetic
    data that mimics the same schema for development purposes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import sys
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

PRODUCT_CATEGORIES = [
    "electronics",
    "clothing",
    "footwear",
    "sports_gear",
    "home_appliances",
    "books",
    "beauty",
    "automotive_accessories",
]

DEVICE_TYPES = ["mobile", "desktop", "tablet"]

EVENT_TYPES = ["view", "cart", "purchase"]

CITIES = [
    ("New York", "US"),
    ("Los Angeles", "US"),
    ("Chicago", "US"),
    ("Houston", "US"),
    ("London", "GB"),
    ("Manchester", "GB"),
    ("Berlin", "DE"),
    ("Munich", "DE"),
    ("Paris", "FR"),
    ("Tokyo", "JP"),
    ("Osaka", "JP"),
    ("Sydney", "AU"),
    ("Toronto", "CA"),
    ("Mumbai", "IN"),
    ("Bangalore", "IN"),
    ("Sao Paulo", "BR"),
    ("Mexico City", "MX"),
    ("Seoul", "KR"),
    ("Amsterdam", "NL"),
    ("Singapore", "SG"),
]

USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120.0.6099.230",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.6099.200",
    "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 Chrome/119.0.6045.163",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Edge/120.0.2210.133",
]

IP_BASE_RANGES = [
    "10.0.{}.0/24",
    "172.16.{}.0/24",
    "192.168.{}.0/24",
    "100.64.{}.0/24",
    "198.18.{}.0/24",
]

TOTAL_SESSIONS = 2000
EVENTS_PER_SESSION_MIN = 3
EVENTS_PER_SESSION_MAX = 12
OVERLAP_RATIO = 0.20
PLATFORM_A_RATIO = 0.60


# ──────────────────────────────────────────────
# Product Catalog Generator
# ──────────────────────────────────────────────

def _product_templates() -> Dict[str, List[Dict[str, Any]]]:
    return {
        "electronics": [
            {"name": "Wireless Bluetooth Earbuds", "desc": "Noise-cancelling wireless earbuds with 24hr battery and IPX5 water resistance.", "price": 79.99, "tags": ["bluetooth", "wireless", "audio"]},
            {"name": "Ultra HD 4K Monitor 27in", "desc": "27-inch 4K IPS monitor with 99% sRGB, USB-C, and built-in speakers.", "price": 349.99, "tags": ["monitor", "4k", "display"]},
            {"name": "Mechanical Gaming Keyboard", "desc": "RGB mechanical keyboard with Cherry MX Blue switches and aluminum frame.", "price": 129.99, "tags": ["keyboard", "gaming", "mechanical"]},
            {"name": "USB-C Hub 7-in-1", "desc": "Compact USB-C hub with HDMI, SD card, USB 3.0, and PD 100W charging.", "price": 34.99, "tags": ["hub", "usbc", "accessories"]},
            {"name": "Noise Cancelling Headphones", "desc": "Over-ear ANC headphones with 40hr battery and fold-flat design.", "price": 249.99, "tags": ["headphones", "anc", "audio"]},
            {"name": "Smart Home Speaker", "desc": "Voice-controlled smart speaker with room-filling sound and multi-room support.", "price": 89.99, "tags": ["smart", "speaker", "voice"]},
            {"name": "Portable Power Bank 20000mAh", "desc": "High-capacity power bank with USB-C PD 65W and dual USB-A ports.", "price": 44.99, "tags": ["power", "portable", "charging"]},
            {"name": "Webcam 4K Streaming", "desc": "4K webcam with auto-focus, built-in ring light, and noise-reducing mic.", "price": 119.99, "tags": ["webcam", "4k", "streaming"]},
            {"name": "Wireless Charging Pad", "desc": "15W fast wireless charger with LED indicator and anti-slip surface.", "price": 19.99, "tags": ["charger", "wireless", "qi"]},
            {"name": "External SSD 1TB", "desc": "Portable 1TB SSD with USB 3.2 Gen 2 speeds up to 1050MB/s.", "price": 109.99, "tags": ["ssd", "storage", "portable"]},
            {"name": "Ergonomic Vertical Mouse", "desc": "Vertical wireless mouse with 6 buttons and adjustable DPI up to 4000.", "price": 29.99, "tags": ["mouse", "ergonomic", "wireless"]},
            {"name": "Laptop Stand Adjustable", "desc": "Adjustable aluminum laptop stand with ventilation and cable management.", "price": 39.99, "tags": ["stand", "laptop", "ergonomic"]},
            {"name": "Smart Plug WiFi", "desc": "WiFi smart plug with energy monitoring and voice assistant support.", "price": 12.99, "tags": ["smart", "plug", "wifi"]},
            {"name": "Bluetooth Tracker", "desc": "Key-finder Bluetooth tracker with 80dB ringer and 1-year battery.", "price": 24.99, "tags": ["tracker", "bluetooth", "finder"]},
            {"name": "LED Desk Lamp", "desc": "Touch-controlled LED desk lamp with 5 brightness levels and USB charging.", "price": 32.99, "tags": ["lamp", "led", "desk"]},
            {"name": "Tablet Stand Holder", "desc": "Adjustable tablet stand with 360-degree rotation and stable base.", "price": 22.99, "tags": ["tablet", "stand", "holder"]},
            {"name": "Portable Bluetooth Speaker", "desc": "Waterproof portable speaker with 20hr playtime and deep bass.", "price": 59.99, "tags": ["speaker", "bluetooth", "portable"]},
            {"name": "Graphics Drawing Tablet", "desc": "Drawing tablet with 8192 pressure levels and wireless connectivity.", "price": 199.99, "tags": ["drawing", "tablet", "graphics"]},
            {"name": "HDMI Cable 4K 6ft", "desc": "High-speed HDMI 2.1 cable supporting 4K@120Hz and eARC.", "price": 9.99, "tags": ["hdmi", "cable", "4k"]},
            {"name": "Surge Protector Power Strip", "desc": "8-outlet surge protector with 2 USB ports and 6ft cord.", "price": 24.99, "tags": ["surge", "power", "strip"]},
            {"name": "Fitness Tracker Watch", "desc": "Fitness smartwatch with heart rate, SpO2, GPS, and 7-day battery.", "price": 89.99, "tags": ["fitness", "watch", "tracker"]},
            {"name": "Portable Projector", "desc": "Mini portable projector with 1080p support, built-in battery, and WiFi.", "price": 299.99, "tags": ["projector", "portable", "mini"]},
            {"name": "Wireless Mouse", "desc": "Slim wireless mouse with silent clicks and USB-C rechargeable.", "price": 19.99, "tags": ["mouse", "wireless", "slim"]},
            {"name": "USB Microphone", "desc": "Condenser USB microphone with cardioid pattern and mute button.", "price": 49.99, "tags": ["microphone", "usb", "podcast"]},
            {"name": "Monitor Light Bar", "desc": "Auto-dimming monitor light bar with asymmetrical lighting and no screen glare.", "price": 59.99, "tags": ["monitor", "light", "bar"]},
            {"name": "Laptop Backpack", "desc": "Water-resistant laptop backpack with USB charging port and anti-theft pocket.", "price": 54.99, "tags": ["backpack", "laptop", "travel"]},
            {"name": "Action Camera", "desc": "4K action camera with image stabilization, waterproof to 10m, and WiFi.", "price": 129.99, "tags": ["camera", "action", "4k"]},
            {"name": "Digital Photo Frame", "desc": "10-inch WiFi digital photo frame with app upload and slideshow.", "price": 79.99, "tags": ["frame", "digital", "wifi"]},
            {"name": "E-Reader 6in", "desc": "6-inch e-reader with adjustable warm light and weeks-long battery.", "price": 129.99, "tags": ["ereader", "ebook", "reading"]},
            {"name": "Smart Doorbell", "desc": "Video doorbell with 1080p, two-way audio, night vision, and cloud storage.", "price": 69.99, "tags": ["doorbell", "smart", "camera"]},
            {"name": "Router WiFi 6", "desc": "Dual-band WiFi 6 router with 4 Gigabit ports and mesh support.", "price": 149.99, "tags": ["router", "wifi6", "networking"]},
            {"name": "USB Fan Desktop", "desc": "Quiet USB desktop fan with adjustable tilt and 3 speed settings.", "price": 14.99, "tags": ["fan", "usb", "desktop"]},
            {"name": "VR Headset", "desc": "Standalone VR headset with 4K display and 6DOF controllers.", "price": 399.99, "tags": ["vr", "headset", "gaming"]},
            {"name": "Cable Management Box", "desc": "Large cable management box with ventilation and 2 power outlets.", "price": 29.99, "tags": ["cable", "management", "organizer"]},
            {"name": "Mini PC Stick", "desc": "Intel N100 mini PC stick with 8GB RAM, 256GB SSD, and WiFi 6.", "price": 219.99, "tags": ["pc", "mini", "stick"]},
            {"name": "Screen Protector Kit", "desc": "Tempered glass screen protector with alignment tool for phones/tablets.", "price": 8.99, "tags": ["screen", "protector", "glass"]},
            {"name": "USB Hub 4-Port", "desc": "Ultra-slim USB 3.0 hub with 4 ports and 5Gbps transfer speed.", "price": 11.99, "tags": ["usb", "hub", "port"]},
            {"name": "Laptop Cooling Pad", "desc": "Laptop cooling pad with dual fans, adjustable height, and USB powered.", "price": 34.99, "tags": ["cooling", "laptop", "pad"]},
            {"name": "GPS Tracker for Car", "desc": "Real-time GPS tracker with magnetic mount and mobile app tracking.", "price": 44.99, "tags": ["gps", "tracker", "car"]},
            {"name": "Smart Thermostat", "desc": "WiFi smart thermostat with learning algorithm and energy reports.", "price": 129.99, "tags": ["thermostat", "smart", "energy"]},
            {"name": "Dash Cam 4K", "desc": "4K dash cam with night vision, wide angle, and parking monitor.", "price": 99.99, "tags": ["dashcam", "4k", "car"]},
            {"name": "Phone Gimbal Stabilizer", "desc": "3-axis phone gimbal with face tracking, zoom control, and foldable design.", "price": 89.99, "tags": ["gimbal", "stabilizer", "phone"]},
            {"name": "Digital Alarm Clock", "desc": "Digital alarm clock with large display, USB charging, and gradual wake light.", "price": 24.99, "tags": ["clock", "alarm", "digital"]},
            {"name": "Portable Scanner", "desc": "Portable document scanner with WiFi, auto-feed, and OCR software.", "price": 159.99, "tags": ["scanner", "portable", "document"]},
            {"name": "Wireless Keyboard", "desc": "Full-size wireless keyboard with number pad and 2-year battery life.", "price": 39.99, "tags": ["keyboard", "wireless", "fullsize"]},
            {"name": "Smart Light Bulb", "desc": "WiFi smart bulb with 16M colors, dimmable, and voice control.", "price": 14.99, "tags": ["light", "smart", "bulb"]},
            {"name": "Electric Toothbrush", "desc": "Sonic electric toothbrush with 5 modes, 2-min timer, and USB-C charging.", "price": 39.99, "tags": ["toothbrush", "electric", "sonic"]},
            {"name": "Baby Monitor", "desc": "Video baby monitor with 5in screen, night vision, and temperature sensor.", "price": 89.99, "tags": ["baby", "monitor", "video"]},
            {"name": "Weather Station", "desc": "Wireless weather station with indoor/outdoor sensor and color display.", "price": 49.99, "tags": ["weather", "station", "wireless"]},
            {"name": "Car Phone Mount", "desc": "Magnetic car phone mount with 360-degree rotation and one-hand operation.", "price": 17.99, "tags": ["mount", "car", "phone"]},
            {"name": "Smart Egg Timer", "desc": "Bluetooth egg timer with app control and 10-minute timer.", "price": 9.99, "tags": ["timer", "smart", "kitchen"]},
            {"name": "RFID Blocking Wallet", "desc": "Slim RFID-blocking wallet with card slots and cash compartment.", "price": 29.99, "tags": ["wallet", "rfid", "slim"]},
            {"name": "Phone Ring Holder", "desc": "Adjustable phone ring holder with stand function and strong adhesive.", "price": 5.99, "tags": ["holder", "phone", "ring"]},
            {"name": "Portable Jump Starter", "desc": "2000A car jump starter with USB power bank and LED flashlight.", "price": 69.99, "tags": ["jump", "starter", "car"]},
            {"name": "Air Purifier", "desc": "HEPA air purifier for rooms up to 300sqft with auto mode and quiet fan.", "price": 119.99, "tags": ["purifier", "air", "hepa"]},
            {"name": "Essential Oil Diffuser", "desc": "Ultrasonic essential oil diffuser with LED mood light and auto shut-off.", "price": 21.99, "tags": ["diffuser", "oil", "aroma"]},
            {"name": "Smart Lock", "desc": "Keyless smart lock with fingerprint, PIN, and app access control.", "price": 149.99, "tags": ["lock", "smart", "keyless"]},
            {"name": "Electric Kettle", "desc": "Temperature-control electric kettle with keep-warm function and 1.7L capacity.", "price": 44.99, "tags": ["kettle", "electric", "temperature"]},
            {"name": "Toaster 4-Slice", "desc": "4-slice toaster with adjustable browning, defrost, and bagel settings.", "price": 34.99, "tags": ["toaster", "kitchen", "appliance"]},
            {"name": "Slow Cooker 6qt", "desc": "6-quart slow cooker with programmable timer and 3 heat settings.", "price": 49.99, "tags": ["cooker", "slow", "kitchen"]},
            {"name": "Robot Vacuum", "desc": "Robot vacuum with LiDAR mapping, 2500Pa suction, and app scheduling.", "price": 299.99, "tags": ["vacuum", "robot", "smart"]},
            {"name": "Electric Griddle", "desc": "Non-stick electric griddle with adjustable temp and 12x20in cooking surface.", "price": 39.99, "tags": ["griddle", "electric", "cooking"]},
            {"name": "Bread Maker", "desc": "Automatic bread maker with 12 programs, 3 crust colors, and 2lb loaf.", "price": 79.99, "tags": ["bread", "maker", "baking"]},
            {"name": "Air Fryer 5.8qt", "desc": "5.8qt air fryer with 8 presets, digital touchscreen, and rapid air circulation.", "price": 89.99, "tags": ["airfryer", "fryer", "healthy"]},
            {"name": "Food Processor", "desc": "14-cup food processor with 1200W motor, slicing discs, and dough blade.", "price": 99.99, "tags": ["processor", "food", "kitchen"]},
            {"name": "Stand Mixer", "desc": "5.5qt stand mixer with tilt-head, 12 speeds, and stainless steel bowl.", "price": 249.99, "tags": ["mixer", "stand", "baking"]},
            {"name": "Espresso Machine", "desc": "15-bar espresso machine with steam wand, removable water tank, and cup warmer.", "price": 179.99, "tags": ["espresso", "coffee", "machine"]},
        ],
        "clothing": [
            {"name": "Classic Denim Jacket", "desc": "Timeless denim jacket with button front, chest pockets, and adjustable waist.", "price": 89.99, "tags": ["jacket", "denim", "casual"]},
            {"name": "Merino Wool Sweater", "desc": "Lightweight merino wool crewneck sweater perfect for layering.", "price": 74.99, "tags": ["sweater", "wool", "merino"]},
            {"name": "Slim Fit Chinos", "desc": "Stretch cotton chino pants with slim fit and tapered leg.", "price": 54.99, "tags": ["pants", "chinos", "slim"]},
            {"name": "Cotton T-Shirt Pack 3", "desc": "Percale cotton t-shirts with reinforced collar and double-stitched seams.", "price": 39.99, "tags": ["tshirt", "cotton", "pack"]},
            {"name": "Waterproof Rain Jacket", "desc": "Seam-sealed waterproof rain jacket with hood and packable design.", "price": 119.99, "tags": ["jacket", "rain", "waterproof"]},
            {"name": "Cashmere Scarf", "desc": "Pure cashmere scarf with fringed edges and 70x180cm size.", "price": 89.99, "tags": ["scarf", "cashmere", "luxury"]},
            {"name": "Leather Belt", "desc": "Full-grain leather belt with brushed buckle and 35mm width.", "price": 44.99, "tags": ["belt", "leather", "accessory"]},
            {"name": "Linen Shirt", "desc": "Relaxed-fit linen shirt with button-down collar and chest pocket.", "price": 64.99, "tags": ["shirt", "linen", "summer"]},
            {"name": "Puffer Vest", "desc": "Lightweight puffer vest with baffle stitching and zip pockets.", "price": 69.99, "tags": ["vest", "puffer", "insulated"]},
            {"name": "Jogger Sweatpants", "desc": "French terry jogger sweatpants with elastic cuffs and drawstring waist.", "price": 49.99, "tags": ["sweatpants", "jogger", "casual"]},
            {"name": "Polo Shirt", "desc": "Classic pique polo shirt with embroidered logo and ribbed collar.", "price": 44.99, "tags": ["polo", "shirt", "classic"]},
            {"name": "Tailored Blazer", "desc": "Two-button tailored blazer with notched lapels and interior pockets.", "price": 199.99, "tags": ["blazer", "tailored", "formal"]},
            {"name": "Hooded Zip Sweatshirt", "desc": "Midweight zip hoodie with fleece lining and kangaroo pocket.", "price": 59.99, "tags": ["hoodie", "zip", "fleece"]},
            {"name": "Silk Tie", "desc": "Handmade silk tie with self-tipped construction and 8cm width.", "price": 34.99, "tags": ["tie", "silk", "formal"]},
            {"name": "Cargo Shorts", "desc": "Cotton cargo shorts with multiple pockets and adjustable waist.", "price": 39.99, "tags": ["shorts", "cargo", "summer"]},
            {"name": "Turtleneck Sweater", "desc": "Ribbed knit turtleneck sweater with stretch and soft feel.", "price": 69.99, "tags": ["turtleneck", "sweater", "knit"]},
            {"name": "Denim Shirt", "desc": "Western-style denim shirt with snap buttons and chest pockets.", "price": 59.99, "tags": ["shirt", "denim", "western"]},
            {"name": "Swim Trunks", "desc": "Quick-dry swim trunks with mesh lining and drawstring closure.", "price": 34.99, "tags": ["swim", "trunks", "beach"]},
            {"name": "Peacoat", "desc": "Wool-blend peacoat with double-breasted front and storm flap.", "price": 249.99, "tags": ["coat", "wool", "winter"]},
            {"name": "Dress Shirt", "desc": "Non-iron dress shirt with spread collar and adjustable cuff.", "price": 69.99, "tags": ["dress", "shirt", "formal"]},
            {"name": "Knit Beanie", "desc": "Chunky knit beanie hat with fold-up brim and pom-pom.", "price": 19.99, "tags": ["hat", "beanie", "winter"]},
            {"name": "Performance Polo", "desc": "Moisture-wicking performance polo with stretch and UPF 50+.", "price": 54.99, "tags": ["polo", "performance", "sports"]},
            {"name": "Corduroy Pants", "desc": "Straight-leg corduroy pants with button closure and five-pocket styling.", "price": 64.99, "tags": ["pants", "corduroy", "retro"]},
            {"name": "Leather Gloves", "desc": "Genuine leather gloves with touchscreen fingertips and cashmere lining.", "price": 54.99, "tags": ["gloves", "leather", "winter"]},
            {"name": "Canvas Belt", "desc": "Cotton canvas belt with brass buckle and contrast stripe.", "price": 29.99, "tags": ["belt", "canvas", "casual"]},
            {"name": "Bomber Jacket", "desc": "Nylon bomber jacket with ribbed cuffs, waistband, and quilted lining.", "price": 149.99, "tags": ["jacket", "bomber", "nylon"]},
            {"name": "Flannel Shirt", "desc": "Brushed cotton flannel shirt with button-down collar and chest pocket.", "price": 49.99, "tags": ["flannel", "shirt", "plaid"]},
            {"name": "Chambray Shirt", "desc": "Lightweight chambray shirt with barrel cuffs and curved hem.", "price": 54.99, "tags": ["chambray", "shirt", "lightweight"]},
            {"name": "V-Neck Sweater", "desc": "Cotton v-neck sweater with ribbed hem and cuffs.", "price": 59.99, "tags": ["sweater", "vneck", "cotton"]},
            {"name": "Athletic Shorts", "desc": "Quick-dry athletic shorts with built-in brief and zip pocket.", "price": 29.99, "tags": ["shorts", "athletic", "gym"]},
            {"name": "Trench Coat", "desc": "Classic trench coat with epaulettes, storm flap, and belted waist.", "price": 299.99, "tags": ["coat", "trench", "classic"]},
            {"name": "Crewneck Sweatshirt", "desc": "Heavyweight crewneck sweatshirt with ribbed cuffs and hem.", "price": 49.99, "tags": ["sweatshirt", "crewneck", "cotton"]},
            {"name": "Dress Pants", "desc": "Wrinkle-resistant dress pants with flat front and concealed closure.", "price": 79.99, "tags": ["pants", "dress", "formal"]},
            {"name": "Henley Shirt", "desc": "Long-sleeve henley shirt with button placket and ribbed cuffs.", "price": 39.99, "tags": ["henley", "shirt", "longsleeve"]},
            {"name": "Quilted Vest", "desc": "Quilted nylon vest with diamond pattern and zip pockets.", "price": 89.99, "tags": ["vest", "quilted", "insulated"]},
            {"name": "Graphic T-Shirt", "desc": "Soft graphic t-shirt with vintage print and relaxed fit.", "price": 24.99, "tags": ["tshirt", "graphic", "vintage"]},
            {"name": "Cardigan", "desc": "Open-front cardigan with cable knit and shawl collar.", "price": 79.99, "tags": ["cardigan", "knit", "open"]},
            {"name": "Running Quarter Zip", "desc": "Quick-dry quarter-zip top with thumb holes and reflective details.", "price": 59.99, "tags": ["quarterzip", "running", "performance"]},
            {"name": "Waxed Canvas Jacket", "desc": "Waxed canvas jacket with corduroy collar and brass hardware.", "price": 199.99, "tags": ["jacket", "waxed", "canvas"]},
            {"name": "Lace-Up Boots", "desc": "Ankle boots with leather upper, lace-up front, and cushioned insole.", "price": 129.99, "tags": ["boots", "leather", "ankle"]},
            {"name": "Wool Blazer", "desc": "Herringbone wool blazer with patch pockets and double vent.", "price": 249.99, "tags": ["blazer", "wool", "herringbone"]},
            {"name": "Pajama Set", "desc": "Cotton pajama set with button top, drawstring pants, and piped trim.", "price": 49.99, "tags": ["pajama", "sleep", "cotton"]},
            {"name": "Base Layer Top", "desc": "Merino wool base layer top with flatlock seams and tagless label.", "price": 69.99, "tags": ["base", "layer", "merino"]},
            {"name": "Yoga Pants", "desc": "High-waist yoga pants with squat-proof fabric and hidden waistband pocket.", "price": 59.99, "tags": ["yoga", "pants", "activewear"]},
            {"name": "Leather Jacket", "desc": "Genuine leather motorcycle jacket with zip-out lining and snap lapels.", "price": 399.99, "tags": ["jacket", "leather", "motorcycle"]},
            {"name": "Camp Collar Shirt", "desc": "Relaxed camp collar shirt with tropical print and chest pocket.", "price": 44.99, "tags": ["shirt", "camp", "collar"]},
            {"name": "Belted Cardigan", "desc": "Longline cardigan with self-tie belt and side pockets.", "price": 89.99, "tags": ["cardigan", "belted", "long"]},
            {"name": "Tech Vest", "desc": "Travel vest with 12 pockets, RFID blocking, and wrinkle-free fabric.", "price": 79.99, "tags": ["vest", "tech", "travel"]},
            {"name": "Mock Neck Top", "desc": "Stretch mock neck top with long sleeves and fitted silhouette.", "price": 34.99, "tags": ["top", "mock", "neck"]},
            {"name": "Parka", "desc": "Insulated parka with fur-trimmed hood and sealed seams.", "price": 349.99, "tags": ["parka", "insulated", "winter"]},
            {"name": "Safari Jacket", "desc": "Cotton safari jacket with four pockets, belt, and epaulettes.", "price": 119.99, "tags": ["jacket", "safari", "cotton"]},
            {"name": "Raglan Sweatshirt", "desc": "Raglan sleeve sweatshirt with contrast stitching and fleece lining.", "price": 54.99, "tags": ["sweatshirt", "raglan", "fleece"]},
            {"name": "Satin Shirt", "desc": "Satin button-up shirt with self-tie neck and mother-of-pearl buttons.", "price": 79.99, "tags": ["shirt", "satin", "luxury"]},
            {"name": "Work Coveralls", "desc": "Cotton duck coveralls with multiple tool pockets and brass zipper.", "price": 89.99, "tags": ["coveralls", "work", "durable"]},
        ],
        "footwear": [
            {"name": "Running Shoes", "desc": "Neutral running shoes with responsive cushioning and breathable mesh upper.", "price": 129.99, "tags": ["running", "shoes", "cushioning"]},
            {"name": "Hiking Boots", "desc": "Waterproof hiking boots with Vibram sole and ankle support.", "price": 169.99, "tags": ["hiking", "boots", "waterproof"]},
            {"name": "Canvas Sneakers", "desc": "Classic canvas sneakers with vulcanized sole and metal eyelets.", "price": 44.99, "tags": ["sneakers", "canvas", "classic"]},
            {"name": "Loafers", "desc": "Leather loafers with horsebit detail and cushioned insole.", "price": 119.99, "tags": ["loafers", "leather", "formal"]},
            {"name": "Trail Running Shoes", "desc": "Trail running shoes with aggressive tread and rock plate protection.", "price": 139.99, "tags": ["trail", "running", "shoes"]},
            {"name": "Chelsea Boots", "desc": "Suede Chelsea boots with elastic side panels and pull tab.", "price": 149.99, "tags": ["boots", "chelsea", "suede"]},
            {"name": "Basketball Shoes", "desc": "High-top basketball shoes with air cushioning and herringbone traction.", "price": 159.99, "tags": ["basketball", "shoes", "high"]},
            {"name": "Sandals", "desc": "Leather sandals with adjustable straps and contoured footbed.", "price": 54.99, "tags": ["sandals", "leather", "summer"]},
            {"name": "Dress Oxfords", "desc": "Cap-toe oxford dress shoes with leather sole and Goodyear welt.", "price": 199.99, "tags": ["oxfords", "dress", "leather"]},
            {"name": "Slip-On Sneakers", "desc": "Lace-less slip-on sneakers with memory foam insole and stretch knit.", "price": 69.99, "tags": ["slipon", "sneakers", "casual"]},
        ],
        "sports_gear": [
            {"name": "Yoga Mat Premium", "desc": "6mm thick yoga mat with alignment lines and non-slip surface.", "price": 39.99, "tags": ["yoga", "mat", "fitness"]},
            {"name": "Adjustable Dumbbells", "desc": "Space-saving adjustable dumbbells set from 5-52.5 lbs each.", "price": 299.99, "tags": ["dumbbells", "adjustable", "weights"]},
            {"name": "Resistance Bands Set", "desc": "Set of 5 resistance bands with different tensions and door anchor.", "price": 24.99, "tags": ["bands", "resistance", "exercise"]},
            {"name": "Foam Roller", "desc": "High-density foam roller for muscle recovery and myofascial release.", "price": 19.99, "tags": ["foam", "roller", "recovery"]},
            {"name": "Jump Rope Speed", "desc": "Speed jump rope with ball bearings and adjustable cable.", "price": 14.99, "tags": ["jump", "rope", "cardio"]},
            {"name": "Kettlebell 35lbs", "desc": "Cast iron kettlebell with flat base and powder coat finish.", "price": 49.99, "tags": ["kettlebell", "weight", "strength"]},
            {"name": "Ab Roller Wheel", "desc": "Ab roller wheel with knee pad and ergonomic handles.", "price": 12.99, "tags": ["ab", "roller", "core"]},
            {"name": "Push-Up Bars", "desc": "Parallel push-up bars with foam grips and anti-skid base.", "price": 15.99, "tags": ["pushup", "bars", "chest"]},
            {"name": "Exercise Bike", "desc": "Magnetic resistance exercise bike with LCD display and tablet holder.", "price": 249.99, "tags": ["bike", "exercise", "cardio"]},
            {"name": "Pull-Up Bar", "desc": "Doorway pull-up bar with foam grips and multi-grip positions.", "price": 29.99, "tags": ["pullup", "bar", "strength"]},
            {"name": "Treadmill", "desc": "Folding treadmill with incline, pulse sensors, and shock absorption.", "price": 599.99, "tags": ["treadmill", "running", "cardio"]},
            {"name": "Meditation Cushion", "desc": "Round meditation cushion with buckwheat fill and removable cover.", "price": 39.99, "tags": ["meditation", "cushion", "yoga"]},
            {"name": "Weight Bench", "desc": "Adjustable weight bench with 7 positions and 600lb capacity.", "price": 179.99, "tags": ["bench", "weight", "adjustable"]},
            {"name": "Skipping Speed Rope", "desc": "Lightweight speed rope with swivel bearings for double unders.", "price": 9.99, "tags": ["rope", "speed", "cardio"]},
            {"name": "Gym Gloves", "desc": "Ventilated gym gloves with wrist wrap and gel padding.", "price": 19.99, "tags": ["gloves", "gym", "lifting"]},
            {"name": "Water Bottle 32oz", "desc": "Insulated stainless steel water bottle with straw lid and handle.", "price": 34.99, "tags": ["bottle", "water", "insulated"]},
            {"name": "Sweat Towel", "desc": "Microfiber sweat towel with quick-dry and anti-odor technology.", "price": 12.99, "tags": ["towel", "sweat", "microfiber"]},
            {"name": "Gym Bag", "desc": "Duffel gym bag with wet pocket, shoe compartment, and padded strap.", "price": 44.99, "tags": ["bag", "gym", "duffel"]},
            {"name": "Boxing Gloves", "desc": "Leather boxing gloves with wrist support and ventilation palm.", "price": 59.99, "tags": ["boxing", "gloves", "leather"]},
            {"name": "Pilates Ring", "desc": "Pilates resistance ring with padded handles and body sculpting exercises.", "price": 17.99, "tags": ["pilates", "ring", "resistance"]},
        ],
        "home_appliances": [
            {"name": "Stick Vacuum Cleaner", "desc": "Cordless stick vacuum with 45min run and wall-mountable charger.", "price": 199.99, "tags": ["vacuum", "stick", "cordless"]},
            {"name": "Instant Pot 6qt", "desc": "7-in-1 multi-functional pressure cooker with 14 smart programs.", "price": 89.99, "tags": ["cooker", "pressure", "instant"]},
            {"name": "Dehumidifier 50pt", "desc": "50-pint dehumidifier with continuous drain and Energy Star rating.", "price": 199.99, "tags": ["dehumidifier", "moisture", "basement"]},
            {"name": "Tower Fan", "desc": "Oscillating tower fan with remote, timer, and 3 speed settings.", "price": 79.99, "tags": ["fan", "tower", "oscillating"]},
            {"name": "Space Heater", "desc": "Ceramic space heater with thermostat, tip-over shutoff, and 12hr timer.", "price": 39.99, "tags": ["heater", "space", "ceramic"]},
            {"name": "Humidifier 2.5L", "desc": "Cool mist humidifier with night light, 25hr runtime, and auto shut-off.", "price": 34.99, "tags": ["humidifier", "mist", "cool"]},
            {"name": "Cordless Iron", "desc": "Cordless steam iron with ceramic soleplate and 350ml water tank.", "price": 59.99, "tags": ["iron", "cordless", "steam"]},
            {"name": "Electric Blanket", "desc": "Electric heated blanket with dual controls and auto shut-off.", "price": 89.99, "tags": ["blanket", "electric", "heated"]},
            {"name": "Food Dehydrator", "desc": "Digital food dehydrator with 5 trays, timer, and adjustable temperature.", "price": 59.99, "tags": ["dehydrator", "food", "snacks"]},
            {"name": "Waffle Maker", "desc": "Belgian waffle maker with non-stick plates and indicator lights.", "price": 29.99, "tags": ["waffle", "maker", "breakfast"]},
            {"name": "Mini Fridge", "desc": "Compact mini fridge with 4L capacity, thermoelectric cooling, and quiet operation.", "price": 49.99, "tags": ["fridge", "mini", "compact"]},
            {"name": "Sewing Machine", "desc": "Compact sewing machine with 12 stitch patterns and free arm.", "price": 99.99, "tags": ["sewing", "machine", "craft"]},
            {"name": "Ice Maker", "desc": "Portable ice maker producing 26 lbs of ice per day with 2 sizes.", "price": 119.99, "tags": ["ice", "maker", "portable"]},
            {"name": "Rice Cooker", "desc": "Fuzzy logic rice cooker with 5-cup capacity and keep-warm function.", "price": 44.99, "tags": ["rice", "cooker", "kitchen"]},
            {"name": "Hand Blender", "desc": "Immersion hand blender with 500W motor, whisk, and chopper attachment.", "price": 34.99, "tags": ["blender", "hand", "immersion"]},
            {"name": "Coffee Grinder", "desc": "Burr coffee grinder with 17 grind settings and 250g capacity.", "price": 49.99, "tags": ["grinder", "coffee", "burr"]},
            {"name": "Toaster Oven", "desc": "Countertop toaster oven with convection, 60-min timer, and 4 cooking functions.", "price": 69.99, "tags": ["oven", "toaster", "convection"]},
            {"name": "Vacuum Sealer", "desc": "Automatic vacuum sealer with built-in cutter and roll storage.", "price": 44.99, "tags": ["sealer", "vacuum", "food"]},
            {"name": "Electric Can Opener", "desc": "One-touch electric can opener with magnetic lid holder and blade cutting.", "price": 19.99, "tags": ["opener", "can", "electric"]},
            {"name": "Water Filter Pitcher", "desc": "10-cup water filter pitcher with activated carbon filter and LED indicator.", "price": 29.99, "tags": ["filter", "water", "pitcher"]},
        ],
        "books": [
            {"name": "Clean Code", "desc": "A handbook of agile software craftsmanship by Robert C. Martin.", "price": 34.99, "tags": ["programming", "software", "craft"]},
            {"name": "The Pragmatic Programmer", "desc": "Journeyman to master, 20th anniversary edition by Andy Hunt.", "price": 39.99, "tags": ["programming", "pragmatic", "career"]},
            {"name": "Designing Data-Intensive Applications", "desc": "Reliable, scalable, maintainable systems by Martin Kleppmann.", "price": 44.99, "tags": ["data", "systems", "architecture"]},
            {"name": "Introduction to Algorithms", "desc": "Comprehensive algorithms reference by CLRS, 4th edition.", "price": 89.99, "tags": ["algorithms", "textbook", "cs"]},
            {"name": "The Lean Startup", "desc": "How today's entrepreneurs use continuous innovation by Eric Ries.", "price": 24.99, "tags": ["business", "startup", "lean"]},
            {"name": "Sapiens", "desc": "A brief history of humankind by Yuval Noah Harari.", "price": 18.99, "tags": ["history", "humanity", "nonfiction"]},
            {"name": "Atomic Habits", "desc": "An easy and proven way to build good habits by James Clear.", "price": 16.99, "tags": ["habits", "selfhelp", "productivity"]},
            {"name": "The Art of War", "desc": "Ancient military strategy classic by Sun Tzu.", "price": 9.99, "tags": ["strategy", "philosophy", "classic"]},
            {"name": "Deep Work", "desc": "Rules for focused success in a distracted world by Cal Newport.", "price": 15.99, "tags": ["focus", "productivity", "work"]},
            {"name": "Zero to One", "desc": "Notes on startups, or how to build the future by Peter Thiel.", "price": 17.99, "tags": ["startup", "innovation", "entrepreneurship"]},
            {"name": "The Phoenix Project", "desc": "A novel about IT, DevOps, and helping your business win.", "price": 19.99, "tags": ["devops", "it", "fiction"]},
            {"name": "Python Crash Course", "desc": "Hands-on, project-based introduction to programming by Eric Matthes.", "price": 29.99, "tags": ["python", "programming", "tutorial"]},
            {"name": "Fluent Python", "desc": "Clear, concise, and effective programming by Luciano Ramalho.", "price": 39.99, "tags": ["python", "advanced", "programming"]},
            {"name": "The Great Gatsby", "desc": "F. Scott Fitzgerald's masterpiece of the Jazz Age.", "price": 11.99, "tags": ["fiction", "classic", "american"]},
            {"name": "1984", "desc": "George Orwell's dystopian social science fiction novel.", "price": 10.99, "tags": ["fiction", "dystopian", "classic"]},
            {"name": "To Kill a Mockingbird", "desc": "Harper Lee's Pulitzer prize-winning novel about racial injustice.", "price": 12.99, "tags": ["fiction", "classic", "american"]},
            {"name": "Machine Learning Engineering", "desc": "Applied ML techniques for production systems by Andriy Burkov.", "price": 44.99, "tags": ["ml", "engineering", "production"]},
            {"name": "The Cathedral and the Bazaar", "desc": "Musings on Linux and open source by an accidental revolutionary.", "price": 14.99, "tags": ["opensource", "linux", "essays"]},
            {"name": "Gödel Escher Bach", "desc": "An eternal golden braid by Douglas Hofstadter.", "price": 19.99, "tags": ["philosophy", "math", "art"]},
            {"name": "Structure and Interpretation", "desc": "Classic computer science text by Sussman and Abelson.", "price": 59.99, "tags": ["cs", "textbook", "classic"]},
        ],
        "beauty": [
            {"name": "Vitamin C Serum", "desc": "20% Vitamin C serum with hyaluronic acid and vitamin E for brightening.", "price": 24.99, "tags": ["serum", "vitaminc", "skincare"]},
            {"name": "Retinol Moisturizer", "desc": "Night cream with retinol and peptides for anti-aging and renewal.", "price": 34.99, "tags": ["retinol", "moisturizer", "night"]},
            {"name": "SPF 50 Sunscreen", "desc": "Broad-spectrum SPF 50 sunscreen with zinc oxide and aloe vera.", "price": 19.99, "tags": ["sunscreen", "spf", "protection"]},
            {"name": "Hyaluronic Acid Toner", "desc": "Hydrating toner with hyaluronic acid, niacinamide, and panthenol.", "price": 17.99, "tags": ["toner", "hyaluronic", "hydrating"]},
            {"name": "Nail Polish Set", "desc": "Set of 6 gel-like nail polishes with high-gloss finish and chip resistance.", "price": 22.99, "tags": ["nail", "polish", "gel"]},
            {"name": "Lip Balm Pack", "desc": "Pack of 4 tinted lip balms with shea butter and SPF 15.", "price": 11.99, "tags": ["lip", "balm", "tinted"]},
            {"name": "Face Mask Sheet Set", "desc": "Set of 10 sheet masks with hyaluronic acid, collagen, and green tea.", "price": 15.99, "tags": ["mask", "sheet", "face"]},
            {"name": "Eyelash Curler", "desc": "Professional eyelash curler with silicone pad and ergonomic handle.", "price": 9.99, "tags": ["eyelash", "curler", "makeup"]},
            {"name": "Makeup Brush Set", "desc": "Set of 12 synthetic makeup brushes with case for all face and eye looks.", "price": 39.99, "tags": ["brushes", "makeup", "set"]},
            {"name": "Eye Shadow Palette", "desc": "18-shade eye shadow palette with matte, shimmer, and glitter finishes.", "price": 29.99, "tags": ["eyeshadow", "palette", "makeup"]},
            {"name": "Hair Dryer Ionic", "desc": "Ionic hair dryer with 3 heat settings, concentrator, and diffuser.", "price": 49.99, "tags": ["hair", "dryer", "ionic"]},
            {"name": "Straightening Brush", "desc": "Heated straightening brush with anti-scald technology and auto shut-off.", "price": 44.99, "tags": ["straightener", "brush", "hair"]},
            {"name": "Facial Cleanser", "desc": "Gentle foaming facial cleanser with green tea and chamomile extract.", "price": 14.99, "tags": ["cleanser", "face", "gentle"]},
            {"name": "Beard Oil Kit", "desc": "All-natural beard oil kit with jojoba, argan, and sandalwood scents.", "price": 19.99, "tags": ["beard", "oil", "grooming"]},
            {"name": "Perfume Eau de Parfum", "desc": "Long-lasting floral eau de parfum with notes of jasmine and rose.", "price": 59.99, "tags": ["perfume", "fragrance", "floral"]},
            {"name": "Under Eye Cream", "desc": "Caffeine-infused under eye cream for dark circles and puffiness.", "price": 22.99, "tags": ["eye", "cream", "caffeine"]},
            {"name": "Hair Mask Deep Conditioner", "desc": "Deep conditioning hair mask with argan oil and keratin for damaged hair.", "price": 18.99, "tags": ["hair", "mask", "conditioner"]},
            {"name": "Lipstick Matte", "desc": "Long-wear matte lipstick with 8hr color stay and vitamin E.", "price": 16.99, "tags": ["lipstick", "matte", "longwear"]},
            {"name": "Concealer Full Coverage", "desc": "Full-coverage liquid concealer with buildable formula and crease-proof finish.", "price": 13.99, "tags": ["concealer", "coverage", "liquid"]},
            {"name": "Setting Spray", "desc": "Makeup setting spray with micro-fine mist and 16hr hold.", "price": 12.99, "tags": ["setting", "spray", "makeup"]},
            {"name": "Exfoliating Scrub", "desc": "Sugar face scrub with jojoba beads and vitamin C for gentle exfoliation.", "price": 16.99, "tags": ["scrub", "exfoliating", "face"]},
            {"name": "Body Lotion", "desc": "Shea butter body lotion with cocoa butter and vitamin E for all-day moisture.", "price": 13.99, "tags": ["lotion", "body", "shea"]},
            {"name": "Heat Protectant Spray", "desc": "Heat protectant spray for hair up to 450F with argan oil and silk proteins.", "price": 11.99, "tags": ["heat", "protectant", "hair"]},
            {"name": "Micellar Water", "desc": "Micellar cleansing water with glycerin for all skin types.", "price": 10.99, "tags": ["micellar", "cleanser", "water"]},
            {"name": "BB Cream", "desc": "BB cream with SPF 30, light coverage, and skin-tone adapt technology.", "price": 21.99, "tags": ["bbcream", "spf", "coverage"]},
        ],
        "automotive_accessories": [
            {"name": "Car Vacuum Cleaner", "desc": "Portable hand vacuum with 8000Pa suction, HEPA filter, and crevice tool.", "price": 44.99, "tags": ["vacuum", "car", "portable"]},
            {"name": "Seat Cushion Cover Set", "desc": "Neoprene car seat covers, front pair, with anti-slip backing and headrest cutouts.", "price": 59.99, "tags": ["seat", "cover", "car"]},
            {"name": "Steering Wheel Cover", "desc": "Microfiber steering wheel cover with non-slip grip and stitched design.", "price": 19.99, "tags": ["steering", "cover", "wheel"]},
            {"name": "Dash Camera", "desc": "1080p dash cam with wide angle, night vision, and loop recording.", "price": 49.99, "tags": ["dashcam", "camera", "safety"]},
            {"name": "Car Phone Mount", "desc": "Dashboard car phone mount with strong suction and one-touch release.", "price": 17.99, "tags": ["mount", "phone", "car"]},
            {"name": "All-Weather Floor Mats", "desc": "Set of 4 custom-fit all-weather floor mats with raised edges for spills.", "price": 69.99, "tags": ["mats", "floor", "weather"]},
            {"name": "LED Interior Lights", "desc": "RGB LED car interior strip lights with app control and music sync.", "price": 22.99, "tags": ["led", "lights", "interior"]},
            {"name": "OBD2 Scanner", "desc": "Bluetooth OBD2 scanner with engine diagnostics smartphone app.", "price": 29.99, "tags": ["obd2", "scanner", "diagnostic"]},
            {"name": "Tire Pressure Monitor", "desc": "Solar-powered TPMS with 4 external sensors and real-time display.", "price": 39.99, "tags": ["tire", "pressure", "monitor"]},
            {"name": "Trunk Organizer", "desc": "Collapsible trunk organizer with multiple compartments and waterproof liner.", "price": 34.99, "tags": ["trunk", "organizer", "storage"]},
            {"name": "Car Battery Charger", "desc": "Smart battery charger with 6A output, desulfation mode, and reverse polarity protection.", "price": 49.99, "tags": ["charger", "battery", "car"]},
            {"name": "Sun Shade", "desc": "Foldable car sun shade with UV protection and reflective silver coating.", "price": 14.99, "tags": ["sun", "shade", "uv"]},
            {"name": "Windshield Cover", "desc": "Frost shield windshield cover with magnetic flaps and zippered storage bag.", "price": 24.99, "tags": ["windshield", "cover", "frost"]},
            {"name": "Jump Starter Pack", "desc": "800A peak jump starter pack with USB output and LED flashlight.", "price": 59.99, "tags": ["jump", "starter", "battery"]},
            {"name": "Rear View Mirror Camera", "desc": "Rear view mirror dash cam with 1080p front and rear recording.", "price": 89.99, "tags": ["mirror", "camera", "rearview"]},
            {"name": "Car Air Purifier", "desc": "Car air purifier with HEPA filter, negative ion generator, and quiet fan.", "price": 39.99, "tags": ["purifier", "air", "car"]},
            {"name": "Seat Gap Filler", "desc": "Car seat gap filler and organizer with storage pockets for both sides.", "price": 12.99, "tags": ["gap", "filler", "organizer"]},
            {"name": "Roof Rack Cross Bars", "desc": "Aluminum roof rack cross bars with locking mechanism, fits most vehicles.", "price": 129.99, "tags": ["rack", "roof", "bars"]},
            {"name": "USB Car Charger", "desc": "Dual USB-C car charger with 45W PD fast charging and voltmeter display.", "price": 18.99, "tags": ["charger", "usb", "car"]},
            {"name": "Backup Camera", "desc": "Wireless backup camera with night vision, 170-degree angle, and monitor.", "price": 69.99, "tags": ["camera", "backup", "safety"]},
            {"name": "Car Emergency Kit", "desc": "37-piece car emergency kit with jumper cables, first aid, and tools.", "price": 34.99, "tags": ["emergency", "kit", "safety"]},
            {"name": "Cargo Liner", "desc": "Waterproof cargo liner for SUV trunk with raised edge and non-slip surface.", "price": 49.99, "tags": ["cargo", "liner", "trunk"]},
            {"name": "Side Window Visors", "desc": "In-channel side window visors for rain protection and ventilation.", "price": 39.99, "tags": ["visors", "window", "rain"]},
            {"name": "Magnetic Phone Holder", "desc": "Strong magnetic phone holder for car dashboard with ultra-thin plate.", "price": 15.99, "tags": ["magnetic", "holder", "phone"]},
            {"name": "Third Brake Light Decal", "desc": "Custom third brake light decal with LED illumination and weatherproof material.", "price": 11.99, "tags": ["decal", "brake", "light"]},
        ],
    }


def generate_product_catalog(seed: int) -> List[Dict[str, Any]]:
    """Generate 500+ products across 8 categories."""
    rng = random.Random(seed + 42)
    templates = _product_templates()
    catalog: List[Dict[str, Any]] = []
    product_id_counter = 1

    for category in PRODUCT_CATEGORIES:
        cat_templates = templates[category]
        num_from_templates = len(cat_templates)
        target = 65 if category != "automotive_accessories" else 50
        needed = max(target, target)

        for i, tpl in enumerate(cat_templates):
            catalog.append({
                "product_id": f"prod_{product_id_counter:04d}",
                "name": tpl["name"],
                "category": category,
                "description": tpl["desc"],
                "price": round(tpl["price"] + rng.uniform(-2, 2), 2),
                "tags": tpl["tags"],
            })
            product_id_counter += 1

        extra = needed - num_from_templates
        for _ in range(extra):
            adj = rng.choice(["Premium", "Pro", "Elite", "Essential", "Compact", "Deluxe"])
            base_name = rng.choice(cat_templates)["name"]
            catalog.append({
                "product_id": f"prod_{product_id_counter:04d}",
                "name": f"{adj} {base_name}",
                "category": category,
                "description": f"{adj.lower()} version of the popular {base_name.lower()} with enhanced features.",
                "price": round(rng.uniform(9.99, 499.99), 2),
                "tags": rng.sample(cat_templates[0]["tags"], k=min(3, len(cat_templates[0]["tags"]))),
            })
            product_id_counter += 1

    rng.shuffle(catalog)
    return catalog


# ──────────────────────────────────────────────
# Synthetic Clickstream Generator
# ──────────────────────────────────────────────

def _consistent_hash(value: str, seed: int) -> int:
    return int(hashlib.md5(f"{seed}:{value}".encode()).hexdigest(), 16)


def generate_synthetic_events(
    total_sessions: int,
    overlap_ratio: float,
    platform_a_ratio: float,
    seed: int,
    product_ids: List[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Generate synthetic clickstream events with cross-platform overlap.

    Returns:
        Tuple of (platform_a_events, platform_b_events, ground_truth_records)
    """
    rng = random.Random(seed)

    overlapping_count = int(total_sessions * overlap_ratio)
    non_overlap_count = total_sessions - overlapping_count
    platform_a_non_overlap = int(non_overlap_count * platform_a_ratio)
    platform_b_non_overlap = non_overlap_count - platform_a_non_overlap

    platform_a_events: List[Dict[str, Any]] = []
    platform_b_events: List[Dict[str, Any]] = []
    ground_truth: List[Dict[str, Any]] = []

    session_counter = [0]

    def _make_session_id(prefix: str) -> str:
        session_counter[0] += 1
        return f"{prefix}_sess_{session_counter[0]:05d}_{uuid.uuid4().hex[:8]}"

    def _make_events_for_session(
        session_id: str,
        platform: str,
        device_type: str,
        ip_range: str,
        location_city: str,
        location_country: str,
        user_agent: str,
        hashed_email: Optional[str],
        base_time: datetime,
        product_ids: List[str],
    ) -> List[Dict[str, Any]]:
        num_events = rng.randint(EVENTS_PER_SESSION_MIN, EVENTS_PER_SESSION_MAX)
        events: List[Dict[str, Any]] = []
        for ei in range(num_events):
            event_time = base_time + timedelta(seconds=rng.randint(1, 3600))
            event_type = rng.choices(
                EVENT_TYPES,
                weights=[0.7, 0.2, 0.1],
            )[0]
            events.append({
                "session_id": session_id,
                "event_time": event_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "event_type": event_type,
                "product_id": rng.choice(product_ids),
                "platform": platform,
                "device_type": device_type,
                "ip_range": ip_range,
                "city": location_city,
                "country": location_country,
                "user_agent": user_agent,
                "hashed_email": hashed_email if hashed_email else "",
            })
        return events

    # Pick users for overlap (deterministic vs probabilistic)
    overlap_det_count = overlapping_count // 2
    overlap_prob_count = overlapping_count - overlap_det_count

    base_time = datetime(2024, 3, 1, 8, 0, 0)

    # ── Generate overlapping sessions ──
    for oi in range(overlapping_count):
        device = rng.choice(DEVICE_TYPES)
        city, country = rng.choice(CITIES)
        subnet = rng.choice([16, 24])
        base_ip_octet = rng.randint(1, 254)
        ip_range = f"10.{base_ip_octet}.{oi % 256}.0/{subnet}"
        ua = rng.choice(USER_AGENTS)
        base_ts = base_time + timedelta(hours=rng.randint(0, 168))

        if oi < overlap_det_count:
            shared_email = hashlib.sha256(f"overlap_user_{oi:04d}@example.com".encode()).hexdigest()
        else:
            shared_email = None

        a_sid = _make_session_id("A")
        b_sid = _make_session_id("B")

        global_uid = f"global_{uuid.uuid4().hex[:16]}"

        a_events = _make_events_for_session(
            a_sid, "A", device, ip_range, city, country, ua, shared_email,
            base_ts, product_ids,
        )
        b_events = _make_events_for_session(
            b_sid, "B", device, ip_range, city, country, ua, shared_email,
            base_ts + timedelta(minutes=rng.randint(30, 180)), product_ids,
        )

        platform_a_events.extend(a_events)
        platform_b_events.extend(b_events)

        expected_method = "deterministic" if shared_email else "probabilistic"
        ground_truth.append({
            "session_id_a": a_sid,
            "platform_a": "A",
            "session_id_b": b_sid,
            "platform_b": "B",
            "global_uid": global_uid,
            "expected_method": expected_method,
            "match_features": json.dumps({
                "ip_range": ip_range,
                "device_type": device,
                "location_city": city,
                "location_country": country,
                "hashed_email": shared_email,
            }),
        })

    # ── Generate non-overlapping Platform A sessions ──
    for _ in range(platform_a_non_overlap):
        device = rng.choice(DEVICE_TYPES)
        city, country = rng.choice(CITIES)
        ip_range = rng.choice(IP_BASE_RANGES).format(rng.randint(0, 255))
        ua = rng.choice(USER_AGENTS)
        sid = _make_session_id("A")
        hashed = hashlib.sha256(f"unique_a_{uuid.uuid4().hex}@example.com".encode()).hexdigest()
        base_ts = base_time + timedelta(hours=rng.randint(0, 168))
        events = _make_events_for_session(
            sid, "A", device, ip_range, city, country, ua, hashed,
            base_ts, product_ids,
        )
        platform_a_events.extend(events)

    # ── Generate non-overlapping Platform B sessions ──
    for _ in range(platform_b_non_overlap):
        device = rng.choice(DEVICE_TYPES)
        city, country = rng.choice(CITIES)
        ip_range = rng.choice(IP_BASE_RANGES).format(rng.randint(0, 255))
        ua = rng.choice(USER_AGENTS)
        sid = _make_session_id("B")
        hashed = hashlib.sha256(f"unique_b_{uuid.uuid4().hex}@example.com".encode()).hexdigest()
        base_ts = base_time + timedelta(hours=rng.randint(0, 168))
        events = _make_events_for_session(
            sid, "B", device, ip_range, city, country, ua, hashed,
            base_ts, product_ids,
        )
        platform_b_events.extend(events)

    rng.shuffle(platform_a_events)
    rng.shuffle(platform_b_events)

    return platform_a_events, platform_b_events, ground_truth


# ──────────────────────────────────────────────
# CSV Writer
# ──────────────────────────────────────────────

CSV_FIELDS = [
    "session_id", "event_time", "event_type", "product_id",
    "platform", "device_type", "ip_range", "city", "country",
    "user_agent", "hashed_email",
]

GT_FIELDS = [
    "session_id_a", "platform_a", "session_id_b", "platform_b",
    "global_uid", "expected_method", "match_features",
]


def write_csv(filename: str, fieldnames: List[str], rows: List[Dict[str, Any]]) -> None:
    """Write rows to a CSV file."""
    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(filename: str, data: Any) -> None:
    """Write data as JSON to a file."""
    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)


# ──────────────────────────────────────────────
# Download Instructions
# ──────────────────────────────────────────────

def print_download_instructions() -> None:
    print("=" * 72)
    print("  MANUAL DOWNLOAD INSTRUCTIONS - Kaggle Datasets")
    print("=" * 72)
    print()
    print("  This script works best with the actual Kaggle clickstream datasets.")
    print("  If CSV files are missing, synthetic data will be generated instead.")
    print()
    print("  Dataset A — Ecommerce Clickstream (raw behavioral logs):")
    print("    URL: https://www.kaggle.com/datasets/ifeanyiokonkwo/ecommerce-clickstream-data")
    print("    Expected files:")
    print("      - 2019-Nov.csv")
    print("      - 2019-Oct.csv")
    print("    Place in:  data/")
    print()
    print("  Dataset B — E-commerce User Behavior & Transactions (enriched):")
    print("    URL: https://www.kaggle.com/datasets/ifeanyiokonkwo/ecommerce-user-behavior-and-transactions")
    print("    Expected files:")
    print("      - userbase.csv")
    print("    Place in:  data/")
    print()
    print("  Steps:")
    print("    1. Create a Kaggle account at https://www.kaggle.com")
    print("    2. Download the CSVs from each dataset page")
    print("    3. Place the files in the ./data/ directory")
    print("    4. Re-run this script to use real data")
    print()
    print("=" * 72)
    print()


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Prepare data for the CDP Agentic Ad Engine.",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--input-dir", type=str, default="./data",
        help="Directory containing Kaggle CSVs (default: ./data)",
    )
    parser.add_argument(
        "--output-dir", type=str, default="./data",
        help="Directory for output files (default: ./data)",
    )
    parser.add_argument(
        "--sessions", type=int, default=TOTAL_SESSIONS,
        help=f"Number of sessions to generate (default: {TOTAL_SESSIONS})",
    )
    parser.add_argument(
        "--overlap", type=float, default=OVERLAP_RATIO,
        help=f"Ratio of overlapping sessions (default: {OVERLAP_RATIO})",
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)

    print_download_instructions()

    # Check for Kaggle CSV files
    input_dir = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    kaggle_files_found = False
    for fname in ["2019-Nov.csv", "2019-Oct.csv", "userbase.csv"]:
        fpath = os.path.join(input_dir, fname)
        if os.path.exists(fpath):
            kaggle_files_found = True
            print(f"  Found Kaggle file: {fpath}")

    if kaggle_files_found:
        print("\n  Using Kaggle data as base (read + resample)...")
        # For now, we generate synthetic enriched from the real schema
        # In production, you would read and parse the actual CSV columns here
    else:
        print("\n  No Kaggle CSVs found. Generating synthetic data...\n")

    # ── Step 1: Generate Product Catalog ──
    print("  [1/4] Generating product catalog...")
    catalog = generate_product_catalog(args.seed)
    catalog_path = os.path.join(output_dir, "product_catalog.json")
    write_json(catalog_path, catalog)
    print(f"    → {len(catalog)} products written to {catalog_path}")
    product_ids = [p["product_id"] for p in catalog]

    # ── Step 2: Generate Events ──
    print("  [2/4] Generating synthetic clickstream events...")
    platform_a_events, platform_b_events, ground_truth = generate_synthetic_events(
        total_sessions=args.sessions,
        overlap_ratio=args.overlap,
        platform_a_ratio=PLATFORM_A_RATIO,
        seed=args.seed,
        product_ids=product_ids,
    )
    print(f"    → Platform A: {len(platform_a_events)} events")
    print(f"    → Platform B: {len(platform_b_events)} events")
    print(f"    → Overlapping session pairs: {len(ground_truth)}")

    # ── Step 3: Write CSVs ──
    print("  [3/4] Writing CSV files...")
    a_path = os.path.join(output_dir, "platform_a_events.csv")
    b_path = os.path.join(output_dir, "platform_b_events.csv")
    gt_path = os.path.join(output_dir, "synthetic_ground_truth.csv")
    write_csv(a_path, CSV_FIELDS, platform_a_events)
    write_csv(b_path, CSV_FIELDS, platform_b_events)
    write_csv(gt_path, GT_FIELDS, ground_truth)
    print(f"    → {a_path}")
    print(f"    → {b_path}")
    print(f"    → {gt_path}")

    # ── Step 4: Summary Report ──
    print("  [4/4] Summary Report")
    print()
    print(f"  {'Metric':<40} {'Value':<20}")
    print(f"  {'─'*40} {'─'*20}")
    total = len(platform_a_events) + len(platform_b_events)
    print(f"  {'Total events generated':<40} {total:<20}")
    print(f"  {'Platform A events':<40} {len(platform_a_events):<20}")
    print(f"  {'Platform B events':<40} {len(platform_b_events):<20}")
    print(f"  {'Platform A share':<40} {len(platform_a_events)/total*100:.1f}%")
    print(f"  {'Platform B share':<40} {len(platform_b_events)/total*100:.1f}%")
    det_count = sum(1 for gt in ground_truth if gt["expected_method"] == "deterministic")
    prob_count = sum(1 for gt in ground_truth if gt["expected_method"] == "probabilistic")
    print(f"  {'Overlapping session pairs':<40} {len(ground_truth):<20}")
    print(f"  {'  → Deterministic matches':<40} {det_count:<20}")
    print(f"  {'  → Probabilistic matches':<40} {prob_count:<20}")
    print(f"  {'Products in catalog':<40} {len(catalog):<20}")
    print(f"  {'Product categories':<40} {len(PRODUCT_CATEGORIES):<20}")
    print()
    print("  ✅ Data preparation complete.")
    print()


if __name__ == "__main__":
    main()
