class ProtocolMessage:
    @staticmethod
    def build_interested():
        return (1).to_bytes(4, 'big') + b'\x02'

    @staticmethod
    def build_not_interested():
        return (1).to_bytes(4, 'big') + b'\x03'  # ID = 3 = not interested

    @staticmethod
    def build_have(index):
        return (5).to_bytes(4, 'big') + b'\x04' + index.to_bytes(4, 'big')

    @staticmethod
    def build_choke():
        return (1).to_bytes(4, 'big') + bytes([0])

    @staticmethod
    def build_unchoke():
        return (1).to_bytes(4, 'big') + bytes([1])

    @staticmethod
    def build_handshake(info_hash, peer_id):
        pstr = b"BitTorrent protocol"
        reserved = b'\x00' * 8
        return bytes([len(pstr)]) + pstr + reserved + info_hash + peer_id

    @staticmethod
    def build_piece(index, begin, length):
        payload = (
                index.to_bytes(4, 'big') +
                begin.to_bytes(4, 'big') +
                length.to_bytes(4, 'big')
        )
        return len(payload + b'\x06').to_bytes(4, 'big') + b'\x06' + payload

    @staticmethod
    def build_response(index, begin, block):
        payload = (
                index.to_bytes(4, 'big') +
                begin.to_bytes(4, 'big') +
                block
        )
        return len(payload).to_bytes(4, 'big') + b'\x07' + payload

    @staticmethod
    def parse_bitfield(bitfield_bytes: bytes, num_pieces: int) -> list[bool]:
        bitfield = []
        for byte in bitfield_bytes:
            for i in range(8):
                bit = (byte >> (7 - i)) & 1
                bitfield.append(bool(bit))
        return bitfield[:num_pieces]  # Trim any padding

    @staticmethod
    def parse_message(sock):
        header = sock.recv(4)
        if len(header) < 4:
            return None, None
        length = int.from_bytes(header, 'big')
        if length == 0:
            return -1, b''
        msg_id = sock.recv(1)
        payload = sock.recv(length) if length > 1 else b''
        return int.from_bytes(msg_id, 'big'), payload
