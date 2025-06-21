# SkyTorrent

## Files Explenation

- tracker_server.py	Flask-based BitTorrent tracker (stores and returns peer lists)
- torrent_generator.py	Creates .torrent files from given input files
- torrent_parser.py	Parses .torrent files to extract metadata and info_hash
- client.py	Entry point for running a peer (Seeder or Leecher)
- torrent_peer.py	Core logic for peer behavior (handshake, download, piece exchange)
- storage_manager.py	Handles file storage, validation, and piece writing
- protocolmessage.py	Manages message parsing, building, and protocol structure
- encrypted_socket.py	Implements Diffie-Hellman + RC4 encryption (BEP-9 hybrid mode)
- piece.py	Helper class for managing piece assembly and completeness checking

## How to Run the Project

### 1. Install Requirements

```bash
pip install flask bencodepy pycryptodome miniupnpc
```
### 2. Start the Tracker

the trakcer will run on the machine you run it on.

>python tracker_server.py

### 3. Run client

>python client.py

client.py is the test file. It creates the peer and the torrent file generation or parsing. TORRENT_FILE = "test_file.torrent" is the place you put the path of the torrent file you get or the one you want to generate. 
if you want to generate a torrent file -> TEST_FILE = "test_file.png" put the path in this value.