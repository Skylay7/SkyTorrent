import threading


class UploadManager:

    def __init__(self):
        self.interested_peers = set()
        self.unchoked_peers = set()
        self.max_slots = 4
        self.lock = threading.Lock()
