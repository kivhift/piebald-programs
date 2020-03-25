#!/usr/bin/env python3

import os
import sqlite3
import sys

from datetime import datetime, time

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QApplication, QDialog, QPushButton, QLabel, QProgressBar
    , QHBoxLayout, QVBoxLayout
)

class SQLite3Connection(sqlite3.Connection):
    def __init__(self, *args, **kwargs):
        super(SQLite3Connection, self).__init__(*args, **kwargs)

        self.row_factory = sqlite3.Row
        self.text_factory = str if 2 == sys.version_info.major else bytes

    def __del__(self):
        self.close()
        s = super(SQLite3Connection, self)
        if hasattr(s, '__del__'): s.__del__()

class ClockInOut(QDialog):
    def __init__(self, parent = None):
        super(ClockInOut, self).__init__(parent)
        self.database = os.path.join(os.environ['HOME'], '.clkins.sqlite3')
        self.total = 0
        self.in_ = None
        self.text = ['Clock ' + x for x in 'In Out'.split()]

        timer = self.timer = QTimer(self)
        button = self.button = QPushButton('Clock')
        label = self.label = QLabel('Total:')
        progress = self.progress = QProgressBar()
        h_layout = QHBoxLayout()
        v_layout = QVBoxLayout()

        h_layout.addWidget(button)
        h_layout.addWidget(label)

        v_layout.addLayout(h_layout)
        v_layout.addWidget(progress)

        self.setLayout(v_layout)

        progress.setRange(0.0, 8.0 * 3600.0)
        progress.setValue(self.total)

        timer.setInterval(1000)
        timer.timeout.connect(self.update_progress)

        self.in_out()
        button.clicked.connect(self.in_out)

        self.setWindowTitle('Clock In/Out')

    def update_label(self):
        h, s = divmod(self.total, 3600)
        m, s = divmod(s, 60)
        self.label.setText(f'Total: {h:02d}:{m:02d}:{s:02d}')

    def set_progress(self):
        p = self.progress
        p.setValue(min(p.maximum(), self.total))

    def update_progress(self):
        self.total += int(self.timer.interval() / 1000.0)
        self.set_progress()
        self.update_label()

    def _no_data_init(self):
        self.in_ = 0
        self.button.setText(self.text[self.in_])

    def in_out(self):
        with SQLite3Connection(self.database) as conn:
            cur = conn.cursor()
            cur.execute('''create table if not exists clocks(
                timestamp datetime primary key, in_ boolean);''')
            midnight = datetime.combine(datetime.today(), time.min)
            if self.in_ is None:
                N = cur.execute('select count(*) from clocks;').fetchone()[0]
                if 0 == N:
                    return self._no_data_init()
                row = cur.execute(f'''select timestamp, in_ from clocks
                    where timestamp >= {midnight.timestamp()}
                    order by timestamp desc limit 1;''').fetchone()
                if row is None:
                    return self._no_data_init()
                ts, in_ = row
                self.in_ = in_
                self.button.setText(self.text[in_])
            else:
                cur.execute('insert into clocks values(?,?);'
                    , (datetime.now().timestamp(), self.in_ ^ 1))
                self.in_ ^= 1
                self.button.setText(self.text[self.in_])
            total = 0.0
            last_in = midnight.timestamp()
            for ts, in_ in cur.execute(f'''select timestamp, in_ from clocks
                    where timestamp >= {midnight.timestamp()}
                    order by timestamp asc;'''):
                if in_:
                    last_in = ts
                else:
                    total += ts - last_in
                    last_in = None
            if last_in is None:
                self.timer.stop()
            else:
                total += datetime.now().timestamp() - last_in
                self.timer.start()
            self.total = int(total)
            self.set_progress()
            self.update_label()

if '__main__' == __name__:
    app = QApplication(sys.argv)
    C = ClockInOut()
    C.show()
#    C.resize(200, C.size().height())
    C.move(0, 0)
    app.exec_()
