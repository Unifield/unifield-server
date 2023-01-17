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

import datetime

from osv import osv
from osv import fields

from tools.translate import _
from tools.misc import float_uom_to_str
from order_types import ORDER_PRIORITY, ORDER_CATEGORY

ORDER_TYPE = [('regular', 'Regular'), ('donation_exp', 'Donation before expiry'),
              ('donation_st', 'Standard donation'), ('loan', 'Loan'), ('loan_return', 'Loan Return'),
              ('in_kind', 'In Kind Donation'), ('purchase_list', 'Purchase List'),
              ('direct', 'Direct Purchase Order')]

class purchase_order_followup(osv.osv_memory):
    _name = 'purchase.order.followup'
    _description = 'Purchase Order Followup'

    def _shipped_rate(self, cr, uid, line, context=None):
        '''
        Return the shipped rate of a PO line
        '''
        uom_obj = self.pool.get('product.uom')
        line_value = line.product_qty
        move_value = 0.00
        for move in line.move_ids:
            if move.state == 'done':
                product_qty = uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, line.product_uom.id)
                if move.type == 'out':
                    move_value -= product_qty
                elif move.type == 'in':
                    move_value += product_qty

        return round((move_value/line_value)*100, 2)

    def _get_move_state(self, cr, uid, move_state, context=None):
        return self.pool.get('ir.model.fields').get_selection(cr, uid, 'stock.move', 'state', move_state, context)

    def update_view(self, cr, uid, ids, context=None):
        '''
        Reload the view
        '''
        if context is None:
            context = {}
        if ids:
            order_id = self.browse(cr, uid, ids, context=context)[0].order_id.id
        else:
            raise osv.except_osv(_('Error'), _('Order followup not found !'))

        self.unlink(cr, uid, ids, context=context)

        context.update({'active_id': order_id,
                        'active_ids': [order_id],
                        'update': True})

        return self.start_order_followup(cr, uid, ids, context)

    def close_view(self, cr, uid, ids, context=None):
        '''
        Close the view
        '''
        return {'type': 'ir.actions.act_window_close'}

    def start_order_followup(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if not context.get('lang'):
            context['lang'] = self.pool.get('res.users').read(cr, uid, uid, ['context_lang'])['context_lang']
        # openERP BUG ?
        ids = context.get('active_ids',[])
        split = True

        if not ids:
            raise osv.except_osv(_('Error'), _('No order found !'))
        if len(ids) != 1:
            raise osv.except_osv(_('Error'),
                                 _('You should select one order to follow !'))

        order_obj = self.pool.get('purchase.order')
        line_obj = self.pool.get('purchase.order.followup.line')

        for order in order_obj.browse(cr, uid, ids, context=context):
            if not order_obj.search(cr, uid, [('id', '=', order.id), ('has_confirmed_or_further_line', '=', True)], context=context):
                raise osv.except_osv(_('Error'),
                                     _('You can only follow up confirmed Purchase order (lines)'))

            followup_id = self.create(cr, uid,
                                      {'order_id': order.id}, context=context)

            order_ids = order_obj.search(cr, uid, [('id', '!=', order.id), ('name', 'like', order.name)], context=context)
            if not order_ids:
                split = False
                order_ids = [order.id]

            for o in order_obj.browse(cr, uid, order_ids, context=context):
                for line in o.order_line:
                    # If the line has no moves
                    if not line.move_ids:
                        line_data = {'followup_id': followup_id,
                                     'order_id': line.order_id and line.order_id.id or False,
                                     'move_id': False,
                                     'line_id': line.id,
                                     'picking_id': False,
                                     'move_state': 'No move',
                                     'line_name': line.line_number,
                                     'line_product_id': line.product_id.id,
                                     'line_product_qty': float_uom_to_str(line.product_qty, line.product_uom),
                                     'line_uom_id': line.product_uom.id,
                                     'line_confirmed_date': line.confirmed_delivery_date,
                                     'line_shipped_rate': 0.0,
                                     'move_product_id': False,
                                     'move_product_qty': '',
                                     'move_uom_id': False,
                                     'move_delivery_date': False,
                                     'return_move': False,
                                     }
                        line_obj.create(cr, uid, line_data, context=context)
                    first_move = True
                    move_ids1 = []
                    move_ids2 = []
                    move_ids3 = []
                    move_ids4 = []
                    move_ids5 = []
                    for move in line.move_ids:
                        if move.type in ('internal', 'out'):
                            continue
                        elif move.state == 'done':
                            move_ids1.append(move)
                        elif move.product_id.id == line.product_id.id:
                            move_ids2.append(move)
                        elif move.product_uom.id == line.product_uom.id:
                            move_ids3.append(move)
                        elif move.date_expected == line.confirmed_delivery_date:
                            move_ids4.append(move)
                        else:
                            move_ids4.append(move)
                    for move_ids in [move_ids1, move_ids2, move_ids3, move_ids4, move_ids5]:
                        for move in move_ids:
                            line_shipped_rate = "no-progressbar"
                            if first_move:
                                line_shipped_rate = self._shipped_rate(cr, uid, line, context)
                            line_data = {'followup_id': followup_id,
                                         'order_id': line.order_id and line.order_id.id or False,
                                         'move_id': move.id,
                                         'line_id': line.id,
                                         'picking_id': move.picking_id.id,
                                         'move_state': self._get_move_state(cr, uid, move.state, context=context),
                                         'line_name': line.line_number,
                                         'line_product_id': first_move and line.product_id.id or False,
                                         'line_product_qty': first_move and float_uom_to_str(line.product_qty, line.product_uom) or False,
                                         'line_uom_id': first_move and line.product_uom.id or False,
                                         'line_confirmed_date': first_move and line.confirmed_delivery_date or False,
                                         'line_shipped_rate': line_shipped_rate,
                                         'move_product_id': line.product_id.id != move.product_id.id and move.product_id.id or False,
                                         'move_product_qty': (line.product_qty != move.product_qty or line.product_id.id != move.product_id.id) and float_uom_to_str(move.product_qty, move.product_uom or line.product_uom) or '',
                                         'move_uom_id': line.product_uom.id != move.product_uom.id and move.product_uom.id or False,
                                         'move_delivery_date': line.confirmed_delivery_date != move.date[:10] and move.date[:10] or False,
                                         'return_move': move.type == 'out',
                                         }
                            line_obj.create(cr, uid, line_data, context=context)

                            # Unflag the first move
                            if first_move:
                                first_move = False

        if split:
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'purchase_followup', 'purchase_order_followup_split_form_view')[1]
        else:
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'purchase_followup', 'purchase_order_followup_form_view')[1]

        res = {'type': 'ir.actions.act_window',
               'res_model': 'purchase.order.followup',
               'view_type': 'form',
               'view_mode': 'form',
               'view_id': [view_id],
               'res_id': followup_id,
               'context': context,}

        # If update the view, return the view in the same screen
        if context.get('update'):
            res.update({'target': 'dummy'})

        return res

    def export_get_file_name(self, cr, uid, ids, prefix='PO_Follow_Up', context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if len(ids) != 1:
            return False
        foup = self.browse(cr, uid, ids[0], context=context)
        if not foup or not foup.order_id or not foup.order_id.name:
            return False
        dt_now = datetime.datetime.now()
        po_name = "%s_%s_%d_%02d_%02d" % (prefix,
                                          foup.order_id.name.replace('/', '_'),
                                          dt_now.year, dt_now.month, dt_now.day)
        return po_name

    def export_xls(self, cr, uid, ids, context=None):
        """
        Print the report (Excel)
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        datas = {'ids': ids}
        file_name = self.export_get_file_name(cr, uid, ids, context=context)
        if file_name:
            datas['target_filename'] = file_name
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'purchase.follow.up.report_xls',
            'datas': datas,
            'context': context,
            'nodestroy': True,
        }

    def export_pdf(self, cr, uid, ids, context=None):
        """
        Print the report (PDF)
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        datas = {'ids': ids}
        file_name = self.export_get_file_name(cr, uid, ids, context=context)
        if file_name:
            datas['target_filename'] = file_name
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'purchase.follow.up.report_pdf',
            'datas': datas,
            'context': context,
            'nodestroy': True,
        }

    _columns = {
        'order_id': fields.many2one('purchase.order', string='Order reference', readonly=True),
        'supplier_ref': fields.related('order_id', 'partner_ref', string='Supplier Reference', readonly=True, type='char'),
        'delivery_requested_date': fields.related('order_id', 'delivery_requested_date', string='Delivery requested date', type='date', readonly=True),
        'delivery_confirmed_date': fields.related('order_id', 'delivery_confirmed_date', string='Delivery confirmed date', type='date', readonly=True),
        'partner_id': fields.related('order_id', 'partner_id', string='Supplier', type='many2one', relation='res.partner', readonly=True),
        'partner_ref': fields.related('order_id', 'partner_ref', string='Supplier reference', type='char', readonly=True),
        'order_type': fields.related('order_id', 'order_type', string='Order Type', type='selection', selection=ORDER_TYPE, readonly=True),
        'priority': fields.related('order_id', 'priority', string='Priority', type='selection', selection=ORDER_PRIORITY, readonly=True),
        'categ': fields.related('order_id', 'categ', string='Order Category', type='selection', selection=ORDER_CATEGORY, readonly=True),
        'line_ids': fields.one2many('purchase.order.followup.line', 'followup_id', readonly=True),

    }

purchase_order_followup()

class purchase_order_followup_line(osv.osv_memory):
    _name = 'purchase.order.followup.line'
    _description = 'Purchase Order Followup Line'
    _rec_name = 'move_id'

    _columns = {
        'move_id': fields.many2one('stock.move', string='Move'),
        'order_id': fields.many2one('purchase.order', string='Order'),
        'line_id': fields.many2one('purchase.order.line', string='Order line'),
        'followup_id': fields.many2one('purchase.order.followup', string='Follow-up'),
        'line_name': fields.char(size=64, string='#'),
        'line_product_id': fields.many2one('product.product', string='Product'),
        'line_product_qty': fields.char(size=64, string='Qty'),
        'line_uom_id': fields.many2one('product.uom', string='UoM'),
        'line_confirmed_date': fields.date(string='Del. Conf. date'),
        'line_shipped_rate': fields.float(digits=(16,2), string='% of line received'),
        'picking_id': fields.many2one('stock.picking', string='Incoming shipment'),
        'move_product_id': fields.many2one('product.product', string='New product'),
        'move_product_qty': fields.char(size=64, string='New Qty'),
        'move_uom_id': fields.many2one('product.uom', string='New UoM'),
        'move_delivery_date': fields.date(string='New Del. date'),
        'move_state': fields.char(size=64, string='State'),
        'return_move': fields.boolean(string='Is a return move ?'),
    }

    def read(self, cr, uid, ids, fields, context=None, load='_classic_write'):
        res = super(purchase_order_followup_line, self).read(cr, uid, ids, fields, context=context, load=load)

        if context.get('export'):
            for r in res:
                if 'line_shipped_rate' in r and r['line_shipped_rate'] == 'no-progressbar':
                    r['line_shipped_rate'] = 0.00

        return res

    def go_to_incoming(self, cr, uid, ids, context=None):
        '''
        Open the associated Incoming shipment
        '''
        for line in self.browse(cr, uid, ids, context=context):
            if not line.picking_id:
                raise osv.except_osv(_('Error'), _('This line has no incoming shipment !'))
            xmlid = self.pool.get('stock.picking')._hook_picking_get_view(cr, uid, ids, context=context, pick=line.picking_id)
            res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, xmlid, ['form', 'tree'], context=context)
            res['res_id'] = line.picking_id.id
            return res

purchase_order_followup_line()

class purchase_order_followup_from_menu(osv.osv_memory):
    _name = 'purchase.order.followup.from.menu'
    _description = 'Purchase order followup menu entry'

    _columns = {
        'order_id': fields.many2one('purchase.order', string='PO reference', required=True),
        'cust_order_id': fields.many2one('purchase.order', string='Supplier reference', required=True),
        'incoming_id': fields.many2one('stock.picking', string='Incoming shipment', required=True),
        'cust_order_id2': fields.many2one('purchase.order', string='Customer Name', required=True),
    }

    def go_to_followup(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        new_context = context.copy()
        new_ids = []
        for menu in self.browse(cr, uid, ids, context=context):
            if menu.order_id:
                new_ids.append(menu.order_id.id)
            elif menu.cust_order_id.id:
                new_ids.append(menu.cust_order_id.id)
            elif menu.cust_order_id2.id:
                new_ids.append(menu.cust_order_id2.id)
            else:
                new_ids.append(menu.incoming_id.purchase_id.id)

        new_context['active_ids'] = new_ids

        return self.pool.get('purchase.order.followup').start_order_followup(cr, uid, ids, context=new_context)

    def change_order_id(self, cr, uid, ids, order_id, cust_order_id, incoming_id, cust_order_id2, type='order_id'):
        res = {}

        if type == 'cust_order_id' and cust_order_id:
            res.update({'order_id': False, 'incoming_id': False, 'cust_order_id2': False})
        elif type == 'order_id' and order_id:
            res.update({'cust_order_id': False, 'incoming_id': False, 'cust_order_id2': False})
        elif type == 'incoming_id' and incoming_id:
            res.update({'cust_order_id': False, 'order_id': False, 'cust_order_id2': False})
        if type == 'cust_order_id2' and cust_order_id2:
            res.update({'cust_order_id': False, 'order_id': False, 'incoming_id': False})

        return {'value': res}

purchase_order_followup_from_menu()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
