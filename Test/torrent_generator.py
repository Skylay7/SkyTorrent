# torrent_generator.py
import os
import hashlib
import bencodepy

PIECE_LEN = 256 * 1024  # 256 KB


def generate_torrent(file_path, tracker_url, out_path):
    with open(file_path, 'rb') as f:
        content = f.read()

    pieces = []
    for i in range(0, len(content), PIECE_LEN):
        piece = content[i:i + PIECE_LEN]
        pieces.append(hashlib.sha1(piece).digest())

    info = {
        b'piece length': PIECE_LEN,
        b'pieces': b''.join(pieces),
        b'name': os.path.basename(file_path).encode(),
        b'length': len(content)
    }

    torrent = {
        b'announce': tracker_url.encode(),
        b'info': info
    }

    with open(out_path, 'wb') as f:
        f.write(bencodepy.encode(torrent))

    print(f"[+] Torrent created: {out_path}")


if __name__ == "__main__":
    # Example:
    generate_torrent("my_file.txt", "http://localhost:6969/announce", "my_file.torrent")
