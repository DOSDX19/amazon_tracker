# main.py
import sys
from PySide6.QtWidgets import QApplication
from gui import ModernTrackerGUI


def main():
    app = QApplication(sys.argv)
    w = ModernTrackerGUI()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
