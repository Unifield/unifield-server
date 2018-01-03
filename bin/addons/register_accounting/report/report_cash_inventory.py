# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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
import datetime


class cash_inventory(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(cash_inventory, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getNow': self.get_now,
            'formatComments': self._format_comments,
        })

    def get_now(self, show_datetime=False):
        date_tools_obj = self.pool.get('date.tools')
        res = datetime.datetime.now()
        return date_tools_obj.datetime2orm(res) if show_datetime \
            else date_tools_obj.date2orm(res.date())

    def _format_comments(self, notes):
        """
        Formats the comments to print:
        - 4 lines max
        - 90 characters per line
        """
        res = ''
        nb_lines = 4
        strlimit = 90
        # remove the existing line breaks from the comments
        notes = notes.replace('\r\n', ' ').replace('\n', ' ')
        for i in range(nb_lines):
            begin = i * strlimit
            end = begin + strlimit
            is_last_line = i == nb_lines - 1
            eol = ''
            if not is_last_line:
                # add an hyphen if the cut is done in the middle of a word
                eol = len(notes) > end and notes[end-1].isalpha() and notes[end].isalpha() and '-\n-' or '\n'
            res = '%s%s%s' % (res, notes[begin:end], eol)
        # add an ellipsis if the comment is too long to be fully printed
        if len(notes) > strlimit * nb_lines:
            res = '%s%s' % (res, '...')
        return res

report_sxw.report_sxw('report.cash.inventory', 'account.bank.statement', 'addons/register_accounting/report/cash_inventory.rml', parser=cash_inventory)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
