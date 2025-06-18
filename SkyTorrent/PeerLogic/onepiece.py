import socket
import threading
from encrypted_socket import EncryptedSocket

HOST = '127.0.0.1'
PORT = 50007

# ---------- Server ----------
def start_server():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind((HOST, PORT))
    server_sock.listen(1)
    print("[SERVER] Listening...")

    conn, addr = server_sock.accept()
    print(f"[SERVER] Connected by {addr}")
    enc_conn = EncryptedSocket(conn)
    enc_conn.perform_handshake_as_responder()

    data = enc_conn.recv(22)
    print(f"[SERVER] Received (decrypted): {data.decode()}")

    enc_conn.send(data)  # echo back
    enc_conn.close()
    server_sock.close()
    print("[SERVER] Closed connection.")

# ---------- Client ----------
def start_client():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))
    enc_sock = EncryptedSocket(sock)
    enc_sock.perform_handshake_as_initiator()

    message = "Hello encrypted world!"
    enc_sock.send(message.encode())
    print(f"[CLIENT] Sent: {message}")

    response = enc_sock.recv(len(message))
    print(f"[CLIENT] Received (decrypted): {response.decode()}")

    enc_sock.close()

# ---------- Run both ----------
if __name__ == "__main__":
    server_thread = threading.Thread(target=start_server)
    server_thread.start()

    server_thread.join()
