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
        self.num_pieces = len(self.piece_hashes)
        self.storage = storage_manager
        self.listen_port = listen_port
        self.backlog = backlog

        self.connected_peers = []
        self.remote_peer_ids = {}
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
                    if isinstance(peers, bytes):
                        for i in range(0, len(peers), 6):
                            ip = '.'.join(str(b) for b in peers[i:i + 4])
                            port = int.from_bytes(peers[i + 4:i + 6], 'big')

                            if ip == '127.0.0.1' and port == self.listen_port:
                                print(f"[-] Skipping self ({ip}:{port})", flush=True)
                                continue

                            print(f"[+] Tracker returned peer: {ip}:{port}", flush=True)

                            sock = self.connect_to_peer(ip, port)
                            if sock:
                                self.send_handshake(sock)
                                peer_id = self.receive_handshake(sock)
                                self.remote_peer_ids[sock] = peer_id  # Store peer ID
                                if peer_id:
                                    print(f"[+] Handshake completed with {ip}:{port}")
                                    threading.Thread(target=self.handle_peer_connection, args=(sock, False),
                                                     daemon=True).start()
                                else:
                                    print(f"[!] Handshake failed with {ip}:{port}")
                                    sock.close()

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
                threading.Thread(target=self.handle_peer_connection, args=(conn, True), daemon=True).start()
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

    def handle_peer_connection(self, conn, is_incoming):
        try:
            if is_incoming:
                peer_id = self.receive_handshake(conn)
                if not peer_id:
                    print(f"[!] Invalid handshake from {conn.getpeername()}")
                    conn.close()
                    return
                self.send_handshake(conn)
                self.remote_peer_ids[conn] = peer_id  # Store peer ID
                self.send_bitfield(conn)
            else:
                print(f"[+] Peer handshake established with {conn.getpeername()}")
                peer_id = self.remote_peer_ids.get(conn)  # optional
                peer_bitfield = self.receive_bitfield(conn)  # ← Only if outgoing
                print(peer_bitfield)
                threading.Thread(target=self.download_loop, args=(conn, peer_bitfield), daemon=True).start()

        except Exception as e:
            print(f"[!] Error handling peer {conn.getpeername()}: {e}")
            conn.close()

    def receive_handshake(self, sock):
        data = b''
        while len(data) < 68:
            chunk = sock.recv(68 - len(data))
            if not chunk:
                return None
            data += chunk

        if not data.startswith(b'\x13BitTorrent protocol'):
            return None

        info_hash_received = data[28:48]
        if info_hash_received != self.info_hash:
            return None

        return data[48:]

    def send_handshake(self, sock):
        pstr = b"BitTorrent protocol"
        reserved = b'\x00' * 8
        handshake = (
                bytes([len(pstr)]) + pstr + reserved + self.info_hash + self.peer_id
        )
        sock.sendall(handshake)

    @staticmethod
    def send_interested(sock):
        msg = b'\x00\x00\x00\x01' + b'\x02'  # length=1, ID=2 (interested)
        sock.sendall(msg)

    def send_bitfield(self, sock):
        try:
            # Convert your storage bitfield (list of bools) to a byte array
            bitfield_bool = self.storage.bitfield  # e.g., [True, False, True, ...]
            bitstring = ''.join(['1' if b else '0' for b in bitfield_bool])

            # Pad the bitstring to be a multiple of 8
            while len(bitstring) % 8 != 0:
                bitstring += '0'

            # Convert to bytes
            bitfield_bytes = bytearray()
            for i in range(0, len(bitstring), 8):
                byte = int(bitstring[i:i + 8], 2)
                bitfield_bytes.append(byte)

            # Build the full message
            payload = b'\x05' + bitfield_bytes  # ID = 5
            length_prefix = len(payload).to_bytes(4, 'big')
            msg = length_prefix + payload

            sock.sendall(msg)
            print(f"[→] Sent bitfield to {sock.getpeername()}")

        except Exception as e:
            print(f"[!] Failed to send bitfield: {e}")

    @staticmethod
    def send_have(index, sock):
        """ To announce a given index piece has been added and able to download"""
        try:
            msg = (
                    (5).to_bytes(4, 'big') +  # length = 5
                    b'\x04' +  # ID = 4 (have)
                    index.to_bytes(4, 'big')  # piece index
            )
            sock.sendall(msg)
            print(f"[→] Sent 'have' message for piece {index} to {sock.getpeername()}")
        except Exception as e:
            print(f"[!] Failed to send 'have' message to {sock.getpeername()}: {e}")

    def receive_bitfield(self, sock):
        try:
            header = sock.recv(4)
            length = int.from_bytes(header, 'big')
            if length == 0:
                return None

            msg_id = sock.recv(1)
            if msg_id != b'\x05':  # ID 5 = bitfield
                return None

            payload = sock.recv(length - 1)
            return self.parse_bitfield(payload, self.num_pieces)

        except Exception as e:
            print(f"[!] Error receiving bitfield: {e}")
            return None

    @staticmethod
    def parse_bitfield(bitfield_bytes: bytes, num_pieces: int) -> list[bool]:
        bitfield = []

        for byte in bitfield_bytes:
            for i in range(8):
                # Get each bit from MSB to LSB (left to right)
                bit = (byte >> (7 - i)) & 1
                bitfield.append(bool(bit))

        # Trim padding bits at the end
        return bitfield[:num_pieces]

    @staticmethod
    def request_piece(sock, index, begin, length):
        payload = (
                index.to_bytes(4, 'big') +
                begin.to_bytes(4, 'big') +
                length.to_bytes(4, 'big')
        )
        msg = len(payload + b'\x06').to_bytes(4, 'big') + b'\x06' + payload
        sock.sendall(msg)

    def download_loop(self, conn, peer_bitfield):
        try:
            while True:
                piece_index = self.storage.get_needed_piece(peer_bitfield)
                if piece_index is None:
                    print(f"[=] No pieces to request from {conn.getpeername()}")
                    time.sleep(2)
                    continue  # wait and retry

                self.send_interested(conn)
                if not self.wait_for_unchoke(conn):
                    print(f"[!] Peer {conn.getpeername()} did not unchoke us")
                    time.sleep(2)
                    continue

                # Here starts the re

                self.request_piece(conn, piece_index, 0, 2 ** 14)
                self.receive_piece(conn)  # should validate & mark it

        except Exception as e:
            print(f"[!] Error in download loop with {conn.getpeername()}: {e}")
            conn.close()

    @staticmethod
    def wait_for_unchoke(sock, timeout=30):
        """
        Blocks until an 'unchoke' (ID=1) message is received.
        Returns True if unchoked within timeout, False otherwise.
        """
        sock.settimeout(timeout)
        try:
            while True:
                # Read message length
                length_bytes = sock.recv(4)
                if len(length_bytes) < 4:
                    print("[!] Connection closed while waiting for unchoke")
                    return False

                length = int.from_bytes(length_bytes, 'big')

                if length == 0:
                    continue  # Keep-alive message, skip

                # Read message ID
                msg_id = sock.recv(1)
                if not msg_id:
                    print("[!] Connection closed (no message ID)")
                    return False

                if msg_id == b'\x01':
                    print(f"[✓] Received unchoke from {sock.getpeername()}")
                    return True

                # Skip rest of the message
                sock.recv(length - 1)

        except socket.timeout:
            print(f"[!] Timed out waiting for unchoke from {sock.getpeername()}")
            return False

        except Exception as e:
            print(f"[!] Error waiting for unchoke: {e}")
            return False

    def receive_piece(self, sock):
        header = sock.recv(4)
        length = int.from_bytes(header, 'big')
        if length == 0:
            return
        msg_id = sock.recv(1)
        if msg_id != b'\x07':
            sock.recv(length - 1)
            return

        # Read: index (4 bytes), begin (4 bytes), block
        index = int.from_bytes(sock.recv(4), 'big')
        begin = int.from_bytes(sock.recv(4), 'big')
        block = b''
        while len(block) < (length - 9):
            block += sock.recv(length - 9 - len(block))

        self.storage.write_block(index, begin, block)
        print(f"[+] Received block: piece {index}, offset {begin}, {len(block)} bytes")

    def start(self):
        """Start the torrent session."""
        threading.Thread(target=self.listen_for_incoming_peers, args=(), daemon=True).start()
        threading.Thread(target=self.try_upnp_port_forwarding, daemon=True).start()
        threading.Thread(target=self.announce_to_tracker, daemon=True).start()
