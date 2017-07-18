# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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

import time


class sale_donation_stock_moves(osv.osv_memory):
    _name = 'sale.donation.stock.moves'

    _colmuns = {
        'report_date': fields.datetime(
            string='Date of the demand',
            readonly=True,
        ),
        'start_date': fields.date(
            string='Start date',
        ),
        'end_date': fields.date(
            string='End date',
        ),
    }

    _defaults = {
        'report_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    def print_excel(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        and print the report in Excel format.
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        self.get_values(cr, uid, ids, context=context)

        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': 'Donations Report',
            'report_name': 'sale.donation.stock.move.report_xls',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        data = {'ids': ids, 'context': context}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'sale.donation.stock.move.report_xls',
            'datas': data,
            'context': context,
        }

sale_donation_stock_moves()
