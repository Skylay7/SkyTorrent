import threading
from protocolmessage import ProtocolMessage


class PeerConnection:
    def __init__(self, sock, peer_id, bitfield, storage, torrent_info):
        self.sock = sock
        self.peer_id = peer_id
        self.bitfield = bitfield
        self.storage = storage
        self.info_hash = torrent_info['info_hash']
        self.num_pieces = len(torrent_info['pieces']) // 20
        self.block_size = 2 ** 14  # 16 KB
        self.running = True
        self.choked = True
        self.sent_interested = False

    def run(self):
        try:
            self.send_bitfield()
            self.download_loop()
        except Exception as e:
            print(f"[!] Peer {self.sock.getpeername()} error: {e}")
        finally:
            self.sock.close()

    def send_bitfield(self):
        try:
            bitstring = ''.join(['1' if b else '0' for b in self.storage.bitfield])
            while len(bitstring) % 8 != 0:
                bitstring += '0'

            bitfield_bytes = bytearray()
            for i in range(0, len(bitstring), 8):
                byte = int(bitstring[i:i + 8], 2)
                bitfield_bytes.append(byte)

            length = len(bitfield_bytes) + 1
            msg = length.to_bytes(4, 'big') + b'\x05' + bitfield_bytes
            self.sock.sendall(msg)
            print(f"[→] Sent bitfield to {self.sock.getpeername()}")
        except Exception as e:
            print(f"[!] Error sending bitfield: {e}")

    def download_loop(self):
        while self.running:
            msg_id, payload = ProtocolMessage.parse_message(self.sock)
            if msg_id is None:
                print(f"[!] Disconnected: {self.sock.getpeername()}")
                break

            if msg_id == 0:
                self.choked = True
                print(f"[←] Choked by {self.sock.getpeername()}")
            elif msg_id == 1:
                self.choked = False
                print(f"[←] Unchoked by {self.sock.getpeername()}")
            elif msg_id == 5:
                self.bitfield = ProtocolMessage.parse_bitfield(payload, self.num_pieces)
            elif msg_id == 7:
                self.handle_piece(payload)

            if not self.choked and not self.sent_interested:
                self.sock.sendall(ProtocolMessage.build_interested())
                self.sent_interested = True
                print(f"[→] Sent interested to {self.sock.getpeername()}")

            if not self.choked:
                index = self.storage.get_needed_piece(self.bitfield)
                if index is None:
                    print(f"[✓] No more pieces needed from {self.sock.getpeername()}")
                    break
                self.request_piece(index)

    def request_piece(self, index):
        begin = 0  # For simplicity, we don't split blocks
        length = self.block_size
        payload = (
            index.to_bytes(4, 'big') +
            begin.to_bytes(4, 'big') +
            length.to_bytes(4, 'big')
        )
        msg = len(payload + b'\x06').to_bytes(4, 'big') + b'\x06' + payload
        self.sock.sendall(msg)
        print(f"[→] Requested piece {index} from {self.sock.getpeername()}")

    def handle_piece(self, payload):
        index = int.from_bytes(payload[0:4], 'big')
        begin = int.from_bytes(payload[4:8], 'big')
        block = payload[8:]
        self.storage.write_block(index, begin, block)
        self.storage.mark_piece_done(index)
        print(f"[↓] Received piece {index} (offset {begin}) from {self.sock.getpeername()}")
