import requests
import time
import urllib3
import re
import os
import math
import json
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import textwrap

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CLIENT_PLATFORM = "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9"

# Currency IDs
CURRENCY_IDS = {
    "85ad13f7-3d1b-5128-9eb2-7cd8ee0b5741": "VP",
    "e59aa87c-4cbf-517a-5983-6e81511be9b7": "Radianite",
    "85ca954a-41f2-ce94-9b45-8ca3dd39a00d": "Kingdom Credits"
}

# Rank Tiers
RANK_NAMES = {
    0: "Unranked",
    3: "Iron 1", 4: "Iron 2", 5: "Iron 3",
    6: "Bronze 1", 7: "Bronze 2", 8: "Bronze 3",
    9: "Silver 1", 10: "Silver 2", 11: "Silver 3",
    12: "Gold 1", 13: "Gold 2", 14: "Gold 3",
    15: "Platinum 1", 16: "Platinum 2", 17: "Platinum 3",
    18: "Diamond 1", 19: "Diamond 2", 20: "Diamond 3",
    21: "Ascendant 1", 22: "Ascendant 2", 23: "Ascendant 3",
    24: "Immortal 1", 25: "Immortal 2", 26: "Immortal 3",
    27: "Radiant"
}

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
        "ERROR": "\033[91m",
        "DEBUG": "\033[95m"
    }
    reset = "\033[0m"
    print(f"[{timestamp}] {colors.get(type, '')}{message}{reset}")

def get_lockfile_data():
    try:
        lockfile_path = os.path.join(os.getenv('LOCALAPPDATA'), r"Riot Games\Riot Client\Config\lockfile")
        log(f"Reading lockfile from: {lockfile_path}", "DEBUG")
        if not os.path.exists(lockfile_path):
            log(f"Lockfile does not exist at {lockfile_path}", "ERROR")
            return None
        with open(lockfile_path, 'r') as f:
            data = f.read().split(':')
            return {'port': data[2], 'password': data[3]}
    except Exception as e:
        log(f"Failed to read lockfile: {e}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
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
        else:
            log(f"Token response: {response.text}", "ERROR")
    except Exception as e:
        log(f"Failed to retrieve tokens: {e}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
    return None

def get_client_version(session, port):
    try:
        url = f"https://127.0.0.1:{port}/product-session/v1/external-sessions"
        response = session.get(url)
        if response.status_code == 200:
            data = response.json()
            for key, value in data.items():
                if 'valorant' in key.lower():
                    version = value.get('version', '')
                    if version:
                        return version
    except Exception as e:
        log(f"Failed to get client version: {e}", "WARNING")
    return "release-11.11-shipping-123-4567890"

def get_region_and_shard_from_log():
    try:
        log_path = os.path.join(os.getenv('LOCALAPPDATA'), r"VALORANT\Saved\Logs\ShooterGame.log")
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # Suche nach glz URL Pattern
            match = re.search(r'https://glz-(.+?)-1\.(.+?)\.a\.pvp\.net', content)
            if match:
                region = match.group(1)
                shard = match.group(2)
                return region, shard
    except Exception as e:
        log(f"Could not read ShooterGame.log: {e}", "WARNING")
    return None, None

def get_region_and_shard(session, port):
    # Versuche zuerst aus dem Log zu lesen
    region, shard = get_region_and_shard_from_log()
    if region and shard:
        return region, shard
    
    # Fallback: Versuche aus Session
    try:
        url = f"https://127.0.0.1:{port}/product-session/v1/external-sessions"
        response = session.get(url)
        if response.status_code == 200:
            data = response.json()
            for key, value in data.items():
                if 'valorant' in key.lower():
                    launch_config = value.get('launchConfiguration', {})
                    args = launch_config.get('arguments', [])
                    for arg in args:
                        if 'ares-cluster' in arg:
                            region = arg.split('=')[1] if '=' in arg else 'eu'
                            return region, region
    except Exception as e:
        log(f"Failed to get region/shard: {e}", "WARNING")
    return 'eu', 'eu'

def get_player_data(session, port):
    try:
        url = f"https://127.0.0.1:{port}/chat/v1/session"
        response = session.get(url)
        if response.status_code == 200:
            data = response.json()
            puuid = data.get("puuid")
            game_name = data.get("game_name")
            game_tag = data.get("game_tag")
            region = data.get("region", "Unknown")

            if game_name and game_tag:
                log(f"CHECKING USER: {game_name}#{game_tag} | Region: {region}", "INFO")
            elif game_name:
                print(f"{game_name} | Region: {region}")
            else:
                print(f"Unknown Player | Region: {region}")
            return puuid, region
    except Exception as e:
        log(f"Failed to retrieve player data: {e}", "ERROR")
    return None, "Unknown"

def get_wallet(region, shard, tokens, puuid):
    url = f"https://pd.{shard}.a.pvp.net/store/v1/wallet/{puuid}"
    headers = {
        'X-Riot-ClientPlatform': CLIENT_PLATFORM,
        'X-Riot-ClientVersion': tokens['client_version'],
        'X-Riot-Entitlements-JWT': tokens['entitlements_token'],
        'Authorization': f"Bearer {tokens['access_token']}"
    }
    try:
        response = requests.get(url, headers=headers, verify=False)
        data = response.json()
        balances = data.get("Balances", {})
        wallet = {}
        for currency_id, amount in balances.items():
            currency_name = CURRENCY_IDS.get(currency_id, "Unknown")
            wallet[currency_name] = amount
        return wallet
    except Exception as e:
        log(f"Failed to retrieve wallet: {e}", "ERROR")
        return {}

def get_player_mmr(region, shard, tokens, puuid):
    # Nutze competitive updates endpoint
    url = f"https://pd.{shard}.a.pvp.net/mmr/v1/players/{puuid}/competitiveupdates?startIndex=0&endIndex=1"
    headers = {
        'X-Riot-ClientPlatform': CLIENT_PLATFORM,
        'X-Riot-ClientVersion': tokens['client_version'],
        'X-Riot-Entitlements-JWT': tokens['entitlements_token'],
        'Authorization': f"Bearer {tokens['access_token']}"
    }
    try:
        response = requests.get(url, headers=headers, verify=False)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extrahiere aus competitive updates
            if data.get("Matches") and len(data["Matches"]) > 0:
                latest = data["Matches"][0]
                current_rank = latest.get("TierAfterUpdate", 0)
                current_rr = latest.get("RankedRatingAfterUpdate", 0)
                
                return {
                    "current_rank": RANK_NAMES.get(current_rank, f"Unknown ({current_rank})"),
                    "current_rr": current_rr
                }
        
        return {
            "current_rank": "Unranked",
            "current_rr": 0
        }
    except Exception as e:
        log(f"Failed to retrieve MMR: {e}", "ERROR")
        return {
            "current_rank": "Unknown",
            "current_rr": 0
        }

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

def create_skin_grid(skins_data, wallet, rank_info, player_region):
    # HOCHAUFLÖSENDE EINSTELLUNGEN
    SKINS_PER_ROW = 8
    CARD_WIDTH = 300
    CARD_HEIGHT = 300
    PADDING = 10
    HEADER_HEIGHT = 150
    IMAGE_TOP_MARGIN = 15
    TEXT_AREA_HEIGHT = 80

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
        title_font = ImageFont.truetype("arial.ttf", 54)
        center_font = ImageFont.truetype("arial.ttf", 36)
        wallet_font = ImageFont.truetype("arial.ttf", 32)
        name_font = ImageFont.truetype("arial.ttf", 24)
    except:
        title_font = ImageFont.load_default()
        center_font = ImageFont.load_default()
        wallet_font = ImageFont.load_default()
        name_font = ImageFont.load_default()

    # Linke Seite: "Skins: X"
    title_text = f"Skins: {total_skins}"
    bbox = draw.textbbox((0, 0), title_text, font=title_font)
    text_height = bbox[3] - bbox[1]
    text_x = PADDING
    text_y = PADDING + (HEADER_HEIGHT - text_height) // 3
    draw.text((text_x + 2, text_y + 2), title_text, fill=(0, 0, 0), font=title_font)
    draw.text((text_x, text_y), title_text, fill=(255, 255, 255), font=title_font)

    # Mitte: Region und Rank
    region_text = f"Region: {player_region.upper()}"
    rank_text = f"{rank_info['current_rank']} ({rank_info['current_rr']} RR)"
    
    # Region
    bbox = draw.textbbox((0, 0), region_text, font=center_font)
    region_width = bbox[2] - bbox[0]
    region_x = (canvas_width - region_width) // 2
    region_y = PADDING + 25
    draw.text((region_x + 2, region_y + 2), region_text, fill=(0, 0, 0), font=center_font)
    draw.text((region_x, region_y), region_text, fill=(100, 200, 255), font=center_font)
    
    # Rank
    bbox = draw.textbbox((0, 0), rank_text, font=center_font)
    rank_width = bbox[2] - bbox[0]
    rank_x = (canvas_width - rank_width) // 2
    rank_y = region_y + 50
    draw.text((rank_x + 2, rank_y + 2), rank_text, fill=(0, 0, 0), font=center_font)
    draw.text((rank_x, rank_y), rank_text, fill=(255, 215, 0), font=center_font)

    # Rechte Seite: Wallet Informationen
    wallet_text_lines = []
    if wallet.get("VP", 0) > 0 or "VP" in wallet:
        wallet_text_lines.append(f"VP: {wallet.get('VP', 0)}")
    if wallet.get("Radianite", 0) > 0 or "Radianite" in wallet:
        wallet_text_lines.append(f"Radianite: {wallet.get('Radianite', 0)}")
    if wallet.get("Kingdom Credits", 0) > 0 or "Kingdom Credits" in wallet:
        wallet_text_lines.append(f"KC: {wallet.get('Kingdom Credits', 0)}")
    
    wallet_x = canvas_width - PADDING - 10
    wallet_y = PADDING + 20
    for line in wallet_text_lines:
        bbox = draw.textbbox((0, 0), line, font=wallet_font)
        line_width = bbox[2] - bbox[0]
        line_x = wallet_x - line_width
        draw.text((line_x + 2, wallet_y + 2), line, fill=(0, 0, 0), font=wallet_font)
        draw.text((line_x, wallet_y), line, fill=(255, 215, 0), font=wallet_font)
        wallet_y += bbox[3] - bbox[1] + 8

    # Skin Cards
    for idx, skin in enumerate(ordered_skins):
        row = idx // SKINS_PER_ROW
        col = idx % SKINS_PER_ROW
        x = PADDING + col * (CARD_WIDTH + PADDING)
        y = PADDING + HEADER_HEIGHT + row * (CARD_HEIGHT + PADDING)

        rarity = skin.get('rarity')
        rarity_info = RARITY_INFO.get(rarity, RARITY_INFO[None])
        group_color = rarity_info['color'] if rarity_info and 'color' in rarity_info else (64, 224, 208)
        card_color = tuple(min(255, int(c * 0.2)) for c in group_color)
        draw.rectangle([x, y, x + CARD_WIDTH, y + CARD_HEIGHT], fill=card_color, outline=group_color, width=4)

        image_area_top = y + IMAGE_TOP_MARGIN
        image_area_bottom = y + CARD_HEIGHT - TEXT_AREA_HEIGHT - 10
        available_h = max(1, image_area_bottom - image_area_top)
        available_w = CARD_WIDTH - 20

        if skin['image']:
            img = skin['image'].copy()
            img.thumbnail((available_w, available_h), Image.Resampling.LANCZOS)
            img_x = x + (CARD_WIDTH - img.width) // 2
            img_y = image_area_top + (available_h - img.height) // 2
            canvas.paste(img, (img_x, img_y), img if img.mode == 'RGBA' else None)

        name = extract_base_skin_name(skin['name'])
        max_text_width = CARD_WIDTH - 16
        lines = wrap_text(draw, name, name_font, max_text_width, max_lines=2)
        draw.rectangle([x + 4, y + CARD_HEIGHT - TEXT_AREA_HEIGHT + 3, x + CARD_WIDTH - 4, y + CARD_HEIGHT - 4], fill=(10, 12, 18))
        total_text_height = 0
        measured_heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=name_font)
            h = bbox[3] - bbox[1]
            measured_heights.append(h)
            total_text_height += h
        spacing = 6 if len(lines) > 1 else 0
        total_text_height += spacing * (len(lines) - 1)
        current_y = y + CARD_HEIGHT - TEXT_AREA_HEIGHT + 8 + ((TEXT_AREA_HEIGHT - 16) - total_text_height) // 2
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=name_font)
            w = bbox[2] - bbox[0]
            text_x = x + (CARD_WIDTH - w) // 2
            draw.text((text_x + 1, current_y + 1), line, fill=(0, 0, 0), font=name_font)
            draw.text((text_x, current_y), line, fill=(255, 255, 255), font=name_font)
            current_y += measured_heights[i] + spacing

    return canvas

def main():
    log("Starting Valorant Skins Checker", "INFO")
    lockfile = get_lockfile_data()
    if not lockfile:
        log("Make sure Valorant AND Riot Client are running!", "ERROR")
        log("The Riot Client creates the lockfile, not just Valorant.", "WARNING")
        input("Press Enter to exit...")
        return

    port = lockfile['port']
    session = create_local_session(lockfile)
    tokens_data = get_entitlements_and_token(session, port)
    if not tokens_data:
        log("Failed to retrieve tokens - is Valorant fully loaded?", "ERROR")
        input("Press Enter to exit...")
        return

    player_uuid, player_region = get_player_data(session, port)
    if not player_uuid:
        log("Failed to retrieve player UUID", "ERROR")
        return


    region, shard = get_region_and_shard(session, port)
    client_version = get_client_version(session, port)

    tokens = {
        'entitlements_token': tokens_data['entitlements_token'],
        'access_token': tokens_data['access_token'],
        'client_version': client_version
    }

    # Hole Wallet Daten
    wallet = get_wallet(region, shard, tokens, player_uuid)
    rank_info = get_player_mmr(region, shard, tokens, player_uuid)


    skins = get_owned_skins(region, shard, tokens, player_uuid)
    log(f"{len(skins)} skins w/variants owned", "SUCCESS")

    skin_mapping = get_skin_mapping()

    skins_data = []
    seen_base_names = set()

    log("Downloading skins", "INFO")
    for skin in skins:
        info = skin_mapping.get(skin['ItemID'])
        if info:
            base_name = info.get('base_name', info['name'])
            if base_name in seen_base_names:
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

    log(f"Creating Image", "SUCCESS")
    canvas = create_skin_grid(skins_data, wallet, rank_info, player_region)
    output_path = "skins.png"
    canvas.save(output_path, quality=100, optimize=False)
    log(f"Saved to {output_path}", "SUCCESS")
    try:
        canvas.show()
    except:
        log("Image saved but couldn't open viewer", "WARNING")

if __name__ == "__main__":
    main()
