import requests
import time
import urllib3
import re
import math
import json
import os
import base64
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CLIENT_PLATFORM = "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9"

CURRENCY_IDS = {
    "85ad13f7-3d1b-5128-9eb2-7cd8ee0b5741": "VP",
    "e59aa87c-4cbf-517a-5983-6e81511be9b7": "Radianite",
    "85ca954a-41f2-ce94-9b45-8ca3dd39a00d": "Kingdom Credits"
}

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
    "e046854e-406c-37f4-6607-19a9ba8426fc": {"name": "Ultra", "color": (255, 215, 0), "order": 1},
    "411e4a55-4e59-7757-41f0-86a53f101bb5": {"name": "Exclusive", "color": (255, 152, 51), "order": 2},
    "60bca009-4182-7998-dee7-b8a2558dc369": {"name": "Premium", "color": (207, 85, 168), "order": 3},
    "0cebb8be-46d7-c12a-d306-e9907bfc5a25": {"name": "Deluxe", "color": (64, 224, 208), "order": 4},
    "12683d76-48d7-84a3-4e09-6985794f0445": {"name": "Deluxe", "color": (64, 224, 208), "order": 4},
    None: {"name": "Deluxe", "color": (64, 224, 208), "order": 4}
}

def log(message, type="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    colors = {"INFO": "\033[94m", "SUCCESS": "\033[92m", "WARNING": "\033[93m", "ERROR": "\033[91m", "DEBUG": "\033[95m"}
    reset = "\033[0m"
    print(f"[{timestamp}] {colors.get(type, '')}{message}{reset}")

def get_lockfile_path():
    """Find Riot Client lockfile"""
    localappdata = os.getenv('LOCALAPPDATA')
    lockfile_path = os.path.join(localappdata, 'Riot Games', 'Riot Client', 'Config', 'lockfile')
    return lockfile_path

def read_lockfile():
    """Read lockfile and extract connection info"""
    lockfile_path = get_lockfile_path()
    
    if not os.path.exists(lockfile_path):
        return None
    
    try:
        with open(lockfile_path, 'r') as f:
            data = f.read().split(':')
            return {
                'process': data[0],
                'pid': data[1],
                'port': data[2],
                'password': data[3],
                'protocol': data[4]
            }
    except Exception as e:
        log(f"Error reading lockfile: {e}", "ERROR")
        return None

def get_tokens_from_riot_client():
    """Get authentication tokens from running Riot Client"""

    
    lockfile = read_lockfile()
    if not lockfile:
        log("❌ Riot Client not running or lockfile not found!", "ERROR")
        log("💡 Please start Riot Client (Valorant doesn't need to be running)", "WARNING")
        return None
    
    
    try:
        # Create session with basic auth
        session = requests.Session()
        session.verify = False
        
        # Basic auth with riot:password
        auth_string = f"riot:{lockfile['password']}"
        auth_token = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {auth_token}',
            'Content-Type': 'application/json'
        }
        
        # Get entitlements token from local client
        url = f"https://127.0.0.1:{lockfile['port']}/entitlements/v1/token"
        response = session.get(url, headers=headers)
        
        if response.status_code != 200:
            log(f"Failed to get tokens: {response.status_code}", "ERROR")
            return None
        
        data = response.json()
        
        # Get user info
        userinfo_url = f"https://127.0.0.1:{lockfile['port']}/chat/v1/session"
        userinfo_response = session.get(userinfo_url, headers=headers)
        
        puuid = data.get('subject', '')
        game_name = "Unknown"
        game_tag = "Unknown"
        
        if userinfo_response.status_code == 200:
            userinfo = userinfo_response.json()
            if 'game_name' in userinfo:
                game_name = userinfo['game_name']
            if 'game_tag' in userinfo:
                game_tag = userinfo['game_tag']
        
        return {
            'access_token': data['accessToken'],
            'entitlements_token': data['token'],
            'puuid': puuid,
            'game_name': game_name,
            'tag_line': game_tag
        }
        
    except Exception as e:
        log(f"Error getting tokens: {e}", "ERROR")
        import traceback
        log(traceback.format_exc(), "DEBUG")
        return None

def get_client_version():
    try:
        response = requests.get("https://valorant-api.com/v1/version")
        data = response.json()
        if data['status'] == 200:
            return data['data']['riotClientVersion']
    except:
        pass
    return "release-09.11-shipping-26-3161450"

def get_region_from_token(access_token):
    try:
        parts = access_token.split('.')
        if len(parts) >= 2:
            payload = parts[1]
            payload += '=' * (4 - len(payload) % 4)
            decoded = base64.b64decode(payload)
            token_data = json.loads(decoded)
            
            if 'pp' in token_data and 'region' in token_data['pp']:
                return token_data['pp']['region'].lower()
    except:
        pass
    return 'eu'

def get_wallet(region, tokens, puuid, client_version):
    url = f"https://pd.{region}.a.pvp.net/store/v1/wallet/{puuid}"
    headers = {
        'X-Riot-ClientPlatform': CLIENT_PLATFORM,
        'X-Riot-ClientVersion': client_version,
        'X-Riot-Entitlements-JWT': tokens['entitlements_token'],
        'Authorization': f"Bearer {tokens['access_token']}"
    }
    try:
        response = requests.get(url, headers=headers, verify=False)
        data = response.json()
        wallet = {
            "VP": 0,
            "Radianite": 0,
            "Kingdom Credits": 0
        }
        for currency_id, amount in data.get("Balances", {}).items():
            currency_name = CURRENCY_IDS.get(currency_id)
            if currency_name in wallet:
                wallet[currency_name] = amount
        return wallet
    except Exception as e:
        log(f"Failed to retrieve wallet: {e}", "ERROR")
        return {"VP": 0, "Radianite": 0, "Kingdom Credits": 0}

def get_player_mmr(region, tokens, puuid, client_version):
    url = f"https://pd.{region}.a.pvp.net/mmr/v1/players/{puuid}/competitiveupdates?startIndex=0&endIndex=1"
    headers = {
        'X-Riot-ClientPlatform': CLIENT_PLATFORM,
        'X-Riot-ClientVersion': client_version,
        'X-Riot-Entitlements-JWT': tokens['entitlements_token'],
        'Authorization': f"Bearer {tokens['access_token']}"
    }
    try:
        response = requests.get(url, headers=headers, verify=False)
        if response.status_code == 200:
            data = response.json()
            if data.get("Matches") and len(data["Matches"]) > 0:
                latest = data["Matches"][0]
                return {
                    "current_rank": RANK_NAMES.get(latest.get("TierAfterUpdate", 0), "Unknown"),
                    "current_rr": latest.get("RankedRatingAfterUpdate", 0)
                }
        return {"current_rank": "Unranked", "current_rr": 0}
    except:
        return {"current_rank": "Unknown", "current_rr": 0}

def get_owned_skins(region, tokens, puuid, client_version):
    url = f"https://pd.{region}.a.pvp.net/store/v1/entitlements/{puuid}"
    headers = {
        'X-Riot-ClientPlatform': CLIENT_PLATFORM,
        'X-Riot-ClientVersion': client_version,
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
            mapping[skin['uuid']] = {'name': base_name, 'icon': skin['displayIcon'], 'rarity': content_tier, 'base_name': base_name}
            for chroma in skin.get('chromas', []):
                mapping[chroma['uuid']] = {'name': chroma['displayName'], 'icon': chroma.get('displayIcon') or skin['displayIcon'], 'rarity': content_tier, 'base_name': base_name}
            for level in skin.get('levels', []):
                mapping[level['uuid']] = {'name': level['displayName'], 'icon': level.get('displayIcon') or skin['displayIcon'], 'rarity': content_tier, 'base_name': base_name}
        return mapping
    except Exception as e:
        log(f"Failed to fetch skins: {e}", "ERROR")
        return {}

def extract_base_skin_name(name):
    clean = re.sub(r'\s+Level\s+\d+', '', name, flags=re.IGNORECASE)
    clean = re.sub(r'\s+Variant\s+\d+.*', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\s+\(.*?\)', '', clean)
    return clean.strip()

def download_image(url):
    try:
        response = requests.get(url, timeout=10)
        return Image.open(BytesIO(response.content)).convert("RGBA")
    except:
        return None

def download_skin_image(skin_info):
    """Download a single skin image - for multithreading"""
    base = skin_info.get('base_name', skin_info['name'])
    icon_url = skin_info['icon']
    rarity = skin_info.get('rarity')
    
    if not icon_url:
        return None
    
    img = download_image(icon_url)
    if img:
        return {'name': base, 'image': img, 'rarity': rarity}
    return None

def wrap_text(draw, text, font, max_width, max_lines=2):
    words = text.split()
    lines, current = [], ""
    for w in words:
        candidate = (current + " " + w).strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = w
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines[:max_lines]

def create_skin_grid(skins_data, wallet, rank_info, player_region, game_name, game_tag):
    SKINS_PER_ROW, CARD_WIDTH, CARD_HEIGHT, PADDING = 8, 400, 280, 10
    HEADER_HEIGHT, FOOTER_HEIGHT, IMAGE_TOP_MARGIN, TEXT_AREA_HEIGHT = 150, 80, 15, 100

    sorted_skins = sorted(skins_data, key=lambda x: RARITY_INFO.get(x['rarity'], RARITY_INFO[None])['order'])
    grouped = {}
    for skin in sorted_skins:
        rinfo = RARITY_INFO.get(skin['rarity'], RARITY_INFO[None])
        key = skin['rarity'] if rinfo['name'] != "Deluxe" else "turquoise"
        grouped.setdefault(key, []).append(skin)

    ordered = []
    for key, _ in [("e046854e-406c-37f4-6607-19a9ba8426fc", None), ("411e4a55-4e59-7757-41f0-86a53f101bb5", None), ("60bca009-4182-7998-dee7-b8a2558dc369", None), ("turquoise", None)]:
        ordered.extend(grouped.get(key, []))

    rows = math.ceil(len(ordered) / SKINS_PER_ROW) if ordered else 0
    canvas_width = SKINS_PER_ROW * (CARD_WIDTH + PADDING) + PADDING
    canvas_height = PADDING + HEADER_HEIGHT + rows * (CARD_HEIGHT + PADDING) + PADDING + FOOTER_HEIGHT
    canvas = Image.new('RGB', (canvas_width, canvas_height), (30, 30, 30))
    draw = ImageDraw.Draw(canvas)

    try:
        try: title_font = ImageFont.truetype("segoeui.ttf", 54)
        except: title_font = ImageFont.truetype("arial.ttf", 54)
        wallet_font = ImageFont.truetype("arial.ttf", 32)
        name_font = ImageFont.truetype("arial.ttf", 30)
        footer_font = ImageFont.truetype("arial.ttf", 30)
    except:
        title_font = wallet_font = name_font = footer_font = ImageFont.load_default()

    # Header
    title = f"Weapon skins: {len(skins_data)} | [{player_region.upper()}] | [{rank_info['current_rank']}]"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    draw.text((PADDING + 2, PADDING + (HEADER_HEIGHT - (bbox[3] - bbox[1])) // 3 + 2), title, fill=(0, 0, 0), font=title_font)
    draw.text((PADDING, PADDING + (HEADER_HEIGHT - (bbox[3] - bbox[1])) // 3), title, fill=(255, 255, 255), font=title_font)

    # Wallet - nur VP, Radianite und KC
    wallet_lines = [
        f"VP: {wallet['VP']}",
        f"Radianite: {wallet['Radianite']}",
        f"KC: {wallet['Kingdom Credits']}"
    ]
    
    wx, wy = canvas_width - PADDING, PADDING + 20
    for line in wallet_lines:
        bbox = draw.textbbox((0, 0), line, font=wallet_font)
        lx = wx - (bbox[2] - bbox[0])
        draw.text((lx + 2, wy + 2), line, fill=(0, 0, 0), font=wallet_font)
        draw.text((lx, wy), line, fill=(255, 215, 0), font=wallet_font)
        wy += (bbox[3] - bbox[1]) + 8

    # Cards
    for idx, skin in enumerate(ordered):
        row, col = idx // SKINS_PER_ROW, idx % SKINS_PER_ROW
        x, y = PADDING + col * (CARD_WIDTH + PADDING), PADDING + HEADER_HEIGHT + row * (CARD_HEIGHT + PADDING)
        rinfo = RARITY_INFO.get(skin['rarity'], RARITY_INFO[None])
        color = rinfo['color']
        draw.rectangle([x, y, x + CARD_WIDTH, y + CARD_HEIGHT], fill=tuple(int(c * 0.2) for c in color), outline=color, width=4)

        if skin['image']:
            img = skin['image'].copy()
            img.thumbnail((CARD_WIDTH - 20, CARD_HEIGHT - TEXT_AREA_HEIGHT - 10 - IMAGE_TOP_MARGIN), Image.Resampling.LANCZOS)
            canvas.paste(img, (x + (CARD_WIDTH - img.width) // 2, y + IMAGE_TOP_MARGIN + ((CARD_HEIGHT - TEXT_AREA_HEIGHT - 10 - IMAGE_TOP_MARGIN) - img.height) // 2), img)

        lines = wrap_text(draw, extract_base_skin_name(skin['name']), name_font, CARD_WIDTH - 16)
        cy = y + CARD_HEIGHT - TEXT_AREA_HEIGHT + 8
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=name_font)
            tx = x + (CARD_WIDTH - (bbox[2] - bbox[0])) // 2
            draw.text((tx + 1, cy + 1), line, fill=(0, 0, 0), font=name_font)
            draw.text((tx, cy), line, fill=(255, 255, 255), font=name_font)
            cy += (bbox[3] - bbox[1]) + 6

    # Footer
    now = datetime.now()
    months = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
    ts = f"{now.day}.{months[now.month]}.{now.year} {now.strftime('%H:%M')}"
    bbox = draw.textbbox((0, 0), ts, font=footer_font)
    fx = (canvas_width - (bbox[2] - bbox[0])) // 2
    fy = canvas_height - FOOTER_HEIGHT + 20
    draw.text((fx + 2, fy + 2), ts, fill=(0, 0, 0), font=footer_font)
    draw.text((fx, fy), ts, fill=(150, 150, 150), font=footer_font)

    return canvas

def main():
    
    try:
        auth = get_tokens_from_riot_client()
        
        if not auth:
            log("❌ Could not get tokens from Riot Client!", "ERROR")
            log("💡 Make sure Riot Client is running and you're logged in", "WARNING")
            input("\nPress Enter to exit...")
            return
        
        log(f"Logged in as: {auth['game_name']}#{auth['tag_line']}", "SUCCESS")
        
        client_version = get_client_version()
        region = get_region_from_token(auth['access_token'])
        
        wallet = get_wallet(region, auth, auth['puuid'], client_version)
        rank_info = get_player_mmr(region, auth, auth['puuid'], client_version)
        
        skins = get_owned_skins(region, auth, auth['puuid'], client_version)
        
        skin_mapping = get_skin_mapping()
        
        # Prepare unique skins for download
        unique_skins = {}
        for skin in skins:
            info = skin_mapping.get(skin['ItemID'])
            if info:
                base = info.get('base_name', info['name'])
                if base not in unique_skins:
                    unique_skins[base] = info
        
        log(f"Downloading {len(unique_skins)} skin images", "INFO")
        
        skins_data = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(download_skin_image, info): name for name, info in unique_skins.items()}
            
            completed = 0
            for future in as_completed(futures):
                completed += 1
                result = future.result()
                if result:
                    skins_data.append(result)
                
                # Progress indicator
                
        
        log("Creating image...", "SUCCESS")
        canvas = create_skin_grid(skins_data, wallet, rank_info, region, auth['game_name'], auth['tag_line'])
        canvas.save("skins.png", quality=100, optimize=False)
        log("✅ Saved to skins.png", "SUCCESS")
        try: canvas.show()
        except: log("Image saved but couldn't open viewer", "WARNING")
            
    except Exception as e:
        log(f"Error: {e}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")

if __name__ == "__main__":
    main()
