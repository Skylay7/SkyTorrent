# torrent_peer.py

import socket
import threading
import hashlib
import random
import time
import urllib.parse
import urllib.request
import bencodepy

try:
    import miniupnpc
except ImportError:
    miniupnpc = None


class TorrentPeer:
    def __init__(self, peer_id, torrent_info, storage_manager, listen_port=6881, backlog=50):
        """
        :param peer_id: 20-byte unique ID for this client
        :param torrent_info: Parsed .torrent dict from torrent_parser
        :param storage_manager: Instance of StorageManager
        :param listen_port: Port to listen on for incoming peers
        """
        self.peer_id = peer_id
        self.info_hash = torrent_info['info_hash']
        self.tracker_url = torrent_info['announce']
        self.name = torrent_info['name']
        self.piece_length = torrent_info['piece_length']
        self.total_length = torrent_info['length']
        self.piece_hashes = torrent_info['pieces']
        self.storage = storage_manager
        self.listen_port = listen_port
        self.backlog = backlog

        self.connected_peers = []
        self.running = True

    def announce_to_tracker(self):
        """Announce to the tracker and retrieve a list of peers."""
        try:
            params = {
                'info_hash': self.info_hash,
                'peer_id': self.peer_id,
                'port': self.listen_port,
                'uploaded': 0,
                'downloaded': 0,
                'left': self.total_length,
                'compact': 1,
                'event': 'started'
            }

            url = self.tracker_url + '?' + urllib.parse.urlencode({
                k: (v if isinstance(v, str) else urllib.parse.quote_from_bytes(v))
                for k, v in params.items()
            })

            print(f"[*] Announcing to tracker: {url}")
            with urllib.request.urlopen(url) as response:
                response_data = response.read()
                decoded = bencodepy.decode(response_data)

                if b'peers' in decoded:
                    peers = decoded[b'peers']
                    if isinstance(peers, bytes):  # compact format
                        for i in range(0, len(peers), 6):
                            ip = '.'.join(str(b) for b in peers[i:i + 4])
                            port = int.from_bytes(peers[i + 4:i + 6], 'big')
                            print(f"[+] Tracker returned peer: {ip}:{port}")
                            self.connect_to_peer(ip, port)
                    else:
                        print("[!] Non-compact peer format not supported yet.")
                else:
                    print("[!] No peers in tracker response.")
        except Exception as e:
            print(f"[!] Tracker communication failed: {e}")

    def listen_for_incoming_peers(self):
        """Start a listening socket for incoming peer connections."""
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind(('', self.listen_port))
        server_sock.listen(self.backlog)
        print(f"[*] Listening for incoming peers on port {self.listen_port}")

        while self.running:
            try:
                conn, addr = server_sock.accept()
                print(f"[+] Accepted connection from {addr}")
                self.connected_peers.append(conn)
                threading.Thread(target=self.handle_peer_connection, args=(conn,), daemon=True).start()
            except Exception as e:
                print(f"[!] Error accepting connection: {e}")

    def try_upnp_port_forwarding(self):
        """Attempt to use UPnP to open a port on the router."""
        if miniupnpc is None:
            print("[!] miniupnpc not available. Skipping UPnP port forwarding.")
            return

        try:
            upnp = miniupnpc.UPnP()
            upnp.discoverdelay = 200
            upnp.discover()
            upnp.selectigd()
            upnp.addportmapping(self.listen_port, 'TCP', upnp.lanaddr, self.listen_port, 'BitTorrentClient', '')
            print(f"[+] UPnP port {self.listen_port} forwarded successfully!")
        except Exception as e:
            print(f"[!] UPnP port forwarding failed: {e}")

    def connect_to_peer(self, ip, port):
        print(f"[*] Attempting connection to {ip}:{port}")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)  # 5 seconds timeout
            sock.connect((ip, port))
            print(f"[+] Connected to {ip}:{port}")
            self.connected_peers.append(sock)
            return sock
        except socket.timeout:
            print(f"[!] Connection to {ip}:{port} timed out.")
        except socket.error as e:
            print(f"[!] Failed to connect to {ip}:{port}: {e}")
        return None

    def handle_peer_connection(self, conn):
        """Handle an incoming or outgoing peer connection (placeholder)."""
        # perform_handshake(conn) should be called here (to be implemented)
        # exchange bitfield, interested/choke should be handled here (to be implemented)
        pass

    def perform_handshake(self, sock):
        # To be implemented
        pass

    def send_interested(self, sock):
        # To be implemented
        pass

    def request_piece(self, sock, index, begin, length):
        # To be implemented
        pass

    def download_loop(self):
        # Main loop for downloading from all peers
        pass

    def start(self):
        """Start the torrent session."""
        threading.Thread(target=self.listen_for_incoming_peers, args=(), daemon=True).start()
        self.try_upnp_port_forwarding()
        # announce_to_tracker() should be called here (to be implemented)
        # connect_to_peers() should be called after tracker response (to be implemented)
