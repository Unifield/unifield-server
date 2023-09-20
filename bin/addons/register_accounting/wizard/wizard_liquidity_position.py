#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) TeMPO Consulting (<http://www.tempo-consulting.fr/>), MSF.
#    All Rigts Reserved
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

from osv import osv
from osv import fields
import time
from tools.translate import _


class wizard_liquidity_position(osv.osv_memory):
    _name = 'wizard.liquidity.position'

    def _get_default_period(self, cr, uid, context=None):
        period_ids = self.pool.get('account.period').search(cr, uid, [('state', '!=', 'created'), ('number', 'not in', range(13, 17)), ('date_start','<=', time.strftime('%Y-%m-%d'))], limit=1, order='date_start desc', context=context)
        return period_ids and period_ids[0] or False

    _columns = {
        'period_id': fields.many2one('account.period', 'Period', required=True,
                                     domain="[('state', '!=', 'created'), ('number', 'not in', range(13, 17))]"),
        'export_type': fields.selection(
            (('excel', 'Excel'),
             ('pdf', 'PDF')),
            'Export type', required=True),
    }

    _defaults = {
        'export_type': 'pdf',
        'period_id': _get_default_period,
    }

    def create_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        wiz_info = self.read(cr, uid, ids, ['export_type', 'period_id'])[0]
        context['period_id'] = wiz_info.get('period_id', None)

        sql_register_ids = """
            SELECT abs.id
            FROM account_bank_statement abs
            LEFT JOIN account_journal aj ON abs.journal_id = aj.id
            WHERE aj.type != 'cheque'
            AND abs.state != 'draft'
            AND abs.period_id = %s"""
        cr.execute(sql_register_ids, (str(context['period_id']),))

        if not cr.fetchall():
            # No registers found
            ap_obj = self.pool.get('account.period')
            period = ap_obj.browse(cr, uid, context['period_id'],
                                   context=context)
            raise osv.except_osv(_('Export Liquidity Position'),
                                 _('No register found for the period selected %s') % period.name)
        data = {
            'ids': [],
            'model': 'account.bank.statement',
            'context': context,
        }
        if wiz_info.get('export_type', None) == 'excel':
            # Call excel report
            return {
                'type': 'ir.actions.report.xml',
                'report_name': 'liquidity.position.2',
                'datas': data
            }
        elif wiz_info.get('export_type', None) == 'pdf':
            # Call pdf report
            return {
                'type': 'ir.actions.report.xml',
                'report_name': 'liquidity.position.pdf',
                'datas': data,
            }
        else:
            raise osv.except_osv(_('Export Liquidity Position'),
                                 _('Select a valid export type.'))

wizard_liquidity_position()
