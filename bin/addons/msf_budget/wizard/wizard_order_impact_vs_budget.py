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
import time


class wizard_order_impact_vs_budget(osv.osv_memory):
    _name = 'wizard.order.impact.vs.budget'
    _description = 'Wizard of the Order Impact vs. Budget report'

    _columns = {
        'export_type': fields.selection([('pdf', 'PDF'), ('excel', 'Excel')], string='Export type', required=True),
    }

    _defaults = {
        'export_type': 'pdf',
    }

    def button_order_impact_vs_budget_report(self, cr, uid, ids, context=None):
        """
        Generates the Order Impact vs. Budget report
        """
        if context is None:
            context = {}
        wiz_data = self.read(cr, uid, ids, ['export_type'])[0]
        po_obj = self.pool.get('purchase.order')
        active_ids = context.get('active_ids', [])
        order_name = active_ids and len(active_ids) > 0 and po_obj.read(cr, uid, active_ids[0], ['name'], context=context)['name'] or ''
        filename = "Order Impact vs. Budget_%s_%s" % (order_name, time.strftime('%Y%m%d'))
        data = {
            'ids': active_ids,
            'model': context.get('active_model', 'ir.ui.menu'),
            'context': context,
            'target_filename': filename,
        }
        if wiz_data.get('export_type', '') == 'excel':
            report = {
                'type': 'ir.actions.report.xml',
                'report_name': 'order.impact.vs.budget.xls',
                'datas': data
            }
        else:
            report = {
                'type': 'ir.actions.report.xml',
                'report_name': 'msf.pdf.engagement',
                'datas': data
            }
        return report


wizard_order_impact_vs_budget()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
