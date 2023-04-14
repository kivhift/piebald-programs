#!/usr/bin/env python3

# TODO:
#
# - Be able to mark start of project work; perhaps Ctrl-M to bring up dialog to
# edit time and description. Be able to break down time by project, if
# applicable.

import sqlite3
import sys

from datetime import datetime, time, timedelta

__version__ = '1.7.0'

_schema = '''create table if not exists
    clocks(timestamp datetime primary key, in_ boolean);'''
_insert = 'insert into clocks values(?,?);'

_day_delta = timedelta(days=1)

class SQLite3Connection(sqlite3.Connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.row_factory = sqlite3.Row
        self.text_factory = str if 2 == sys.version_info.major else bytes

    def __del__(self):
        self.close()
        s = super()
        if hasattr(s, '__del__'): s.__del__()

def hms(s):
    h, s = divmod(round(s), 3600)
    m, s = divmod(s, 60)

    return h, m, s

def gui(database):
    from math import sqrt
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
        def __init__(self, parent=None):
            super().__init__(parent)
            self.database = database
            self.day_total = 0
            self.pay_period_total = 0
            self.in_ = None
            self.text = ['Clock ' + x for x in 'In Out'.split()]

            self.seconds_per_day = 8 * 3600
            self.seconds_per_pay_period = 10 * self.seconds_per_day
            self.done_time_fmt = '%H:%M:%S'

            timer = self.timer = QTimer(self)
            button = self.button = QPushButton('Clock')
            day_total_label = self.day_total_label = QLabel()
            pay_period_total_label = self.pay_period_total_label = QLabel()
            day_progress = self.day_progress = QProgressBar()
            pay_period_progress = self.pay_period_progress = QProgressBar()
            whats_done_label = self.whats_done_label = QLabel('Finish (?):')
            done_at_label = self.done_at_label = QLabel('??:??:??')

            layout = QGridLayout()
            self.setLayout(layout)
            layout.setColumnStretch(2, 2)

            align_right = Qt.Alignment() | Qt.AlignRight
            layout.addWidget(QLabel('Day:'), 0, 0, alignment=align_right)
            layout.addWidget(day_total_label, 0, 1, alignment=align_right)
            layout.addWidget(day_progress, 0, 2, 1, 2)

            layout.addWidget(QLabel('Period:'), 1, 0, alignment=align_right)
            layout.addWidget(pay_period_total_label, 1, 1, alignment=align_right)
            layout.addWidget(pay_period_progress, 1, 2, 1, 2)

            layout.addWidget(whats_done_label, 2, 0, alignment=align_right)
            layout.addWidget(done_at_label, 2, 1, alignment=align_right)
            layout.addWidget(button, 2, 3)

            day_progress.setRange(0, self.seconds_per_day)
            day_progress.setValue(self.day_total)

            pay_period_progress.setRange(0, self.seconds_per_pay_period)
            pay_period_progress.setValue(self.pay_period_total)

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
            h, m, s = hms(self.pay_period_total)
            self.pay_period_total_label.setText(f'{h:d}:{m:02d}:{s:02d}')

        def set_progress(self):
            p = self.day_progress
            p.setValue(min(p.maximum(), self.day_total))
            p = self.pay_period_progress
            p.setValue(min(p.maximum(), self.pay_period_total))

        def update_progress(self):
            delta = datetime.now().timestamp() - self.last_in_ts
            self.day_total = round(self.last_in_day_total + delta)
            self.pay_period_total = round(self.last_in_pay_period_total + delta)
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
                self.pay_period_total = round(sum(totals))
                if self.in_:
                    self.last_in_day_total = self.day_total
                    self.last_in_pay_period_total = self.pay_period_total

                    day_to_go = timedelta(
                        seconds = self.seconds_per_day - self.last_in_day_total
                    )
                    pay_period_to_go = timedelta(
                        seconds =
                            self.seconds_per_pay_period
                            - self.last_in_pay_period_total
                    )

                    day_done = now + day_to_go
                    pay_period_done = now + pay_period_to_go
                    if pay_period_done <= day_done:
                        self.whats_done_label.setText('Finish (P):')
                        self.done_at_label.setText(
                            pay_period_done.strftime(self.done_time_fmt)
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
    m.setWindowTitle(f'Clock In/Out v{__version__}')
    m.adjustSize()
    s = m.size()
    _2phi = 1 + sqrt(5)
    s.setWidth(round(_2phi * s.height()))
    m.resize(s)
    m.move(0, 0)
    m.show()
    sys.exit(app.exec())

def relative_pay_period_start(now):
    # At the time of writing, the last period start is 2023-01-14.
    known_start = datetime.fromisoformat('2023-01-14')
    period_length = timedelta(days=14)
    delta = now - known_start

    return now - (delta % period_length)

def day_totals(cur, start=None):
    now = datetime.now()
    totals = []
    _t = totals.append

    start = start or relative_pay_period_start(now)

    if 0 == cur.execute(f'''select count(*) from clocks
            where timestamp >= {start.timestamp()};''').fetchone()[0]:
        return totals

    while start < now:
        next_start = start + _day_delta
        total = 0.0
        last_in = start.timestamp()
        has_in_out = False
        for ts, in_ in cur.execute(f'''select timestamp, in_ from clocks
                where timestamp >= {start.timestamp()}
                and timestamp < {next_start.timestamp()}
                order by timestamp asc;'''):
            has_in_out = True
            if in_:
                last_in = ts
            else:
                total += ts - last_in
                last_in = None
        if has_in_out and last_in is not None:
            if now < next_start:
                total += now.timestamp() - last_in
            else:
                total += next_start.timestamp() - last_in
        _t(total)
        start = next_start

    return totals

def hours(database):
    date = relative_pay_period_start(datetime.now())
    with SQLite3Connection(database) as conn:
        grand_total = 0.0
        cur = conn.cursor()
        cur.execute(_schema)
        for total in day_totals(cur, date):
            if total > 0.0:
                grand_total += total
                h, m, s = hms(total)
                print(f'{date.date()}: {h:3d}:{m:02d}:{s:02d}', end=' = ')
                print(f'{h + (m * 60 + s) / 3600:6.2f}')
            date += _day_delta
        if grand_total > 0.0:
            h, m, s = hms(grand_total)
            print(f'     Total: {h:3d}:{m:02d}:{s:02d}', end=' = ')
            print(f'{h + (m * 60 + s) / 3600:6.2f}')

def main(args_list=None):
    import argparse
    import os

    arg_parser = argparse.ArgumentParser(
        description = 'Use a SQLite database to keep up with clock ins/outs'
    )
    _a = arg_parser.add_argument
    _a('--database', help = 'File to use for clock ins/outs')
    _a('--gui', action = 'store_true', help = 'Show the GUI')
    _a('--version', action = 'store_true', help = 'Show version')
    args = arg_parser.parse_args(args_list or sys.argv[1:])

    if args.version:
        print(os.path.basename(sys.argv[0]), __version__)
        return

    fn = gui if args.gui else hours
    fn(args.database or os.path.join(os.environ['HOME'], '.clkins.sqlite3'))

if '__main__' == __name__: main()
