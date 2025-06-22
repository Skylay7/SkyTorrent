import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QStackedWidget, QFileDialog, QLineEdit, QSizePolicy, QMessageBox
)
from PyQt6.QtGui import QPixmap, QFont, QColor, QPalette
from PyQt6.QtCore import Qt, QTimer
import os
from SkyTorrent.utils.torrent_generator import generate_torrent

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

    def resizeEvent(self, event):
        self.update_backgrounds()
        super().resizeEvent(event)

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
        layout = QVBoxLayout()

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
        self.back_button.clicked.connect(self.go_back)
        layout.addWidget(self.back_button)

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
        self.background.resize(self.size())
        self.overlay.resize(self.size())
        super().resizeEvent(event)


class PlaceholderScreen(QWidget):
    def __init__(self, label_text, stacked_widget):
        super().__init__()
        layout = QVBoxLayout()
        label = QLabel(label_text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        back = QPushButton("Back")
        back.clicked.connect(lambda: stacked_widget.setCurrentIndex(0))
        layout.addWidget(label)
        layout.addWidget(back)
        self.setLayout(layout)


def main():
    app = QApplication(sys.argv)
    stacked = QStackedWidget()

    home = HomeScreen(stacked)
    generate = GenerateTorrentScreen()
    generate.set_stacked_widget(stacked)
    download = PlaceholderScreen("Download Torrent File", stacked)

    stacked.addWidget(home)
    stacked.addWidget(generate)
    stacked.addWidget(download)

    stacked.resize(960, 600)
    stacked.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
