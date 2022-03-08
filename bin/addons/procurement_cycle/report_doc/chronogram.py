# -*- coding: utf-8 -*-
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from datetime import datetime
from dateutil import relativedelta
from tools.translate import _
import math
import calendar
from .. import normalize_td

class chronogram(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(chronogram, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_start': self.get_start,
            'relativedelta': relativedelta.relativedelta,
            'MO': relativedelta.MO,
            'month': self.month,
            'ceil': math.ceil,
            'num_cells_in_month': self.num_cells_in_month,
            'get_1_offset': self.get_1_offset,
            'get_cells': self.get_cells,
        })


    def get_cells(self, value, unit):
        if unit == 'd':
            return int(round(value))

        if unit == 'm':
            return int(round(value * 4))

        if unit == 'w':
            return int(round(value * 2))

    def get_1_offset(self, calendar_start, o, cycle):
        '''
            returns the number of empty cells before the Order Preperation Date

        '''
        if not o.date_preparing.val:
            dt = datetime.now()
        else:
            dt = datetime.strptime(o.date_preparing, '%Y-%m-%d')
        if cycle > 1:
            dt += relativedelta.relativedelta(**normalize_td(o.time_unit_lt, (cycle-1) * (o.order_coverage or 0)))
        if calendar_start == dt:
            return False

        divisor = 1
        if o.time_unit_lt == 'm':
            divisor = (calendar_start + relativedelta.relativedelta(months=1, day=1, days=-1)).day
        elif o.time_unit_lt == 'w':
            divisor = 7.
        ret = self.get_cells((dt-calendar_start).days / float(divisor), o.time_unit_lt) - 1
        if ret < 0:
            return False
        return ret


    def num_cells_in_month(self, dt):
        '''
            UoT = w
        '''

        m = calendar.Calendar(0).monthdayscalendar(dt.year, dt.month)
        nb_days = (dt + relativedelta.relativedelta(months=1, day=1, days=-1)).day - dt.day

        if dt.day == 1:
            cells = (len(m) -2) * 2
            index_k = [0, -1]
        else:
            cells =  nb_days/7 * 2
            index_k = [-1]

        for index in index_k:
            nb_d = len([x for x in m[index] if x != 0])
            if nb_d > 5:
                cells += 2
            elif nb_d >= 2:
                cells += 1
        return cells - 1

    def month(self, nb):
        return [
            '', _('January'), _('February'), _('March'), _('April'), _('May'), _('June'),
            _('July'), _('August'), _('September'), _('October'), _('November'), _('December')
        ][nb]

    def get_start(self, o):
        if not o.date_preparing.val:
            date_preparing = datetime.now()
        else:
            date_preparing = datetime.strptime(o.date_preparing, '%Y-%m-%d')

        if o.time_unit_lt == 'w':
            cols = 0
            start_date = date_preparing + relativedelta.relativedelta(day=1, weekday=relativedelta.MO(0))
        elif o.time_unit_lt in 'd':
            start_date = date_preparing + relativedelta.relativedelta(weekday=relativedelta.MO(-1))
            cols = (start_date + relativedelta.relativedelta(months=1, day=1, days=-1)).day - start_date.day
        elif o.time_unit_lt == 'm':
            start_date = date_preparing + relativedelta.relativedelta(day=1)
            cols = 3

        return {'date': start_date, 'cols': cols}

SpreadsheetReport('report.report_replenishment_parent_segment_chronogram_xls', 'replenishment.parent.segment', 'addons/procurement_cycle/report_doc/chronogram.mako', parser=chronogram)
