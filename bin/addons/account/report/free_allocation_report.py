# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2018 TeMPO Consulting, MSF. All Rights Reserved
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
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _


class free_allocation_report(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(free_allocation_report, self).__init__(cr, uid, name, context=context)
        self.lines = {}
        self.total_lines = {}
        self.localcontext.update({
            'lines': self._get_lines,
            'total_line': self._get_total_line,
        })

    def _get_lines(self, data):
        """
        Returns the report lines as a list of dicts
        """
        if not self.lines:
            move_obj = self.pool.get('account.move')
            aml_obj = self.pool.get('account.move.line')
            context = data.get('context', {})
            account_ids = data.get('account_ids', [])
            cost_center_ids = data.get('cost_center_ids', [])
            free1_ids = data.get('free1_ids', [])
            free2_ids = data.get('free2_ids', [])
            dom = []
            if data.get('fiscalyear_id', False):
                dom.append(('fiscalyear_id', '=', data['fiscalyear_id']))
            if data.get('period_id', False):
                dom.append(('period_id', '=', data['period_id']))
            if data.get('document_date_from', False):
                dom.append(('document_date', '>=', data['document_date_from']))
            if data.get('document_date_to', False):
                dom.append(('document_date', '<=', data['document_date_to']))
            if data.get('posting_date_from', False):
                dom.append(('date', '>=', data['posting_date_from']))
            if data.get('posting_date_to', False):
                dom.append(('date', '<=', data['posting_date_to']))
            if data.get('instance_id', False):
                dom.append(('instance_id', '=', data['instance_id']))
            if data.get('journal_ids', []):
                dom.append(('journal_id', 'in', data['journal_ids']))
            sql_part = ""
            sql_part_param = []
            if cost_center_ids:
                sql_part += " AND (aac.category != 'FUNDING' OR cc.id IN %s ) "
                sql_part_param.append(tuple(cost_center_ids))
            if free1_ids:
                sql_part += " AND (aac.category != 'FREE1' OR fp.id IN %s ) "
                sql_part_param.append(tuple(free1_ids))
            if free2_ids:
                sql_part += " AND (aac.category != 'FREE2' OR fp.id IN %s ) "
                sql_part_param.append(tuple(free2_ids))
            # get the JE matching the criteria sorted by Entry Sequence
            move_ids = move_obj.search(self.cr, self.uid, dom, order='name', context=context)
            for move in move_obj.browse(self.cr, self.uid, move_ids, fields_to_fetch=['name'], context=context):
                self.lines[move.name] = []
                book_total = 0.0
                func_total = 0.0
                book_currency = ''
                aml_dom = [('move_id', '=', move.id)]
                if account_ids:
                    aml_dom.append(('account_id', 'in', account_ids))
                aml_ids = aml_obj.search(self.cr, self.uid, aml_dom, order='account_id', context=context)
                for aml in aml_obj.browse(self.cr, self.uid, aml_ids, context=context):
                    aml_booking = aml.amount_currency or (aml.debit_currency - aml.credit_currency) or 0.0
                    if not aml_booking:
                        continue
                    book_currency = aml.currency_id and aml.currency_id.name or ''  # will be the same for all JE lines
                    ad_data = {}
                    ad_data['free1'] = {}
                    ad_data['free2'] = {}
                    ad_data['ad'] = {}
                    aal_sql = """
                        SELECT dest.code AS dest, cc.code AS cc,
                        CASE WHEN aac.category = 'FUNDING' THEN fp.code ELSE '' END AS fp,
                        CASE WHEN aac.category = 'FREE1' THEN fp.code ELSE '' END AS free1,
                        CASE WHEN aac.category = 'FREE2' THEN fp.code ELSE '' END AS free2,
                        aal.amount_currency, aal.amount
                        FROM account_analytic_line aal 
                        INNER JOIN account_analytic_account aac ON aal.account_id = aac.id
                        LEFT JOIN account_analytic_account cc on aal.cost_center_id = cc.id
                        LEFT JOIN account_analytic_account dest on aal.destination_id = dest.id
                        LEFT JOIN account_analytic_account fp on aal.account_id = fp.id
                        WHERE move_id = %s """ + sql_part + """ ORDER BY free1, free2;
                        """
                    params = (aml.id,) + tuple(sql_part_param)
                    self.cr.execute(aal_sql, params)
                    aals = self.cr.dictfetchall()
                    for aal in aals:
                        # fill in ad_data values for FREE1 axis
                        if aal['free1']:
                            if aal['free1'] not in ad_data['free1']:
                                ad_data['free1'][aal['free1']] = {}
                                ad_data['free1'][aal['free1']]['amount_currency'] = 0.0
                                ad_data['free1'][aal['free1']]['amount'] = 0.0
                            ad_data['free1'][aal['free1']]['amount_currency'] += aal['amount_currency'] or 0.0
                            ad_data['free1'][aal['free1']]['amount'] += aal['amount'] or 0.0
                        # fill in ad_data values for FREE2 axis
                        if aal['free2']:
                            if aal['free2'] not in ad_data['free2']:
                                ad_data['free2'][aal['free2']] = {}
                                ad_data['free2'][aal['free2']]['amount_currency'] = 0.0
                                ad_data['free2'][aal['free2']]['amount'] = 0.0
                            ad_data['free2'][aal['free2']]['amount_currency'] += aal['amount_currency'] or 0.0
                            ad_data['free2'][aal['free2']]['amount'] += aal['amount'] or 0.0
                        # fill in ad_data values for AD axis. Key = tuple (DEST, CC, FP)
                        if aal['dest'] and aal['cc'] and aal['fp']:
                            if (aal['dest'], aal['cc'], aal['fp']) not in ad_data['ad']:
                                ad_data['ad'][(aal['dest'], aal['cc'], aal['fp'])] = {}
                                ad_data['ad'][(aal['dest'], aal['cc'], aal['fp'])]['amount_currency'] = 0.0
                                ad_data['ad'][(aal['dest'], aal['cc'], aal['fp'])]['amount'] = 0.0
                            ad_data['ad'][(aal['dest'], aal['cc'], aal['fp'])]['amount_currency'] += aal['amount_currency'] or 0.0
                            ad_data['ad'][(aal['dest'], aal['cc'], aal['fp'])]['amount'] += aal['amount'] or 0.0
                    # after all lines have been handled, if there is no free1 or free2 create empty free axis entries
                    # (unless specific free1/2 accounts have been selected)
                    if not ad_data['free1'] and not free1_ids:
                        ad_data['free1'][''] = {}
                        ad_data['free1']['']['amount_currency'] = 0.0
                        ad_data['free1']['']['amount'] = 0.0
                    if not ad_data['free2'] and not free2_ids:
                        ad_data['free2'][''] = {}
                        ad_data['free2']['']['amount_currency'] = 0.0
                        ad_data['free2']['']['amount'] = 0.0
                    # create lines to be displayed for the JI
                    for free1 in ad_data['free1']:
                        for free2 in ad_data['free2']:
                            for ad in ad_data['ad']:
                                # booking amounts
                                free1_booking = ad_data['free1'][free1]['amount_currency']
                                free2_booking = ad_data['free2'][free2]['amount_currency']
                                ad_booking = ad_data['ad'][ad]['amount_currency']
                                free1_part_booking = free1_booking / aml_booking
                                free2_part_booking = free2_booking / aml_booking
                                ad_part_booking = ad_booking / aml_booking
                                # functional amounts
                                aml_fctal = (aml.debit or 0.0) - (aml.credit or 0.0)
                                if not aml_fctal:
                                    free1_part_fctal = 0.0
                                    free2_part_fctal = 0.0
                                    ad_part_fctal = 0.0
                                else:
                                    free1_fctal = ad_data['free1'][free1]['amount']
                                    free2_fctal = ad_data['free2'][free2]['amount']
                                    ad_fctal = ad_data['ad'][ad]['amount']
                                    free1_part_fctal = free1_fctal / aml_fctal
                                    free2_part_fctal = free2_fctal / aml_fctal
                                    ad_part_fctal = ad_fctal / aml_fctal
                                # the amount computation depends on the axis combination
                                # (avoids multiplying by zero if an AD axis doesn't exist)
                                # no free axis
                                if abs(free1_booking) <= 10**-3 and abs(free2_booking) <= 10**-3:
                                    book_amount = abs(aml_booking * ad_part_booking)
                                    func_amount = abs(aml_fctal * ad_part_fctal)
                                # free1 only
                                elif abs(free2_booking) <= 10**-3:
                                    book_amount = abs(aml_booking * free1_part_booking * ad_part_booking)
                                    func_amount = abs(aml_fctal * free1_part_fctal * ad_part_fctal)
                                # free2 only
                                elif abs(free1_booking) <= 10**-3:
                                    book_amount = abs(aml_booking * free2_part_booking * ad_part_booking)
                                    func_amount = abs(aml_fctal * free2_part_fctal * ad_part_fctal)
                                # all axis
                                else:
                                    book_amount = abs(aml_booking * free1_part_booking * free2_part_booking * ad_part_booking)
                                    func_amount = abs(aml_fctal * free1_part_fctal * free2_part_fctal * ad_part_fctal)
                                # don't display lines with zero amount
                                if abs(book_amount) <= 10**-3:
                                    continue
                                # determine if the amounts are positive or negative
                                sign = 1
                                if aml_booking > 0:  # positive JI amount = JI amount in debit
                                    sign = -1  # negative AJI
                                book_amount = sign * book_amount
                                func_amount = sign * func_amount
                                line = {
                                    'account': aml.account_id.code,
                                    'destination': ad[0],
                                    'cost_center': ad[1],
                                    'funding_pool': ad[2],
                                    'free1': free1,
                                    'free2': free2,
                                    'book_amount': book_amount,
                                    'book_currency': book_currency,
                                    'func_amount': func_amount,
                                    'func_currency': aml.functional_currency_id and aml.functional_currency_id.name or '',
                                }
                                self.lines[aml.move_id.name].append(line)
                                book_total += book_amount or 0.0
                                func_total += func_amount or 0.0
                # create the total line for each Entry Sequence
                self.total_lines[move.name] = {
                        'book_amount': book_total,
                        'book_currency': book_currency,
                        'func_amount': func_total,
                    }
        return self.lines

    def _get_total_line(self, entry_sequence):
        """
        Returns a dict with functional amount, and booking amount & currency for the Entry Seq. in parameter
        """
        if entry_sequence in self.total_lines:
            return self.total_lines[entry_sequence]
        else:
            return {
                'book_amount': 0.0,
                'book_currency': '',
                'func_amount': 0.0,
            }


SpreadsheetReport('report.free.allocation.report.xls', 'account.analytic.line',
                  'addons/account/report/free_allocation_report.mako', parser=free_allocation_report)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
