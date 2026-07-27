import sys

import random
import time
import threading
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout, QLineEdit, QCheckBox
from PySide6.QtGui import QIcon

from pynput import mouse, keyboard

myMouse = mouse.Controller()
myKeyboard = keyboard.Controller()
shouldRun = False

intervalMillis = 161

def work():
    while shouldRun:
        if pressKeyCk.isChecked():
            myKeyboard.press('r')
            myKeyboard.release('r')
        myMouse.click(mouse.Button.left)
        time.sleep((intervalMillis + random.randint(1, 19)) / 1000)


def startStop():
    global intervalMillis
    try:
        intervalMillis = int(intervalInput.text())
    except ValueError:
        intervalMillis = 1000
    global shouldRun
    shouldRun = not shouldRun

    if shouldRun:
        time.sleep(1)
        threading.Thread(target=work, daemon=True).start()

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
pressKeyCk = QCheckBox("with keypress (r)")
pressKeyCk.setChecked(True)

startStopBtn = QPushButton("start/stop (f8)")
startStopBtn.clicked.connect(startStop)

exitBtn = QPushButton("exit")
exitBtn.clicked.connect(app.exit)

window = QWidget()
window.setWindowIcon(QIcon("yclicker.ico"))
window.setWindowTitle("yclicker")
layout = QVBoxLayout()
layout.addWidget(intervalInput)
layout.addWidget(pressKeyCk)
layout.addWidget(startStopBtn)
layout.addWidget(exitBtn)

window.setLayout(layout)
window.show()
app.exec()


