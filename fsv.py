#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT
#
# Copyright 2023 Joshua Hughes <kivhift@gmail.com>

# TODO:
# - Use QPlainTextEdit.verticalScrollBar.valueChanged along with an iterator
# for the hexdump to be able to add lines at the bottom when needed instead of
# dumping everything to the widget up front since this is slow for larger
# files. The viewable part could be filled and then lines added when someone
# scrolls to the bottom.

import argparse
import collections
import math
import mmap
import pathlib
import sys

try:
    from PySide6.QtCore import Qt, Signal, Slot, QPointF
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QDockWidget,
        QFileDialog,
        QGraphicsScene,
        QGraphicsView,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QPlainTextEdit,
        QSpinBox,
        QWidget,
    )
    from PySide6.QtGui import (
        QAction,
        QBrush,
        QFont,
        QImage,
        QPixmap,
        QTransform,
    )
except ImportError:
    sys.exit(
        "Couldn't import PySide6. Perhaps you need to 'pip install PySide6'?"
    )

__version__ = '1.6.0'

# This function (and its partner-in-crime below) are adapted from the
# Summerfield book; Rapid GUI Programming with Python and Qt.
def create_action(
    parent, text, shortcut=None, tip=None, checkable=False, action=None
):
    action = action or QAction(text, parent)

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

PixelType = collections.namedtuple('PixelType', 'format bits_per_pixel')
_f, _p = QImage.Format, PixelType
_pixels = {
    'Mono': _p(_f.Format_Mono, 1),
    'Mono LSb': _p(_f.Format_MonoLSB, 1),
    'Gray 8': _p(_f.Format_Grayscale8, 8),
    'Gray 16': _p(_f.Format_Grayscale16, 16),
    'BGR 888': _p(_f.Format_BGR888, 24),
    'RGB 888': _p(_f.Format_RGB888, 24),
}
del _f, _p

class GraphicsScene(QGraphicsScene):
    mousePressPosition = Signal(QPointF)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def mousePressEvent(self, event):
        self.mousePressPosition.emit(event.scenePos())

class OffsetInfo(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        font = QFont('Consolas', 8)
        font.setStyleHint(QFont.Monospace)

        layout = QHBoxLayout()
        self.offset = QLabel()
        layout.addWidget(self.offset)
        self.values = QLabel()
        self.values.setFont(font)
        layout.addWidget(self.values)

        layout.addStretch()

        self.setLayout(layout)

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

        self.setWindowTitle(f'File Slice View v{__version__}')
        size = self.size()
        size.setHeight(500)
        size.setWidth(round(500 * ((1 + math.sqrt(5)) / 2)))
        self.resize(size)

        self._image = None
        self._mem_view = None
        xform = self._xform = QTransform()
        xform.scale(scale, scale)

        sb = self._status_bar = self.statusBar()
        self._status_msg_timeout = 3000

        scene = self._scene = GraphicsScene(self)
        scene.mousePressPosition.connect(self.show_byte_offset)

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

        hd = self._hexdump = QPlainTextEdit(self)
        hd.setReadOnly(True)
        hd.setLineWrapMode(QPlainTextEdit.NoWrap)
        font = QFont('Consolas', 8)
        font.setStyleHint(QFont.Monospace)
        hd.setFont(font)

        dw = self._hexdump_dock = QDockWidget('Hexdump', self)
        dw.setVisible(False)
        dw.setWidget(hd)
        dact = create_action(
            parent=None,
            text=None,
            shortcut='Ctrl+H',
            tip='View hexdump',
            checkable=True,
            action=dw.toggleViewAction(),
        )
        dact.triggered.connect(self._update_hexdump)
        view_menu = mb.addMenu('&View')
        add_actions(view_menu, (dact,))
        self.addDockWidget(Qt.RightDockWidgetArea, dw)

        hex_tt = self._hex_tt = [None] * 256
        for i in range(len(hex_tt)):
            hex_tt[i] = f'{i:02x}'

        dot = '.'
        prn_tt = self._prn_tt = [dot] * 256
        for i in range(32, 127):
            prn_tt[i] = chr(i)

        oi = self._offset_info = OffsetInfo(self)

        oid = self._offset_info_dock = QDockWidget('Offset Info', self)
        oid.setVisible(False)
        oid.setWidget(oi)
        self.addDockWidget(Qt.BottomDockWidgetArea, oid)

        if filename is not None:
            self.open_file(filename)

    @Slot(QPointF)
    def show_byte_offset(self, p):
        if (im := self._image) is None:
            return

        x = p.x()
        if x < 0.0:
            return

        # Truncate towards zero.
        x = int(x)
        w = im.width()
        if x >= w:
            return

        y = p.y()
        if y < 0.0:
            return

        # Similarly, truncate towards zero.
        y = int(y)
        if y >= im.height():
            return

        offset = (self._bits_per_pixel * (y * w + x)) // 8
        slice_length = max(1, self._bits_per_pixel // 8)

        oi = self._offset_info
        oi.offset.setText(f'{offset} / 0x{offset:x} / ')

        v = self._mem_view[offset : offset + slice_length]
        oi.values.setText(
            f'{" ".join(self._hex_tt[b] for b in v)}'
            f'  |{"".join(self._prn_tt[b] for b in v)}|'
        )

        self._offset_info_dock.setVisible(True)

    def _update_hexdump(self):
        if self._mem_view is None or not self._hexdump_dock.isVisible():
            return

        hd = self._hexdump
        hd.clear()

        hex_tt = self._hex_tt
        prn_tt = self._prn_tt
        buffer = self._mem_view
        start_address = self._start_sb.value()

        sz = len(buffer)
        fmt = f'{{:0{len(hex(start_address + sz)) - 2}x}}  {{:23s}}  {{:23s}}  |{{}}|'
        chunk_sz = 16
        chunk_half_sz = chunk_sz >> 1
        last_chunk = memoryview(b'')
        skipped = False
        lines = []
        _l = lines.append
        for offset in range(0, sz, chunk_sz):
            chunk = memoryview(buffer[offset : min(offset + chunk_sz, sz)])
            if chunk == last_chunk:
                skipped = True
                continue
            if skipped:
                _l('*')
                skipped = False
            _l(fmt.format(
                offset + start_address,
                ' '.join(hex_tt[b] for b in chunk[:chunk_half_sz]),
                ' '.join(hex_tt[b] for b in chunk[chunk_half_sz:]),
                ''.join(prn_tt[b] for b in chunk),
            ))
            last_chunk = chunk
        if skipped:
            _l('*')
        _l(f'{sz:x}')

        hd.setPlainText('\n'.join(lines))

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
        pixel_count = (length << 3) // pixel_type.bits_per_pixel

        if pixel_count < 1:
            self._status_bar.showMessage(
                'Not enough data for given pixel format',
                self._status_msg_timeout,
            )
            return

        W = self._width_sb.value() or int(math.sqrt(pixel_count))
        if W > pixel_count:
            self._status_bar.showMessage(
                'Too wide for given pixel count',
                self._status_msg_timeout,
            )
            return

        bit_width = W * pixel_type.bits_per_pixel
        bytes_per_line = bit_width >> 3
        if bit_width & 7:
            bytes_per_line += 1

        H = min(pixel_count // W, length // bytes_per_line) or 1

        mem_view = self._mem_view = memoryview(mm)[start : start + length]
        image = QImage(
            mem_view,
            W,
            H,
            bytes_per_line,
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
        self._bits_per_pixel = pixel_type.bits_per_pixel

        self._update_hexdump()

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
    v = int(x, 0)
    if v < 0:
        raise ValueError(f'Value should non-negative: {v}')

    return v

def positive_int(x):
    v = int(x, 0)
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
_a('--version', action='store_true', help='Print version')
args = arg_parser.parse_args()

if args.version:
    print(f'{pathlib.Path(__file__).name} {__version__}')
    sys.exit(0)

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
