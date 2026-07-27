import sys

import random
import time
import threading
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout, QLineEdit

from pynput import mouse, keyboard

myMouse = mouse.Controller()
myKeyboard = keyboard.Controller()
shouldRun = False

intervalMillis = 1000

def work():
    while shouldRun:
        myKeyboard.press('r')
        myKeyboard.release('r')
        time.sleep((intervalMillis + random.randint(1, 50)) / 1000)


def startStop():
    global intervalMillis
    try:
        intervalMillis = int(intervalInput.text())
    except ValueError:
        intervalMillis = 1000
    global shouldRun
    shouldRun = not shouldRun

    if shouldRun:
        threading.Thread(target=work, daemon=True).start()

def myOnPress(key):
    if key == keyboard.Key.f8:
        startStop()

listener = keyboard.Listener(on_press=myOnPress)
listener.start()


app = QApplication(sys.argv)

intervalInput = QLineEdit()
intervalInput.setText(str(intervalMillis))

startStopBtn = QPushButton("start/stop (f8)")
startStopBtn.clicked.connect(startStop)

exitBtn = QPushButton("exit")
exitBtn.clicked.connect(app.exit)

window = QWidget()
window.setWindowTitle("yclicker")
layout = QVBoxLayout()
layout.addWidget(intervalInput)
layout.addWidget(startStopBtn)
layout.addWidget(exitBtn)

window.setLayout(layout)
window.show()
app.exec()


