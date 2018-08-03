#!/usr/bin/env python
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

from osv import osv
from osv import fields


class free_allocation_wizard(osv.osv_memory):
    _name = 'free.allocation.wizard'
    _description = 'Wizard for the "Analytic Allocation with Free - Report"'

    _columns = {
        'fiscalyear_id': fields.many2one('account.fiscalyear', string='Fiscal Year'),
        'period_id': fields.many2one('account.period', string='Period'),
        'document_date': fields.date('Document Date'),
        'posting_date': fields.date('Posting Date'),
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
        'account_ids': fields.many2many('account.account', 'free_allocation_account_rel', 'wizard_id', 'account_id',
                                        string='Accounts', domain=[('type', '!=', 'view')]),
        'journal_ids': fields.many2many('account.journal', 'free_allocation_journal_rel', 'wizard_id', 'journal_id',
                                        string='Journals'),
        'cost_center_ids': fields.many2many('account.analytic.account', 'free_allocation_cost_center_rel', 'wizard_id',
                                            'cost_center_id', 'Cost Centers',
                                            domain=[('category', '=', 'OC'), ('type', '=', 'normal')]),
        'free1_ids': fields.many2many('account.analytic.account', 'free_allocation_free1_rel', 'wizard_id', 'free1_id',
                                      'Free 1', domain=[('category', '=', 'FREE1'), ('type', '=', 'normal')]),
        'free2_ids': fields.many2many('account.analytic.account', 'free_allocation_free2_rel', 'wizard_id', 'free2_id',
                                      'Free 2', domain=[('category', '=', 'FREE2'), ('type', '=', 'normal')]),
    }

    def onchange_fiscalyear(self, cr, uid, ids, fiscalyear_id, context=None):
        """
        If a FY is selected:
        resets the selected period, and adapts the domain so that the selectable period is inside the chosen FY.
        If no FY is selected: resets the period domain
        """
        res = {}
        if fiscalyear_id:
            res['domain'] = {'period_id': [('fiscalyear_id', '=', fiscalyear_id)], }
            res['value'] = {'period_id': False, }
        else:
            res['domain'] = {'period_id': [], }
        return res

    def print_free_allocation_report(self, cr, uid, ids, context=None):
        """
        Generates the "Analytic Allocation with Free - Report"
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        wiz = self.browse(cr, uid, ids[0], context=context)
        data = {
            'fiscalyear_id': wiz.fiscalyear_id and wiz.fiscalyear_id.id or False,
            'period_id': wiz.period_id and wiz.period_id.id or False,
            'document_date': wiz.document_date or False,
            'posting_date': wiz.posting_date or False,
            'instance_id': wiz.instance_id and wiz.instance_id.id or False,
            'account_ids': wiz.account_ids and [x.id for x in wiz.account_ids] or [],
            'journal_ids': wiz.journal_ids and [x.id for x in wiz.journal_ids] or [],
            'cost_center_ids': wiz.cost_center_ids and [x.id for x in wiz.cost_center_ids] or [],
            'free1_ids': wiz.free1_ids and [x.id for x in wiz.free1_ids] or [],
            'free2_ids': wiz.free2_ids and [x.id for x in wiz.free2_ids] or [],
        }
        report_name = 'free.allocation.report'
        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': data,
            'context': context,
        }


free_allocation_wizard()


class ir_values(osv.osv):
    _name = 'ir.values'
    _inherit = 'ir.values'

    def get(self, cr, uid, key, key2, models, meta=False, context=None, res_id_req=False, without_user=True, key2_req=True):
        """
        Hides the Report "Analytic Allocation with Free" in AJI view menu
        """
        if context is None:
            context = {}
        values = super(ir_values, self).get(cr, uid, key, key2, models, meta, context, res_id_req, without_user, key2_req)
        model_names = [x[0] for x in models]
        if key == 'action' and key2 == 'client_print_multi' and 'account.analytic.line' in model_names:
            new_act = []
            for v in values:
                display_fp = context.get('display_fp', False)
                not_free_axis = context.get('categ', '') not in ['FREE1', 'FREE2']
                if v[1] == 'action_analytic_allocation_with_free' and (display_fp or not_free_axis):
                    continue
                else:
                    new_act.append(v)
            values = new_act
        return values


ir_values()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
