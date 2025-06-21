# torrent_generator.py
import os
import hashlib
import bencodepy
import argparse

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
    parser = argparse.ArgumentParser(description="Generate a .torrent file from a file.")
    parser.add_argument("file_path", nargs='?', default="my_file.txt", help="Path to the source file")
    parser.add_argument("tracker_url", nargs='?', default="http://localhost:6969/announce", help="Tracker URL")
    parser.add_argument("out_path", nargs='?', default="my_file.torrent", help="Output .torrent file path")

    args = parser.parse_args()
    generate_torrent(args.file_path, args.tracker_url, args.out_path)
