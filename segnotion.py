#!/usr/bin/env python3

import io
import sys

import segno

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
)
from PySide6.QtSvgWidgets import QSvgWidget


class QRCodeWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('QR Code')
        self.setGeometry(0, 0, 300, 300)
        self.setCentralWidget(svg := QSvgWidget())

        buf = io.BytesIO()

        # with open(__file__, 'rb') as fin:
        #     segno.make(fin, micro=False).save(
        #         buf,
        #         kind='svg',
        #         dark='black',
        #         light='white',
        #         quiet_zone='lightblue',
        #     )

        segno.make('Yellow Submarine', micro=False).save(
            buf,
            kind='svg',
            # dark='darkorange',
            # light='yellow',
            dark='black',
            light='white',
            quiet_zone='lightblue',
        )

        svg.load(buf.getvalue())



def main():
    app = QApplication()
    win = QRCodeWindow()
    win.show()
    sys.exit(app.exec())


if '__main__' == __name__:
    main()
