# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF.
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
from order_types import ORDER_PRIORITY, ORDER_CATEGORY

import netsvc
import decimal_precision as dp


class wizard_compare_rfq(osv.osv_memory):
    _name = 'wizard.compare.rfq'
    _description = 'Compare Quotations'

    _columns = {
        'line_ids': fields.one2many(
            'wizard.compare.rfq.line',
            'compare_id',
            string='Lines',
        ),
        'tender_id': fields.many2one(
            'tender',
            string="Tender",
            readonly=True,
        ),
        'creator': fields.many2one(
            'res.users',
            string='Creator',
            readonly=True,
        ),
        'creation_date': fields.date(
            string="Creation Date",
            readonly=True,
        ),
        'name': fields.char(
            'Tender Reference',
            size=64,
            readonly=True,
        ),
        'sale_order_id': fields.many2one(
            'sale.order',
            string="Sale Order",
            readonly=True,
        ),
        'requested_date': fields.date(
            string="Requested Date",
            readonly=True,
        ),
        'location_id': fields.many2one(
            'stock.location',
            string='Location',
            readonly=True,
        ),
        'categ': fields.selection(
            ORDER_CATEGORY,
            string='Tender Category',
            readonly=True,
        ),
        'warehouse_id': fields.many2one(
            'stock.warehouse',
            string='Warehouse',
            readonly=True,
        ),
        'details': fields.char(
            size=30,
            string='Details',
            readonly=True,
        ),
        'priority': fields.selection(
            ORDER_PRIORITY,
            string='Tender Priority',
            readonly=True,
        ),
        'notes': fields.text(
            string='Notes',
            readonly=True,
        ),
    }

    def start_compare_rfq(self, cr, uid, ids, context=None):
        """
        Build the compare RfQ wizard
        """
        t_obj = self.pool.get('tender')
        wcr_obj = self.pool.get('wizard.compare.rfq')
        wcrl_obj = self.pool.get('wizard.compare.rfq.line')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for tender in t_obj.browse(cr, uid, ids, context=context):
            line_dict = {}
            for line in tender.tender_line_ids:
                if line.line_state != 'draft':
                    continue

                cs_id = False       # Choosen supplier ID
                rfql_id = False     # Choosen RfQ line ID
                if line.purchase_order_line_id:
                    cs_id = line.purchase_order_line_id.order_id.partner_id.id
                    rfql_id = line.purchase_order_line_id.id

                line_dict.update({
                    line.id: {
                        'tender_line_id': line.id,
                        'product_code': line.product_id.default_code,
                        'product_name': line.product_id.name,
                        'quantity': line.qty,
                        'uom_id': line.product_uom.id,
                        'choosen_supplier_id': cs_id,
                        'rfq_line_id': rfql_id,
                    },
                })

            if not line_dict:
                raise osv.except_osv(
                    _('Error'),
                    _('Nothing to compare !'),
                )

            so_id = tender.sale_order_id
            loc_id = tender.location_id
            wh_id = tender.warehouse_id
            cmp_id = wcr_obj.create(cr, uid, {
                'tender_id': tender.id,
                'creator': tender.creator and tender.creator.id or False,
                'creation_date': tender.creation_date or False,
                'name': tender.name or '',
                'sale_order_id': so_id and so_id.id or False,
                'requested_date': tender.requested_date or False,
                'location_id': loc_id and loc_id.id or False,
                'categ': tender.categ,
                'priority': tender.priority,
                'warehouse_id': wh_id and wh_id.id or False,
                'details': tender.details or '',
                'notes': tender.notes or '',
            }, context=context)

            context.update({'tender_id': tender.id})

            for line in line_dict.itervalues():
                line_vals = line.copy()
                line_vals['compare_id'] = cmp_id
                wcrl_obj.create(cr, uid, line_vals, context=context)

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.compare.rfq',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': cmp_id,
                'context': context,
            }

    def update_tender(self, cr, uid, ids, context=None):
        '''
        Update the corresponding tender lines

        related rfq line: po_line_id.id
        '''
        t_obj = self.pool.get('tender')
        tl_obj = self.pool.get('tender.line')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        t_id = False    # Tender ID
        for w_brw in self.browse(cr, uid, ids, context=context):
            t_id = w_brw.tender_id.id
            # loop through wizard_compare_rfq_line
            for wl_brw in w_brw.line_ids:
                # check if a supplier has been selected for this product
                pol_id = wl_brw.rfq_line_id and wl_brw.rfq_line_id.id or False
                tl_obj.write(cr, uid, [wl_brw.tender_line_id.id], {
                    'purchase_order_line_id': pol_id,
                }, context=context)

            # UF-733: if all tender lines have been compared (have PO Line id),
            # then set the tender to be ready
            # for proceeding to other actions (create PO, Done etc)
            flag = tl_obj.search(cr, uid, [
                ('tender_id', '=', t_id),
                ('line_state', '!=' ,'cancel'),
                ('purchase_order_line_id', '=', False),
            ], limit=1, context=context)

            t_obj.write(cr, uid, t_id, {
                'internal_state': flag and 'draft' or 'updated',
            }, context=context)

        # Display the corresponding tender
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'tender',
            'view_type': 'form',
            'view_mode': 'form,tree',
            'target': 'crush',
            'res_id': t_id,
            'context': context
        }

wizard_compare_rfq()


class wizard_compare_rfq_line(osv.osv_memory):
    _name = 'wizard.compare.rfq.line'
    _description = 'Compare Quotation Line'

    _columns = {
        'compare_id': fields.many2one(
            'wizard.compare.rfq',
            string='Wizard',
        ),
        'tender_line_id': fields.many2one(
            'tender.line',
            string='Tender line',
        ),
        'product_code': fields.char(
            size=128,
            string='Product Code',
        ),
        'product_name': fields.char(
            size=256,
            string='Product Description',
        ),
        'quantity': fields.float(
            digits=(16,2),
            string='Qty',
        ),
        'uom_id': fields.many2one(
            'product.uom',
            string='UoM',
        ),
        'rfq_line_id': fields.many2one(
            'purchase.order.line',
            string='Selected RfQ line',
        ),
        'choosen_supplier_id': fields.many2one(
            'res.partner',
            string='Selected supplier',
        ),
        'choosen_supplier_name': fields.related(
            'choosen_supplier_id',
            'name',
            string='Selected supplier',
            type='char',
            size=256,
        ),
   }

    def fields_get(self, cr, uid, fields=None, context=None):
        """
        Add some fields according to number of suppliers on the tender.
        """
        t_obj = self.pool.get('tender')

        if context is None:
            context = {}

        res = super(wizard_compare_rfq_line, self).\
            fields_get(cr, uid, fields, context)

        t_id = context.get('tender_id', False)
        s_ids = []
        if t_id:
            s_ids = t_obj.browse(cr, uid, t_id, context=context).supplier_ids

        for sup in s_ids:
            sid = sup.id
            res.update({
                # Name of the supplier
                'name_%s' % sid: {
                    'selectable': True,
                    'type': 'char',
                    'size': 128,
                    'string': 'Supplier',
                },
                # Unit price on the related RfQ line
                'unit_price_%s' % sid: {
                    'selectable': True,
                    'type': 'float',
                    'digits': (16,2),
                    'string': 'Unit price',
                },
                # Comment of the related RfQ line
                'comment_%s' % sid: {
                    'selectable': True,
                    'type': 'text',
                    'string': 'Comment',
                },
            })

        return res

    def read(self, cr, uid, ids, vals, context=None, load='_classic_read'):
        '''
        Read the RfQ lines related to each tender line and each supplier
        and put values on the wizard lines.
        '''
        t_obj = self.pool.get('tender')
        pol_obj = self.pool.get('purchase.order.line')
        cur_obj = self.pool.get('res.currency')
        user_obj = self.pool.get('res.users')

        if context is None:
            context = context

        func_cur_id = user_obj.browse(cr, uid, uid, context=context).company_id.currency_id.id

        # Force the reading of some fields
        forced_flds = [
            'tender_line_id',
        ]
        for ffld in forced_flds:
            if ffld not in vals:
                vals.append(ffld)

        res = super(wizard_compare_rfq_line, self).\
            read(cr, uid, ids, vals, context=context, load=load)

        t_id = context.get('tender_id', False)
        s_ids = []
        if t_id:
            s_ids = t_obj.browse(cr, uid, t_id, context=context).supplier_ids

        for sup in s_ids:
            sid = sup.id
            for r in res:
                rfql_ids = pol_obj.search(cr, uid, [
                    ('order_id.partner_id', '=', sid),
                    ('tender_line_id', '=', r['tender_line_id']),
                ], context=context)
                rfql = None
                pu = 0.00
                if rfql_ids:
                    rfql = pol_obj.browse(cr, uid, rfql_ids[0], context=context)
                    pu = rfql.price_unit
                    same_cur = rfql.order_id.pricelist_id.currency_id.id == func_cur_id
                    if not same_cur:
                        pu = cur_obj.compute(
                            cr, uid,
                            rfql.order_id.pricelist_id.currency_id.id,
                            func_cur_id,
                            pu,
                            round=True)

                r.update({
                    'name_%s' % sid: sup.name,
                    'unit_price_%s' % sid: rfql and pu or 0.00,
                    'comment_%s' % sid: rfql and rfql.comment or '',
                })

        return res

    def fields_view_get(self, cr, uid, view_id=None, view_type='form',
            context=None, toolbar=False, submenu=False):
        """
        Display the computed fields according to number of suppliers in the
        tender.
        """
        t_obj = self.pool.get('tender')

        if context is None:
            context = {}

        res = super(wizard_compare_rfq_line, self).fields_view_get(
            cr, uid, view_id, view_type,
            context=context, toolbar=toolbar,
            submenu=submenu)

        if view_type == 'tree':
            tree_view = """<tree string="Compared products" editable="top">
                <field name="tender_line_id" invisible="1" />
                <field name="product_code" readonly="1" />
                <field name="product_name" readonly="1" />
                <field name="quantity" readonly="1" />
                <field name="uom_id" readonly="1" />
            """
            fld_to_add = ['name', 'unit_price', 'comment']
            t_id = context.get('tender_id', False)
            s_ids = []
            if t_id:
                s_ids = t_obj.\
                    browse(cr, uid, t_id, context=context).supplier_ids

            for sup in s_ids:
                tree_view += """
                    <separator string="|" type="separator" />
                    <button
                        name="select_supplier_%(sid)s"
                        icon="terp-mail-forward"
                        string="Select this supplier"
                        type="object"
                        attrs="{
                            'invisible': [
                                '|',
                                ('choosen_supplier_id', '=', %(sid)s),
                                ('unit_price_%(sid)s', '=', 0.00),
                            ]
                        }" />
                """ % {'sid': sup.id}

                for fld in fld_to_add:
                    tree_view += """
                        <field name="%s_%s" readonly="1" />
                     """ % (fld, sup.id)

            if s_ids:
                tree_view += """
                    <separator string="|" editable="0" />
                    <field name="choosen_supplier_id" invisible="1" />
                    <button
                        name="reset_selection"
                        icon="gtk-undo"
                        string="Reset supplier selection"
                        type="object"
                        attrs="{
                            'invisible': [('choosen_supplier_id', '=', False)],
                        }" />
                    <field name="choosen_supplier_name" readonly="1" />
                    <field name="rfq_line_id" invisible="1" />
                """

            tree_view += """</tree>"""
            res['arch'] = tree_view

        return res

    def __getattr__(self, name, *args, **kwargs):
        """
        Call the select_supplier_x() method with good paramater
        """
        if name[:16] == 'select_supplier_':
            sup_id = name[16:]
            self.sup_id = int(sup_id)
            return self.choose_supplier
        else:
            return super(wizard_compare_rfq_line, self).\
                __getattr__(name, *args, **kwargs)


    def choose_supplier(self, cr, uid, ids, context=None):
        '''
        Select the supplier
        '''
        pol_obj = self.pool.get('purchase.order.line')

        if context is None:
            context = {}

        if not self.sup_id:
            raise osv.except_osv(
                _('Error'),
                _('No supplier selected'),
            )

        for wiz_line in self.browse(cr, uid, ids, context=context):
            rfq_line_ids = pol_obj.search(cr, uid, [
                ('order_id.partner_id', '=', self.sup_id),
                ('tender_line_id', '=', wiz_line.tender_line_id.id),
            ], context=context)
            compare_rfq_id = wiz_line.compare_id.id
            if rfq_line_ids:
                self.write(cr, uid, [wiz_line.id], {
                    'rfq_line_id': rfq_line_ids[0],
                    'choosen_supplier_id': self.sup_id,
                }, context=context)
            else:
                raise osv.except_osv(
                    _('Error'),
                    _('Bad supplier selected'),
                )

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.compare.rfq',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': compare_rfq_id,
            'context': context,
        }

    def reset_selection(self, cr, uid, ids, context=None):
        """
        Remove the selected supplier on the selected lines
        """
        if not ids:
            raise osv.except_osv(
                _('Error'),
                _('No line selected'),
            )

        ctx = context.copy()
        self.write(cr, uid, ids, {
            'rfq_line_id': False,
            'choosen_supplier_id': False,
        }, context=ctx)

        if 'tender_id' in ctx:
            del ctx['tender_id']

        compare_rfq_id = self.\
            read(cr, uid, ids[0], ['compare_id'], context=ctx)['compare_id']

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.compare.rfq',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': compare_rfq_id,
            'context': context,
        }

wizard_compare_rfq_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
