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

from osv import  osv
from osv import fields
from tools.translate import _

class purchase_order_group(osv.osv_memory):
    _name = "purchase.order.group"
    _description = "Purchase Order Merge"

    _columns = {
        'po_value_id': fields.many2one('purchase.order', string='Template PO', help='All values in this PO will be used as default values for the merged PO'),
        'unmatched_categ': fields.boolean(string='Unmatched categories'),
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form',
                        context=None, toolbar=False, submenu=False):
        """
         Changes the view dynamically
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param context: A standard dictionary
         @return: New arch of view.
        """
        if context is None:
            context={}
        res = super(purchase_order_group, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar,submenu=False)
        if context.get('active_model','') == 'purchase.order' and len(context['active_ids']) < 2:
            raise osv.except_osv(_('Warning'),
                                 _('Please select multiple order to merge in the list view.'))
        return res

    def merge_orders(self, cr, uid, ids, context=None):
        """
             To merge similar type of purchase orders.

             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param ids: the ID or list of IDs
             @param context: A standard dictionary

             @return: purchase order view

        """
        order_obj = self.pool.get('purchase.order')
        mod_obj =self.pool.get('ir.model.data')
        if context is None:
            context = {}
        result = mod_obj._get_id(cr, uid, 'purchase', 'view_purchase_order_filter')
        id = mod_obj.read(cr, uid, result, ['res_id'])

        tmpl_po = self.browse(cr, uid, ids[0], fields_to_fetch=['po_value_id'], context=context).po_value_id
        tmpl_data = {
            'dest_partner_id': tmpl_po.dest_partner_id and tmpl_po.dest_partner_id.id or False,
            'related_sourcing_id': tmpl_po.related_sourcing_id and tmpl_po.related_sourcing_id.id or False
        }
        allorders = order_obj.do_merge(cr, uid, context.get('active_ids',[]), tmpl_data, context=context)
        if not allorders:
            raise osv.except_osv(_('Error'), _('No PO merged !'))
        return {
            'domain': "[('id','in', [" + ','.join(map(str, allorders.keys())) + "])]",
            'name': 'Purchase Orders',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'purchase.order',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'search_view_id': id['res_id'],
            'context': {'search_default_draft': 1, 'search_default_approved': 0,'search_default_create_uid':uid, 'purchase_order': True},
        }

    def default_get(self, cr, uid, fields, context=None):
        res = super(purchase_order_group, self).default_get(cr, uid, fields, context=context)
        if context.get('active_model','') == 'purchase.order' and len(context['active_ids']) < 2:
            raise osv.except_osv(_('Warning'),
                                 _('Please select multiple order to merge in the list view.'))

        res['po_value_id'] = context['active_ids'][-1]

        categories = set()
        for po in self.pool.get('purchase.order').read(cr, uid, context['active_ids'], ['categ'], context=context):
            categories.add(po['categ'])

        if len(categories) > 1:
            res['unmatched_categ'] = True

        return res

purchase_order_group()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
