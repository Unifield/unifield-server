# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2017 TeMPO Consulting, MSF. All Rights Reserved
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from report import report_sxw

class report_gl_selector(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(report_gl_selector, self).__init__(cr, uid, name, context=context)
        self.total = {}
        self.current_line_position = 0
        self.nb_lines = 0
        self._display_hq_account = self.pool.get('account.export.mapping')._is_mapping_display_active(cr, uid)
        self.localcontext.update({
            'total_booking_debit': self._get_total_booking_debit,
            'total_booking_credit': self._get_total_booking_credit,
            'total_output_debit': self._get_total_output_debit,
            'total_output_credit': self._get_total_output_credit,
            'update_percent': self._update_percent,
            'display_hq_account': lambda *a: self._display_hq_account,
            'get_col_widths': self.get_col_widths,
        })
        self.log_export = True

    def get_col_widths(self):
        if not self._display_hq_account:
            return {'colWidths': "45.0,45.0,58.0,52.0,45.0,48.0,48.0,43.0,45.0,45.0,45.0,45.0,40.0,45.0,42.0,43.0,42.0,40.0"}
        return {'colWidths': "45.0,45.0,58.0,50.0,43.0,46.0,46.0,41.0,43.0,43.0,43.0,43.0,38.0,43.0,41.0,41.0,40.0,38.0,30.0"}

    def _update_percent(self, data, objects):
        """
        Updates the loading percentage for the report running in background
        """
        if self.nb_lines == 0:
            self.nb_lines = len(objects)
        if data.get('context') and data.get('context').get('background_id'):
            bg_obj = self.pool.get('memory.background.report')
            self.current_line_position += 1
            if self.current_line_position % 50 == 0:  # update percentage every 50 lines
                percent = self.current_line_position / float(self.nb_lines)
                bg_obj.update_percent(self.cr, self.uid, [data['context']['background_id']], percent)
        return True

    def _get_total(self, data):
        """
        Returns a dict with the total of the booking debits and credits, and of the output debits and credits
        """
        if not self.total:
            booking_debit = booking_credit = output_debit = output_credit = 0.0
            for aml in data:
                booking_debit += aml.debit_currency or 0.0
                booking_credit += aml.credit_currency or 0.0
                output_debit += aml.output_amount_debit or 0.0
                output_credit += aml.output_amount_credit or 0.0
            self.total = {'booking_debit': booking_debit,
                          'booking_credit': booking_credit,
                          'output_debit': output_debit,
                          'output_credit': output_credit}
        return self.total

    def _get_total_booking_debit(self, data):
        return self._get_total(data)['booking_debit']

    def _get_total_booking_credit(self, data):
        return self._get_total(data)['booking_credit']

    def _get_total_output_debit(self, data):
        return self._get_total(data)['output_debit']

    def _get_total_output_credit(self, data):
        return self._get_total(data)['output_credit']

report_sxw.report_sxw('report.gl.selector', 'account.move.line',
                      'addons/account_mcdb/report/report_account_move_line.rml',
                      parser=report_gl_selector, header='internal landscape')


class report_analytic_selector(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(report_analytic_selector, self).__init__(cr, uid, name, context=context)
        self.total = {}
        self.current_line_position = 0
        self.nb_lines = 0
        self._display_hq_account = self.pool.get('account.export.mapping')._is_mapping_display_active(cr, uid)
        self.localcontext.update({
            'total_booking': self._get_total_booking,
            'total_functional': self._get_total_functional,
            'total_output': self._get_total_output,
            'update_percent': self._update_percent,
            'display_hq_account': lambda *a: self._display_hq_account,
            'get_col_widths': self.get_col_widths,
        })
        self.log_export = True

    def get_col_widths(self):
        if self.localcontext.get('data', {}).get('context', {}).get('display_fp'):
            if self._display_hq_account:
                return {'colWidths': "40.0,33.0,45.0,49.0,38.0,46.0,46.0,31.0,39.0,38.0,33.0,31.0,43.0,40.0,32.0,40.0,32.0,40.0,30.0,36.0,34.0,30.0"}
            return {'colWidths': "40.0,33.0,45.0,49.0,38.0,48.0,48.0,31.0,40.0,40.0,35.0,33.0,45.0,42.0,34.0,42.0,34.0,42.0,32.0,38.0,36.0"}

        if self._display_hq_account:
            return {'colWidths': "42.0,37.0,49.0,53.0,40.0,50.0,50.0,32.0,43.0,35.0,49.0,44.0,36.0,44.0,36.0,44.0,34.0,40.0,38.0,30.0"}
        return {'colWidths': "44.0,37.0,49.0,53.0,42.0,52.0,52.0,34.0,45.0,37.0,49.0,46.0,38.0,46.0,38.0,46.0,36.0,42.0,40.0"}

    def _update_percent(self, data, objects):
        """
        Updates the loading percentage for the report running in background
        """
        if self.nb_lines == 0:
            self.nb_lines = len(objects)
        if data.get('context') and data.get('context').get('background_id'):
            bg_obj = self.pool.get('memory.background.report')
            self.current_line_position += 1
            if self.current_line_position % 50 == 0:  # update percentage every 50 lines
                percent = self.current_line_position / float(self.nb_lines)
                bg_obj.update_percent(self.cr, self.uid, [data['context']['background_id']], percent)
        return True

    def _get_total(self, data):
        """
        Returns a dict with the AJI total amount in booking, functional, and output currency
        """
        if not self.total:
            booking = functional = output = 0.0
            for aal in data:
                booking += aal.amount_currency or 0.0
                functional += aal.amount or 0.0
                output += aal.output_amount or 0.0
            self.total = {'booking': booking,
                          'functional': functional,
                          'output': output}
        return self.total

    def _get_total_booking(self, data):
        return self._get_total(data)['booking']

    def _get_total_functional(self, data):
        return self._get_total(data)['functional']

    def _get_total_output(self, data):
        return self._get_total(data)['output']


report_sxw.report_sxw('report.analytic.selector', 'account.analytic.line',
                      'addons/account_mcdb/report/report_account_analytic_line.rml',
                      parser=report_analytic_selector, header='internal landscape')
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
