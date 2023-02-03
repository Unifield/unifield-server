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
        'date_from': fields.date("Date From"),
        'date_to': fields.date("To"),
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
        Resets the period when one of the date fields is filled in
        """
        res = {}
        if date_from or date_to:
            res['value'] = {'period_id': False, }
        return res

    def _check_wizard_data(self, wiz, context=None):
        """
        Checks the data selected in the wizard and raises an error if needed
        :param wiz: wizard browse_record
        :param context: context arguments (dict), not directly used in this method but enables the messages to be translated in the right language
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
        self._check_wizard_data(wiz, context=context)
        data = {}
        data['form'] = {}
        # get the selected period and dates
        data['form'].update({'period_id': wiz.period_id and wiz.period_id.id or False,
                             'date_from': wiz.date_from or False,
                             'date_to': wiz.date_to or False,
                             })

        # get the selected instance AND its children
        if wiz.instance_id.level == 'section':
            data['form'].update({'instance_ids': wiz.instance_id and
                                 ([wiz.instance_id.id] + [x.id for x in wiz.instance_id.child_ids] +
                                  [y.id for x in wiz.instance_id.child_ids for y in x.child_ids]) or False})
        elif wiz.instance_id.level == 'coordo':
            data['form'].update({'instance_ids': wiz.instance_id and
                                 ([wiz.instance_id.id] + [x.id for x in wiz.instance_id.child_ids]) or False})
        data['context'] = context
        instance = wiz.instance_id and wiz.instance_id.code or ''
        """
        Get the period title:
        - if a period is selected: YYYYMM for both the filename and the value to display in the column "Period"
        - else: end date as YYYYMMDD for the filename, both dates as YYYYMMDD - YYYYMMDD for the column "Period"
        """
        period_title = period_title_filename = ''
        if wiz.period_id:
            tm = strptime(wiz.period_id.date_start, '%Y-%m-%d')
            period_title_filename = "%s%02d" % (str(tm.tm_year), tm.tm_mon)
            period_title = period_title_filename
        elif wiz.date_from and wiz.date_to:
            tm_from = strptime(wiz.date_from, '%Y-%m-%d')
            tm_from_formatted = "%s%02d%02d" % (str(tm_from.tm_year), tm_from.tm_mon, tm_from.tm_mday)
            tm_to = strptime(wiz.date_to, '%Y-%m-%d')
            tm_to_formatted = "%s%02d%02d" % (str(tm_to.tm_year), tm_to.tm_mon, tm_to.tm_mday)
            period_title_filename = tm_to_formatted
            period_title = "%s - %s" % (tm_from_formatted, tm_to_formatted)

        data['target_filename'] = "%s_%s_%s" % (instance, period_title_filename, _('Liquidity Balances'))
        data['form'].update({'period_title': period_title})
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.liquidity.balance',
            'datas': data,
            'context': context,
        }

liquidity_balance_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
