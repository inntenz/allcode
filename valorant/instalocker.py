# VALORANT - INSTALOCKER (modernized GUI)
# Requirements: python3, requests, tkinter
# Hinweis: Dieses Skript interagiert mit deinem lokalen Valorant-Client (Lockfile).
# Nutze es nur lokal und auf eigenes Risiko.

import requests
import time
import urllib3
import re
import os
from datetime import datetime
from base64 import b64encode
import threading
from queue import Queue, Empty
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, font

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

AGENTS = {
    "Breach": "f94b3e03-415b-7c70-2b4a-afb1f5bfb5c0",
    "Chamber": "963be1e6-485b-82f3-8f88-099a2a54b2b6",
    "Clove": "1dbf2edd-4729-0984-3115-daa5eed44993",
    "Cypher": "117ed9e3-49f3-6512-3ccf-0cada7e3823b",
    "Fade": "7f8d69ea-4ad0-50b0-0e55-13d0c063fff4",
    "Gekko": "0a6f94e7-4f17-2dd6-7e4d-569390a3f3d2",
    "Harbor": "2f25d0f0-41bd-cf31-cb4d-00a63db0a0d8",
    "Jett": "add6443a-41bd-e414-f6ad-e58d267f4e95",
    "KAY/O": "601dbbe7-43ce-be57-2a40-4abd24953621",
    "Killjoy": "f94c3b30-42be-e959-889c-5aa313dba261",
    "Neon": "bb2a4828-46eb-8cd2-05f9-04b8f1d8c7a5",
    "Phoenix": "eb93336a-449b-9c1b-0a54-a891f7921d69",
    "Reyna": "a3bfb853-43b2-7238-a4f1-ad90e9e46bcc",
    "Sage": "569fdd95-4d10-43ab-ca70-79becc718b46",
    "Skye": "f94c3b30-42be-e959-889c-5aa313dba261",
    "Sova": "f94c3b30-42be-e959-889c-5aa313dba261",
    "Viper": "707eab51-483e-f488-046a-cda6bf494859",
    "Vyse": "efba5359-4016-a1e5-7626-b1ae76895940",
    "Waylay": "df1cb487-4902-002e-5c17-d28e83e78588",
    "Yoru": "6f2a04ca-43e0-be17-7f36-b3908627744d"
}

CLIENT_PLATFORM = "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9"

CHECK_INTERVAL = 0.1
MAX_LOCK_ATTEMPTS = 5
LOCK_RETRY_DELAY = 0.05
LOG_QUEUE: "Queue[str]" = Queue()


def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    prefix = f"[{timestamp}] [{level}]"
    formatted = f"{prefix} {message}"
    try:
        LOG_QUEUE.put_nowait((formatted, level))
    except Exception:
        pass
    # keep a plain console print for debugging
    print(formatted)


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
        response = session.get(url, timeout=2)
        if response.status_code == 200:
            data = response.json()
            return {'entitlements_token': data['token'], 'access_token': data['accessToken']}
    except Exception as e:
        log(f"Failed to fetch tokens: {e}", "ERROR")
    return None


def get_player_session(session, port):
    # try to get puuid and display name if possible
    try:
        url = f"https://127.0.0.1:{port}/chat/v1/session"
        response = session.get(url, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        log(f"Failed to fetch chat session: {e}", "DEBUG")
    return None


def get_region_and_shard(session, port):
    try:
        url = f"https://127.0.0.1:{port}/product-session/v1/external-sessions"
        response = session.get(url, timeout=2)
        if response.status_code == 200:
            data = response.json()
            for key, value in data.items():
                if 'affinities' in value and 'pbe' in value['affinities']:
                    return 'na', 'pbe'
                elif 'affinities' in value:
                    region = value['affinities'].get('live', 'eu')
                    shard_map = {'na': 'na', 'latam': 'na', 'br': 'na', 'eu': 'eu', 'ap': 'ap', 'kr': 'kr'}
                    shard = shard_map.get(region, 'eu')
                    return region, shard

        log_path = os.path.join(os.getenv('LOCALAPPDATA'), r"VALORANT\Saved\Logs\ShooterGame.log")
        if os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                match = re.search(r'https://glz-(.+?)-1\.(.+?)\.a\.pvp\.net', content)
                if match:
                    return match.group(1), match.group(2)

        log("Unable to detect region; defaulting to EU", "WARNING")
        return 'eu', 'eu'
    except Exception as e:
        log(f"Region detection error: {e}", "WARNING")
        return 'eu', 'eu'


def get_client_version(session, port):
    try:
        url = f"https://127.0.0.1:{port}/product-session/v1/external-sessions"
        response = session.get(url, timeout=2)
        if response.status_code == 200:
            data = response.json()
            for key, value in data.items():
                if 'version' in value:
                    version_data = value['version']
                    return f"release-{version_data['branch']}-shipping-{version_data['buildVersion']}-{version_data['version']}"
        return "release-09.11-shipping-30-2892379"
    except Exception:
        return "release-09.11-shipping-30-2892379"


def get_pregame_match_id(region, shard, tokens, player_uuid):
    try:
        url = f"https://glz-{region}-1.{shard}.a.pvp.net/pregame/v1/players/{player_uuid}"
        headers = {
            'X-Riot-ClientPlatform': CLIENT_PLATFORM,
            'X-Riot-ClientVersion': tokens['client_version'],
            'X-Riot-Entitlements-JWT': tokens['entitlements_token'],
            'Authorization': f"Bearer {tokens['access_token']}"
        }
        response = requests.get(url, headers=headers, verify=False, timeout=2)
        if response.status_code == 200:
            data = response.json()
            return data.get('MatchID')
        elif response.status_code == 404:
            return None
        else:
            log(f"Pregame status: {response.status_code}", "DEBUG")
            return None
    except Exception as e:
        if "Connection" not in str(e) and "timeout" not in str(e).lower():
            log(f"Pregame check error: {e}", "DEBUG")
        return None


def select_agent(region, shard, tokens, match_id, agent_uuid):
    try:
        url = f"https://glz-{region}-1.{shard}.a.pvp.net/pregame/v1/matches/{match_id}/select/{agent_uuid}"
        headers = {
            'X-Riot-ClientPlatform': CLIENT_PLATFORM,
            'X-Riot-ClientVersion': tokens['client_version'],
            'X-Riot-Entitlements-JWT': tokens['entitlements_token'],
            'Authorization': f"Bearer {tokens['access_token']}"
        }
        response = requests.post(url, headers=headers, verify=False, timeout=2)
        log(f"Select status: {response.status_code}", "DEBUG")
        return response.status_code == 200
    except Exception as e:
        log(f"Select error: {e}", "ERROR")
        return False


def lock_agent(region, shard, tokens, match_id, agent_uuid):
    time.sleep(2)
    try:
        url = f"https://glz-{region}-1.{shard}.a.pvp.net/pregame/v1/matches/{match_id}/lock/{agent_uuid}"
        headers = {
            'X-Riot-ClientPlatform': CLIENT_PLATFORM,
            'X-Riot-ClientVersion': tokens['client_version'],
            'X-Riot-Entitlements-JWT': tokens['entitlements_token'],
            'Authorization': f"Bearer {tokens['access_token']}"
        }
        response = requests.post(url, headers=headers, verify=False, timeout=2)
        log(f"Lock status: {response.status_code}", "DEBUG")
        return response.status_code == 200
    except Exception as e:
        log(f"Lock error: {e}", "ERROR")
        return False


def attempt_instalock(region, shard, tokens, match_id, agent_uuid):
    log(f"Starting instalock sequence for agent {agent_uuid}...", "INFO")
    for attempt in range(1, MAX_LOCK_ATTEMPTS + 1):
        log(f"Attempt {attempt}/{MAX_LOCK_ATTEMPTS}...", "INFO")
        if select_agent(region, shard, tokens, match_id, agent_uuid):
            log("Agent selected", "SUCCESS")
            time.sleep(LOCK_RETRY_DELAY)
            if lock_agent(region, shard, tokens, match_id, agent_uuid):
                log("────────────────────────────────────────────────────────", "SUCCESS")
                log("AGENT LOCKED ✓", "SUCCESS")
                log("────────────────────────────────────────────────────────", "SUCCESS")
                return True
            else:
                log(f"Lock failed (attempt {attempt})", "WARNING")
        else:
            log(f"Select failed (attempt {attempt})", "WARNING")
        time.sleep(LOCK_RETRY_DELAY)
    log("Failed to lock agent", "ERROR")
    return False


class InstalockGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("VALORANT - INSTALOCKER")
        self.root.geometry("900x600")
        self.root.minsize(760, 520)
        self.root.configure(bg="#0b1020")

        # fonts
        self.title_font = font.Font(family="Segoe UI", size=16, weight="bold")
        self.small_font = font.Font(family="Segoe UI", size=10)
        self.mono_font = font.Font(family="Consolas", size=10)

        # top bar (colored)
        self.top_bar = tk.Frame(self.root, bg="#0f1724", height=50)
        self.top_bar.pack(side="top", fill="x")

        # left title
        self.title_label = tk.Label(self.top_bar, text="VALORANT - INSTALOCKER", bg="#0f1724",
                                    fg="#ffffff", font=self.title_font, anchor="w")
        self.title_label.place(relx=0.02, rely=0.18)

        # connected username (small, right)
        self.connected_var = tk.StringVar(value="Not connected")
        self.connected_label = tk.Label(self.top_bar, textvariable=self.connected_var, bg="#0f1724",
                                        fg="#d1f7e6", font=self.small_font, anchor="e")
        self.connected_label.place(relx=0.70, rely=0.35)

        # small status dot
        self.status_dot = tk.Canvas(self.top_bar, width=14, height=14, bg="#0f1724", highlightthickness=0)
        self.status_dot.place(relx=0.88, rely=0.42)
        self._set_status_dot("#ff6b6b")  # red at start

        # main area
        self.main_frame = tk.Frame(self.root, bg="#081018")
        self.main_frame.pack(fill="both", expand=True, padx=14, pady=(12,14))

        # left controls card
        self.controls_frame = tk.Frame(self.main_frame, bg="#0b1225", bd=0)
        self.controls_frame.place(relx=0.015, rely=0.02, relwidth=0.97, relheight=0.15)

        # agent selection
        
        self.agent_var = tk.StringVar(value="Reyna")
        agent_names = list(AGENTS.keys())
        self.agent_combo = ttk.Combobox(self.controls_frame, values=agent_names, textvariable=self.agent_var, state='readonly', width=26)
        self.agent_combo.place(x=14, y=20)

        # buttons (colorful)
        self.start_btn = tk.Button(self.controls_frame, text="Start", command=self.start,
                                   bg="#6a8cff", fg="#ffffff", activebackground="#8eaaff", bd=0, padx=12, pady=8)
        self.start_btn.place(x=200, y=20)
        self.stop_btn = tk.Button(self.controls_frame, text="Stop", command=self.stop,
                                  bg="#ff6b6b", fg="#ffffff", activebackground="#ff8a8a", bd=0, padx=12, pady=8)
        self.stop_btn.place(x=260, y=20)

        # status label
        self.status_var = tk.StringVar(value="Status: Idle")
        self.status_label = tk.Label(self.controls_frame, textvariable=self.status_var, bg="#0b1220", fg="#cbd6d8", font=self.small_font)
        self.status_label.place(x=320, y=20)

        # right log area
        self.log_frame = tk.Frame(self.main_frame, bg="#071018")
        self.log_frame.place(relx=0.01, rely=0.18, relwidth=0.98, relheight=0.58)

        # scrolled text for logs with colored tags
        self.log_box = scrolledtext.ScrolledText(self.log_frame, wrap='word', state='disabled',
                                                 height=18, bg='#051018', fg='#e6f2f1', insertbackground='white',
                                                 font=self.mono_font)
        self.log_box.pack(fill='both', expand=True, padx=6, pady=6)

        # configure tags for colors
        self.log_box.tag_config('INFO', foreground='#9cc4ff')
        self.log_box.tag_config('SUCCESS', foreground='#6af2c3')
        self.log_box.tag_config('WARNING', foreground='#ffd27a')
        self.log_box.tag_config('ERROR', foreground='#ff8a8a')
        self.log_box.tag_config('GAME', foreground='#d8a6ff')
        self.log_box.tag_config('DEBUG', foreground='#9ae6ff')

        # internal worker control
        self.worker_thread = None
        self.stop_event = threading.Event()
        self.tokens = None
        self.session = None
        self.port = None
        self.player_uuid = None
        self.player_name = None
        self.region = None
        self.shard = None
        self.client_version = None
        self.last_match_id = None

        # start polling logs
        self.root.after(120, self.poll_logs)

        # try to auto-connect right away (in background)
        threading.Thread(target=self._auto_connect_on_start, daemon=True).start()

    def _set_status_dot(self, hexcolor):
        self.status_dot.delete("all")
        self.status_dot.create_oval(1, 1, 13, 13, fill=hexcolor, outline=hexcolor)

    def poll_logs(self):
        try:
            while True:
                line, level = LOG_QUEUE.get_nowait()
                self.append_log(line, level)
        except Empty:
            pass
        self.root.after(120, self.poll_logs)

    def append_log(self, text_line, level="INFO"):
        def _insert():
            self.log_box.configure(state='normal')
            try:
                self.log_box.insert('end', text_line + '\n', level)
            except Exception:
                self.log_box.insert('end', text_line + '\n')
            self.log_box.see('end')
            self.log_box.configure(state='disabled')
        self.root.after(0, _insert)

    def set_status(self, text):
        self.status_var.set(f"Status: {text}")

    def _auto_connect_on_start(self):
        # called once at startup to attempt connection & fill username display
        self.set_status("Connecting...")
        self._set_status_dot("#ffb86b")  # orange while connecting
        ok = self.initialize_connection()
        if ok:
            self.set_status("Connected (idle)")
            self._set_status_dot("#5af27f")
            if self.player_name:
                self.connected_var.set(f"Connected: {self.player_name}")
            else:
                # fallback short puuid
                short = (self.player_uuid[:8] + "...") if self.player_uuid else "Unknown"
                self.connected_var.set(f"Connected: {short}")
            log("Auto-connect successful.", "SUCCESS")
        else:
            self.set_status("Not connected")
            self._set_status_dot("#ff6b6b")
            self.connected_var.set("Not connected")
            log("Auto-connect failed. Make sure Valorant is running.", "WARNING")

    def initialize_connection(self):
        lockfile = get_lockfile_data()
        if not lockfile:
            log("Make sure Valorant is running (lockfile missing).", "ERROR")
            return False
        self.port = lockfile['port']
        self.session = create_local_session(lockfile)
        log(f"Connected to Valorant Client (Port {self.port})", "SUCCESS")

        tokens_data = get_entitlements_and_token(self.session, self.port)
        if not tokens_data:
            log("Failed to retrieve tokens", "ERROR")
            return False
        log("Tokens retrieved", "SUCCESS")

        # try to get session info (puuid + maybe display name)
        session_info = get_player_session(self.session, self.port)
        if session_info:
            self.player_uuid = session_info.get('puuid') or session_info.get('id') or session_info.get('subject')
            # try possible name fields
            self.player_name = session_info.get('displayName') or session_info.get('name') or session_info.get('username')
            if self.player_name:
                log(f"Player name: {self.player_name}", "SUCCESS")
            if self.player_uuid:
                log(f"Player UUID: {self.player_uuid[:8]}...", "SUCCESS")
        else:
            # fallback to other method
            self.player_uuid = None

        self.region, self.shard = get_region_and_shard(self.session, self.port)
        log(f"Region: {self.region.upper()}, Shard: {self.shard.upper()}", "SUCCESS")

        self.client_version = get_client_version(self.session, self.port)
        log(f"Client Version: {self.client_version}", "SUCCESS")

        self.tokens = {'entitlements_token': tokens_data['entitlements_token'],
                       'access_token': tokens_data['access_token'],
                       'client_version': self.client_version}
        # If we still don't have puuid, try to derive from tokens (best-effort)
        if not self.player_uuid:
            # try retrieving puuid from /riot-account or other endpoints — best-effort omitted here
            log("Player UUID not detected during init", "WARNING")
        return True

    def start(self):
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("Info", "Worker already running.")
            return
        # try to initialize if not already
        if not self.tokens or not self.session:
            ok = self.initialize_connection()
            if not ok:
                messagebox.showerror("Error", "Initialisierung fehlgeschlagen. Stelle sicher, dass Valorant läuft.")
                self.set_status("Init failed")
                return
            else:
                # update connected label if new info
                if self.player_name:
                    self.connected_var.set(f"Connected: {self.player_name}")
                elif self.player_uuid:
                    self.connected_var.set(f"Connected: {self.player_uuid[:8]}...")

        self.stop_event.clear()
        self.worker_thread = threading.Thread(target=self.background_loop, daemon=True)
        self.worker_thread.start()
        self.set_status("Running")
        self._set_status_dot("#6af2c3")
        log("Background worker started", "INFO")

    def stop(self):
        self.stop_event.set()
        self.set_status("Stopping...")
        self._set_status_dot("#ffb86b")
        log("Stop signal sent", "INFO")
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)
        self.set_status("Stopped")
        self._set_status_dot("#ff6b6b")
        log("Worker stopped", "WARNING")

    def background_loop(self):
        try:
            # ensure connection initialized
            if not self.tokens:
                ok = self.initialize_connection()
                if not ok:
                    self.set_status("Init failed")
                    return
            self.set_status("Waiting for selection")
            self.last_match_id = None
            check_count = 0
            log(f"Waiting for agent selection... (checking every {CHECK_INTERVAL}s)", "INFO")
            while not self.stop_event.is_set():
                check_count += 1
                if check_count % 50 == 0:
                    log(f"Still searching... ({check_count * CHECK_INTERVAL:.1f}s)", "INFO")

                if not self.player_uuid:
                    # try to refresh session info occasionally
                    sess = get_player_session(self.session, self.port)
                    if sess:
                        self.player_uuid = sess.get('puuid') or sess.get('id') or self.player_uuid

                match_id = get_pregame_match_id(self.region, self.shard, self.tokens, self.player_uuid)

                if match_id and match_id != self.last_match_id:
                    log("────────────────────────────────────────────────────────", "GAME")
                    log("AGENT SELECTION DETECTED", "GAME")
                    log(f"Match ID: {match_id[:16]}...", "GAME")
                    log("────────────────────────────────────────────────────────", "GAME")
                    selected = self.agent_var.get()
                    agent_uuid = AGENTS.get(selected)
                    if agent_uuid:
                        success = attempt_instalock(self.region, self.shard, self.tokens, match_id, agent_uuid)
                        self.last_match_id = match_id
                        if success:
                            log("Waiting 10 seconds...", "INFO")
                            time.sleep(10)
                        else:
                            log("Waiting 5 seconds...", "INFO")
                            time.sleep(5)
                    else:
                        log("No valid agent selected", "ERROR")
                time.sleep(CHECK_INTERVAL)
        except Exception as e:
            log(f"Background error: {e}", "ERROR")
            import traceback
            traceback.print_exc()
        finally:
            self.set_status("Idle")
            self._set_status_dot("#ff6b6b")
            log("Background loop ended", "INFO")

    def instalock_once(self):
        def _task():
            try:
                if not self.tokens:
                    ok = self.initialize_connection()
                    if not ok:
                        log("Init failed — cannot instalock once.", "ERROR")
                        return
                match_id = get_pregame_match_id(self.region, self.shard, self.tokens, self.player_uuid)
                if not match_id:
                    log("No active pregame match found.", "WARNING")
                    return
                selected = self.agent_var.get()
                agent_uuid = AGENTS.get(selected)
                if not agent_uuid:
                    log("No valid agent selected", "ERROR")
                    return
                attempt_instalock(self.region, self.shard, self.tokens, match_id, agent_uuid)
            except Exception as e:
                log(f"Instalock once error: {e}", "ERROR")
        threading.Thread(target=_task, daemon=True).start()


def main():
    root = tk.Tk()
    app = InstalockGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
