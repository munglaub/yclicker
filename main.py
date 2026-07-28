import sys

import random
import time
import threading
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout, QLineEdit, QCheckBox, QRadioButton
from PySide6.QtGui import QIcon

from pynput import mouse, keyboard

myMouse = mouse.Controller()
myKeyboard = keyboard.Controller()
shouldRun = False

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

startStopBtn = QPushButton("start/stop (f8)")
startStopBtn.clicked.connect(startStop)

exitBtn = QPushButton("exit")
exitBtn.clicked.connect(app.exit)

rbClickonly = QRadioButton("click only")
rbClickPress = QRadioButton("click && r")
rbClickPress.setChecked(True)
rbKeyMode = QRadioButton("key mode")


window = QWidget()
window.setWindowIcon(QIcon("yclicker.ico"))
window.setWindowTitle("yclicker")
layout = QVBoxLayout()
layout.addWidget(intervalInput)
layout.addWidget(rbClickonly)
layout.addWidget(rbClickPress)
layout.addWidget(rbKeyMode)
layout.addWidget(startStopBtn)
layout.addWidget(exitBtn)

window.setLayout(layout)
window.show()
app.exec()


