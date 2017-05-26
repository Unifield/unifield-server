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

from time import strftime

class liquidity_balance_wizard(osv.osv_memory):
    _name = 'liquidity.balance.wizard'

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Top proprietary instance', required=True),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal year', required=True),
        'period_id': fields.many2one('account.period', 'Period', required=True),
    }

    _defaults = {
        'fiscalyear_id': lambda self, cr, uid, c: self.pool.get('account.fiscalyear').find(cr, uid, strftime('%Y-%m-%d'), context=c),
    }

    def print_liquidity_balance_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        wiz = self.browse(cr, uid, ids[0], fields_to_fetch=['period_id', 'instance_id'], context=context)
        data = {}
        data['form'] = {}
        # get the selected period
        data['form'].update({'period_id': wiz.period_id and wiz.period_id.id or False})
        # get the selected instance AND its children
        data['form'].update({'instance_ids': wiz.instance_id and
                                             ([wiz.instance_id.id] + [x.id for x in wiz.instance_id.child_ids]) or False})
        data['context'] = context
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.liquidity.balance',
            'datas': data,
            'context': context,
        }

liquidity_balance_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
