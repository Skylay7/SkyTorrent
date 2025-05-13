from flask import Flask, request, Response
import time
import bencodepy
import threading
import urllib.parse

app = Flask(__name__)
tracker_data = {}  # info_hash → list of peers

PEER_TIMEOUT = 1800  # seconds
CLEANUP_INTERVAL = 60


def cleanup_peers():
    print("[*] Cleanup thread started")
    while True:
        now = time.time()
        for info_hash, peers in list(tracker_data.items()):
            print("[*] Running cleanup for:", info_hash)
            print(tracker_data)
            tracker_data[info_hash] = [
                peer for peer in peers if now - peer['last_seen'] < PEER_TIMEOUT
            ]
        time.sleep(CLEANUP_INTERVAL)


@app.route("/announce", methods=["GET"])
def announce():
    try:
        print("[*] Incoming /announce request")
        print(f"[*] /announce from {request.remote_addr}")
        print(f"    Query: {request.query_string!r}")

        # Step 1: Parse raw query string as bytes → list of (key, value)
        raw_params = request.query_string.split(b"&")
        query = {}
        for param in raw_params:
            if b"=" in param:
                k, v = param.split(b"=", 1)
                query[k] = v

        # Step 2: Decode percent-encoded values safely
        info_hash_bytes = urllib.parse.unquote_to_bytes(query[b"info_hash"])
        peer_id_bytes = urllib.parse.unquote_to_bytes(query[b"peer_id"])
        port = int(query[b"port"].decode("ascii"))
        ip = request.remote_addr

        print(f"[#] Clean decoded info_hash: {info_hash_bytes.hex()}")
        print(f"[#] Decoded peer_id: {peer_id_bytes}")
        print(f"[#] Decoded port: {port}")

        peer = {
            "ip": ip,
            "port": port,
            "peer_id": peer_id_bytes,
            "last_seen": time.time()
        }

        print(peer)

        if info_hash_bytes not in tracker_data:
            tracker_data[info_hash_bytes] = []

        peers = tracker_data[info_hash_bytes]
        # Update or add peer
        for i, existing in enumerate(peers):
            if existing['peer_id'] == peer['peer_id']:
                peers[i] = peer
                break
        else:
            peers.append(peer)

        print(f"[#] All peers stored for hash {info_hash_bytes.hex()}:")
        for p in tracker_data[info_hash_bytes]:
            print(f"   - {p['ip']}:{p['port']} ({p['peer_id'].decode(errors='ignore')})")

        print(f"[#] Current peer requesting: {ip}:{port}")

        # Build compact peer list (4 bytes IP + 2 bytes port each)
        compact_peers = b''
        for p in peers:
            ip_parts = [int(part) for part in p['ip'].split('.')]
            compact_peers += bytes(ip_parts) + p['port'].to_bytes(2, 'big')

        print(f"[#] Peers that will be returned to {ip}:{port}:")
        for p in peers:
            print(f"   - {p['ip']}:{p['port']}")

        response = {
            b'interval': PEER_TIMEOUT,
            b'peers': compact_peers
        }

        return Response(bencodepy.encode(response), content_type='text/plain')

    except Exception as e:
        return Response(f"Error: {e}", status=500)


if __name__ == "__main__":
    threading.Thread(target=cleanup_peers, daemon=True).start()
    app.run(host="0.0.0.0", port=6969)
