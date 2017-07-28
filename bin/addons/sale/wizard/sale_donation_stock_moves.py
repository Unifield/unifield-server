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
from msf_partner import PARTNER_TYPE

import time


class sale_donation_stock_moves(osv.osv_memory):
    _name = 'sale.donation.stock.moves'

    PICKING_STATE = [
        ('draft', 'Draft'),
        ('auto', 'Waiting'),
        ('confirmed', 'Confirmed'),
        ('assigned', 'Available'),
        ('shipped', 'Available Shipped'),
        ('done', 'Closed'),
        ('cancel', 'Cancelled'),
        ('import', 'Import in progress'),
        ('delivered', 'Delivered'),
    ]

    _columns = {
        'start_date': fields.date(
            string='Start date',
        ),
        'end_date': fields.date(
            string='End date',
        ),
        'company_id': fields.many2one(
            'res.company',
            string='Company',
            readonly=True,
        ),
        'partner_id': fields.many2one(
            'res.partner',
            string='Partner',
            help="The partner you want have the donations from",
        ),
        'partner_type': fields.selection(
            PARTNER_TYPE,
            string='Partner Type',
        ),
        'product_id': fields.many2one(
            'product.product',
            string='Product Ref.',
        ),
        'picking_id': fields.many2one(
            'stock.picking',
            string='Move Ref.',
        ),
        'state': fields.selection(
            PICKING_STATE,
            string='Status',
        ),
        'sm_ids': fields.text(
            string='Stock Moves',
            readonly=True
        ),
    }

    _defaults = {
    }


    def get_values(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        '''
        sm_obj = self.pool.get('stock.move')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        type_donation_ids = self.pool.get('stock.picking')._get_type_donation_ids(cr, uid)

        for wizard in self.browse(cr, uid, ids, context=context):
            sm_domain = []

            sm_domain.append(('reason_type_id', 'in', type_donation_ids))

            if wizard.picking_id:
                sm_domain.append(('picking_id', '=', wizard.picking_id))

                sm_ids = [wizard.picking_id.id]
            else:
                if wizard.start_date:
                    sm_domain.append(('date', '>=', wizard.start_date))

                if wizard.end_date:
                    sm_domain.append(('date', '<=', wizard.end_date))

                if wizard.partner_id:
                    sm_domain.append(('partner_id', '=', wizard.partner_id.id))

                if wizard.partner_type:
                    sm_domain.append(('partner_id.partner_type', '=', wizard.partner_type))

                if wizard.product_id:
                    sm_domain.append(('product_id', '=', wizard.product_id.id))

                if wizard.state:
                    sm_domain.append(('state', '=', wizard.state))

                sm_ids = sm_obj.search(cr, uid, sm_domain, context=context)

                if not sm_ids:
                    raise osv.except_osv(
                        _('Error'),
                        _('No data found with these parameters'),
                    )

            self.write(cr, uid, [wizard.id], {'sm_ids': sm_ids}, context=context)

        return True

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
            'file_name': 'Donation Report',
            'report_name': 'sale.donation.stock.moves.report_xls',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        data = {'ids': ids, 'context': context}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'sale.donation.stock.moves.report_xls',
            'datas': data,
            'context': context,
        }

    def partner_onchange(self, cr, uid, ids, partner_id=False, picking_id=False):
        '''
        If the partner is changed, check if the picking is to this partner
        '''
        sp_obj = self.pool.get('stock.picking')

        res = {}

        if partner_id and picking_id:
            sp_ids = sp_obj.search(cr, uid, [
                ('id', '=', picking_id),
                ('partner_id', '=', partner_id),
            ], count=True)
            if not sp_ids:
                res['value'] = {'picking_id': False}
                res['warning'] = {
                    'title': _('Warning'),
                    'message': _('The partner of the selected picking doesn\'t \
                        match with the selected partner. The selected picking has been reset'),
                }

        if partner_id:
            res['domain'] = {'picking_id': [('is_donation', '=', True), ('partner_id', '=', partner_id)]}
        else:
            res['domain'] = {'picking_id': [('is_donation', '=', True)]}

        return res

sale_donation_stock_moves()
