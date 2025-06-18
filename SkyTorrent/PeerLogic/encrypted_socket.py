import socket
import hashlib
import random
from Crypto.Cipher import ARC4

# 768-bit MODP Group (from RFC 2409 Appendix E)
p_hex = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A63A3620FFFFFFFFFFFFFFFF"
)
p = int(p_hex, 16)
g = 2


class EncryptedSocket:
    def __init__(self, sock):
        self.sock = sock
        self.shared_secret = None
        self.rc4_encryptor = None
        self.rc4_decryptor = None

    def _dh_generate_keypair(self):
        priv = random.randint(2, p - 2)
        pub = pow(g, priv, p)
        return priv, pub

    def _dh_compute_shared_secret(self, priv, peer_pub):
        return pow(peer_pub, priv, p)

    def _derive_keys(self, secret):
        s_bytes = secret.to_bytes((secret.bit_length() + 7) // 8, 'big')
        key = hashlib.sha1(s_bytes).digest()[:16]  # 128-bit key
        return ARC4.new(key), ARC4.new(key)  # (encryptor, decryptor)

    def _recv_exact(self, n):
        data = b''
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Connection closed during receive")
            data += chunk
        return data

    def perform_handshake_as_initiator(self):
        priv, pub = self._dh_generate_keypair()
        self.sock.sendall(pub.to_bytes(96, 'big'))  # send our DH public key

        peer_pub_bytes = self._recv_exact(96)
        peer_pub = int.from_bytes(peer_pub_bytes, 'big')
        shared_secret = self._dh_compute_shared_secret(priv, peer_pub)

        self.rc4_encryptor, self.rc4_decryptor = self._derive_keys(shared_secret)
        self.shared_secret = shared_secret

    def perform_handshake_as_responder(self):
        peer_pub_bytes = self._recv_exact(96)
        peer_pub = int.from_bytes(peer_pub_bytes, 'big')

        priv, pub = self._dh_generate_keypair()
        self.sock.sendall(pub.to_bytes(96, 'big'))

        shared_secret = self._dh_compute_shared_secret(priv, peer_pub)
        self.rc4_encryptor, self.rc4_decryptor = self._derive_keys(shared_secret)
        self.shared_secret = shared_secret

    def send(self, data):
        encrypted = self.rc4_encryptor.encrypt(data)
        self.sock.sendall(encrypted)

    def recv(self, n):
        data = self._recv_exact(n)
        return self.rc4_decryptor.decrypt(data)

    def close(self):
        self.sock.close()

    def fileno(self):
        return self.sock.fileno()
