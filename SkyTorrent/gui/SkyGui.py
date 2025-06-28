import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QStackedWidget, QFileDialog, QLineEdit, QSizePolicy,
    QMessageBox, QProgressBar
)
from PyQt6.QtGui import QPixmap, QFont, QColor, QPalette, QIcon, QMovie
from PyQt6.QtCore import Qt, QTimer
import os
import threading
from SkyTorrent.utils.torrent_generator import generate_torrent
from SkyTorrent.utils.torrent_parser import parse_torrent_file
from SkyTorrent.core.torrent_peer import TorrentPeer
from SkyTorrent.core.storage_manager import StorageManager


class ScrollingBackground(QWidget):
    def __init__(self, image_path):
        super().__init__()
        self.cloud_pixmap = QPixmap(image_path)
        self.label1 = QLabel(self)
        self.label2 = QLabel(self)
        for label in (self.label1, self.label2):
            label.setScaledContents(True)
        self.offset = 0
        self.speed = 1
        self.scroll_width = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_scroll)
        self.timer.start(30)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#87ceeb"))
        self.setAutoFillBackground(True)
        self.setPalette(palette)

        self.update_backgrounds()

    def update_scroll(self):
        if self.scroll_width == 0:
            return
        self.offset = (self.offset + self.speed) % self.scroll_width
        self.update_backgrounds()

    def update_backgrounds(self):
        if self.cloud_pixmap.isNull():
            return
        h = self.height()
        scaled = self.cloud_pixmap.scaledToHeight(h, Qt.TransformationMode.SmoothTransformation)
        self.scroll_width = scaled.width()
        self.label1.setPixmap(scaled)
        self.label2.setPixmap(scaled)
        self.label1.setGeometry(-self.offset, 0, self.scroll_width, h)
        self.label2.setGeometry(-self.offset + self.scroll_width, 0, self.scroll_width, h)


class GenerateTorrentScreen(QWidget):
    def set_stacked_widget(self, stacked_widget):
        self.stacked_widget = stacked_widget

    def go_back(self):
        if hasattr(self, 'stacked_widget') and self.stacked_widget:
            self.stacked_widget.setCurrentIndex(0)

    def __init__(self):
        super().__init__()
        # Modern UI container
        layout = QVBoxLayout()
        layout.setSpacing(20)

        # Title and description
        title = QLabel("Generate Torrent")
        title.setStyleSheet("color: white; font-size: 56px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel("Select a file and provide a tracker URL to create your .torrent file.")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: lightgray; font-size: 20px;")
        layout.addWidget(desc)
        layout.setContentsMargins(40, 40, 40, 40)
        self.setStyleSheet("""
            QPushButton {
                background-color: #4682B4;
                font-size: 16px;
                font-weight: bold;
                color: white;
                font-size: 14px;
                padding: 10px 16px;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #5a9bd4;
            }
            QLineEdit {
                border: 2px solid #87ceeb;
                padding: 6px;
                border-radius: 8px;
                font-size: 14px;
            }
            QLabel {
                font-size: 13px;
                color: #333;
            }
        """)

        self.choose_file_btn = QPushButton("Choose File")
        self.choose_file_btn.clicked.connect(self.choose_file)
        layout.addWidget(self.choose_file_btn)

        self.tracker_input = QLineEdit("http://localhost:6969/announce")
        layout.addWidget(self.tracker_input)

        self.generate_btn = QPushButton("Generate Torrent")
        self.generate_btn.clicked.connect(self.generate_torrent_file)
        layout.addWidget(self.generate_btn)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.back_button = QPushButton("Back")
        self.back_button.setFixedSize(80, 35)
        self.back_button.clicked.connect(self.go_back)
        back_layout = QHBoxLayout()
        back_layout.addStretch()
        back_layout.addWidget(self.back_button)
        layout.addLayout(back_layout)

        self.setLayout(layout)

    def choose_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if file_path:
            self.choose_file_btn.setText(file_path)

    def generate_torrent_file(self):
        file_path = self.choose_file_btn.text()
        tracker_url = self.tracker_input.text()
        if not os.path.exists(file_path):
            self.status_label.setText("Invalid file path.")
            return
        out_dir = "../torrents"
        os.makedirs(out_dir, exist_ok=True)
        file_name = os.path.basename(file_path).split(".")[0]
        out_path = os.path.join(out_dir, file_name + ".torrent")
        try:
            generate_torrent(file_path, tracker_url, out_path)
            self.status_label.setText(f"Torrent generated: {out_path}")
            QMessageBox.information(self, "Success", f"Torrent file created at:\n{out_path}")
        except Exception as e:
            self.status_label.setText(f"Error: {e}")


class HomeScreen(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.background = ScrollingBackground("assets/cloud_scroll.png")
        self.background.setParent(self)
        self.gif_label = QLabel(self)
        self.gif_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.gif_label.setScaledContents(True)
        self.movie = QMovie("assets/banner.gif")
        self.gif_label.setMovie(self.movie)
        self.movie.start()

        self.overlay = QWidget(self)
        self.overlay_layout = QVBoxLayout(self.overlay)
        self.overlay_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.overlay_layout.setSpacing(30)
        self.overlay_layout.setContentsMargins(50, 30, 50, 30)

        self.title = QLabel("SkyTorrent")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setFont(QFont("Comic Sans MS", 28, QFont.Weight.Bold))
        self.title.setStyleSheet("background-color: white; color: #87ceeb; padding: 4px 10px; border-radius: 4px;")
        self.title.setMinimumWidth(200)
        self.title.setMaximumWidth(400)
        self.title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.gen_btn = QPushButton("Generate Torrent File")
        self.dl_btn = QPushButton("Download Torrent File")
        for btn in (self.gen_btn, self.dl_btn):
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #8b5a2b;
                    color: white;
                    font-size: 16px;
                    font-weight: bold;
                    padding: 10px 20px;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #a9743b;
                }
            """)
            btn.setMinimumSize(140, 40)
            btn.setMaximumSize(300, 50)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.gen_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        self.dl_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))

        buttons_layout = QHBoxLayout()
        buttons_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        buttons_layout.setSpacing(40)
        buttons_layout.addWidget(self.gen_btn)
        buttons_layout.addWidget(self.dl_btn)

        self.overlay_layout.addStretch()
        self.overlay_layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.overlay_layout.addLayout(buttons_layout)
        self.overlay_layout.addStretch()

    def resizeEvent(self, event):
        self.gif_label.setGeometry(0, 0, self.width(), self.height())
        self.background.resize(self.size())
        self.overlay.resize(self.size())
        super().resizeEvent(event)


class DownloadTorrentScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.stacked_widget = None

        # Modern layout
        self.layout = QVBoxLayout()
        self.layout.setSpacing(20)
        self.layout.setContentsMargins(40, 40, 40, 40)

        # Title and description
        title = QLabel("Download Torrent")
        title.setStyleSheet("color: white; font-size: 56px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(title)

        desc = QLabel("Select a .torrent file to start the download and track progress.")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: lightgray; font-size: 20px;")
        self.layout.addWidget(desc)

        self.setStyleSheet("""
            QPushButton {
                background-color: #4682B4;
                font-size: 16px;
                font-weight: bold;
                color: white;
                padding: 10px 16px;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #5a9bd4;
            }
            QLabel {
                font-size: 13px;
                color: #333;
            }
            QProgressBar {
                height: 20px;
                border-radius: 10px;
                border: 2px solid #87ceeb;
                background: white;
            }
            QProgressBar::chunk {
                background-color: #4682B4;
                border-radius: 10px;
            }
        """)
        self.choose_btn = QPushButton("Choose .torrent File")
        self.choose_btn.clicked.connect(self.load_torrent)
        self.layout.addWidget(self.choose_btn)

        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.layout.addWidget(self.progress)

        self.status_label = QLabel("")
        self.layout.addWidget(self.status_label)

        self.peer_info_label = QLabel("Peers connected: 0 | Peers completed: 0")
        self.peer_info_label.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        self.layout.addWidget(self.peer_info_label)

        self.back_btn = QPushButton("Back")
        self.back_btn.setFixedSize(80, 35)
        self.back_btn.clicked.connect(self.go_back)
        back_layout = QHBoxLayout()
        back_layout.addStretch()
        back_layout.addWidget(self.back_btn)
        self.layout.addLayout(back_layout)

        self.setLayout(self.layout)

    def set_stacked_widget(self, stacked):
        self.stacked_widget = stacked

    def go_back(self):
        if self.stacked_widget:
            self.stacked_widget.setCurrentIndex(0)

    def load_torrent(self):
        import random
        self.peer_id_label = QLabel()
        self.layout.insertWidget(2, self.peer_id_label)
        peer_id = b'-PC0001-' + bytes(f'{random.randint(0, 999999):06}', encoding='utf-8')
        self.peer_id_label.setText(f"Peer ID: {peer_id.decode('utf-8')}")
        path, _ = QFileDialog.getOpenFileName(self, "Open .torrent file", "", "Torrent Files (*.torrent)")
        if path:
            try:
                meta = parse_torrent_file(path)
                file_path = os.path.join("../files", meta['info']['name'])
                sm = StorageManager(file_path, meta['info']['length'], meta['info']['piece length'],
                                    meta['info']['pieces'])
                peer = TorrentPeer(peer_id, meta, sm)
                self.progress.setMaximum(len(sm.bitfield))
                self.status_label.setText("Downloading...")
                threading.Thread(target=self.monitor_progress, args=(sm,), daemon=True).start()
                peer.start()
            except Exception as e:
                self.status_label.setText(f"Error: {e}")

    def monitor_progress(self, storage):
        import time
        connected = 1
        completed = 0
        while True:
            done = storage.bitfield.count(True)
            self.peer_info_label.setText(f"Peers connected: {connected} | Peers completed: {completed}")
            self.progress.setValue(done)
            if done == len(storage.bitfield):
                completed += 1
                self.status_label.setText("Download complete!")
                self.back_btn.setVisible(True)
                break
            time.sleep(1)


def main():
    app = QApplication(sys.argv)
    stacked = QStackedWidget()

    home = HomeScreen(stacked)
    generate = GenerateTorrentScreen()
    generate.set_stacked_widget(stacked)
    download = DownloadTorrentScreen()
    download.set_stacked_widget(stacked)

    stacked.addWidget(home)
    stacked.addWidget(generate)
    stacked.addWidget(download)

    stacked.resize(960, 600)
    stacked.setWindowIcon(QIcon("assets/icon.png"))
    stacked.setWindowTitle("SkyTorrent")
    stacked.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
