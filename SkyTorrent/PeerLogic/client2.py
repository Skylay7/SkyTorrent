import os
from torrent_generator import generate_torrent
from torrent_parser import parse_torrent_file
from torrent_peer import TorrentPeer
from storage_manager import StorageManager
import random

TEST_FILE = "test_file.txt"
TORRENT_FILE = "test_file.torrent"
TRACKER_URL = "http://localhost:6969/announce"
PORT = 6882

if not os.path.exists(TORRENT_FILE):
    generate_torrent(TEST_FILE, TRACKER_URL, TORRENT_FILE)
    print(f"[✓] .torrent file generated at {TORRENT_FILE}")

if os.path.exists(TORRENT_FILE):
    parsed_torrent = parse_torrent_file(TORRENT_FILE)

torrent_info = parse_torrent_file(TORRENT_FILE)

peer_id = b'-PC0001-' + bytes(f'{random.randint(0, 999999):06}', encoding='utf-8')

storage = StorageManager(torrent_info['name'], torrent_info['length'],
                         torrent_info['piece_length'], torrent_info['pieces'])

try:
    peer = TorrentPeer(peer_id, torrent_info, storage, listen_port=PORT)
    peer.start()
except Exception as e:
    print(f"[!] Failed to start TorrentPeer: {e}")
