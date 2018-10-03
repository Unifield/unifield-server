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
        'location_id': fields.many2one('stock.location', string='Location'),
        'product_id': fields.many2one('product.product', string='Product'),
    }

    def get_lines_data(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if not ids:
            raise osv.except_osv(_('Error'), _('An error has occured with the wizard, please reload the page'))

        loc_obj = self.pool.get('stock.location')
        prod_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        lot_obj = self.pool.get('stock.production.lot')
        pick_obj = self.pool.get('stock.picking')
        partner_obj = self.pool.get('res.partner')

        wizard = self.browse(cr, uid, ids[0], context=context)
        loc_id = wizard.location_id and wizard.location_id.id or False
        loc_name = wizard.location_id and wizard.location_id.name or False
        prod_id = wizard.product_id and wizard.product_id.id or False
        prod_name = wizard.product_id and wizard.product_id.name or False

        if loc_id and prod_id:
            cr.execute('''
                SELECT location_id, product_id, product_uom, product_qty, prodlot_id, picking_id, partner_id, origin
                FROM stock_move
                WHERE state = 'assigned' AND product_qty > 0 AND type in ('internal', 'out')
                    AND location_id = %s AND product_id = %s
                GROUP BY location_id, product_id, prodlot_id, picking_id, product_uom, partner_id, origin, product_qty
                ORDER BY location_id, product_id
            ''', (loc_id, prod_id))
        elif loc_id and not prod_id:
            cr.execute('''
                SELECT location_id, product_id, product_uom, product_qty, prodlot_id, picking_id, partner_id, origin
                FROM stock_move
                WHERE state = 'assigned' AND product_qty > 0 AND type in ('internal', 'out') AND location_id = %s
                GROUP BY location_id, product_id, prodlot_id, picking_id, product_uom, partner_id, origin, product_qty
                ORDER BY location_id, product_id
            ''', (loc_id,))
        elif not loc_id and prod_id:
            cr.execute('''
                SELECT location_id, product_id, product_uom, product_qty, prodlot_id, picking_id, partner_id, origin
                FROM stock_move
                WHERE state = 'assigned' AND product_qty > 0 AND type in ('internal', 'out') AND product_id = %s
                GROUP BY location_id, product_id, prodlot_id, picking_id, product_uom, partner_id, origin, product_qty
                ORDER BY location_id, product_id
            ''', (prod_id,))
        else:
            cr.execute('''
                SELECT location_id, product_id, product_uom, product_qty, prodlot_id, picking_id, partner_id, origin
                FROM stock_move
                WHERE state = 'assigned' AND product_qty > 0 AND type in ('internal', 'out')
                GROUP BY location_id, product_id, prodlot_id, picking_id, product_uom, partner_id, origin, product_qty
                ORDER BY location_id, product_id
            ''')

        lines = cr.fetchall()
        lines_data = []
        tuples = []
        line_sum = {}
        sum_qty = 0.00
        index = 0
        for i, line in enumerate(lines):
            loc_name = loc_obj.browse(cr, uid, line[0], fields_to_fetch=['name'], context=context).name
            product = prod_obj.browse(cr, uid, line[1], fields_to_fetch=['default_code', 'name'], context=context)
            uom_name = uom_obj.browse(cr, uid, line[2], fields_to_fetch=['name'], context=context).name
            prodlot = line[4] and lot_obj.browse(cr, uid, line[4], fields_to_fetch=['name', 'life_date'],
                                                 context=context) or False
            pick_name = pick_obj.browse(cr, uid, line[5], fields_to_fetch=['name'], context=context).name
            partner_name = partner_obj.browse(cr, uid, line[6], fields_to_fetch=['name'], context=context).name
            lines_data.append({
                'sum_line': False,
                'loc_name': loc_name,
                'prod_name': product and product.default_code or False,
                'prod_desc': product and tools.ustr(product.name) or False,
                'prod_uom': uom_name,
                'batch': prodlot and prodlot.name or '',
                'exp_date': prodlot and prodlot.life_date or '',
                'prod_qty': line[3],
                'pick_name': pick_name,
                'partner_name': partner_name,
                'origin': line[7],
                'sum_qty': 0.00,
            })
            current_tuple = (loc_name, product and product.id or False, prodlot and prodlot.name or False)
            if current_tuple in tuples:
                sum_qty += line[3]
                line_sum.update({'sum_qty': sum_qty})
            else:
                if line_sum:
                    lines_data.insert(index, line_sum)
                sum_qty = line[3]
                line_sum = {
                    'sum_line': True,
                    'loc_name': loc_name,
                    'prod_name': product and product.default_code or False,
                    'prod_desc': product and tools.ustr(product.name) or False,
                    'prod_uom': uom_name,
                    'batch': prodlot and prodlot.name or '',
                    'exp_date': prodlot and prodlot.life_date or '',
                    'prod_qty': 0.00,
                    'pick_name': '',
                    'partner_name': '',
                    'origin': '',
                    'sum_qty': line[3],
                }
                tuples.append(current_tuple)
                index = len(lines_data) - 1
            if i == len(lines) - 1:
                lines_data.insert(index, line_sum)

        return {'loc_name': loc_name, 'prod_name': prod_name, 'lines_data': lines_data}

    def export_reserved_products_report_xls(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        wiz = self.browse(cr, uid, ids[0], context=context)
        if wiz.location_id and wiz.product_id:
            cr.execute('''
                SELECT COUNT(id) FROM stock_move 
                WHERE state = 'assigned' AND product_qty > 0 AND type in ('internal', 'out')
                    AND location_id = %s AND product_id = %s''', (wiz.location_id.id, wiz.product_id.id))
        elif wiz.location_id and not wiz.product_id:
            cr.execute('''
                SELECT COUNT(id) FROM stock_move 
                WHERE state = 'assigned' AND product_qty > 0 AND type in ('internal', 'out') AND location_id = %s
            ''', (wiz.location_id.id,))
        elif not wiz.location_id and wiz.product_id:
            cr.execute('''
                SELECT COUNT(id) FROM stock_move 
                WHERE state = 'assigned' AND product_qty > 0 AND type in ('internal', 'out') AND product_id = %s
            ''', (wiz.product_id.id,))
        else:
            cr.execute('''
                SELECT COUNT(id) FROM stock_move 
                WHERE state = 'assigned' AND product_qty > 0 AND type in ('internal', 'out')
            ''')
        nb_res = cr.fetchall()
        if nb_res[0][0] == 0:
            raise osv.except_osv(_('Error'), _('No data found with these parameters'))

        file_name = _('%s-Product reservation report - excel export') % (datetime.today().strftime('%Y%m%d'),)

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
