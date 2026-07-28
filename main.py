import sys
from pathlib import Path

import random
import time
import threading
from PySide6.QtCore import Qt, QRect, QEvent, QTimer
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout, QLineEdit, QCheckBox, QRadioButton, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter, QAction

from pynput import mouse, keyboard

myMouse = mouse.Controller()
myKeyboard = keyboard.Controller()
shouldRun = False
window = None
tray = None
icon_path = Path(__file__).resolve().parent / "yclicker.ico"

intervalMillis = 161

def press(key):
    myKeyboard.press(key)
    myKeyboard.release(key)

def work():
    while shouldRun:
        if rbClickPress.isChecked():
            press('r')
            myMouse.click(mouse.Button.left)
        elif rbClickonly.isChecked():
            myMouse.click(mouse.Button.left)
        elif rbKeyMode.isChecked():
            press('r')
            time.sleep(0.05)
            press('b')
            time.sleep(0.05)
            press('b')
            time.sleep(0.05)
            press(keyboard.Key.esc)
        time.sleep((intervalMillis + random.randint(1, 19)) / 1000)


def iconForActive(active: bool) -> QIcon:
    base_pixmap = QPixmap(str(icon_path))
    if base_pixmap.isNull():
        base_pixmap = QPixmap(64, 64)
        base_pixmap.fill(Qt.transparent)

    if not active:
        icon = QIcon()
        for size in (16, 24, 32, 48, 64):
            icon.addPixmap(base_pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        return icon

    overlay = QPixmap(base_pixmap)
    painter = QPainter(overlay)
    painter.setRenderHint(QPainter.Antialiasing, True)
    radius = 42
    margin = 4
    painter.setBrush(QColor(76, 175, 80))
    painter.setPen(Qt.NoPen)
    rect = QRect(margin, margin, radius * 2, radius * 2)
    painter.drawEllipse(rect)
    painter.end()

    icon = QIcon()
    for size in (16, 24, 32, 48, 64):
        icon.addPixmap(overlay.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    return icon


def setControlsEnabled(enabled: bool):
    intervalInput.setEnabled(enabled)
    rbClickonly.setEnabled(enabled)
    rbClickPress.setEnabled(enabled)
    rbKeyMode.setEnabled(enabled)


class MainWindow(QWidget):
    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange and self.isMinimized():
            QTimer.singleShot(0, self.hide)
        super().changeEvent(event)


def setAppIcon(icon: QIcon):
    if window is not None:
        window.setWindowIcon(icon)
        handle = window.windowHandle()
        if handle is not None:
            handle.setIcon(icon)
        window.setWindowState(window.windowState())
    app.setWindowIcon(icon)
    app.processEvents()


def updateTrayIcon(active: bool):
    global tray
    if tray is None:
        return
    tray.setIcon(iconForActive(active))
    tray.setToolTip("yclicker – running" if active else "yclicker – stopped")


def onTrayActivated(reason):
    if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
        if window is not None:
            window.showNormal()
            window.activateWindow()
            window.raise_()


def startStop():
    global intervalMillis
    try:
        intervalMillis = int(intervalInput.text())
    except ValueError:
        intervalMillis = 1000
    global shouldRun
    shouldRun = not shouldRun

    if shouldRun:
        setControlsEnabled(False)
        startStopBtn.setStyleSheet("background-color: #4CAF50; color: white")
        active_icon = iconForActive(True)
        setAppIcon(active_icon)
        updateTrayIcon(True)
        threading.Thread(target=work, daemon=True).start()
    else:
        setControlsEnabled(True)
        startStopBtn.setStyleSheet("")
        inactive_icon = iconForActive(False)
        setAppIcon(inactive_icon)
        updateTrayIcon(False)

def myOnPress(key):
    if key == keyboard.Key.f8:
        startStop()

listener = keyboard.Listener(on_press=myOnPress)
listener.start()

if sys.platform == 'win32':
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("yclicker.app.1.0")

app = QApplication(sys.argv)

intervalInput = QLineEdit()
intervalInput.setText(str(intervalMillis))

startStopBtn = QPushButton("start/stop (f8)")
startStopBtn.clicked.connect(startStop)

exitBtn = QPushButton("exit")
exitBtn.clicked.connect(app.exit)

rbClickonly = QRadioButton("click only")
rbClickPress = QRadioButton("click && r")
rbClickPress.setChecked(True)
rbKeyMode = QRadioButton("key mode")


window = MainWindow()
inactive_icon = iconForActive(False)
window.setWindowIcon(inactive_icon)
app.setWindowIcon(inactive_icon)
window.setWindowTitle("yclicker")
layout = QVBoxLayout()

tray = QSystemTrayIcon(inactive_icon, app)
tray_menu = QMenu()
tray_toggle = QAction("Start/Stop")
tray_quit = QAction("Exit")
tray_toggle.triggered.connect(startStop)
tray_quit.triggered.connect(app.quit)
tray_menu.addAction(tray_toggle)
tray_menu.addAction(tray_quit)
tray.setContextMenu(tray_menu)
tray.activated.connect(onTrayActivated)
tray.show()
layout.addWidget(intervalInput)
layout.addWidget(rbClickonly)
layout.addWidget(rbClickPress)
layout.addWidget(rbKeyMode)
layout.addWidget(startStopBtn)
layout.addWidget(exitBtn)

window.setLayout(layout)
window.show()
app.exec()


