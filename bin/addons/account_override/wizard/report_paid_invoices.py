#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2017 TeMPO Consulting, MSF. All Rights Reserved
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
from datetime import datetime

class wizard_report_paid_invoice(osv.osv_memory):
    _name = 'wizard.report.paid.invoice'
    _description = 'Wizard of the Paid Invoices Report'

    _columns = {
        'beginning_date': fields.date(string='Beginning date', required=True),
        'ending_date': fields.date(string='Ending date', required=True),
    }

    _defaults = {
        'beginning_date': lambda *a: datetime.today(),
        'ending_date': lambda *a: datetime.today(),
    }

    def button_paid_invoices_report(self, cr, uid, ids, context=None):
        """
        Generates the Paid Invoices Report
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        user_obj = self.pool.get('res.users')
        bg_obj = self.pool.get('memory.background.report')
        data = {}
        data['ids'] = context.get('active_ids', [])
        data['model'] = context.get('active_model', 'ir.ui.menu')
        data['form'] = self.read(cr, uid, ids, ['beginning_date', 'ending_date'])[0]
        instance = user_obj.browse(cr, uid, uid).company_id.instance_id
        inst_code = instance and instance.code or ''
        report_date = datetime.today().strftime('%Y%m%d')
        report_name = 'paid.invoices'
        data['target_filename'] = 'Paid Invoices_%s_%s' % (inst_code, report_date)
        # make the report run in background
        background_id = bg_obj.create(cr, uid,
                                      {'file_name': data['target_filename'],
                                       'report_name': report_name,
                                       },
                                      context=context)
        context['background_id'] = background_id
        context['background_time'] = 2
        data['context'] = context
        return {'type': 'ir.actions.report.xml', 'report_name': report_name, 'datas': data, 'context': context}


wizard_report_paid_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
