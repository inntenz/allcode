import requests
import time
import urllib3
import re
import os
import math
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import textwrap

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CLIENT_PLATFORM = "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9"

RARITY_INFO = {
    "e046854e-406c-37f4-6607-19a9ba8426fc": {
        "name": "Ultra",
        "color": (255, 215, 0),
        "order": 1
    },
    "411e4a55-4e59-7757-41f0-86a53f101bb5": {
        "name": "Exclusive",
        "color": (255, 152, 51),
        "order": 2
    },
    "60bca009-4182-7998-dee7-b8a2558dc369": {
        "name": "Premium",
        "color": (207, 85, 168),
        "order": 3
    },
    "0cebb8be-46d7-c12a-d306-e9907bfc5a25": {
        "name": "Deluxe",
        "color": (64, 224, 208),
        "order": 4
    },
    "12683d76-48d7-84a3-4e09-6985794f0445": {
        "name": "Deluxe",
        "color": (64, 224, 208),
        "order": 4
    },
    None: {
        "name": "Deluxe",
        "color": (64, 224, 208),
        "order": 4
    }
}

def log(message, type="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    colors = {
        "INFO": "\033[94m",
        "SUCCESS": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m"
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

def get_player_data(session, port):
    try:
        url = f"https://127.0.0.1:{port}/chat/v1/session"
        response = session.get(url)
        if response.status_code == 200:
            data = response.json()
            puuid = data.get("puuid")
            game_name = data.get("game_name")
            game_tag = data.get("game_tag")
            if game_name and game_tag:
                print(f"{game_name}#{game_tag}")
            elif game_name:
                print(game_name)
            else:
                print("Unknown Player")
            return puuid
    except Exception as e:
        log(f"Failed to retrieve player data: {e}", "ERROR")
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
            mapping[skin['uuid']] = {
                'name': base_name,
                'icon': skin['displayIcon'],
                'rarity': content_tier,
                'base_name': base_name
            }
            for chroma in skin.get('chromas', []):
                mapping[chroma['uuid']] = {
                    'name': chroma['displayName'],
                    'icon': chroma.get('displayIcon') or skin['displayIcon'],
                    'rarity': content_tier,
                    'base_name': base_name
                }
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
    clean_name = re.sub(r'\s+Level\s+\d+', '', name, flags=re.IGNORECASE)
    clean_name = re.sub(r'\s+Variant\s+\d+.*', '', clean_name, flags=re.IGNORECASE)
    clean_name = re.sub(r'\s+\(.*?\)', '', clean_name)
    return clean_name.strip()

def download_image(url):
    try:
        response = requests.get(url, timeout=10)
        img = Image.open(BytesIO(response.content))
        return img.convert("RGBA")
    except Exception:
        return None

def wrap_text(draw, text, font, max_width, max_lines=2):
    words = text.split()
    lines = []
    current = ""
    for w in words:
        candidate = (current + " " + w).strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        wlen = bbox[2] - bbox[0]
        if wlen <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = w
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    return lines

def create_skin_grid(skins_data):
    SKINS_PER_ROW = 8
    CARD_WIDTH = 200
    CARD_HEIGHT = 200
    PADDING = 6
    HEADER_HEIGHT = 100
    IMAGE_TOP_MARGIN = 10
    TEXT_AREA_HEIGHT = 52

    total_skins = len(skins_data)
    sorted_skins = sorted(skins_data, key=lambda x: RARITY_INFO.get(x['rarity'], RARITY_INFO[None]).get('order', 999))
    grouped_skins = {}
    for skin in sorted_skins:
        rarity = skin['rarity']
        rarity_info = RARITY_INFO.get(rarity, RARITY_INFO[None])
        group_key = rarity if rarity_info['name'] != "Deluxe" else "turquoise"
        grouped_skins.setdefault(group_key, []).append(skin)

    group_order = [
        ("e046854e-406c-37f4-6607-19a9ba8426fc", (255, 215, 0)),
        ("411e4a55-4e59-7757-41f0-86a53f101bb5", (255, 152, 51)),
        ("60bca009-4182-7998-dee7-b8a2558dc369", (207, 85, 168)),
        ("turquoise", (64, 224, 208))
    ]

    ordered_skins = []
    for key, _ in group_order:
        if key in grouped_skins:
            ordered_skins.extend(grouped_skins[key])
    for key, skins in grouped_skins.items():
        if key not in [k for k, _ in group_order]:
            ordered_skins.extend(skins)

    rows_needed = math.ceil(len(ordered_skins) / SKINS_PER_ROW) if ordered_skins else 0
    total_height = PADDING + HEADER_HEIGHT + rows_needed * (CARD_HEIGHT + PADDING) + PADDING
    canvas_width = SKINS_PER_ROW * (CARD_WIDTH + PADDING) + PADDING
    canvas = Image.new('RGB', (canvas_width, total_height), color=(15, 18, 25))
    draw = ImageDraw.Draw(canvas)

    try:
        title_font = ImageFont.truetype("arial.ttf", 36)
    except:
        title_font = ImageFont.load_default()
    try:
        name_font = ImageFont.truetype("arial.ttf", 16)
    except:
        name_font = ImageFont.load_default()

    title_text = f"Skins: {total_skins}"
    bbox = draw.textbbox((0, 0), title_text, font=title_font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    text_x = PADDING
    text_y = PADDING + (HEADER_HEIGHT - text_height) // 3
    draw.text((text_x + 2, text_y + 2), title_text, fill=(0, 0, 0), font=title_font)
    draw.text((text_x, text_y), title_text, fill=(255, 255, 255), font=title_font)

    for idx, skin in enumerate(ordered_skins):
        row = idx // SKINS_PER_ROW
        col = idx % SKINS_PER_ROW
        x = PADDING + col * (CARD_WIDTH + PADDING)
        y = PADDING + HEADER_HEIGHT + row * (CARD_HEIGHT + PADDING)

        rarity = skin.get('rarity')
        rarity_info = RARITY_INFO.get(rarity, RARITY_INFO[None])
        group_color = rarity_info['color'] if rarity_info and 'color' in rarity_info else (64, 224, 208)
        card_color = tuple(min(255, int(c * 0.2)) for c in group_color)
        draw.rectangle([x, y, x + CARD_WIDTH, y + CARD_HEIGHT], fill=card_color, outline=group_color, width=3)

        image_area_top = y + IMAGE_TOP_MARGIN
        image_area_bottom = y + CARD_HEIGHT - TEXT_AREA_HEIGHT - 6
        available_h = max(1, image_area_bottom - image_area_top)
        available_w = CARD_WIDTH - 14

        if skin['image']:
            img = skin['image'].copy()
            img.thumbnail((available_w, available_h), Image.Resampling.LANCZOS)
            img_x = x + (CARD_WIDTH - img.width) // 2
            img_y = image_area_top + (available_h - img.height) // 2
            canvas.paste(img, (img_x, img_y), img if img.mode == 'RGBA' else None)

        name = extract_base_skin_name(skin['name'])
        max_text_width = CARD_WIDTH - 12
        lines = wrap_text(draw, name, name_font, max_text_width, max_lines=2)
        draw.rectangle([x + 3, y + CARD_HEIGHT - TEXT_AREA_HEIGHT + 2, x + CARD_WIDTH - 3, y + CARD_HEIGHT - 3], fill=(10, 12, 18))
        total_text_height = 0
        measured_heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=name_font)
            h = bbox[3] - bbox[1]
            measured_heights.append(h)
            total_text_height += h
        spacing = 4 if len(lines) > 1 else 0
        total_text_height += spacing * (len(lines) - 1)
        current_y = y + CARD_HEIGHT - TEXT_AREA_HEIGHT + 6 + ((TEXT_AREA_HEIGHT - 12) - total_text_height) // 2
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=name_font)
            w = bbox[2] - bbox[0]
            text_x = x + (CARD_WIDTH - w) // 2
            draw.text((text_x + 1, current_y + 1), line, fill=(0, 0, 0), font=name_font)
            draw.text((text_x, current_y), line, fill=(255, 255, 255), font=name_font)
            current_y += measured_heights[i] + spacing

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

    player_uuid = get_player_data(session, port)
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

    skins_data = []
    seen_base_names = set()

    log("Downloading skin images", "INFO")
    for skin in skins:
        info = skin_mapping.get(skin['ItemID'])
        if info:
            base_name = info.get('base_name', info['name'])
            if base_name in seen_base_names:
                log(f"Skipped: {info['name']}", "WARNING")
                continue
            seen_base_names.add(base_name)
            img = None
            if info['icon']:
                img = download_image(info['icon'])
                if img:
                    time.sleep(0.05)
            skins_data.append({
                'name': base_name,
                'image': img,
                'rarity': info.get('rarity')
            })
            log(f"✓ {base_name}", "INFO")

    log(f"Creating grid with {len(skins_data)} unique skins...", "SUCCESS")
    canvas = create_skin_grid(skins_data)
    output_path = "valorant_skins_collection.png"
    canvas.save(output_path, quality=95)
    log(f"Saved to {output_path}", "SUCCESS")
    try:
        canvas.show()
    except:
        log("Image saved but couldn't open viewer", "WARNING")

if __name__ == "__main__":
    main()
