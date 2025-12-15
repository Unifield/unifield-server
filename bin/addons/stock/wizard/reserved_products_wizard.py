# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from osv import osv, fields
from tools.translate import _
from datetime import datetime
import tools


class reserved_products_wizard(osv.osv):
    _name = "reserved.products.wizard"
    _description = "Reserved Products Export"

    _columns = {
        'location_id': fields.many2one('stock.location', string='Source Location'),
        'product_id': fields.many2one('product.product', string='Product'),
    }

    def get_lines_data(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if not ids:
            raise osv.except_osv(_('Error'), _('An error has occurred with the wizard, please reload the page'))

        loc_obj = self.pool.get('stock.location')
        prod_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        lot_obj = self.pool.get('stock.production.lot')
        pick_obj = self.pool.get('stock.picking')
        ship_obj = self.pool.get('shipment')
        so_line_obj = self.pool.get('sale.order.line')

        wizard = self.browse(cr, uid, ids[0], context=context)
        loc_id = wizard.location_id and wizard.location_id.id or False
        header_loc_name = wizard.location_id and wizard.location_id.name or False
        prod_id = wizard.product_id and wizard.product_id.id or False
        header_prod_name = wizard.product_id and wizard.product_id.default_code or False

        add_sql = ''
        if loc_id:
            add_sql += ' AND location_id = %s' % (loc_id,)
        if prod_id:
            add_sql += ' AND product_id = %s' % (prod_id,)

        cr.execute('''
            SELECT location_id, product_id, product_uom, product_qty, prodlot_id, picking_id, pick_shipment_id, sale_line_id
            FROM stock_move
            WHERE state = 'assigned' AND product_qty > 0 AND type in ('internal', 'out')''' + add_sql + '''
            GROUP BY location_id, product_id, prodlot_id, picking_id, pick_shipment_id, product_uom, sale_line_id, product_qty
            ORDER BY location_id, product_id
        ''')

        lines = cr.fetchall()
        lines_data = []
        tuples = []
        used_sol_ids = []
        line_sum = {}
        sum_ordered_qty, sum_qty, sum_value = 0.00, 0.00, 0.00
        index = 0
        for i, line in enumerate(lines):
            loc_name = loc_obj.browse(cr, uid, line[0], fields_to_fetch=['name'], context=context).name
            product = prod_obj.browse(cr, uid, line[1], fields_to_fetch=['default_code', 'name', 'standard_price', 'currency_id'], context=context)
            uom_name = uom_obj.browse(cr, uid, line[2], fields_to_fetch=['name'], context=context).name
            prodlot = line[4] and lot_obj.browse(cr, uid, line[4], fields_to_fetch=['name', 'life_date'],
                                                 context=context) or False
            pick_name = pick_obj.browse(cr, uid, line[5], fields_to_fetch=['name'], context=context).name
            ship = ship_obj.browse(cr, uid, line[6], fields_to_fetch=['name'], context=context)
            sol = so_line_obj.browse(cr, uid, line[7], fields_to_fetch=['order_id', 'product_uom_qty'], context=context)
            sale = sol and sol.order_id
            currency_name = product and product.currency_id and product.currency_id.name or ''
            po_name = ''
            if sol:
                cr.execute('''SELECT p.name FROM purchase_order_line pl LEFT JOIN purchase_order p ON pl.order_id = p.id
                           WHERE pl.linked_sol_id = %s''', (sol.id,))
                res_fetch = cr.fetchone()
                po_name = res_fetch and res_fetch[0] or ''
            docs_name = pick_name or ''
            if ship:
                docs_name += pick_name and '/' + ship.name or ship.name
            lines_data.append({
                'sum_line': False,
                'loc_name': loc_name,
                'prod_name': product and product.default_code or False,
                'prod_desc': product and tools.ustr(product.name) or False,
                'prod_uom': uom_name,
                'batch': prodlot and prodlot.name or '',
                'exp_date': prodlot and prodlot.life_date or '',
                'prod_qty': line[3],
                'documents': docs_name,
                'so_name': sale and sale.name or '',
                'partner_name': sale and not sale.procurement_request and sale.partner_id and sale.partner_id.name or '',
                'origin': sale and sale.procurement_request and sale.location_requestor_id and sale.location_requestor_id.name or '',
                'customer_ref': sale and sale.client_order_ref and sale.client_order_ref.split('.')[-1] or '',
                'so_details': sale and sale.details or '',
                'sum_ordered_qty': 0.00,
                'sum_qty': 0.00,
                'sum_value': 0.00,
                'currency': currency_name,
                'po_name': po_name,
            })
            current_tuple = (loc_name, product and product.id or False, prodlot and prodlot.name or False)
            if current_tuple in tuples:
                if sol and sol.id not in used_sol_ids:
                    sum_ordered_qty += sol.product_uom_qty or 0.00
                    used_sol_ids.append(sol.id)
                sum_qty += line[3]
                sum_value += product and line[3] * product.standard_price or 0.00
                line_sum.update({'sum_ordered_qty': sum_ordered_qty, 'sum_qty': sum_qty, 'sum_value': sum_value})
            else:
                if line_sum:
                    lines_data.insert(index, line_sum)
                if sol:
                    sum_ordered_qty = sol.product_uom_qty or 0.00
                    used_sol_ids.append(sol.id)
                else:
                    sum_ordered_qty = 0.00
                sum_qty = line[3]
                sum_value = product and line[3] * product.standard_price or 0.00
                line_sum = {
                    'sum_line': True,
                    'loc_name': loc_name,
                    'prod_name': product and product.default_code or False,
                    'prod_desc': product and tools.ustr(product.name) or False,
                    'prod_uom': uom_name,
                    'batch': prodlot and prodlot.name or '',
                    'exp_date': prodlot and prodlot.life_date or '',
                    'prod_qty': 0.00,
                    'documents': '',
                    'so_name': '',
                    'partner_name': '',
                    'origin': '',
                    'customer_ref': '',
                    'so_details': '',
                    'sum_ordered_qty': sum_ordered_qty,
                    'sum_qty': sum_qty,
                    'sum_value': sum_value,
                    'currency': currency_name,
                    'po_name': '',
                }
                tuples.append(current_tuple)
                index = len(lines_data) - 1
            if i == len(lines) - 1:
                lines_data.insert(index, line_sum)

        return {'loc_name': header_loc_name, 'prod_name': header_prod_name, 'lines_data': lines_data}

    def export_reserved_products_report_xls(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        wiz = self.browse(cr, uid, ids[0], context=context)
        add_sql = ''
        if wiz.location_id:
            add_sql += ' AND location_id = %s' % (wiz.location_id.id,)
        if wiz.product_id:
            add_sql += ' AND product_id = %s' % (wiz.product_id.id,)
        cr.execute('''
            SELECT COUNT(id) FROM stock_move
            WHERE state = 'assigned' AND product_qty > 0 AND type in ('internal', 'out')
        ''' + add_sql)
        nb_res = cr.fetchall()
        if nb_res[0][0] == 0:
            raise osv.except_osv(_('Error'), _('No data found with these parameters'))

        file_name = _('Reserved_Product_Report_%s') % (datetime.today().strftime('%Y%m%d_%H_%M'),)

        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': file_name,
            'report_name': 'reserved.products.report_xls',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'reserved.products.report_xls',
            'datas': {'wizard_id': ids, 'target_filename': file_name},
            'context': context,
        }


reserved_products_wizard()
