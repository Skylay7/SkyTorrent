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
        try:
            encoded_info_hash = urllib.parse.quote_from_bytes(self.info_hash)
            encoded_peer_id = urllib.parse.quote_from_bytes(self.peer_id)

            params = (
                f"info_hash={encoded_info_hash}"
                f"&peer_id={encoded_peer_id}"
                f"&port={self.listen_port}"
                f"&uploaded=0"
                f"&downloaded=0"
                f"&left={self.total_length}"
                f"&compact=1"
                f"&event=started"
            )

            url = f"{self.tracker_url}?{params}"
            print(f"[*] Announcing to tracker: {url}", flush=True)

            with urllib.request.urlopen(url) as response:
                response_data = response.read()
                decoded = bencodepy.decode(response_data)

                if b'peers' in decoded:
                    peers = decoded[b'peers']
                    if isinstance(peers, bytes):  # compact format
                        for i in range(0, len(peers), 6):
                            ip = '.'.join(str(b) for b in peers[i:i + 4])
                            port = int.from_bytes(peers[i + 4:i + 6], 'big')

                            # ✅ Block self-connection
                            if ip == '127.0.0.1' and port == self.listen_port:
                                print(f"[-] Skipping self ({ip}:{port})", flush=True)
                                continue

                            print(f"[+] Tracker returned peer: {ip}:{port}", flush=True)

                            sock = self.connect_to_peer(ip, port)
                            if sock:
                                threading.Thread(target=self.handle_peer_connection, args=(sock,), daemon=True).start()

                    else:
                        print("[!] Non-compact peer format not supported yet.", flush=True)
                else:
                    print("[!] No peers in tracker response.", flush=True)

        except Exception as e:
            print(f"[!] Tracker communication failed: {e}", flush=True)

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
        try:
            # Try to read the first 20 bytes
            conn.settimeout(5)
            header = conn.recv(20, socket.MSG_PEEK)
            if not header.startswith(b'\x13BitTorrent protocol'):
                print(f"[!] Rejected non-BitTorrent connection from {conn.getpeername()}")
                conn.close()
                return

            print(f"[*] Valid BitTorrent handshake detected from {conn.getpeername()}")
            if self.perform_handshake(conn):
                print(f"[+] Handshake completed with {conn.getpeername()}")
            else:
                print(f"[!] Handshake failed with {conn.getpeername()}")
                conn.close()
        except Exception as e:
            print(f"[!] Error handling peer {conn.getpeername()}: {e}")
            conn.close()

    def perform_handshake(self, sock):
        try:
            pstr = b"BitTorrent protocol"
            pstrlen = len(pstr)
            reserved = b'\x00' * 8

            handshake = (
                    bytes([pstrlen]) +
                    pstr +
                    reserved +
                    self.info_hash +
                    self.peer_id
            )

            sock.sendall(handshake)
            response = sock.recv(68)
            if len(response) != 68:
                return False

            their_info_hash = response[28:48]
            if their_info_hash != self.info_hash:
                return False

            return True
        except Exception:
            return False

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
        threading.Thread(target=self.try_upnp_port_forwarding, daemon=True).start()
        threading.Thread(target=self.announce_to_tracker, daemon=True).start()
        # connect_to_peers() should be called after tracker response (to be implemented)
