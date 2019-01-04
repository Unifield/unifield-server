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

from osv import fields
from osv import osv
from tools.translate import _

from time import strftime
from time import strptime

class liquidity_balance_wizard(osv.osv_memory):
    _name = 'liquidity.balance.wizard'

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Top proprietary instance', required=True),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal year', required=True),
        'period_id': fields.many2one('account.period', 'Period'),
        'date_from': fields.date("Date from"),
        'date_to': fields.date("to"),
    }

    _defaults = {
        'fiscalyear_id': lambda self, cr, uid, c: self.pool.get('account.fiscalyear').find(cr, uid, strftime('%Y-%m-%d'), context=c),
    }

    def onchange_period_id(self, cr, uid, ids, period_id, context=None):
        """
        Resets the date fields when a period is selected
        """
        res = {}
        if period_id:
            res['value'] = {'date_from': False,
                            'date_to': False,
                            }
        return res

    def onchange_date(self, cr, uid, ids, date_from, date_to, context=None):
        """
        Resets the period when one the date fields is filled in
        """
        res = {}
        if date_from or date_to:
            res['value'] = {'period_id': False, }
        return res

    def _check_wizard_data(self, wiz):
        """
        Checks the data selected in the wizard and raises an error if needed
        """
        if not wiz.period_id and not wiz.date_from and not wiz.date_to:
            raise osv.except_osv(_('Error'), _('You must select a period or a date range.'))
        elif (wiz.date_from and not wiz.date_to) or (wiz.date_to and not wiz.date_from):
            raise osv.except_osv(_('Error'), _("Either the start date or the end date is missing."))
        elif wiz.date_to and wiz.date_from and wiz.date_to < wiz.date_from:
            raise osv.except_osv(_('Error'), _("The end date can't precede the start date."))

    def print_liquidity_balance_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        wiz = self.browse(cr, uid, ids[0], context=context)
        self._check_wizard_data(wiz)
        data = {}
        data['form'] = {}
        # get the selected period and dates
        data['form'].update({'period_id': wiz.period_id and wiz.period_id.id or False,
                             'date_from': wiz.date_from or False,
                             'date_to': wiz.date_to or False,
                             })

        # get the selected instance AND its children
        data['form'].update({'instance_ids': wiz.instance_id and
                             ([wiz.instance_id.id] + [x.id for x in wiz.instance_id.child_ids]) or False})
        data['context'] = context
        instance = wiz.instance_id and wiz.instance_id.code or ''
        # get the year and month number (used in the file name)
        year = ''
        month = ''
        if wiz.period_id:
            tm = strptime(wiz.period_id.date_start, '%Y-%m-%d')
            year_num = tm.tm_year
            year = str(year_num)
            month = '%02d' % tm.tm_mon
        data['target_filename'] = "%s_%s%s_%s" % (instance, year, month, _('Liquidity Balances'))
        data['form'].update({'year': year, 'month': month})
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.liquidity.balance',
            'datas': data,
            'context': context,
        }

liquidity_balance_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
