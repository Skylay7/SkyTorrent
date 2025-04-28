import socket
import threading
import hashlib

# Constants
PORT = 6881  # Standard BitTorrent port
PEER_ID = b"-PY0001-ABCDEFGHIJKLMNOP"  # Example peer ID (20 bytes)
INFO_HASH = hashlib.sha1(b"My test torrent file").digest()  # Fake hash for testing


def handle_peer(conn, addr):
    print(f"[+] Incoming connection from {addr}")

    try:
        # Receive handshake (68 bytes total)
        handshake = conn.recv(68)
        if len(handshake) != 68:
            print("[-] Invalid handshake length.")
            return

        # Parse the handshake
        pstrlen = handshake[0]
        pstr = handshake[1:20].decode(errors="ignore")
        received_info_hash = handshake[28:48]
        received_peer_id = handshake[48:68]

        print(f"[=] Protocol: {pstr}")
        print(f"[=] Info hash: {received_info_hash.hex()}")
        print(f"[=] Peer ID:   {received_peer_id.decode(errors='ignore')}")

        # Respond with our own handshake
        pstr = b"BitTorrent protocol"
        reserved = b"\x00" * 8
        response = bytes([len(pstr)]) + pstr + reserved + INFO_HASH + PEER_ID
        conn.sendall(response)

        print("[+] Handshake sent back. Peer connected successfully.")

        # Optional: Keep the connection open to test
        while True:
            data = conn.recv(1024)
            if not data:
                break
            print(f"[>] Received {len(data)} bytes: {data.hex()}")

    except Exception as e:
        print(f"[!] Error with {addr}: {e}")
    finally:
        conn.close()
        print(f"[x] Connection closed: {addr}")


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', PORT))  # Listen on all interfaces
    server.listen()
    print(f"[*] Listening on port {PORT} (CTRL+C to stop)")

    try:
        while True:
            conn, addr = server.accept()
            thread = threading.Thread(target=handle_peer, args=(conn, addr), daemon=True)
            thread.start()
    except KeyboardInterrupt:
        print("\n[!] Server shutting down.")
    finally:
        server.close()


if __name__ == "__main__":
    start_server()
