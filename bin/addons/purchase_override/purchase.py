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

from osv import osv, fields
from tools.translate import _
import netsvc
import decimal_precision as dp



class purchase_order_confirm_wizard(osv.osv):
    _name = 'purchase.order.confirm.wizard'
    _rec_name = 'order_id'

    _columns = {
        'order_id': fields.many2one('purchase.order', string='Purchase Order', readonly=True),
        'errors': fields.text(string='Error message', readonly=True),
    }

    def validate_order(self, cr, uid, ids, context=None):
        wf_service = netsvc.LocalService("workflow")
        for wiz in self.read(cr, uid, ids, ['order_id'], context=context):
            wf_service.trg_validate(uid, 'purchase.order', wiz['order_id'][0], 'purchase_confirmed_wait', cr)
        return {'type': 'ir.actions.act_window_close'}

purchase_order_confirm_wizard()


class purchase_order_merged_line(osv.osv):
    '''
    A purchase order merged line is a special PO line.
    These lines give the total quantity of all normal PO lines
    which have the same product and the same quantity.
    When a new normal PO line is created, the system will check
    if this new line can be attached to other PO lines. If yes,
    the unit price of all normal PO lines with the same product and
    the same UoM will be computed from supplier catalogue and updated on lines.
    '''
    _name = 'purchase.order.merged.line'
    _inherit = 'purchase.order.line'
    _description = 'Purchase Order Merged Lines'
    _table = 'purchase_order_merged_line'

    def _get_name(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            if line.order_line_ids:
                res[line.id] = line.product_id and line.product_id.name or line.order_line_ids[0].comment
        return res

    _columns = {
        'order_line_ids': fields.one2many('purchase.order.line', 'merged_id', string='Purchase Lines'),
        'date_planned': fields.date(string='Delivery Requested Date', required=False, select=True,
                                    help='Header level dates has to be populated by default with the possibility of manual updates'),
        'name': fields.function(_get_name, method=True, type='char', string='Name', store=False),
    }
    def create(self, cr, uid, vals, context=None):

        '''
        Set the line number to 0
        '''
        if self._name == 'purchase.order.merged.line':
            vals.update({'line_number': 0})
        return super(purchase_order_merged_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Update unit price of PO lines attached to the merged line
        '''
        if not ids:
            return True
        if context is None:
            context = {}
        new_context = context.copy()
        new_context.update({'update_merge': True})
        # If the unit price is changing, update the price unit of all normal PO lines
        # associated to this merged PO line
        if 'price_unit' in vals:
            merged_line_list = self.read(cr, uid, ids, ['order_line_ids'], context=context)
            merged_line_order_line_ids = set()
            for merged_line in merged_line_list:
                merged_line_order_line_ids.update(merged_line['order_line_ids'])
            self.pool.get('purchase.order.line').write(cr, uid,
                                                       list(merged_line_order_line_ids),
                                                       {'price_unit': vals['price_unit'],
                                                           'old_price_unit': vals['price_unit']},
                                                       context=new_context)

        res = super(purchase_order_merged_line, self).write(cr, uid, ids, vals, context=context)

        return res

    def _update(self, cr, uid, p_id, po_line_id, product_qty, price=0.00, context=None, no_update=False):
        '''
        Update the quantity and the unit price according to the new qty
        '''
        line = self.browse(cr, uid, p_id, context=context)
        change_price_ok = True
        if not po_line_id:
            change_price_ok = context.get('change_price_ok', True)
        else:
            po_line = self.pool.get('purchase.order.line').browse(cr, uid, po_line_id, context=context)
            change_price_ok = po_line.change_price_ok
            if 'change_price_ok' in context:
                change_price_ok = context.get('change_price_ok')

        # If no PO line attached to this merged line, remove the merged line
        if not line.order_line_ids:
            self.unlink(cr, uid, [p_id], context=context)
            return False, False

        new_price = False
        new_qty = line.product_qty + float(product_qty)

        if (po_line_id and not change_price_ok and not po_line.order_id.rfq_ok) or (not po_line_id and not change_price_ok):
            # Get the catalogue unit price according to the total qty
            new_price = self.pool.get('product.pricelist').price_get(cr, uid,
                                                                     [line.order_id.pricelist_id.id],
                                                                     line.product_id.id,
                                                                     new_qty,
                                                                     line.order_id.partner_id.id,
                                                                     {'uom': line.product_uom.id,
                                                                         'date': line.order_id.date_order})[line.order_id.pricelist_id.id]

        # Update the quantity of the merged line
        values = {'product_qty': new_qty}
        # If a catalogue unit price exist and the unit price is not manually changed
        if new_price:
            values.update({'price_unit': new_price})
        else:
            # Keep the unit price given by the user
            values.update({'price_unit': price})
            new_price = price

        # Update the unit price and the quantity of the merged line
        if not no_update:
            self.write(cr, uid, [p_id], values, context=context)

        return p_id, new_price or False


purchase_order_merged_line()

class purchase_order_group(osv.osv_memory):
    _name = "purchase.order.group"
    _inherit = "purchase.order.group"
    _description = "Purchase Order Merge"

    _columns = {
        'po_value_id': fields.many2one('purchase.order', string='Template PO', help='All values in this PO will be used as default values for the merged PO'),
        'unmatched_categ': fields.boolean(string='Unmatched categories'),
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

    def merge_orders(self, cr, uid, ids, context=None):
        res = super(purchase_order_group, self).merge_orders(cr, uid, ids, context=context)
        res.update({'context': {'search_default_draft': 1, 'search_default_approved': 0,'search_default_create_uid':uid, 'purchase_order': True}})

        if 'domain' in res and eval(res['domain'])[0][2]:
            return res

        raise osv.except_osv(_('Error'), _('No PO merged !'))
        return {'type': 'ir.actions.act_window_close'}

purchase_order_group()

class product_product(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'

    def _product_price(self, cr, uid, ids, field_name, args, context=None):
        res = super(product_product, self)._product_price(cr, uid, ids, field_name, args, context=context)

        for product in res:
            if res[product] == 0.00:
                try:
                    res[product] = self.pool.get('product.product').read(cr, uid, [product], ['standard_price'], context=context)[0]['standard_price']
                except:
                    pass

        return res

    def _get_purchase_type(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for p_id in ids:
            res[p_id] = True

        return res

    def _src_purchase_type(self, cr, uid, obj, name, args, context=None):
        '''
        Returns a domain according to the PO type
        '''
        res = []
        for arg in args:
            if arg[0] == 'purchase_type':
                if arg[1] != '=':
                    raise osv.except_osv(_('Error'), _('Only the \'=\' operator is allowed.'))
                # Returns all service products
                if arg[2] == 'service':
                    res.append(('type', '=', 'service_recep'))
                elif arg[2] == 'transport':
                    res.append(('transport_ok', '=', True))

        return res

    _columns = {

        'purchase_type': fields.function(_get_purchase_type, fnct_search=_src_purchase_type, type='boolean', string='Purchase type', method=True, store=False),
        'price': fields.function(_product_price, method=True, type='float', string='Pricelist', digits_compute=dp.get_precision('Sale Price')),
    }

    def check_consistency(self, cr, uid, product_id, category, context=None):
        """
        Check the consistency of product according to category
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param product_id: ID of the product.product to check
        :param category: DB value of the category to check
        :param context: Context of the call
        :return: A warning message or False
        """
        nomen_obj = self.pool.get('product.nomenclature')

        if context is None:
            context = {}

        display_message = False

        # No check for Other
        if category == 'other':
            return False

        product = self.read(cr, uid, product_id, [
            'nomen_manda_0',
            'type',
            'transport_ok',
        ], context=context)
        transport_product = product['transport_ok']
        product_type = product['type']
        main_type = product['nomen_manda_0'][0]

        if category == 'medical':
            try:
                med_nomen = nomen_obj.search(cr, uid, [
                    ('level', '=', 0),
                    ('name', '=', 'MED'),
                ], context=context)[0]
            except IndexError:
                raise osv.except_osv(
                    _('Error'),
                    _('MED nomenclature Main Type not found'),
                )

            if main_type != med_nomen:
                display_message = True

        if category == 'log':
            try:
                log_nomen = nomen_obj.search(cr, uid, [
                    ('level', '=', 0),
                    ('name', '=', 'LOG'),
                ], context=context)[0]

            except IndexError:
                raise osv.except_osv(
                    _('Error'),
                    _('LOG nomenclature Main Type not found')
                )

            if main_type != log_nomen:
                display_message = True

        if category == 'service' and product_type != 'service_recep':
            display_message = True

        if category == 'transport' and (product_type != 'service_recep' or not transport_product):
            display_message = True

        if display_message:
            return 'Warning you are about to add a product which does not conform to this' \
                ' order category, do you wish to proceed ?'
        else:
            return False

product_product()


class purchase_order_cancel_wizard(osv.osv_memory):
    _name = 'purchase.order.cancel.wizard'

    def _get_has_linked_line(self, cr, uid, ids, field_name, args, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        res = {}
        for wiz in self.browse(cr, uid, ids, context=context):
            po = self.pool.get('purchase.order').browse(cr, uid, wiz.order_id.id, context=context)
            res[wiz.id] = False
            for pol in po.order_line:
                if pol.linked_sol_id:
                    res[wiz.id] = True

        return res


    _columns = {
        'order_id': fields.many2one('purchase.order', string='Order to delete'),
        'has_linked_line': fields.function(_get_has_linked_line, method=True, type='boolean', string='has linked line'),
        'unlink_po': fields.boolean(string='Unlink PO'),
        'last_lines': fields.boolean(string='Remove last lines of the FO'),
    }

    def _get_last_lines(self, cr, uid, order_id, context=None):
        """
        Returns True if the deletion of the PO will delete the last lines
        of the FO/IR.
        """
        exp_sol_obj = self.pool.get('expected.sale.order.line')
        po_obj = self.pool.get('purchase.order')

        po_so_ids, po_ids, so_ids, sol_nc_ids = po_obj.sourcing_document_state(cr, uid, [order_id], context=context)
        if order_id in po_ids:
            po_ids.remove(order_id)

        exp_sol_ids = exp_sol_obj.search(cr, uid,
                                         [('order_id', 'in', po_so_ids),
                                          ('po_id', '!=', order_id)],
                                         limit=1, order='NO_ORDER', context=context)

        if not exp_sol_ids and not po_ids:
            return True

        return False

    def fields_view_get(self, cr, uid, view_id=False, view_type='form', context=None, toolbar=False, submenu=False):
        return super(purchase_order_cancel_wizard, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)

    def ask_unlink(self, cr, uid, order_id, context=None):
        '''
        Return the wizard
        '''
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        if self._name == 'rfq.cancel.wizard':
            view_id = data_obj.get_object_reference(cr, uid, 'tender_flow', 'ask_rfq_cancel_wizard_form_view')[1]
        else:
            view_id = data_obj.get_object_reference(cr, uid, 'purchase_override', 'ask_po_cancel_wizard_form_view')[1]
        wiz_id = self.create(cr, uid, {'order_id': order_id}, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order.cancel.wizard',
                'res_id': wiz_id,
                'view_id': [view_id],
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context}

    def close_window(self, cr, uid, ids, context=None):
        '''
        Close the pop-up and reload the PO
        '''
        return {'type': 'ir.actions.act_window_close'}


    def cancel_po(self, cr, uid, ids, context=None, resource=False):
        '''
        Cancel the PO and display his form
        @param resource: do we have to resource the cancelled line ?
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")

        # get PO
        po = False
        for wiz in self.browse(cr, uid, ids, context=context):
            po = wiz.order_id

        # cancel all non-confirmed lines:
        if po.rfq_ok:
            self.pool.get('purchase.order').cancel_rfq(cr, uid, [po.id], context=context)
        else:
            for pol in po.order_line:
                if (pol.order_id.partner_type in ('external', 'esc') and pol.state in ('draft', 'validated', 'validated_n'))\
                        or (pol.order_id.partner_type not in ('external', 'esc') and pol.state == 'draft'):
                    if pol.has_pol_been_synched:
                        continue
                    signal = 'cancel'
                    if resource and pol.linked_sol_id:
                        signal = 'cancel_r'
                    wf_service.trg_validate(uid, 'purchase.order.line', pol.id, signal, cr)
            # check if the related CV should be set to Done
            if po:
                self.pool.get('purchase.order').check_close_cv(cr, uid, po.id, context=context)

        return {'type': 'ir.actions.act_window_close'}


    def cancel_and_resource(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        return self.cancel_po(cr, uid, ids, context=context, resource=True)

purchase_order_cancel_wizard()



class res_partner(osv.osv):
    _inherit = 'res.partner'

    def address_multiple_get(self, cr, uid, ids, adr_pref=['default']):
        address_obj = self.pool.get('res.partner.address')
        address_ids = address_obj.search(cr, uid, [('partner_id', '=', ids)])
        address_rec = address_obj.read(cr, uid, address_ids, ['type'])
        res = {}
        for addr in address_rec:
            res.setdefault(addr['type'], [])
            res[addr['type']].append(addr['id'])
        if res:
            default_address = res.get('default', False)
        else:
            default_address = False
        result = {}
        for a in adr_pref:
            result[a] = res.get(a, default_address)

        return result

res_partner()


class res_partner_address(osv.osv):
    _inherit = 'res.partner.address'

    def _get_dummy(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for a_id in ids:
            res[a_id] = True

        return res

    def _src_address(self, cr, uid, obj, name, args, context=None):
        '''
        Returns all the destination addresses of a partner or all default
        addresses if he hasn't destination addresses
        '''
        partner_obj = self.pool.get('res.partner')
        user_obj = self.pool.get('res.users')
        res = []

        for arg in args:
            if arg[0] == 'dest_address':
                addr_type = 'delivery'
            elif arg[0] == 'inv_address':
                addr_type = 'invoice'

            if arg[2]:
                partner_id = arg[2]
            else:
                partner_id = user_obj.browse(cr, uid, uid, context=context).company_id.partner_id.id
                if arg[1] == 'in':
                    partner_id = [partner_id]

            addr_ids = []
            if isinstance(partner_id, list):
                for partner in partner_id:
                    if not partner:
                        continue
                    addr_ids.extend(partner_obj.address_multiple_get(cr, uid, partner, [addr_type])[addr_type])

            else:
                addr_ids = partner_obj.address_multiple_get(cr, uid, partner_id, [addr_type])[addr_type]

            res.append(('id', 'in', list(i for i in addr_ids if i)))

        return res

    _columns = {
        'dest_address': fields.function(_get_dummy, fnct_search=_src_address, method=True,
                                        type='boolean', string='Dest. Address', store=False),
        'inv_address': fields.function(_get_dummy, fnct_search=_src_address, method=True,
                                       type='boolean', string='Invoice Address', store=False),
    }


res_partner_address()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
