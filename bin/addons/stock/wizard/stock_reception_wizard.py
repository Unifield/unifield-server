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
from order_types import ORDER_CATEGORY

import time

ORDER_TYPES_SELECTION = [
    ('regular', _('Regular')),
    ('donation_exp', _('Donation before expiry')),
    ('donation_st', _('Standard donation')),
    ('loan', _('Loan')),
    ('in_kind', _('In Kind Donation')),
    ('purchase_list', _('Purchase List')),
    ('direct', _('Direct Purchase Order')),
]


class stock_reception_wizard(osv.osv_memory):
    _name = 'stock.reception.wizard'
    _rec_name = 'report_date'

    _columns = {
        'report_date': fields.datetime(string='Date of the demand', readonly=True),
        'company_id': fields.many2one('res.company', string='Company', readonly=True),
        'moves_ids': fields.text(string='Moves', readonly=True),
        'start_date': fields.date(string='Actual Receipt Date from'),
        'end_date': fields.date(string='Actual Receipt Date to'),
        'reason_type_id': fields.many2one('stock.reason.type', string='Reason type'),
        'partner_id': fields.many2one('res.partner', string='Partner', help="The partner you want have the IN data"),
        'order_category': fields.selection(ORDER_CATEGORY, string='Order Category'),
        'order_type': fields.selection(ORDER_TYPES_SELECTION, string='Order Type'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Product Main Type'),
        'location_dest_id': fields.many2one('stock.location', 'Reception Destination', select=True,
                                            help="Location where the system will stock the finished products."),
        'final_dest_id': fields.many2one('stock.location', 'Final Dest. Location', select=True,
                                          help="Location where the stock will be at the end of the flow."),
        'final_partner_id': fields.many2one('res.partner', 'Final Dest. Partner', select=True,
                                             help="Partner where the stock will be at at the end of the flow."),
    }

    _defaults = {
        'report_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self, cr, uid, ids, c={}: self.pool.get('res.users').browse(cr, uid, uid).company_id.id,
    }

    def onchange_final_dest_id(self, cr, uid, ids, final_dest_id, context=None):
        if context is None:
            context = {}

        res = {}
        if final_dest_id:
            res.update({'value': {'final_partner_id': False}})

        return res

    def onchange_final_partner_id(self, cr, uid, ids, final_partner_id, context=None):
        if context is None:
            context = {}

        res = {}
        if final_partner_id:
            res.update({'value': {'final_dest_id': False}})

        return res

    def get_values(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        '''
        move_obj = self.pool.get('stock.move')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        model_obj = self.pool.get('ir.model.data')
        cross_docking_id = model_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        loan_rt_id = model_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan')[1]
        no_match = False
        for wizard in self.browse(cr, uid, ids, context=context):
            move_domain = [
                ('type', '=', 'in'),
                ('picking_id.state', '=', 'done'),
                ('state', '=', 'done'),
            ]
            if wizard.start_date:
                move_domain.append(('picking_id.date_done', '>=', wizard.start_date))

            if wizard.end_date:
                move_domain.append(('picking_id.date_done', '<=', wizard.end_date))

            if wizard.reason_type_id:
                move_domain.append(('reason_type_id', '=', wizard.reason_type_id.id))

            if wizard.partner_id:
                move_domain.append(('picking_id.partner_id', '=', wizard.partner_id.id))

            if wizard.order_category:
                move_domain.append(('picking_id.order_category', '=', wizard.order_category))

            if wizard.order_type:
                move_domain.extend((('purchase_line_id', '!=', False), ('purchase_line_id.order_id.order_type', '=', wizard.order_type)))

            if wizard.nomen_manda_0:
                move_domain.append(('product_id.nomen_manda_0', '=', wizard.nomen_manda_0.id))

            if wizard.location_dest_id:
                move_domain.append(('location_dest_id', '=', wizard.location_dest_id.id))

            final_dest_moves = []
            if wizard.final_dest_id:
                f_dest_id = wizard.final_dest_id.id
                cr.execute('''
                SELECT CASE
                    WHEN sol.procurement_request = 't' AND dm.location_dest_id = %s AND dp.type = 'internal' AND sloc.usage = 'internal' THEN m.id
                    WHEN sol.procurement_request = 't' AND m.location_dest_id = %s AND sloc.usage != 'customer' THEN m.id
                    WHEN sol.procurement_request = 't' AND (dm.location_dest_id = %s OR (m.move_dest_id IS NULL AND sloc.id = %s)) 
                        AND m.location_dest_id = %s THEN m.id
                    WHEN dm.location_dest_id = %s AND dp.type = 'internal' AND dm.state = 'done' THEN m.id
                    ELSE NULL
                    END
                FROM stock_move m 
                LEFT JOIN stock_picking p ON m.picking_id = p.id
                LEFT JOIN stock_move dm ON m.move_dest_id = dm.id
                LEFT JOIN stock_picking dp ON dm.picking_id = dp.id
                LEFT JOIN purchase_order_line pol ON m.purchase_line_id = pol.id
                LEFT JOIN sale_order_line sol ON pol.linked_sol_id = sol.id
                LEFT JOIN sale_order s ON sol.order_id = s.id
                LEFT JOIN stock_location sloc ON s.location_requestor_id = sloc.id
                WHERE p.state = 'done' AND p.type = 'in' AND p.subtype = 'standard'
                ''', (f_dest_id, cross_docking_id, f_dest_id, f_dest_id, cross_docking_id, f_dest_id))
                for x in cr.fetchall():
                    if x[0]:
                        final_dest_moves.append(x[0])
                if not final_dest_moves:
                    no_match = True

            final_partner_moves = []
            if wizard.final_partner_id:
                f_part_id = wizard.final_partner_id.id
                cr.execute('''
                    SELECT CASE
                        WHEN m.reason_type_id != %s AND sol.procurement_request = 'f' AND s.partner_id = %s THEN m.id
                        WHEN m.reason_type_id != %s AND sol.procurement_request = 't' AND sloc.usage = 'customer' AND dp.type = 'out' AND dp.partner_id = %s THEN m.id
                        WHEN m.reason_type_id != %s AND sol.procurement_request = 't'AND m.move_dest_id IS NULL AND s.partner_id = %s THEN m.id 
                        WHEN m.reason_type_id != %s AND m.location_dest_id = %s AND dp.type = 'out' AND dp.partner_id = %s THEN m.id
                        WHEN m.reason_type_id = %s AND comp.partner_id = %s AND dp.type = 'internal' THEN m.id
                        ELSE NULL
                    END
                FROM stock_move m 
                LEFT JOIN stock_picking p ON m.picking_id = p.id
                LEFT JOIN stock_move dm ON m.move_dest_id = dm.id
                LEFT JOIN stock_picking dp ON dm.picking_id = dp.id
                LEFT JOIN purchase_order_line pol ON m.purchase_line_id = pol.id
                LEFT JOIN sale_order_line sol ON pol.linked_sol_id = sol.id
                LEFT JOIN sale_order s ON sol.order_id = s.id
                LEFT JOIN stock_location sloc ON s.location_requestor_id = sloc.id
                LEFT JOIN res_company comp ON p.company_id = comp.id
                WHERE p.state = 'done' AND p.type = 'in' AND p.subtype = 'standard'
                ''', (loan_rt_id, f_part_id, loan_rt_id, f_part_id, loan_rt_id, f_part_id, loan_rt_id, cross_docking_id,
                      f_part_id, loan_rt_id, f_part_id))
                for x in cr.fetchall():
                    if x[0]:
                        final_partner_moves.append(x[0])
                if not final_partner_moves:
                    no_match = True

            if final_dest_moves and final_partner_moves:
                move_domain.append(('id', 'in', list(set(final_dest_moves).intersection(final_partner_moves))))
            elif final_dest_moves or final_partner_moves:
                move_domain.append(('id', 'in', final_dest_moves or final_partner_moves))

            if no_match:
                move_ids = []
            else:
                move_ids = move_obj.search(cr, uid, move_domain, order='picking_id, line_number', context=context)

            if not move_ids:
                raise osv.except_osv(
                    _('Error'),
                    _('No data found with these parameters'),
                )

            self.write(cr, uid, [wizard.id], {'moves_ids': move_ids}, context=context)

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
            'file_name': _('Receptions Report'),
            'report_name': 'stock.reception.report_xls',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        data = {'ids': ids, 'context': context}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'stock.reception.report_xls',
            'datas': data,
            'context': context,
        }


stock_reception_wizard()
