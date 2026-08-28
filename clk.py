#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT
#
# Copyright 2020-2026 Joshua Hughes <kivhift@gmail.com>

# TODO:
#
# - Be able to mark start of project work; perhaps Ctrl-M to bring up dialog to
# edit time and description. Be able to break down time by project, if
# applicable.

import hashlib
import mmap
import os
import pathlib
import sqlite3
import sys

from datetime import datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

__version__ = '1.14.0'

_schema = '''create table if not exists
    clocks(timestamp datetime primary key, in_ boolean);'''
_insert = 'insert into clocks values(?,?);'

_day_delta = timedelta(days=1)
_seconds_per_hour = 3600
_seconds_per_period = 80 * _seconds_per_hour


class SQLite3Connection(sqlite3.Connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.row_factory = sqlite3.Row
        self.text_factory = str if 2 == sys.version_info.major else bytes

    def __del__(self):
        self.close()
        s = super()
        if hasattr(s, '__del__'):
            s.__del__()


# ``round()`` uses Banker's rounding. Re-define it for our use case.
def round(x):
    if isinstance(x, int):
        return x

    return int(Decimal(x).quantize(_round_exp, ROUND_HALF_UP))


# Cache this instead of instantiating it each time.
_round_exp = Decimal(1)


def hms(s):
    h, s = divmod(round(s), _seconds_per_hour)
    m, s = divmod(s, 60)

    return h, m, s


def s2h(s):
    return round(s) / _seconds_per_hour


def s2p(s):
    return (100.0 * s) / _seconds_per_period


def path_hash(path, *, algo=None):
    algo = algo or 'md5'
    path = pathlib.Path(path)

    if not path.exists():
        return 'non-extant'

    if 0 == path.stat().st_size:
        return hashlib.new(algo).hexdigest()

    with (
        path.open('rb') as f,
        mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm,
    ):
        return hashlib.new(algo, memoryview(mm)).hexdigest()


def home_relative(path):
    p = pathlib.Path(path).absolute()
    home = p.home()

    return (
        f'~{os.path.sep}{p.relative_to(home)}'
        if p.is_relative_to(home)
        else str(p)
    )


def gui(database):
    from collections import namedtuple
    from math import ceil, floor, sqrt

    from PySide6.QtCore import QDateTime, QRectF, Qt, QTimer, Slot
    from PySide6.QtGui import (
        QAction,
        QColor,
        QFont,
        QIcon,
        QImage,
        QPainter,
        QPixmap,
    )
    from PySide6.QtWidgets import (
        QAbstractScrollArea,
        QApplication,
        QCheckBox,
        QDateTimeEdit,
        QDialog,
        QDialogButtonBox,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMenu,
        QProgressBar,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    # This function (and its partner-in-crime below) are adapted from the
    # Summerfield book; Rapid GUI Programming with Python and Qt.
    def create_action(
        parent,
        text,
        *,
        action=None,
        shortcut=None,
        handler=None,
        tip=None,
        checkable=False,
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

        if handler is not None:
            action.triggered.connect(handler)

        return action

    def add_actions(target, *actions):
        for action in actions:
            if action is None:
                target.addSeparator()
            else:
                target.addAction(action)

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

    class HoursReportDialog(QDialog):
        def __init__(self, parent=None, database=None):
            super().__init__(parent)

            def twi(text):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() ^ Qt.ItemFlags.ItemIsEditable)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                return item

            vbox = QVBoxLayout(self)
            vbox.setSizeConstraint(vbox.SizeConstraint.SetFixedSize)
            vbox.setContentsMargins(0, 0, 0, 0)

            headers = 'Date Σ % Δ'.split()
            table = QTableWidget(0, len(headers))
            vbox.addWidget(table)

            table.setAlternatingRowColors(True)
            table.verticalHeader().hide()
            table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
            table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            table.setHorizontalHeaderLabels(headers)

            # Cache this rather than instantiating it every time
            # ``hours_str()`` needs it.
            _hours_exp = Decimal('1.0')

            def hours_str(s):
                return str(Decimal(s2h(s)).quantize(_hours_exp, ROUND_HALF_UP))

            def get_and_add_row():
                row = table.rowCount()
                table.setRowCount(row + 1)

                return row

            date = relative_pay_period_start(datetime.now())
            grand_total = 0.0
            with SQLite3Connection(database) as conn:
                cur = conn.cursor()
                cur.execute(_schema)
                for total in day_totals(cur, date):
                    if total > 0.0:
                        grand_total += total
                        row = get_and_add_row()
                        table.setItem(row, 0, twi(str(date.date())))
                        table.setItem(row, 1, twi(hours_str(grand_total)))
                        table.setItem(row, 2, twi(f'{s2p(grand_total):.1f}'))
                        table.setItem(row, 3, twi(hours_str(total)))
                    date += _day_delta

            table.resizeColumnsToContents()
            table.resizeRowsToContents()

    class FileInfoDialog(QDialog):
        def __init__(self, parent=None, database=None):
            super().__init__(parent)

            layout = QGridLayout()
            self.setLayout(layout)
            add = layout.addWidget
            right = Qt.Alignment() | Qt.AlignRight
            mono = QFont('Hack')

            database_hash_label = QLabel(path_hash(database))
            script_hash_label = QLabel(path_hash(__file__))

            database_hash_label.setFont(mono)
            script_hash_label.setFont(mono)

            add(QLabel('Database Path:'), 0, 0, alignment=right)
            add(QLabel(home_relative(database)), 0, 1)
            add(QLabel('Database MD5:'), 1, 0, alignment=right)
            add(database_hash_label, 1, 1)
            add(QLabel('Script Path:'), 2, 0, alignment=right)
            add(QLabel(home_relative(__file__)), 2, 1)
            add(QLabel('Script MD5:'), 3, 0, alignment=right)
            add(script_hash_label, 3, 1)

    class ClockInOut(QWidget):
        Progress = namedtuple('Progress', 'day_fraction period_fraction')

        def __init__(self, parent=None, database=None):
            super().__init__(parent)
            self.database = database
            self.day_total = 0
            self.pay_period_total = 0
            self.in_ = None

            self.seconds_per_day = 8 * _seconds_per_hour
            self.seconds_per_pay_period = _seconds_per_period
            self.time_fmt = '%H:%M:%S'

            timer = self.timer = QTimer(self)
            day_total_label = self.day_total_label = QLabel()
            pay_period_total_label = self.pay_period_total_label = QLabel()
            day_progress = self.day_progress = QProgressBar()
            pay_period_progress = self.pay_period_progress = QProgressBar()
            whats_done_label = self.whats_done_label = QLabel('Finish (?):')
            done_at_label = self.done_at_label = QLabel('??:??:??')
            tenth_step_label = self.tenth_step_label = QLabel('0% @ ??:??:??')
            tenth_step_label.setFrameStyle(QFrame.Box | QFrame.Sunken)
            datetime_label = self.datetime_label = QLabel('??-?? ??:??:??')

            layout = QGridLayout()
            self.setLayout(layout)
            layout.setColumnStretch(2, 2)

            align_right = Qt.Alignment() | Qt.AlignRight
            layout.addWidget(QLabel('Day:'), 0, 0, alignment=align_right)
            layout.addWidget(day_total_label, 0, 1, alignment=align_right)
            layout.addWidget(day_progress, 0, 2, 1, 2)

            layout.addWidget(QLabel('Period:'), 1, 0, alignment=align_right)
            layout.addWidget(
                pay_period_total_label, 1, 1, alignment=align_right
            )
            layout.addWidget(pay_period_progress, 1, 2, 1, 2)

            layout.addWidget(whats_done_label, 2, 0, alignment=align_right)
            layout.addWidget(done_at_label, 2, 1, alignment=align_right)
            layout.addWidget(
                tenth_step_label,
                2,
                2,
                alignment=Qt.Alignment() | Qt.AlignCenter,
            )
            layout.addWidget(datetime_label, 2, 3, alignment=align_right)

            day_progress.setRange(0, self.seconds_per_day)
            day_progress.setValue(self.day_total)

            pay_period_progress.setRange(0, self.seconds_per_pay_period)
            pay_period_progress.setValue(self.pay_period_total)

            timer.setInterval(1000)
            timer.timeout.connect(self.update_progress)

            self.in_out()

            self.setFocusPolicy(Qt.StrongFocus)

            self.menu_actions = (
                create_action(
                    self,
                    'Enter Date/Time',
                    shortcut='Ctrl+E',
                    handler=self.input_datetime,
                ),
                create_action(
                    self,
                    "Show File Info",
                    shortcut='Ctrl+F',
                    handler=self.show_file_info,
                ),
                create_action(
                    self,
                    'Report Hours',
                    shortcut='Ctrl+R',
                    handler=self.show_report,
                ),
            )

            self.quit_act = create_action(
                self, 'Quit', shortcut='Ctrl+Q', handler=QApplication.quit
            )

            add_actions(self, self.quit_act, *self.menu_actions)

        def contextMenuEvent(self, event):  # noqa: N802
            menu = QMenu(self)
            add_actions(menu, *self.menu_actions)
            menu.exec(event.globalPos())

        @Slot()
        def show_report(self):
            report = HoursReportDialog(self, database=self.database)
            report.setWindowTitle('Hours Report')
            report.exec()

        @Slot()
        def input_datetime(self):
            dt = DateTimeInOutDialog(self)
            dt.setWindowTitle('Date/Time')
            dt.checkbox.setChecked(not self.in_)
            if QDialog.Rejected == dt.exec():
                return

            with SQLite3Connection(self.database) as conn:
                cur = conn.cursor()
                cur.execute(_schema)
                cur.execute(_insert, (dt.timestamp(), dt.in_()))

            self.in_ = None
            self.in_out()

        @Slot()
        def show_file_info(self):
            fi = FileInfoDialog(self, self.database)
            fi.setWindowTitle('File Info')
            fi.exec()

        def update_totals(self):
            h, m, s = hms(self.day_total)
            self.day_total_label.setText(f'{h:d}:{m:02d}:{s:02d}')
            h, m, s = hms(self.pay_period_total)
            self.pay_period_total_label.setText(f'{h:d}:{m:02d}:{s:02d}')

        def get_progress(self):
            return type(self).Progress(
                day_fraction=self.day_total / self.seconds_per_day,
                period_fraction=self.pay_period_total
                / self.seconds_per_pay_period,
            )

        def set_progress(self):
            p = self.day_progress
            p.setValue(min(p.maximum(), self.day_total))
            p = self.pay_period_progress
            p.setValue(min(p.maximum(), self.pay_period_total))

        def update_progress(self):
            now = datetime.now()
            delta = now.timestamp() - self.last_in_ts
            self.day_total = round(self.last_in_day_total + delta)
            self.pay_period_total = round(self.last_in_pay_period_total + delta)
            self.set_progress()
            self.update_totals()

            if now >= self.this_tenth_done:
                next_tenth = (
                    floor(
                        10
                        * (self.pay_period_total / self.seconds_per_pay_period)
                    )
                    + 1
                )
                pp_tenth = timedelta(
                    seconds=round(self.seconds_per_pay_period / 10)
                )
                self.this_tenth_done = this_tenth_done = now + pp_tenth
                self.tenth_step_label.setText(
                    f'{10 * next_tenth}%'
                    f' @ {this_tenth_done.strftime(self.time_fmt)}'
                )

            self.datetime_label.setText(
                f'{now.month:02d}-{now.day:02d}'
                f' {now.hour:02d}:{now.minute:02d}:{now.second:02d}'
            )

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
                        return
                    ts, in_ = row
                    self.in_ = in_
                else:
                    cur.execute(_insert, (now_ts, self.in_ ^ 1))
                    self.in_ ^= 1
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
                        seconds=self.seconds_per_day - self.last_in_day_total
                    )
                    pay_period_to_go = timedelta(
                        seconds=self.seconds_per_pay_period
                        - self.last_in_pay_period_total
                    )

                    day_done = now + day_to_go
                    pay_period_done = now + pay_period_to_go
                    if pay_period_done <= day_done:
                        self.whats_done_label.setText('Finish (P):')
                        self.done_at_label.setText(
                            pay_period_done.strftime(self.time_fmt)
                        )
                    else:
                        self.whats_done_label.setText('Finish (D):')
                        self.done_at_label.setText(
                            day_done.strftime(self.time_fmt)
                        )

                    next_tenth = (
                        floor(
                            10
                            * (
                                self.last_in_pay_period_total
                                / self.seconds_per_pay_period
                            )
                        )
                        + 1
                    )
                    next_tenth_to_go = timedelta(
                        seconds=ceil(
                            (next_tenth / 10) * self.seconds_per_pay_period
                        )
                        - self.last_in_pay_period_total
                    )
                    self.this_tenth_done = this_tenth_done = (
                        now + next_tenth_to_go
                    )
                    self.tenth_step_label.setText(
                        f'{10 * next_tenth}%'
                        f' @ {this_tenth_done.strftime(self.time_fmt)}'
                    )

                self.set_progress()
                self.update_totals()

    app = QApplication(sys.argv)
    cio = ClockInOut(database=database)

    icon_w = 256
    icon_image = QImage(icon_w, icon_w, QImage.Format_ARGB32)
    period_r = icon_w / 2
    day_r = period_r / sqrt(2)
    day_w = 2 * day_r
    icon_period_rect = QRectF(0, 0, icon_w, icon_w)
    delta_r = period_r - day_r
    icon_day_rect = QRectF(delta_r, delta_r, day_w, day_w)
    hole_r = day_r - delta_r
    hole_w = 2 * hole_r
    hole_offset = 2 * delta_r
    hole_rect = QRectF(hole_offset, hole_offset, hole_w, hole_w)
    start_angle = 90 * 16
    full_arc = 360 * 16
    bg_color = QColor('#000000')
    period_color = QColor('#ff0000')
    day_color = QColor('#00ff00')
    painter = QPainter()

    def update_app_icon():
        prog = cio.get_progress()
        icon_image.fill(0)
        painter.begin(icon_image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        painter.drawPie(icon_period_rect, 0, full_arc)
        painter.setBrush(period_color)
        painter.drawPie(
            icon_period_rect,
            start_angle,
            -round(full_arc * prog.period_fraction),
        )
        painter.setBrush(day_color)
        painter.drawPie(
            icon_day_rect, start_angle, -round(full_arc * prog.day_fraction)
        )

        painter.setBrush(bg_color)
        painter.drawPie(hole_rect, 0, full_arc)
        painter.end()

        app.setWindowIcon(QIcon(QPixmap.fromImage(icon_image)))

    t = QTimer(app)
    # Not sure if it's discernible, but let's update every degree increase for
    # the day: 8 * 3600 / 360 = 80 ==> 80000ms.
    t.setInterval(80000)
    t.timeout.connect(update_app_icon)

    m = QMainWindow()
    m.setCentralWidget(cio)
    m.setWindowTitle(f'Clock In/Out v{__version__}')
    m.adjustSize()
    s = m.size()
    _2phi = 1 + sqrt(5)
    s.setWidth(round(_2phi * s.height()))
    m.resize(s)
    m.move(0, 0)

    update_app_icon()
    m.show()
    t.start()

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

    if (
        0
        == cur.execute(f'''select count(*) from clocks
            where timestamp >= {start.timestamp()};''').fetchone()[0]
    ):
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
        cur = conn.cursor()
        cur.execute(_schema)

        totals = day_totals(cur, date)
        if 0 == len(totals):
            return

        print('   Date        Work       Σ       %      Δ')
        grand_total = 0.0
        for total in totals:
            if total > 0.0:
                grand_total += total
                print(
                    '{}: {:3d}:{:02d}:{:02d}  {:6.2f}  {:5.1f}  {:6.2f}'.format(
                        date.date(),
                        *hms(total),
                        s2h(grand_total),
                        s2p(grand_total),
                        s2h(total),
                    )
                )
            date += _day_delta
        if grand_total > 0.0:
            print('     Total: {:3d}:{:02d}:{:02d}'.format(*hms(grand_total)))


def file_info(database):
    print(
        f'Database Path: {home_relative(database)}',
        f' Database MD5: {path_hash(database)}',
        f'  Script Path: {home_relative(__file__)}',
        f'   Script MD5: {path_hash(__file__)}',
        sep='\n',
    )


def main(args_list=None):
    import argparse

    arg_parser = argparse.ArgumentParser(
        description='Use a SQLite database to keep up with clock ins/outs'
    )
    _a = arg_parser.add_argument
    _a('--database', help='file to use for clock ins/outs')
    _a('--gui', action='store_true', help='show the GUI')
    _a('--info', action='store_true', help='show info about files')
    _a('--version', action='version', version=f'%(prog)s {__version__}')
    args = arg_parser.parse_args(args_list or sys.argv[1:])

    (gui if args.gui else file_info if args.info else hours)(
        args.database or os.path.join(os.environ['HOME'], '.clkins.sqlite3')
    )


if '__main__' == __name__:
    main()
