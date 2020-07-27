#!/usr/bin/env python3

import os
import sqlite3
import sys

from datetime import datetime, time, timedelta

__version__ = '1.0.1'

_schema = '''create table if not exists
    clocks(timestamp datetime primary key, in_ boolean);'''

class SQLite3Connection(sqlite3.Connection):
    def __init__(self, *args, **kwargs):
        super(SQLite3Connection, self).__init__(*args, **kwargs)

        self.row_factory = sqlite3.Row
        self.text_factory = str if 2 == sys.version_info.major else bytes

    def __del__(self):
        self.close()
        s = super(SQLite3Connection, self)
        if hasattr(s, '__del__'): s.__del__()

def hms(s):
    h, s = divmod(round(s), 3600)
    m, s = divmod(s, 60)

    return h, m, s

def gui(database):
    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import (
        QApplication, QPushButton, QLabel, QProgressBar
        , QHBoxLayout, QVBoxLayout, QWidget, QMainWindow
    )

    class ClockInOut(QWidget):
        def __init__(self, parent = None):
            super(ClockInOut, self).__init__(parent)
            self.database = database
            self.day_total = 0
            self.week_total = 0
            self.in_ = None
            self.text = ['Clock ' + x for x in 'In Out'.split()]

            timer = self.timer = QTimer(self)
            button = self.button = QPushButton('Clock')
            day_total_label = self.day_total_label = QLabel()
            week_total_label = self.week_total_label = QLabel()
            day_progress = self.day_progress = QProgressBar()
            week_progress = self.week_progress = QProgressBar()

            v_layout = QVBoxLayout()

            v_layout.addWidget(button)

            h_layout = QHBoxLayout()
            h_layout.addWidget(QLabel('Day:'))
            h_layout.addWidget(day_total_label)
            v_layout.addLayout(h_layout)

            v_layout.addWidget(day_progress)

            h_layout = QHBoxLayout()
            h_layout.addWidget(QLabel('Week:'))
            h_layout.addWidget(week_total_label)
            v_layout.addLayout(h_layout)

            v_layout.addWidget(week_progress)

            self.setLayout(v_layout)

            day_progress.setRange(0, 8 * 3600)
            day_progress.setValue(self.day_total)

            week_progress.setRange(0, 5 * day_progress.maximum())
            week_progress.setValue(self.week_total)

            timer.setInterval(1000)
            timer.timeout.connect(self.update_progress)

            self.in_out()
            button.clicked.connect(self.in_out)

        def update_totals(self):
            h, m, s = hms(self.day_total)
            self.day_total_label.setText(f'{h:d}:{m:02d}:{s:02d}')
            h, m, s = hms(self.week_total)
            self.week_total_label.setText(f'{h:d}:{m:02d}:{s:02d}')

        def set_progress(self):
            p = self.day_progress
            p.setValue(min(p.maximum(), self.day_total))
            p = self.week_progress
            p.setValue(min(p.maximum(), self.week_total))

        def update_progress(self):
            self.day_total += 1
            self.week_total += 1
            self.set_progress()
            self.update_totals()

        def in_out(self):
            with SQLite3Connection(self.database) as conn:
                cur = conn.cursor()
                cur.execute(_schema)
                midnight = datetime.combine(datetime.today(), time.min)
                if self.in_ is None:
                    row = cur.execute(f'''select timestamp, in_ from clocks
                        where timestamp >= {midnight.timestamp()}
                        order by timestamp desc limit 1;''').fetchone()
                    if row is None:
                        self.in_ = 0
                        self.button.setText(self.text[self.in_])
                        return
                    ts, in_ = row
                    self.in_ = in_
                    self.button.setText(self.text[in_])
                else:
                    cur.execute('insert into clocks values(?,?);'
                        , (datetime.now().timestamp(), self.in_ ^ 1))
                    self.in_ ^= 1
                    self.button.setText(self.text[self.in_])
                if self.in_:
                    self.timer.start()
                else:
                    self.timer.stop()
                totals = day_totals(cur)
                self.day_total = round(totals[-1])
                self.week_total = round(sum(totals))
                self.set_progress()
                self.update_totals()

    app = QApplication(sys.argv)
    m = QMainWindow()
    m.setCentralWidget(ClockInOut())
    m.setWindowTitle('Clock In/Out')
    m.move(0, 0)
    m.show()
    sys.exit(app.exec_())

def day_totals(cur):
    now = datetime.now()
    day_delta = timedelta(days = 1)
    totals = []
    _t = totals.append

    # This could be today and that's OK.
    midnight = datetime.combine(
        (now - now.weekday() * day_delta).date(), time.min)

    if 0 == cur.execute(f'''select count(*) from clocks
            where timestamp >= {midnight.timestamp()};''').fetchone()[0]:
        return totals

    while midnight < now:
        next_midnight = midnight + day_delta
        total = 0.0
        last_in = midnight.timestamp()
        has_in_out = False
        for ts, in_ in cur.execute(f'''select timestamp, in_ from clocks
                where timestamp >= {midnight.timestamp()}
                and timestamp < {next_midnight.timestamp()}
                order by timestamp asc;'''):
            has_in_out = True
            if in_:
                last_in = ts
            else:
                total += ts - last_in
                last_in = None
        if has_in_out and last_in is not None:
            if now < next_midnight:
                total += now.timestamp() - last_in
            else:
                total += next_midnight.timestamp() - last_in
        _t(total)
        midnight = next_midnight

    return totals

def hours(database):
    now = datetime.now()
    now_weekday = now.weekday()
    day_delta = timedelta(days = 1)
    date = (now - now_weekday * day_delta).date()
    with SQLite3Connection(database) as conn:
        grand_total = 0.0
        cur = conn.cursor()
        cur.execute(_schema)
        for total in day_totals(cur):
            if total > 0.0:
                grand_total += total
                h, m, s = hms(total)
                print(f'{date}: {h:3d}:{m:02d}:{s:02d}')
            date += day_delta
        if grand_total > 0.0:
            h, m, s = hms(grand_total)
            print(f'     Total: {h:3d}:{m:02d}:{s:02d}')

def main(args_list = None):
    import argparse
    arg_parser = argparse.ArgumentParser(
        description = 'Use a SQLite database to keep up with clock ins/outs')
    _a = arg_parser.add_argument
    _a('--database'
        , help = 'File to use for clock ins/outs')
    _a('--gui', action = 'store_true'
        , help = 'Show the GUI')
    _a('--version', action = 'store_true'
        , help = 'Show version')
    args = arg_parser.parse_args(args_list or sys.argv[1:])

    if args.version:
        print(os.path.basename(sys.argv[0]), __version__)
        return

    fn = gui if args.gui else hours
    fn(args.database or os.path.join(os.environ['HOME'], '.clkins.sqlite3'))

if '__main__' == __name__: main()
