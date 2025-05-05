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
        print(request.args)
        print(f"[*] /announce from {request.remote_addr}")
        print(f"    Query: {request.query_string}")

        info_hash_raw = request.args.get('info_hash')
        peer_id_raw = request.args.get('peer_id')
        port = request.args.get('port', type=int)
        ip = request.remote_addr

        # ✅ Validate required fields
        if not info_hash_raw or not peer_id_raw or port is None:
            return Response("Missing required parameters", status=400)

        # ✅ Decode percent-encoded values back to raw bytes
        try:
            info_hash_bytes = urllib.parse.unquote_to_bytes(info_hash_raw)
            peer_id_bytes = urllib.parse.unquote_to_bytes(peer_id_raw)
        except Exception as e:
            return Response(f"Invalid encoding: {e}", status=400)

        # Store peer in tracker
        peer = {
            'ip': ip,
            'port': port,
            'peer_id': peer_id_bytes,
            'last_seen': time.time()
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
    app.run(host="0.0.0.0", port=6969, debug=True)
