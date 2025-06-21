import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QStackedWidget, QSizePolicy
)
from PyQt6.QtGui import QPixmap, QFont, QColor, QPalette
from PyQt6.QtCore import Qt, QTimer


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

        # Set initial background color to match sky (prevents black flicker)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#87ceeb"))  # Light sky blue
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


class HomeScreen(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget

        # Background layer
        self.background = ScrollingBackground("assets/cloud_scroll.png")
        self.background.setParent(self)

        # Overlay layout
        self.overlay = QWidget(self)
        self.overlay_layout = QVBoxLayout(self.overlay)
        self.overlay_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.overlay_layout.setSpacing(30)
        self.overlay_layout.setContentsMargins(50, 30, 50, 30)

        # Title
        self.title = QLabel("SkyTorrent")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setFont(QFont("Comic Sans MS", 28, QFont.Weight.Bold))
        self.title.setStyleSheet("background-color: white; color: #87ceeb; padding: 4px 10px; border-radius: 4px;")
        self.title.setMinimumWidth(200)
        self.title.setMaximumWidth(400)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Buttons
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

        # Button row
        buttons_layout = QHBoxLayout()
        buttons_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        buttons_layout.setSpacing(40)
        buttons_layout.addWidget(self.gen_btn)
        buttons_layout.addWidget(self.dl_btn)

        # Final layout assembly
        self.overlay_layout.addStretch()
        self.overlay_layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.overlay_layout.addStretch()
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
    generate = PlaceholderScreen("Generate Torrent File", stacked)
    download = PlaceholderScreen("Download Torrent File", stacked)

    stacked.addWidget(home)
    stacked.addWidget(generate)
    stacked.addWidget(download)

    stacked.resize(960, 600)
    stacked.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
