

class Piece:
    def __init__(self, total_length, block_size):
        self.total_length = total_length
        self.block_size = block_size
        self.blocks = {}  # {offset → bytes}
        self.received_bytes = 0

    def store_block(self, begin, data):
        if begin not in self.blocks:
            self.blocks[begin] = data
            self.received_bytes += len(data)

    def is_complete(self):
        return self.received_bytes >= self.total_length

    def reassemble(self):
        return b''.join(self.blocks[offset] for offset in sorted(self.blocks))
