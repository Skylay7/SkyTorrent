# test_peer.py

import time
import random
import hashlib
from torrent_peer import TorrentPeer
from storage_manager import StorageManager


def generate_dummy_torrent_info():
    """Create dummy torrent info for testing without real torrent files."""
    dummy_data = b"Test Data for Torrent"
    piece_length = 262144  # 256 KB
    pieces = hashlib.sha1(dummy_data).digest()  # Fake single piece hash
    info_hash = hashlib.sha1(b"dummy_info").digest()

    return {
        'info_hash': info_hash,
        'announce': 'http://127.0.0.1:8000/announce',  # dummy tracker
        'name': 'dummy_file.txt',
        'piece_length': piece_length,
        'length': len(dummy_data),
        'pieces': pieces
    }


def main():
    listen_port = 6881  # You can change this if needed

    # Random 20-byte peer_id like BitTorrent clients use
    peer_id = b'-PC0001-' + bytes(f'{random.randint(0, 999999):06}', encoding='utf-8')

    # Generate fake torrent info
    torrent_info = generate_dummy_torrent_info()

    # Create a dummy StorageManager
    storage = StorageManager('dummy_file.txt', torrent_info['length'],
                             torrent_info['piece_length'], torrent_info['pieces'])

    # Create and start the TorrentPeer
    peer = TorrentPeer(peer_id, torrent_info, storage, listen_port=listen_port)
    peer.start()

    print(f"[*] TorrentPeer running with peer_id: {peer_id.decode()}")
    print(f"[*] Listening on port {listen_port}")
    print(f"[*] Ready for incoming or outgoing peer connections!")

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        print("[*] Shutting down TorrentPeer...")
        peer.running = False
        storage.close()


if __name__ == "__main__":
    main()
