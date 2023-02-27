#!/usr/bin/env python3

import argparse
import collections
import math
import mmap
import pathlib
import sys

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QMainWindow,
    QSpinBox,
)
from PySide6.QtGui import QAction, QBrush, QImage, QPixmap, QTransform,

# This function (and its partner-in-crime below) are adapted from the
# Summerfield book; Rapid GUI Programming with Python and Qt.
def create_action(
    parent, text, shortcut=None, tip=None, checkable=False
):
    action = QAction(text, parent)

    if shortcut is not None:
        action.setShortcut(shortcut)

    if tip is not None:
        # Bah, tooltips...
        action.setToolTip(tip)
        action.setStatusTip(tip)

    if checkable:
        action.setCheckable(True)

    return action

def add_actions(target, actions):
    for action in actions:
        if action is None:
            target.addSeparator()
        else:
            target.addAction(action)

PixelType = collections.namedtuple('PixelType', 'format bytes_per_pixel')
_f, _p = QImage.Format, PixelType
_pixels = {
    'Gray 8': _p(_f.Format_Grayscale8, 1),
    'Gray 16': _p(_f.Format_Grayscale16, 2),
    'BGR 888': _p(_f.Format_BGR888, 3),
    'RGB 888': _p(_f.Format_RGB888, 3),
}
del _f, _p

class FileSliceView(QMainWindow):
    def __init__(
        self,
        filename=None,
        start=0,
        length=0,
        width=0,
        scale=1,
        pixel_format=None,
    ):
        pixel_format = pixel_format or 'RGB 888'
        if pixel_format not in _pixels:
            raise ValueError(f'Invalid pixel format: {pixel_format}')

        super().__init__()

        self.setWindowTitle('File Slice View')
        size = self.size()
        size.setHeight(500)
        size.setWidth(round(500 * ((1 + math.sqrt(5)) / 2)))
        self.resize(size)

        self._image = None
        xform = self._xform = QTransform()

        sb = self._status_bar = self.statusBar()
        self._status_msg_timeout = 3000

        scene = self._scene = QGraphicsScene(self)
        view = self._view = QGraphicsView(scene)
        view.setTransform(xform)

        brush = QBrush()
        brush.setStyle(Qt.DiagCrossPattern)
        view.setBackgroundBrush(brush)

        self.setCentralWidget(view)

        foa = self._file_open_act = create_action(
            self,
            '&Open',
            'Ctrl+O',
            'Open file',
        )
        foa.triggered.connect(self.open_file)

        xa = self._quit_act = create_action(self, 'E&xit', 'Ctrl+X', 'Exit')
        xa.triggered.connect(self.close)

        mb = self._menubar = self.menuBar()
        file_menu = mb.addMenu('&File')
        add_actions(file_menu, (foa, None, xa))

        x = self._filename = QLabel(self)
        sb.addPermanentWidget(x)

        # Tried to use sys.maxsize but Shiboken complained about it not fitting
        # within a signed, 4-byte integer when calling .setRange()...
        range_max = 0x7fffffff
        x = self._start_sb = QSpinBox(self)
        x.setPrefix('Start: ')
        x.setRange(0, range_max)
        x.setValue(start)
        x.valueChanged.connect(self.adjust_image)
        sb.addPermanentWidget(x)

        x = self._length_sb = QSpinBox(self)
        x.setPrefix('Length: ')
        x.setRange(0, range_max)
        x.setValue(length)
        x.valueChanged.connect(self.adjust_image)
        sb.addPermanentWidget(x)

        wsb = self._width_sb = QSpinBox(self)
        wsb.setPrefix('Width: ')
        wsb.setRange(0, range_max)
        wsb.setValue(width)
        wsb.valueChanged.connect(self.adjust_image)
        sb.addPermanentWidget(wsb)

        ssb = self._scale_sb = QSpinBox(self)
        ssb.setPrefix('Scale: ')
        ssb.setRange(1, 100)
        ssb.setValue(scale)
        ssb.valueChanged.connect(self.adjust_scale)
        sb.addPermanentWidget(ssb)

        pcb = self._pixel_cb = QComboBox(self)
        pcb.addItems(list(sorted(_pixels)))
        pcb.setCurrentText(pixel_format)
        pcb.currentTextChanged.connect(self.adjust_image)
        sb.addPermanentWidget(pcb)

        if filename is not None:
            self.open_file(filename)

    def _update_image(self):
        mm = self._mmap
        L = len(mm)

        start = self._start_sb.value()
        if start >= L:
            self._status_bar.showMessage(
                'Start exceeds length of file',
                self._status_msg_timeout,
            )
            return

        length = min(self._length_sb.value() or L, L - start)
        if (start + length) > L:
            self._status_bar.showMessage(
                'Start plus length exceeds length of file',
                self._status_msg_timeout,
            )
            return

        pixel_type = _pixels[self._pixel_cb.currentText()]
        pixel_count = length // pixel_type.bytes_per_pixel

        if pixel_count < 1:
            self._status_bar.showMessage(
                'Not enough data for given pixel format',
                self._status_msg_timeout,
            )
            return

        W = self._width_sb.value() or int(math.sqrt(pixel_count))
        H = pixel_count // W

        image = QImage(
            memoryview(mm)[start : start + length],
            W,
            H,
            W * pixel_type.bytes_per_pixel,
            pixel_type.format,
        )

        scene, view = self._scene, self._view
        scene.clear()
        view.centerOn(scene.addPixmap(QPixmap.fromImage(image)))
        view.setSceneRect(0, 0, image.width(), image.height())

        start_sp = self._start_sb
        start_sp.setMaximum(L)

        length_sp = self._length_sb
        length_sp.setMaximum(L)
        length_sp.setValue(length)

        width_sb = self._width_sb
        width_sb.setMaximum(pixel_count)
        width_sb.setValue(W)

        self._image = image

    @Slot()
    def open_file(self, filename=None):
        filename = filename or QFileDialog.getOpenFileName(self)[0]
        if not filename:
            return

        in_file = self._in_file = open(filename, 'rb')
        self._mmap = mmap.mmap(in_file.fileno(), 0, access=mmap.ACCESS_READ)

        self._update_image()

        self._filename.setText(pathlib.Path(filename).name)

    @Slot()
    def adjust_scale(self, value):
        xform = self._xform
        xform.reset()
        xform.scale(value, value)
        self._view.setTransform(xform)

    @Slot()
    def adjust_image(self, _):
        if self._image is None:
            return

        self._update_image()

def non_negative_int(x):
    v = int(x)
    if v < 0:
        raise ValueError(f'Value should non-negative: {v}')

    return v

def positive_int(x):
    v = int(x)
    if v < 1:
        raise ValueError(f'Value should be positive: {v}')

    return v

arg_parser = argparse.ArgumentParser(
    description='View a file slice',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)
_a = arg_parser.add_argument
_a('-f', '--filename', help='File to use as input')
_a('-l', '--length', default=0, type=non_negative_int, help='Slice length to use')
_a(
    '-p',
    '--pixel-format',
    default='RGB 888',
    choices=list(sorted(_pixels)),
    help='Pixel format to use'
)
_a('-s', '--start', default=0, type=non_negative_int, help='Starting offset to use')
_a('-S', '--scale', default=1, type=positive_int, help='Scale to use')
_a('-w', '--width', default=0, type=non_negative_int, help='Width to use')
args = arg_parser.parse_args()

app = QApplication()
w = FileSliceView(
    filename=args.filename,
    start=args.start,
    length=args.length,
    width=args.width,
    scale=args.scale,
    pixel_format=args.pixel_format,
)
w.show()
sys.exit(app.exec())
