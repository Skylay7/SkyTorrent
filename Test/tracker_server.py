from flask import Flask, request, Response
import time
import bencodepy
import threading

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
        # Extract required query parameters
        info_hash = request.args.get('info_hash', type=str)
        peer_id = request.args.get('peer_id', type=str)
        port = request.args.get('port', type=int)
        ip = request.remote_addr

        if not info_hash or not peer_id or not port:
            return Response("Missing required parameters", status=400)

        # Store peer in tracker
        peer = {
            'ip': ip,
            'port': port,
            'peer_id': peer_id,
            'last_seen': time.time()
        }
        info_hash_bytes = info_hash.encode('latin-1')  # Preserve raw bytes

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

        # Build compact peer list (4 bytes IP + 2 bytes port each)
        compact_peers = b''
        for p in peers:
            ip_parts = [int(part) for part in p['ip'].split('.')]
            compact_peers += bytes(ip_parts) + p['port'].to_bytes(2, 'big')

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
