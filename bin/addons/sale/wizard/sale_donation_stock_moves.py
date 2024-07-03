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


class sale_donation_stock_moves(osv.osv_memory):
    _name = 'sale.donation.stock.moves'

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
        'nomen_manda_0': fields.many2one(
            'product.nomenclature',
            'Product Main Type',
        ),
        'move_id': fields.many2one(
            'stock.move',
            string='Move Ref.',
        ),
        'sm_ids': fields.text(
            string='Stock Moves',
            readonly=True
        ),
        'display_bn_ed': fields.boolean(
            string='Display BN/ED details',
        ),
    }

    _defaults = {
        'display_bn_ed': False,
    }


    def get_values(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        '''
        sm_obj = self.pool.get('stock.move')
        prod_obj = self.pool.get('product.product')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        type_donation_ids = self.pool.get('stock.picking')._get_type_donation_ids(cr, uid)

        for wizard in self.browse(cr, uid, ids, context=context):
            sm_domain = []

            sm_domain.append(('reason_type_id', 'in', type_donation_ids))
            sm_domain += ['|', ('type', '=', 'in'), '&', ('location_id.usage', '=', 'internal'), ('location_dest_id.usage', 'in', ['customer', 'supplier'])]

            if wizard.move_id:
                sm_domain.append(('move_id', '=', wizard.move_id))

                sm_ids = [wizard.move_id.id]
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
                    if wizard.nomen_manda_0:
                        if prod_obj.search(cr, uid, [('id', '=', wizard.product_id.id), ('nomen_manda_0', '=', wizard.nomen_manda_0.id)], limit=1, context=context):
                            sm_domain.append(('product_id', '=', wizard.product_id.id))
                        else:
                            raise osv.except_osv(_('Error'), _('The Product (%s) does not have this Nomenclature')
                                                 % (wizard.product_id.default_code))
                    else:
                        sm_domain.append(('product_id', '=', wizard.product_id.id))
                elif wizard.nomen_manda_0:
                    prod_ids = prod_obj.search(cr, uid, [('nomen_manda_0', '=', wizard.nomen_manda_0.id)], context=context)
                    if prod_ids:
                        sm_domain.append(('product_id', 'in', prod_ids))

                if wizard.display_bn_ed:
                    sm_domain.append(('state', '!=', 'cancel'))
                else:
                    sm_domain.append(('state', '=', 'done'))

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

        if isinstance(ids, int):
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

    def donation_report_onchange(self, cr, uid, ids, partner_id=False, move_id=False, display_bn_ed=False):
        '''
        If the partner is changed, check if the move is to this partner
        If the BN/ED checkbox is changed, check if the move is state-restricted
        '''
        sm_obj = self.pool.get('stock.move')

        res = {}

        if partner_id and move_id:
            sm_ids = sm_obj.search(cr, uid, [
                ('id', '=', move_id),
                ('partner_id', '=', partner_id),
            ], count=True)
            if not sm_ids:
                res['value'] = {'move_id': False}
                res['warning'] = {
                    'title': _('Warning'),
                    'message': _('The partner of the selected move doesn\'t \
                        match with the selected partner. The selected move has been reset'),
                }

        sm_domain = [
            ('reason_type_id.name', 'in', ['In-Kind Donation', 'Donation to prevent losses', 'Donation (standard)']),
            '|', ('type', '=', 'in'), '&', ('location_id.usage', '=', 'internal'),
            ('location_dest_id.usage', 'in', ['customer', 'supplier'])
        ]

        if display_bn_ed:
            sm_domain.append(('state', '!=', 'cancel'))
        else:
            sm_domain.append(('state', '=', 'done'))

        if partner_id:
            sm_domain.append(('partner_id', '=', partner_id))

        res['domain'] = {'move_id': sm_domain}

        return res


sale_donation_stock_moves()
