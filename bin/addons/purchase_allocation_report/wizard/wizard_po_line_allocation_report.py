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


class wizard_po_line_allocation_report(osv.osv_memory):
    _name = 'wizard.po.line.allocation.report'
    _description = 'Wizard of the Purchase Order Line Allocation Report'

    _columns = {
        'export_type': fields.selection([('pdf', 'PDF'), ('excel', 'Excel')], string='Export type', required=True),
    }

    _defaults = {
        'export_type': 'pdf',
    }

    def button_po_line_allocation_report(self, cr, uid, ids, context=None):
        """
        Generates the Purchase Order Line Allocation Report
        """
        if context is None:
            context = {}
        wiz_data = self.read(cr, uid, ids, ['export_type'])[0]
        data = {
            'ids': context.get('active_ids', []),
            'model': context.get('active_model', 'ir.ui.menu'),
            'context': context,
            'target_filename': 'Allocation Report_%s' % (time.strftime('%Y%m%d_%H_%M'),),
        }
        if wiz_data.get('export_type', '') == 'excel':
            report = {
                'type': 'ir.actions.report.xml',
                'report_name': 'po.line.allocation.report.xls',
                'datas': data
            }
        else:
            report = {
                'type': 'ir.actions.report.xml',
                'report_name': 'purchase.order.allocation.report',
                'datas': data
            }
        return report


wizard_po_line_allocation_report()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
