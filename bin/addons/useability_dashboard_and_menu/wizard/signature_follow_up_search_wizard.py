#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) TeMPO Consulting (<http://www.tempo-consulting.fr/>), MSF.
#    All Rigts Reserved
#    Developer: Stéphane Codazzi
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
from tools.translate import _


class signature_follow_up_search_wizard(osv.osv_memory):
    _name = 'signature.follow_up.search.wizard'

    _columns = {
        'export_format': fields.selection([('xlsx', 'Excel'), ('pdf', 'PDF')], string="Export format", required=True),
    }

    def button_validate(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        for wiz in self.browse(cr, uid, ids, context=context):
            data = {
                'ids': [],
                'model': 'signature.follow_up',
                'context': context,
            }
            report_name = 'signature.follow_up.search.pdf'
            if wiz.export_format == 'xlsx':
                report_name = 'signature.follow_up.search.xlsx'
            return {
                'type': 'ir.actions.report.xml',
                'report_name': report_name,
                'datas': data,
            }
        return {'type': 'ir.actions.act_window_close'}


signature_follow_up_search_wizard()
