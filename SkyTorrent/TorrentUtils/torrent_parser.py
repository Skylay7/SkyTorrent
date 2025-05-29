# torrent_parser.py

import bencodepy
import hashlib


def parse_torrent_file(path):
    with open(path, 'rb') as f:
        raw = f.read()

    # Decode using bencode
    meta = bencodepy.decode(raw)

    # Extract fields
    info = meta[b'info']
    info_encoded = bencodepy.encode(info)  # for info_hash
    info_hash = hashlib.sha1(info_encoded).digest()

    # Basic fields
    parsed = {
        'announce': meta.get(b'announce', b'').decode(),
        'info_hash': info_hash,
        'name': info[b'name'].decode(),
        'piece_length': info[b'piece length'],
        'pieces': info[b'pieces'],
        'length': info.get(b'length')  # single-file torrent
    }

    return parsed
