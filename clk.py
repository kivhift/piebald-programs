#!/usr/bin/env python3

import os
import sqlite3
import sys

from datetime import datetime, time, timedelta
from math import sqrt

__version__ = '1.3.0'

_schema = '''create table if not exists
    clocks(timestamp datetime primary key, in_ boolean);'''
_insert = 'insert into clocks values(?,?);'

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
    from PySide6.QtCore import Qt, QDateTime, QTimer
    from PySide6.QtWidgets import (
        QApplication, QPushButton, QLabel, QProgressBar
        , QGridLayout, QHBoxLayout, QVBoxLayout, QWidget, QMainWindow
        , QDialog, QDialogButtonBox, QDateTimeEdit, QCheckBox
    )

    class DateTimeInOutDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)

            vbox = QVBoxLayout(self)
            self.setLayout(vbox)

            e = QDateTimeEdit(QDateTime.currentDateTime(), parent=self)
            e.setDisplayFormat('yyyy-MM-dd hh:mm:ss')
            e.setCalendarPopup(True)
            vbox.addWidget(e)
            self.edit = e

            hbox = QHBoxLayout()
            cb = QCheckBox('In', parent=self)
            hbox.addWidget(cb)
            self.checkbox = cb

            buttons = QDialogButtonBox(
                QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
            )
            hbox.addWidget(buttons)
            vbox.addLayout(hbox)

            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)

        def timestamp(self):
            return float(self.edit.dateTime().toSecsSinceEpoch())

        def in_(self):
            return self.checkbox.isChecked()

    class ClockInOut(QWidget):
        def __init__(self, parent = None):
            super(ClockInOut, self).__init__(parent)
            self.database = database
            self.day_total = 0
            self.week_total = 0
            self.in_ = None
            self.text = ['Clock ' + x for x in 'In Out'.split()]

            self.seconds_per_day = 8 * 3600
            self.seconds_per_week = 5 * self.seconds_per_day
            self.done_time_fmt = '%H:%M:%S'

            timer = self.timer = QTimer(self)
            button = self.button = QPushButton('Clock')
            day_total_label = self.day_total_label = QLabel()
            week_total_label = self.week_total_label = QLabel()
            day_progress = self.day_progress = QProgressBar()
            week_progress = self.week_progress = QProgressBar()
            whats_done_label = self.whats_done_label = QLabel('Finish (?):')
            done_at_label = self.done_at_label = QLabel('??:??:??')

            layout = QGridLayout()
            self.setLayout(layout)
            layout.setColumnStretch(2, 2)

            align_right = Qt.Alignment() | Qt.AlignRight
            layout.addWidget(QLabel('Day:'), 0, 0, alignment=align_right)
            layout.addWidget(day_total_label, 0, 1, alignment=align_right)
            layout.addWidget(day_progress, 0, 2, 1, 2)

            layout.addWidget(QLabel('Week:'), 1, 0, alignment=align_right)
            layout.addWidget(week_total_label, 1, 1, alignment=align_right)
            layout.addWidget(week_progress, 1, 2, 1, 2)

            layout.addWidget(whats_done_label, 2, 0, alignment=align_right)
            layout.addWidget(done_at_label, 2, 1, alignment=align_right)
            layout.addWidget(button, 2, 3)

            day_progress.setRange(0, self.seconds_per_day)
            day_progress.setValue(self.day_total)

            week_progress.setRange(0, self.seconds_per_week)
            week_progress.setValue(self.week_total)

            timer.setInterval(1000)
            timer.timeout.connect(self.update_progress)

            self.in_out()
            button.clicked.connect(self.in_out)

            self.setFocusPolicy(Qt.StrongFocus)

        def keyReleaseEvent(self, event):
            # Use CTRL-T to edit the date/time, otherwise bubble up.
            if '\x14' != event.text():
                return super().keyReleaseEvent(event)

            dt = DateTimeInOutDialog(self)
            dt.setWindowTitle('Date/Time')
            if QDialog.Rejected == dt.exec():
                return

            with SQLite3Connection(self.database) as conn:
                cur = conn.cursor()
                cur.execute(_schema)
                cur.execute(_insert, (dt.timestamp(), dt.in_()))

            self.in_ = None
            self.in_out()

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
            delta = datetime.now().timestamp() - self.last_in_ts
            self.day_total = round(self.last_in_day_total + delta)
            self.week_total = round(self.last_in_week_total + delta)
            self.set_progress()
            self.update_totals()

        def in_out(self):
            now = datetime.now()
            now_ts = now.timestamp()
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
                    cur.execute(_insert, (now_ts, self.in_ ^ 1))
                    self.in_ ^= 1
                    self.button.setText(self.text[self.in_])
                if self.in_:
                    self.last_in_ts = now_ts
                    self.timer.start()
                else:
                    self.timer.stop()
                totals = day_totals(cur)
                self.day_total = round(totals[-1])
                self.week_total = round(sum(totals))
                if self.in_:
                    self.last_in_day_total = self.day_total
                    self.last_in_week_total = self.week_total

                    day_to_go = timedelta(
                        seconds = self.seconds_per_day - self.last_in_day_total
                    )
                    week_to_go = timedelta(
                        seconds = self.seconds_per_week - self.last_in_week_total
                    )

                    day_done, week_done = now + day_to_go, now + week_to_go
                    if week_done <= day_done:
                        self.whats_done_label.setText('Finish (W):')
                        self.done_at_label.setText(
                            week_done.strftime(self.done_time_fmt)
                        )
                    else:
                        self.whats_done_label.setText('Finish (D):')
                        self.done_at_label.setText(
                            day_done.strftime(self.done_time_fmt)
                        )
                self.set_progress()
                self.update_totals()

    app = QApplication(sys.argv)
    m = QMainWindow()
    m.setCentralWidget(ClockInOut())
    m.setWindowTitle('Clock In/Out')
    m.adjustSize()
    s = m.size()
    _2phi = 1 + sqrt(5)
    s.setWidth(round(_2phi * s.height()))
    m.resize(s)
    m.move(0, 0)
    m.show()
    sys.exit(app.exec())

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
