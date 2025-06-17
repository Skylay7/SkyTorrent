import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QStackedWidget
)
from PyQt6.QtCore import Qt

class HomeScreen(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        title = QLabel("SkyTorrent")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 32px; font-weight: bold;")

        gen_button = QPushButton("Generate Torrent File")
        gen_button.clicked.connect(self.goto_generate)

        down_button = QPushButton("Download Torrent File")
        down_button.clicked.connect(self.goto_download)

        layout.addWidget(title)
        layout.addWidget(gen_button)
        layout.addWidget(down_button)
        self.setLayout(layout)

    def goto_generate(self):
        self.stacked_widget.setCurrentIndex(1)  # switch to generation screen

    def goto_download(self):
        self.stacked_widget.setCurrentIndex(2)  # switch to download screen


class GenerateScreen(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        layout = QVBoxLayout()
        layout.addWidget(QLabel("This will be the Generate Torrent screen."))
        back_button = QPushButton("Back")
        back_button.clicked.connect(lambda: stacked_widget.setCurrentIndex(0))
        layout.addWidget(back_button)
        self.setLayout(layout)


class DownloadScreen(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        layout = QVBoxLayout()
        layout.addWidget(QLabel("This will be the Download Torrent screen."))
        back_button = QPushButton("Back")
        back_button.clicked.connect(lambda: stacked_widget.setCurrentIndex(0))
        layout.addWidget(back_button)
        self.setLayout(layout)


def main():
    app = QApplication(sys.argv)
    stacked_widget = QStackedWidget()

    home = HomeScreen(stacked_widget)
    generate = GenerateScreen(stacked_widget)
    download = DownloadScreen(stacked_widget)

    stacked_widget.addWidget(home)
    stacked_widget.addWidget(generate)
    stacked_widget.addWidget(download)

    stacked_widget.setFixedSize(600, 400)
    stacked_widget.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
