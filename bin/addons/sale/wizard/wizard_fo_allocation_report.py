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


class wizard_fo_allocation_report(osv.osv_memory):
    _name = 'wizard.fo.allocation.report'
    _description = 'Wizard of the Field Order Allocation Report'

    _columns = {
        'export_type': fields.selection([('pdf', 'PDF'), ('excel', 'Excel')], string='Export type', required=True),
    }

    _defaults = {
        'export_type': 'pdf',
    }

    def button_fo_allocation_report(self, cr, uid, ids, context=None):
        """
        Generates the Field Order Allocation Report
        """
        if context is None:
            context = {}
        wiz_data = self.read(cr, uid, ids, ['export_type'])[0]
        fo_obj = self.pool.get('sale.order')
        active_ids = context.get('active_ids', [])
        order_name = active_ids and len(active_ids) > 0 and fo_obj.read(cr, uid, ids[0], ['name'], context=context)['name'] or ''
        filename = "Allocation Report_%s_%s" % (order_name, time.strftime('%Y%m%d'))
        data = {
            'ids': active_ids,
            'model': context.get('active_model', 'ir.ui.menu'),
            'context': context,
            'target_filename': filename,
        }
        if wiz_data.get('export_type', '') == 'excel':
            report = {
                'type': 'ir.actions.report.xml',
                'report_name': 'fo.allocation.report.xls',
                'datas': data
            }
        else:
            report = {
                'type': 'ir.actions.report.xml',
                'report_name': 'sale.order.allocation.report',
                'datas': data
            }
        return report


wizard_fo_allocation_report()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
