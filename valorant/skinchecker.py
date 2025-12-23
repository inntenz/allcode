import requests
import time
import urllib3
import re
import os
from datetime import datetime
import json

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Client Platform (Base64 encoded)
CLIENT_PLATFORM = "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9"

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    colors = {
        "INFO": "\033[94m",
        "SUCCESS": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
    }
    reset = "\033[0m"
    print(f"[{timestamp}] {colors.get(level, '')}{message}{reset}")

def get_lockfile_data():
    try:
        lockfile_path = os.path.join(
            os.getenv('LOCALAPPDATA'),
            r"Riot Games\Riot Client\Config\lockfile"
        )
        with open(lockfile_path, 'r') as f:
            data = f.read().split(':')
            return {'port': data[2], 'password': data[3]}
    except Exception as e:
        log(f"Error reading lockfile: {e}", "ERROR")
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
        log(f"Error fetching tokens: {e}", "ERROR")
    return None

def get_player_uuid(session, port):
    try:
        url = f"https://127.0.0.1:{port}/chat/v1/session"
        response = session.get(url)
        if response.status_code == 200:
            return response.json()['puuid']
    except Exception as e:
        log(f"Error fetching player UUID: {e}", "ERROR")
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
        log(f"Error fetching skins: {e}", "ERROR")
        return []

def get_skin_mapping():
    try:
        response = requests.get("https://valorant-api.com/v1/weapons/skins")
        data = response.json()
        mapping = {}
        for skin in data['data']:
            mapping[skin['uuid']] = skin['displayName']
            # optional: chromas
            for chroma in skin.get('chromas', []):
                mapping[chroma['uuid']] = chroma['displayName']
            # optional: levels
            for level in skin.get('levels', []):
                mapping[level['uuid']] = level['displayName']
        return mapping
    except Exception as e:
        log(f"Error fetching official skins: {e}", "ERROR")
        return {}

def main():
    lockfile = get_lockfile_data()
    if not lockfile:
        log("Make sure Valorant is running!", "ERROR")
        return

    port = lockfile['port']
    session = create_local_session(lockfile)
    
    tokens_data = get_entitlements_and_token(session, port)
    if not tokens_data:
        log("✗ Could not fetch tokens", "ERROR")
        return
    
    player_uuid = get_player_uuid(session, port)
    if not player_uuid:
        log("✗ Could not fetch player UUID", "ERROR")
        return

    # Dummy values for region/shard/client version
    region, shard = 'eu', 'eu'
    client_version = "release-11.11-shipping-123-4567890"

    tokens = {
        'entitlements_token': tokens_data['entitlements_token'],
        'access_token': tokens_data['access_token'],
        'client_version': client_version
    }

    log(f"Fetching owned skins for player {player_uuid[:8]}...", "INFO")
    skins = get_owned_skins(region, shard, tokens, player_uuid)
    log(f"✅ Found skins: {len(skins)}", "SUCCESS")

    # API mapping
    skin_mapping = get_skin_mapping()

    for skin in skins:
        name = skin_mapping.get(skin['ItemID'], f"❓ Unknown Skin ({skin['ItemID']})")
        print(f"- {name} ({skin['ItemID']})")

if __name__ == "__main__":
    main()
