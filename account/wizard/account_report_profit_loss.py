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

from osv import osv, fields
from tools.translate import _
import time

class account_pl_report(osv.osv_memory):
    """
    This wizard will provide the account profit and loss report by periods, between any two dates.
    """
    _inherit = "account.common.account.report"
    _name = "account.pl.report"
    _description = "Account Profit And Loss Report"
    _columns = {
        'export_format': fields.selection([('xls', 'Excel'), ('pdf', 'PDF')], string="Export format", required=True),
        'instance_ids': fields.many2many('msf.instance', 'account_report_general_ledger_instance_rel', 'instance_id', 'argl_id', 'Proprietary Instances'),
    }

    _defaults = {
        'export_format': 'pdf',
        'journal_ids': [],
        'target_move': False
    }

    def _print_report(self, cr, uid, ids, data, context=None):
        if context is None:
            context = {}
        update_fields = [
            'export_format',
            'instance_ids',
        ]
        data = self.pre_print_report(cr, uid, ids, data, context=context)
        data['form'].update(self.read(cr, uid, ids, update_fields)[0])
        instance = self.pool.get('ir.sequence')._get_instance(cr, uid)
        data['target_filename'] = _('Account Profit_and_Loss_%s_%s') % (instance, time.strftime('%Y%m%d'))

        if data['form']['export_format'] \
           and data['form']['export_format'] == 'xls':
            # US-227: excel version
            return {
                'type': 'ir.actions.report.xml',
                'report_name': 'account.profit.loss_xls',
                'datas': data,
            }

        # PDF version (portrait version 'pl.account' not used now)
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'pl.account.horizontal',
            'datas': data,
        }

account_pl_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
