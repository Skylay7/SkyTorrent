# storage_manager.py
import os
import hashlib
import threading


# TO DO : THREAD SAFETY
class StorageManager:
    def __init__(self, filepath, total_length, piece_length, piece_hashes):
        """
        :param filepath: Path to the file (from .torrent info['name'])
        :param total_length: Total file size
        :param piece_length: Piece size (usually 256 KB or similar)
        :param piece_hashes: Concatenated SHA-1 hashes (b''.join(...)) of all pieces
        """
        self.filepath = filepath
        self.total_length = total_length
        self.piece_length = piece_length
        self.piece_hashes = [piece_hashes[i:i + 20] for i in range(0, len(piece_hashes), 20)]
        self.num_pieces = len(self.piece_hashes)

        # Ensure the file exists (create if missing)
        self._prepare_file()

        # Open the file for read/write in binary mode
        self.file = open(self.filepath, 'r+b')

        # Build bitfield (True for valid pieces, False for missing or invalid)
        self.bitfield = self._build_bitfield()
        self.requested_pieces = set()
        self.lock = threading.Lock()

    def _prepare_file(self):
        if not os.path.exists(self.filepath):
            print(f"[+] Creating empty file: {self.filepath}")
            with open(self.filepath, 'wb') as f:
                f.truncate(self.total_length)
        else:
            actual_size = os.path.getsize(self.filepath)
            if actual_size != self.total_length:
                raise ValueError(f"File size mismatch: expected {self.total_length}, found {actual_size}")

    def _build_bitfield(self):
        print("[*] Validating file and building bitfield...")
        bitfield = []
        with open(self.filepath, 'rb') as f:
            for i in range(self.num_pieces):
                f.seek(i * self.piece_length)
                data = f.read(self.piece_length)
                expected_hash = self.piece_hashes[i]
                actual_hash = hashlib.sha1(data).digest()
                bitfield.append(actual_hash == expected_hash)
        print(f"[+] Bitfield built: {bitfield.count(True)} / {self.num_pieces} pieces valid.")
        return bitfield

    def write_piece(self, index, data):
        if len(data) > self.piece_length:
            raise ValueError(f"Data too large for piece {index} (expected ≤ {self.piece_length}, got {len(data)})")

        offset = index * self.piece_length
        self.file.seek(offset)
        self.file.write(data)
        self.file.flush()  # ← flush buffer
        os.fsync(self.file.fileno())  # ← force write to disk

    def read_block(self, index, begin, length):
        offset = index * self.piece_length + begin
        self.file.seek(offset)
        return self.file.read(length)

    def validate_piece_data(self, index, data):
        """
        Validate that the given piece data matches the expected SHA-1 hash.
        Used before writing the piece to disk.
        """
        expected_hash = self.piece_hashes[index]
        actual_hash = hashlib.sha1(data).digest()
        return actual_hash == expected_hash

    def get_needed_piece(self, peer_bitfield):
        with self.lock:
            for index, their_has in enumerate(peer_bitfield):
                if their_has and not self.bitfield[index] and index not in self.requested_pieces:
                    self.requested_pieces.add(index)
                    return index
            print(self.bitfield)
            print(self.requested_pieces)
        return None  # Nothing useful to request

    def request_piece(self, index):
        with self.lock:
            self.requested_pieces.add(index)

    def mark_piece_done(self, index):
        with self.lock:
            self.requested_pieces.discard(index)
            self.bitfield[index] = True

    def release_piece(self, index):
        with self.lock:
            self.requested_pieces.discard(index)

    def close(self):
        print(f"[✓] Closing storage. Final flush.")
        self.file.flush()
        os.fsync(self.file.fileno())
        self.file.close()

