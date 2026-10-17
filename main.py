import sys
import os
import importlib
from pathlib import Path

from dataclasses import dataclass, asdict
import json
import random
import time
import threading
from PySide6.QtCore import Qt, QRect, QObject, Slot, Signal
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout, QLineEdit, QCheckBox, QRadioButton, QSystemTrayIcon, QMenu, QLabel, QMainWindow, QMessageBox
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter, QAction

IS_WAYLAND = sys.platform.startswith("linux") and (
    os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
    or bool(os.environ.get("WAYLAND_DISPLAY"))
)

if IS_WAYLAND:
    wayland_support = importlib.import_module("wayland_support")
    GlobalShortcutPortal = wayland_support.GlobalShortcutPortal
    ToggleIpcServer = wayland_support.ToggleIpcServer
    WaylandInput = wayland_support.WaylandInput
    request_running_toggle = wayland_support.request_running_toggle
else:
    from pynput import mouse, keyboard


if IS_WAYLAND and "--toggle" in sys.argv[1:]:
    if request_running_toggle():
        sys.exit(0)
    sys.exit("yclicker is not running; the Wayland F8 fallback could not toggle it.")

input_backend = None
shouldRun = False
window = None
tray = None
def resource_path(name: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parent
    return base_path / name

icon_path = resource_path("yclicker.ico")

CONFIG_FILE = resource_path("config.json")

@dataclass
class Config:
    intervalMillis: int = 161
    withKeypress: bool = True
    keypressDelayMillis: int = 0

def loadConfig():
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open() as f:
            return Config(**json.load(f))
    return Config()
def saveConfig():
    config.intervalMillis = int(intervalInput.text())
    config.withKeypress = pressKeyCk.isChecked()
    config.keypressDelayMillis = int(keypressDelayInput.text())
    with CONFIG_FILE.open("w") as f:
        json.dump(asdict(config), f, indent=4)

config = loadConfig()


class PynputInput:
    def __init__(self):
        self.mouse = mouse.Controller()
        self.keyboard = keyboard.Controller()

    def click_left(self):
        self.mouse.click(mouse.Button.left)

    def press_r(self):
        self.keyboard.press("r")
        self.keyboard.release("r")


def work():
    global config
    while shouldRun:
        if config.withKeypress:
            if config.keypressDelayMillis > 0:
                time.sleep(config.keypressDelayMillis / 1000)
            input_backend.press_r()
        input_backend.click_left()
        time.sleep((config.intervalMillis + random.randint(1, 10)) / 1000)


def iconForActive(active: bool) -> QIcon:
    base_pixmap = QPixmap(str(icon_path))
    if base_pixmap.isNull():
        base_pixmap = QPixmap(64, 64)
        base_pixmap.fill(Qt.GlobalColor.transparent)

    if not active:
        icon = QIcon()
        for size in (16, 24, 32, 48, 64):
            icon.addPixmap(base_pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        return icon

    overlay = QPixmap(base_pixmap)
    painter = QPainter(overlay)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    radius = 42
    margin = 4
    painter.setBrush(QColor(76, 175, 80))
    painter.setPen(Qt.PenStyle.NoPen)
    rect = QRect(margin, margin, radius * 2, radius * 2)
    painter.drawEllipse(rect)
    painter.end()

    icon = QIcon()
    for size in (16, 24, 32, 48, 64):
        icon.addPixmap(overlay.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
    return icon


def setControlsEnabled(enabled: bool):
    intervalInput.setEnabled(enabled)
    keypressDelayInput.setEnabled(enabled)
    pressKeyCk.setEnabled(enabled)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.texture = QPixmap(str(resource_path("steel.png")))

    def closeEvent(self, event):
        self.hide()
        event.accept()

    def restoreFromTray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawTiledPixmap(self.rect(), self.texture)
        super().paintEvent(event)


def setAppIcon(icon: QIcon):
    global window
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
            window.restoreFromTray()


class HotkeyRelay(QObject):
    toggle_requested = Signal()

    def __init__(self):
        super().__init__()
        self.toggle_requested.connect(self.toggle, Qt.ConnectionType.QueuedConnection)

    def request_toggle(self):
        self.toggle_requested.emit()

    @Slot()
    def toggle(self):
        startStop()


def startStop():
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
    if key == keyboard.Key.f8 and hotkey_relay is not None:
        hotkey_relay.request_toggle()


listener = None
hotkey_relay = None
wayland_portal = None
toggle_ipc = None

if sys.platform == 'win32':
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("yclicker.app.1.0")

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
try:
    input_backend = WaylandInput() if IS_WAYLAND else PynputInput()
except RuntimeError as error:
    QMessageBox.critical(None, "yclicker input error", str(error))
    sys.exit(1)

hotkey_relay = HotkeyRelay()
if not IS_WAYLAND:
    listener = keyboard.Listener(on_press=myOnPress, suppress=False)
    listener.start()
    app.aboutToQuit.connect(listener.stop)

intervalInput = QLineEdit()
intervalInput.setText(str(config.intervalMillis))
intervalInput.textChanged.connect(saveConfig)

keypressDelayInput = QLineEdit()
keypressDelayInput.setText(str(config.keypressDelayMillis))
keypressDelayInput.textChanged.connect(saveConfig)

startStopBtn = QPushButton("start/stop (f8)")
startStopBtn.clicked.connect(startStop)

exitBtn = QPushButton("exit")
exitBtn.clicked.connect(app.exit)

pressKeyCk = QCheckBox("with keypress (r)")
pressKeyCk.setChecked(config.withKeypress)
pressKeyCk.checkStateChanged.connect(saveConfig)

header = QLabel("yClicker Pro")
headerfont = header.font()
headerfont.setBold(True)
header.setFont(headerfont)

footer = QLabel("version 3.0.0 special edition (certified)")
shortcutStatus = QLabel(f"Status: {'Wayland' if IS_WAYLAND else 'X11'}")
shortcutStatus.setWordWrap(True)



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
layout.addWidget(header)
layout.addWidget(QLabel("click interval (ms)"))
layout.addWidget(intervalInput)
layout.addWidget(pressKeyCk)
layout.addWidget(QLabel("delay keypress (ms)"))
layout.addWidget(keypressDelayInput)
layout.addWidget(startStopBtn)
layout.addWidget(exitBtn)
layout.addWidget(footer)
layout.addWidget(shortcutStatus)
if IS_WAYLAND:
    wayland_portal = GlobalShortcutPortal()
    wayland_portal.toggle_requested.connect(hotkey_relay.request_toggle, Qt.ConnectionType.QueuedConnection)
    wayland_portal.status_changed.connect(
        lambda status: shortcutStatus.setText(f"Status: {status}")
    )
    wayland_portal.start()
    try:
        toggle_ipc = ToggleIpcServer(hotkey_relay.request_toggle)
        toggle_ipc.start()
    except RuntimeError:
        shortcutStatus.setText("Status: Error")
    app.aboutToQuit.connect(wayland_portal.stop)
    app.aboutToQuit.connect(input_backend.close)
    if toggle_ipc is not None:
        app.aboutToQuit.connect(toggle_ipc.close)


window.setLayout(layout)
window.show()

style_path = resource_path("style.qss")
if style_path.exists():
    with style_path.open("r") as f:
        app.setStyleSheet(f.read())

app.exec()


