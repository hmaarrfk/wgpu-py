"""
An example demonstrating a qt app with a wgpu viz inside.
If needed, change the PySide6 import to e.g. PyQt6, PyQt5, or PySide2.

# run_example = false
"""

import importlib

# For the sake of making this example Just Work, we try multiple QT libs
for lib in ("PySide6", "PyQt6", "PySide2", "PyQt5"):
    try:
        QtWidgets = importlib.import_module(".QtWidgets", lib)
        break
    except ModuleNotFoundError:
        pass


from wgpu.gui.qt import WgpuWidget

from triangle import main
import PySide6

class MyWidget(QtWidgets.QWidget):
    def grab(self, rectangle: PySide6.QtCore.QRect=PySide6.QtCore.QRect(0, 0, -1, -1)):
        print("grabbing screenshot MyWidget")
        return super().grab(*args, **kwargs)


class ExampleWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.resize(640, 480)
        self.setWindowTitle("wgpu triangle embedded in a qt app")

        splitter = QtWidgets.QSplitter()

        self.button = QtWidgets.QPushButton("Hello world", self)
        self.button_grab = QtWidgets.QPushButton("Grab", self)
        self.canvas1 = WgpuWidget(splitter)
        self.canvas2 = WgpuWidget(splitter)
        self.my_widget = MyWidget()

        splitter.addWidget(self.canvas1)
        splitter.addWidget(self.canvas2)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.button, 0)
        layout.addWidget(self.button_grab, 0)
        layout.addWidget(self.my_widget)
        layout.addWidget(splitter, 1)
        self.setLayout(layout)

        self.button_grab.clicked.connect(self.grab_screenshot)

        self.show()

    def grab_screenshot(self):
        print("grabbing screenshot")
        qpix = self.grab()
        qpix.save("screenshot.png", "PNG")


app = QtWidgets.QApplication([])
example = ExampleWidget()

main(example.canvas1)
main(example.canvas2)

# Enter Qt event loop (compatible with qt5/qt6)
app.exec() if hasattr(app, "exec") else app.exec_()
