import requests
import time
import urllib3
import re
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CLIENT_PLATFORM = "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9"

# Valorant Skin Rarity UUIDs und Farben (sortiert von BEST zu WORST)
RARITY_INFO = {
    "e046854e-406c-37f4-6607-19a9ba8426fc": {  # Ultra
        "name": "Ultra",
        "color": (255, 215, 0),  # Gold
        "order": 1
    },
    "411e4a55-4e59-7757-41f0-86a53f101bb5": {  # Exclusive
        "name": "Exclusive",
        "color": (255, 152, 51),  # Orange
        "order": 2
    },
    "60bca009-4182-7998-dee7-b8a2558dc369": {  # Premium
        "name": "Premium",
        "color": (207, 85, 168),  # Pink/Magenta
        "order": 3
    },
    "0cebb8be-46d7-c12a-d306-e9907bfc5a25": {  # Deluxe -> Türkis
        "name": "Battle Pass / Standard",
        "color": (64, 224, 208),  # Türkis
        "order": 4
    },
    "12683d76-48d7-84a3-4e09-6985794f0445": {  # Select -> Türkis
        "name": "Battle Pass / Standard",
        "color": (64, 224, 208),  # Türkis
        "order": 4
    },
    None: {  # Keine Seltenheit -> auch Türkis
        "name": "Battle Pass / Standard",
        "color": (64, 224, 208),  # Türkis
        "order": 4
    }
}

def log(message, type="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    colors = {
        "INFO": "\033[94m",
        "SUCCESS": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
    }
    reset = "\033[0m"
    print(f"[{timestamp}] {colors.get(type, '')}{message}{reset}")

def get_lockfile_data():
    try:
        lockfile_path = os.path.join(os.getenv('LOCALAPPDATA'), r"Riot Games\Riot Client\Config\lockfile")
        with open(lockfile_path, 'r') as f:
            data = f.read().split(':')
            return {'port': data[2], 'password': data[3]}
    except Exception as e:
        log(f"Failed to read lockfile: {e}", "ERROR")
        return None

def create_local_session(lockfile):
    session = requests.Session()
    session.verify = False
    session.auth = ('riot', lockfile['password'])
    return session

def get_entitlements_and_token(session, port):
    try:
        url = f"https://127.0.0.1:{port}/entitlements/v1/token"
        response = session.get(url)
        if response.status_code == 200:
            data = response.json()
            return {'entitlements_token': data['token'], 'access_token': data['accessToken']}
    except Exception as e:
        log(f"Failed to retrieve tokens: {e}", "ERROR")
    return None

def get_player_uuid(session, port):
    try:
        url = f"https://127.0.0.1:{port}/chat/v1/session"
        response = session.get(url)
        if response.status_code == 200:
            return response.json()['puuid']
    except Exception as e:
        log(f"Failed to retrieve player UUID: {e}", "ERROR")
    return None

def get_owned_skins(region, shard, tokens, puuid):
    url = f"https://pd.{shard}.a.pvp.net/store/v1/entitlements/{puuid}"
    headers = {
        'X-Riot-ClientPlatform': CLIENT_PLATFORM,
        'X-Riot-ClientVersion': tokens['client_version'],
        'X-Riot-Entitlements-JWT': tokens['entitlements_token'],
        'Authorization': f"Bearer {tokens['access_token']}"
    }
    try:
        response = requests.get(url, headers=headers, verify=False)
        data = response.json()
        owned_skins = []
        for entry in data.get("EntitlementsByTypes", []):
            if entry.get("ItemTypeID") == "e7c63390-eda7-46e0-bb7a-a6abdacd2433":
                owned_skins.extend(entry.get("Entitlements", []))
        return owned_skins
    except Exception as e:
        log(f"Failed to retrieve skins: {e}", "ERROR")
        return []

def get_skin_mapping():
    try:
        response = requests.get("https://valorant-api.com/v1/weapons/skins")
        data = response.json()
        mapping = {}
        for skin in data['data']:
            content_tier = skin.get('contentTierUuid')
            base_name = skin['displayName']
            
            # Base Skin
            mapping[skin['uuid']] = {
                'name': base_name,
                'icon': skin['displayIcon'],
                'rarity': content_tier,
                'base_name': base_name
            }
            
            # Alle Chromas auch mappen
            for chroma in skin.get('chromas', []):
                mapping[chroma['uuid']] = {
                    'name': chroma['displayName'],
                    'icon': chroma.get('displayIcon') or skin['displayIcon'],
                    'rarity': content_tier,
                    'base_name': base_name
                }
            
            # Alle Levels auch mappen
            for level in skin.get('levels', []):
                mapping[level['uuid']] = {
                    'name': level['displayName'],
                    'icon': level.get('displayIcon') or skin['displayIcon'],
                    'rarity': content_tier,
                    'base_name': base_name
                }
        return mapping
    except Exception as e:
        log(f"Failed to fetch official skins: {e}", "ERROR")
        return {}

def extract_base_skin_name(name):
    """Entfernt Level/Chroma-Suffixe aus Skin-Namen"""
    # Entferne "Level X", "Chroma X", "Variant X" etc.
    clean_name = re.sub(r'\s+Level\s+\d+', '', name, flags=re.IGNORECASE)
    clean_name = re.sub(r'\s+Variant\s+\d+.*', '', clean_name, flags=re.IGNORECASE)
    clean_name = re.sub(r'\s+\(.*?\)', '', clean_name)  # Entferne (Brackets)
    return clean_name.strip()

def download_image(url):
    try:
        response = requests.get(url, timeout=10)
        img = Image.open(BytesIO(response.content))
        return img.convert("RGBA")
    except Exception as e:
        return None

def create_skin_grid(skins_data):
    # Einstellungen für das Grid
    SKINS_PER_ROW = 8
    CARD_WIDTH = 180
    CARD_HEIGHT = 180
    PADDING = 5
    HEADER_HEIGHT = 60  # Platz für die Gesamtzahl oben

    total_skins = len(skins_data)

    # Skins nach Seltenheit sortieren
    sorted_skins = sorted(skins_data, key=lambda x: RARITY_INFO.get(x['rarity'], RARITY_INFO[None]).get('order', 999))

    # Skins nach Seltenheit gruppieren
    grouped_skins = {}
    for skin in sorted_skins:
        rarity = skin['rarity']
        rarity_info = RARITY_INFO.get(rarity, RARITY_INFO[None])
        if rarity_info['name'] == "Battle Pass / Standard":
            group_key = "turquoise"
        else:
            group_key = rarity
        grouped_skins.setdefault(group_key, []).append(skin)

    # Berechne Gesamthöhe (inkl. Header)
    total_height = PADDING + HEADER_HEIGHT
    for group, skins in grouped_skins.items():
        rows = (len(skins) + SKINS_PER_ROW - 1) // SKINS_PER_ROW
        total_height += rows * (CARD_HEIGHT + PADDING) + PADDING

    # Erstelle Canvas
    canvas_width = SKINS_PER_ROW * (CARD_WIDTH + PADDING) + PADDING
    canvas = Image.new('RGB', (canvas_width, total_height), color=(15, 18, 25))
    draw = ImageDraw.Draw(canvas)

    # Schriftversuche
    try:
        title_font = ImageFont.truetype("arial.ttf", 36)
    except:
        title_font = ImageFont.load_default()
    try:
        name_font = ImageFont.truetype("arial.ttf", 12)
    except:
        name_font = ImageFont.load_default()

    # Zeichne Header: Gesamtanzahl oben, zentriert, weiß mit Schatten
    title_text = f"Total skins: {total_skins}"
    bbox = draw.textbbox((0, 0), title_text, font=title_font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    text_x = (canvas_width - text_width) // 2
    text_y = PADDING + (HEADER_HEIGHT - text_height) // 2

    # Schatten
    draw.text((text_x + 2, text_y + 2), title_text, fill=(0, 0, 0), font=title_font)
    # Weißer Text
    draw.text((text_x, text_y), title_text, fill=(255, 255, 255), font=title_font)

    # Start-Y nach Header
    y_offset = PADDING + HEADER_HEIGHT

    # Reihenfolge für die Gruppen
    group_order = [
        ("e046854e-406c-37f4-6607-19a9ba8426fc", "Ultra", (255, 215, 0)),  
        ("411e4a55-4e59-7757-41f0-86a53f101bb5", "Exclusive", (255, 152, 51)),
        ("60bca009-4182-7998-dee7-b8a2558dc369", "Premium", (207, 85, 168)),
        ("turquoise", "Battle Pass / Standard", (64, 224, 208))
    ]

    # Zeichne jede Gruppe und ihre Karten
    for group_key, group_name, group_color in group_order:
        if group_key not in grouped_skins:
            continue

        skins = grouped_skins[group_key]

        for idx, skin in enumerate(skins):
            row = idx // SKINS_PER_ROW
            col = idx % SKINS_PER_ROW

            x = PADDING + col * (CARD_WIDTH + PADDING)
            y = y_offset + row * (CARD_HEIGHT + PADDING)

            card_color = tuple(min(255, int(c * 0.2)) for c in group_color)
            draw.rectangle([x, y, x + CARD_WIDTH, y + CARD_HEIGHT],
                           fill=card_color, outline=group_color, width=3)

            # Bild einfügen
            if skin['image']:
                img = skin['image'].copy()
                img.thumbnail((CARD_WIDTH - 15, 125), Image.Resampling.LANCZOS)
                img_x = x + (CARD_WIDTH - img.width) // 2
                img_y = y + 10
                canvas.paste(img, (img_x, img_y), img if img.mode == 'RGBA' else None)

            # Skin-Name
            name = skin['name']
            if len(name) > 24:
                name = name[:21] + "..."

            text_y = y + CARD_HEIGHT - 45
            draw.rectangle([x + 3, text_y, x + CARD_WIDTH - 3, y + CARD_HEIGHT - 3],
                           fill=(10, 12, 18))

            bbox = draw.textbbox((0, 0), name, font=name_font)
            text_width = bbox[2] - bbox[0]
            text_x = x + (CARD_WIDTH - text_width) // 2

            draw.text((text_x + 1, text_y + 11), name, fill=(0, 0, 0), font=name_font)
            draw.text((text_x, text_y + 10), name, fill=(255, 255, 255), font=name_font)

        rows = (len(skins) + SKINS_PER_ROW - 1) // SKINS_PER_ROW
        y_offset += rows * (CARD_HEIGHT + PADDING) + PADDING

    return canvas


def main():
    lockfile = get_lockfile_data()
    if not lockfile:
        log("Make sure Valorant is running!", "ERROR")
        return

    port = lockfile['port']
    session = create_local_session(lockfile)
    
    tokens_data = get_entitlements_and_token(session, port)
    if not tokens_data:
        log("Failed to retrieve tokens", "ERROR")
        return
    
    player_uuid = get_player_uuid(session, port)
    if not player_uuid:
        log("Failed to retrieve player UUID", "ERROR")
        return

    region, shard = 'eu', 'eu'
    client_version = "release-11.11-shipping-123-4567890"

    tokens = {
        'entitlements_token': tokens_data['entitlements_token'],
        'access_token': tokens_data['access_token'],
        'client_version': client_version
    }

    log(f"Fetching owned skins for player {player_uuid[:8]}...", "INFO")
    skins = get_owned_skins(region, shard, tokens, player_uuid)
    log(f"Found {len(skins)} skin entries", "SUCCESS")

    skin_mapping = get_skin_mapping()
    
    # Bereite Skin-Daten vor - NUR UNIQUE SKINS (keine Duplikate)!
    skins_data = []
    seen_base_names = set()  # Track gesehene Base-Namen
    
    log("Downloading skin images", "INFO")
    for skin in skins:
        info = skin_mapping.get(skin['ItemID'])
        # Akzeptiere jetzt ALLE Skins, auch ohne Rarity
        if info:
            # Nutze den base_name um Duplikate zu erkennen
            base_name = info.get('base_name', info['name'])
            
            # Skip wenn wir diesen Skin schon haben
            if base_name in seen_base_names:
                log(f"✗ Skipped duplicate: {info['name']}", "WARNING")
                continue
                
            seen_base_names.add(base_name)
            
            img = None
            if info['icon']:
                img = download_image(info['icon'])
                if img:
                    time.sleep(0.05)  # Kurzes Rate limiting
            
            skins_data.append({
                'name': base_name,
                'image': img,
                'rarity': info.get('rarity')  # Kann None sein
            })
            log(f"✓ {base_name}", "INFO")
    
    log(f"Creating grid with {len(skins_data)} unique skins...", "SUCCESS")
    canvas = create_skin_grid(skins_data)
    
    # Speichere das Bild
    output_path = "valorant_skins_collection.png"
    canvas.save(output_path, quality=95)
    log(f"Saved to {output_path}", "SUCCESS")
    
    # Zeige das Bild an
    try:
        canvas.show()
    except:
        log("Image saved but couldn't open viewer", "WARNING")

if __name__ == "__main__":
    main()
