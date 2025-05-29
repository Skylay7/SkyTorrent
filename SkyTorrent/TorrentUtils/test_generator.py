from torrent_generator import generate_torrent
from torrent_parser import parse_torrent_file

#generate_torrent("test_file.txt", "http://localhost:6969/announce", "test_file.torrent")
"""
parsed = parse_torrent_file("test_file.torrent")

print("Info Hash:", parsed['info_hash'].hex())
print("Name:", parsed['name'])
print("Length:", parsed['length'])
print("Piece length:", parsed['piece_length'])
print("Number of pieces:", len(parsed['pieces']) // 20)
"""
import hashlib
import bencodepy

info1 = {
    b'name': b'test_file.txt',
    b'length': 100,
    b'piece length': 262144,
    b'pieces': b'\x12'*20  # fake hash
}
info2 = {
    b'length': 100,
    b'name': b'test_file.txt',
    b'piece length': 262144,
    b'pieces': b'\x12'*20  # same content, but field order changed
}

print("Hash 1:", hashlib.sha1(bencodepy.encode(info1)).hexdigest())
print("Hash 2:", hashlib.sha1(bencodepy.encode(info2)).hexdigest())
