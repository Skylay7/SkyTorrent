# torrent_peer.py

import socket
import threading
import time
import urllib.parse
import urllib.request
import bencodepy
from protocolmessage import ProtocolMessage
from piece import Piece
from encrypted_socket import EncryptedSocket

try:
    import miniupnpc
except ImportError:
    miniupnpc = None

UPLOAD_SLOT_LIMIT = 4
BLOCK_SIZE = 2 ** 14


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
        self.piece_hashes = [torrent_info['pieces'][i:i + 20] for i in range(0, len(torrent_info['pieces']), 20)]
        self.num_pieces = len(self.piece_hashes)
        self.storage = storage_manager
        self.listen_port = listen_port
        self.backlog = backlog

        self.threads = []
        self.pending_pieces = {}  # index - Pieces
        self.connected_peers = []
        self.remote_peer_ids = {}
        self.peer_bitfields = {}
        self.sent_interested = set()  # Peers we’ve sent 'interested' to
        self.upload_slots = threading.Semaphore(UPLOAD_SLOT_LIMIT)
        self.choked_peers = set()  # Peers who choked us
        self.running = True

    def start(self):
        """Start the torrent session."""
        server_thread = threading.Thread(target=self.listen_for_incoming_peers, args=())
        upnp_thread = threading.Thread(target=self.try_upnp_port_forwarding)
        tracker_thread = threading.Thread(target=self.announce_to_tracker)
        server_thread.start()
        upnp_thread.start()
        tracker_thread.start()
        self.threads.append(server_thread)
        self.threads.append(upnp_thread)
        self.threads.append(tracker_thread)

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
                                if not peer_id:
                                    print(f"[!] Invalid handshake from {sock.getpeername()}")
                                    sock.close()
                                    return
                                sock = self.secure_socket(sock, is_initiator=True)
                                print(f"[+] peer-id - {peer_id}")
                                self.remote_peer_ids[sock] = peer_id  # SKYLAY
                                if peer_id:
                                    print(f"[+] Handshake completed with {ip}:{port}")
                                    t = threading.Thread(target=self.handle_peer_connection, args=(sock, False))
                                    t.start()
                                    self.threads.append(t)
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
                t = threading.Thread(target=self.handle_peer_connection, args=(conn, True))
                t.start()
                self.threads.append(t)
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
        sockname = conn.getpeername()
        try:
            if is_incoming:
                peer_id = self.receive_handshake(conn)
                if not peer_id:
                    print(f"[!] Invalid handshake from {conn.getpeername()}")
                    conn.close()
                    return
                self.send_handshake(conn)
                conn = self.secure_socket(conn, is_initiator=False)
                self.remote_peer_ids[conn] = peer_id
                self.send_bitfield(conn)
                self.peer_bitfields[conn] = self.receive_bitfield(conn)
                self.handle_server_peer_message(conn)
            else:
                print(f"[+] Peer handshake established with {conn.getpeername()}")
                peer_bitfield = self.receive_bitfield(conn)
                print(f"[→] Bitfield received from {sockname}: {peer_bitfield}")
                self.peer_bitfields[conn] = peer_bitfield
                self.send_bitfield(conn)
                self.download_loop(conn, self.peer_bitfields[conn])

        except Exception as e:
            print(f"[!] Error handling peer {sockname}: {e}")
            conn.close()

    def handle_server_peer_message(self, sock):
        sock.settimeout(60)
        peer_choked = True  # choke until interested is sent

        try:
            while True:
                msg_id, payload = ProtocolMessage.parse_message(sock)
                if msg_id is None:
                    print(f"[!] Peer {sock.getpeername()} disconnected.")
                    break

                if msg_id == 4:  # have
                    self._handle_have(sock, payload)

                elif msg_id == 3:  # not interested
                    print(f"[←] Peer {sock.getpeername()} not interested. Closing connection.")
                    self.safe_close_peer(sock)
                    break

                elif msg_id == 2:  # interested
                    print(f"[←] Peer {sock.getpeername()} is interested.")
                    peer_choked = self._handle_interested(sock)

                elif msg_id == 6:  # request
                    if peer_choked:
                        print(f"[!] Refusing request from choked peer {sock.getpeername()}")
                        continue
                    index = int.from_bytes(payload[0:4], 'big')
                    begin = int.from_bytes(payload[4:8], 'big')
                    length = int.from_bytes(payload[8:12], 'big')
                    self.respond_to_request(sock, index, begin, length)

                else:
                    print(f"[←] Unhandled server-side msg ID {msg_id} from {sock.getpeername()}")

        except (socket.timeout, Exception) as e:
            print(f"[!] Upload loop terminated: {e}")
            sock.close()

    def respond_to_request(self, sock, index, begin, length):
        try:
            # Read the requested block from disk or memory
            block = self.storage.read_block(index, begin, length)
            if block is None:
                print(f"[!] Block read failed: index={index}, begin={begin}, length={length}")
                return

            msg = ProtocolMessage.build_response(index, begin, block)

            print(msg)

            # Send to peer
            sock.send(msg)
            print(f"[→] Sent piece {index} [{begin}:{begin + length}] to {sock.getpeername()}")

        except Exception as e:
            print(f"[!] Failed to send piece {index} to {sock.getpeername()}: {e}")

    def download_loop(self, conn, peer_bitfield):
        try:
            sockname = conn.getpeername()
            peer_id = self.remote_peer_ids.get(conn, b'unknown').decode(errors='ignore')

            # Step 1: Check if peer has anything useful
            if not self._should_interested(conn, peer_bitfield, sockname, peer_id):
                return

            # Step 2: Send 'interested' once
            if conn not in self.sent_interested:
                self.send_interested(conn)
                self.sent_interested.add(conn)
                print(f"[→] Sent 'interested' to {sockname}")

            # Step 3: Wait for initial unchoke
            if conn in self.choked_peers:
                if not self._wait_until_unchoked(conn, sockname):
                    return

            # Step 4: Begin request loop
            while True:
                # If we've been choked again, wait
                if conn in self.choked_peers:
                    if not self._wait_until_unchoked(conn, sockname):
                        break

                piece_index = self.storage.get_needed_piece(peer_bitfield)
                if piece_index is None:
                    print(f"[✓] No more pieces to request from {sockname}. Done with this peer.")
                    break

                # Compute actual piece size (especially important for the last piece)
                piece_size = min(self.piece_length, self.total_length - piece_index * self.piece_length)
                self.pending_pieces[piece_index] = Piece(piece_size, BLOCK_SIZE)

                try:
                    piece_size = min(self.piece_length, self.total_length - piece_index * self.piece_length)
                    for offset in range(0, piece_size, BLOCK_SIZE):
                        block_len = min(BLOCK_SIZE, piece_size - offset)
                        self.request_piece(conn, piece_index, offset, block_len)

                    while piece_index in self.pending_pieces and not self.pending_pieces[piece_index].is_complete():
                        if not self.receive_and_dispatch(conn):
                            raise Exception("Connection dropped or corrupted")

                except Exception as e:
                    print(f"[!] Failed to download piece {piece_index} from {sockname}: {e}")
                    self.storage.release_piece(piece_index)
                    time.sleep(2)

        except Exception as e:
            print(f"[!] Error in download loop with {conn.getpeername()}: {e}")
        finally:
            conn.close()

    def receive_and_dispatch(self, sock):
        try:
            msg_id, payload = ProtocolMessage.parse_message(sock)
            if msg_id is None:
                print(f"[!] Peer {sock.getpeername()} closed connection.")
                return False

            if msg_id == 7:
                self.handle_piece_message(payload)
            else:
                self.handle_peer_message(sock, msg_id, payload)

            return True

        except Exception as e:
            print(f"[!] Error receiving from {sock.getpeername()}: {e}")
            return False

    def handle_peer_message(self, sock, msg_id, payload):
        if msg_id == 0:
            self.choked_peers.add(sock)
            print(f"[←] Peer {sock.getpeername()} choked us.")
        elif msg_id == 1:
            self.choked_peers.discard(sock)
            print(f"[←] Peer {sock.getpeername()} unchoked us.")
        elif msg_id == 2:
            print(f"[←] Peer {sock.getpeername()} sent interested.")
        elif msg_id == 3:
            print(f"[←] Peer {sock.getpeername()} not interested.")
        elif msg_id == 4:
            self._handle_have(sock, payload)
        elif msg_id == 5:
            self.peer_bitfields[sock] = ProtocolMessage.parse_bitfield(payload, self.num_pieces)
            print(f"[←] Received bitfield from {sock.getpeername()}")
        else:
            print(f"[?] Unknown message ID {msg_id} from {sock.getpeername()}")

    def handle_piece_message(self, payload):
        index = int.from_bytes(payload[0:4], 'big')
        begin = int.from_bytes(payload[4:8], 'big')
        block = payload[8:]

        pending = self.pending_pieces[index]
        pending.store_block(begin, block)

        if pending.is_complete():
            piece_data = pending.reassemble()
            if self.storage.validate_piece_data(index, piece_data):
                self.storage.write_piece(index, piece_data)
                self.storage.mark_piece_done(index)
                del self.pending_pieces[index]
                for peer_conn in self.peer_bitfields.keys():
                    try:
                        self.send_have(index, peer_conn)
                    except Exception as e:
                        print(f"[!] Failed to send 'have' to {peer_conn.getpeername()}: {e}")
            else:
                print(f"[✗] Hash mismatch on piece {index}")
                self.pending_pieces[index] = Piece(self.piece_length, BLOCK_SIZE)

    def receive_handshake(self, sock):
        data = b''
        while len(data) < 62:
            chunk = sock.recv(62 - len(data))
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
        sock.send(ProtocolMessage.build_handshake(self.info_hash, self.peer_id))

    def send_interested(self, sock):
        sock.send(ProtocolMessage.build_interested())

    def send_bitfield(self, sock):
        try:
            # Convert your storage bitfield (list of bools) to a byte array
            bitfield_bool = self.storage.bitfield  # e.g., [True, False, True, ...]
            print(bitfield_bool)
            bitstring = ''.join(['1' if b else '0' for b in bitfield_bool])
            # Pad the bitstring to be a multiple of 8
            while len(bitstring) % 8 != 0:
                bitstring += '0'

            print(bitstring)
            # Convert to bytes
            bitfield_bytes = bytearray()
            for i in range(0, len(bitstring), 8):
                byte = int(bitstring[i:i + 8], 2)
                bitfield_bytes.append(byte)

            # Build the full message
            payload = b'\x05' + bitfield_bytes  # ID = 5
            length_prefix = len(payload).to_bytes(4, 'big')
            msg = length_prefix + payload
            print(msg)
            sock.send(msg)
            print(f"[→] Sent bitfield to {sock.getpeername()}")

        except Exception as e:
            print(f"[!] Failed to send bitfield: {e}")

    def receive_bitfield(self, sock):
        try:
            msg_id, payload = ProtocolMessage.parse_message(sock)
            if msg_id == 5:
                return ProtocolMessage.parse_bitfield(payload, self.num_pieces)
            return None
        except Exception as e:
            print(f"[!] Error receiving bitfield: {e}")
            return None

    def send_have(self, index, sock):
        """ To announce a given index piece has been added and able to download"""
        try:
            sock.send(ProtocolMessage.build_have(index))
            print(f"[→] Sent 'have' message for piece {index} to {sock.getpeername()}")
        except Exception as e:
            print(f"[!] Failed to send 'have' message to {sock.getpeername()}: {e}")

    def send_choke(self, sock):
        try:
            sock.send(ProtocolMessage.build_choke())
            print(f"[↑] Sent choke to {sock.getpeername()}")
        except Exception as e:
            print(f"[!] Failed to send choke: {e}")

    def send_unchoke(self, sock):
        try:
            sock.send(ProtocolMessage.build_unchoke())
            print(f"[↑] Sent unchoke to {sock.getpeername()}")
        except Exception as e:
            print(f"[!] Failed to send unchoke: {e}")

    def request_piece(self, sock, index, begin, length):
        sock.send(ProtocolMessage.build_piece(index, begin, length))

    def wait_for_unchoke(self, sock, timeout=30):
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

    def _should_interested(self, conn, peer_bitfield, sockname, peer_id):
        initial_piece = self.storage.get_needed_piece(peer_bitfield)
        if initial_piece is None:
            print(f"[=] Peer {sockname} ({peer_id}) has nothing we need. Sending 'not interested' and closing.")
            conn.send(ProtocolMessage.build_not_interested())
            conn.close()
            return False
        self.storage.release_piece(initial_piece)
        return True

    def _wait_until_unchoked(self, conn, sockname):
        if not self.wait_for_unchoke(conn):
            print(f"[!] Timed out waiting for unchoke from {sockname}")
            conn.close()
            return False
        self.choked_peers.discard(conn)
        return True

    def _handle_interested(self, sock):
        if self.upload_slots.acquire(blocking=False):  # try getting a slot
            self.send_unchoke(sock)
            self.choked_peers.discard(sock)
            print(f"[↑] Unchoked {sock.getpeername()}")
            return False
        self.send_choke(sock)
        self.choked_peers.add(sock)
        print(f"[×] No slots available: Choked {sock.getpeername()}")
        return True

    def _handle_have(self, sock, payload):
        try:
            if len(payload) != 4:
                print(f"[!] Malformed 'have' message from {sock.getpeername()}")
                return

            piece_index = int.from_bytes(payload, 'big')

            if sock not in self.peer_bitfields.keys():
                print(f"[!] Received 'have' from unknown peer {sock.getpeername()}")
                return

            bitfield = self.peer_bitfields[sock]
            if piece_index < 0 or piece_index >= len(bitfield):
                print(f"[!] Invalid piece index {piece_index} from {sock.getpeername()}")
                return

            bitfield[piece_index] = True
            print(f"[←] Peer {sock.getpeername()} now has piece {piece_index}")

            if all(bitfield):
                print(f"[✓] Peer {sock.getpeername()} has completed the file!")

        except Exception as e:
            print(f"[!] Error handling 'have' from {sock.getpeername()}: {e}")

    def secure_socket(self, sock, is_initiator):
        es = EncryptedSocket(sock)
        if is_initiator:
            es.perform_handshake_as_initiator()
        else:
            es.perform_handshake_as_responder()
        return es

    def safe_close_peer(self, sock):
        sockname = None
        try:
            sockname = sock.getpeername()
            sock.shutdown(socket.SHUT_RDWR)
        except:
            pass  # Already disconnected or invalid

        try:
            sock.close()
        except:
            pass

        # Clean up all peer-related state
        self.choked_peers.discard(sock)
        self.peer_bitfields.pop(sock, None)
        self.remote_peer_ids.pop(sock, None)
        if hasattr(self, 'peer_interested'):
            self.peer_interested.pop(sock, None)
        if hasattr(self, 'pending_pieces'):
            self.pending_pieces.pop(sock, None)

        # Upload slot handling
        if hasattr(self, 'upload_slots') and isinstance(self.upload_slots, threading.Semaphore):
            if sock not in self.choked_peers:  # was unchoked → release slot
                self.upload_slots.release()

        print(f"[×] Cleaned up connection with {sockname or '<unknown peer>'}")

    def shutdown_all_peers(self):
        print("[⏻] Shutting down all peer connections...")
        all_peers = set()

        # Aggregate all known connections to all_peers
        all_peers.update(self.peer_bitfields.keys())
        all_peers.update(self.remote_peer_ids.keys())
        all_peers.update(self.choked_peers)
        if hasattr(self, 'peer_interested'):
            all_peers.update(self.peer_interested.keys())
        if hasattr(self, 'pending_pieces'):
            all_peers.update(self.pending_pieces.keys())

        for sock in all_peers:
            self.safe_close_peer(sock)

        print("[✓] All peers cleaned up.")
