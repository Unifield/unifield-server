# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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

from osv import fields
from osv import osv
from tools.translate import _

from ..sale_order_line import _SELECTION_PO_CFT

_SELECTION_TYPE = [
    ('make_to_stock', 'from stock'),
    ('make_to_order', 'on order'), ]


class multiple_sourcing_wizard(osv.osv_memory):
    _name = 'multiple.sourcing.wizard'

    def _get_values(self, cr, uid, ids, field_name, args, context=None):
        """
        Get some values from the wizard.
        """
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        res = {}

        for wizard in self.browse(cr, uid, ids, context=context):
            values = {
                'supplier_type': wizard.supplier_id and wizard.supplier_id.partner_type or False,
                'supplier_split_po': wizard.supplier_id and wizard.supplier_id.split_po or False,
            }
            res[wizard.id] = values

        return res

    _columns = {
        'line_ids': fields.many2many(
            'sale.order.line',
            'source_sourcing_line_rel',
            'line_id',
            'wizard_id',
            string='Sourcing lines',
        ),
        'run_scheduler': fields.boolean(
            string='Run scheduler ?',
            readonly="True",
        ),
        'type': fields.selection(
            _SELECTION_TYPE,
            string='Procurement Method',
            required=True,
        ),
        'po_cft': fields.selection(
            _SELECTION_PO_CFT,
            string='PO/CFT',
        ),
        'related_sourcing_id': fields.many2one(
            'related.sourcing',
            string='Group',
        ),
        'location_id': fields.many2one(
            'stock.location',
            string='Location',
        ),
        'supplier_id': fields.many2one(
            'res.partner',
            string='Supplier',
            help="If you chose lines coming from Field Orders, External/ESC suppliers will be available for Internal/Inter-section/Intermission customers and Internal/External/Inter-section/Intermission/ESC suppliers will be available for External customers",
        ),
        'company_id': fields.many2one(
            'res.company',
            string='Current company',
        ),
        'error_on_lines': fields.boolean(
            string='Error',
            help="If there is line without need sourcing on selected lines",
        ),
        'related_sourcing_ok': fields.boolean(
            string='Related sourcing OK',
        ),
        'supplier_type': fields.function(
            _get_values,
            method=True,
            string='Supplier Type',
            type='char',
            readonly=True,
            store=False,
            multi='wizard_info',
        ),
        'supplier_split_po': fields.function(
            _get_values,
            method=True,
            string='Supplier can Split POs',
            type='char',
            readonly=True,
            store=False,
            multi='wizard_info',
        ),
    }

    def default_get(self, cr, uid, fields_list, context=None, from_web=False):
        """
        Set lines with the selected lines to source
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param fields_list: List of field names to fill with default value
        :param context: Context of the call
        :return: A dictionary that contains the field name as key and the default value for this field as value.
        """
        sol_obj = self.pool.get('sale.order.line')
        user_obj = self.pool.get('res.users')
        po_auto_cfg_obj = self.pool.get('po.automation.config')

        if context is None:
            context = {}

        active_ids = context.get('active_ids')
        if not active_ids or len(active_ids) < 2:
            raise osv.except_osv(_('Error'), _('You should select at least two lines to process.'))

        res = super(multiple_sourcing_wizard, self).default_get(cr, uid, fields_list, context=context, from_web=from_web)

        res.update({
            'line_ids': [],
            'error_on_lines': False,
            'run_scheduler': po_auto_cfg_obj.get_po_automation(cr, uid, context=context),
            'type': 'make_to_stock',
            'po_cft': False,
            'related_sourcing_ok': False,
        })

        # Check if all lines are with the same type, then set that type, otherwise set make_to_order
        # Ignore all lines which have already been sourced, if there are some already sourced lines, a message
        # will be displayed at the top of the wizard
        res['type'] = 'make_to_stock'
        res['po_cft'] = False
        res['location_id'] = False
        supplier = -1  # first location flag
        group = None
        for line in sol_obj.browse(cr, uid, active_ids, context=context):
            if line.state == 'validated':
                res['line_ids'].append(line.id)
            else:
                res['error_on_lines'] = True

            if line.type == 'make_to_order':
                res['type'] = 'make_to_order'
                res['po_cft'] = 'po'

                if not line.supplier:
                    supplier = False
                else:
                    temp = line.supplier.id
                    if supplier == -1:
                        supplier = temp
                    elif supplier != temp:
                        supplier = False

                if not line.related_sourcing_ok or not line.related_sourcing_id:
                    group = False
                else:
                    temp = line.related_sourcing_id.id
                    if group is None:
                        group = temp
                    elif group != temp:
                        group = False

            else:
                supplier = False  # if source from stock, always set False to partner
                group = False

        # UTP-1021: Set default values on opening the wizard
        if supplier != -1:
            res['supplier_id'] = supplier
            local_market_id = 0
            try:
                local_market_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'order_types', 'res_partner_local_market')[1]
            except ValueError:
                pass
            if supplier == local_market_id:
                res['po_cft'] = 'pli'
        if group is not None:
            res['related_sourcing_id'] = group

        res['related_sourcing_ok'] = sol_obj._check_related_sourcing_ok(cr, uid, supplier, res['type'], context=context)

        if not res['line_ids']:
            raise osv.except_osv(
                _('Error'),
                _('No non-sourced lines are selected. Please select non-sourced lines'),
            )

        res['company_id'] = user_obj.browse(cr, uid, uid, context=context).company_id.id

        return res

    def _get_related_sourcing_id(self, wiz):
        """
        Return the ID of a related.sourcing record or False
        :param wiz: browse_record of multiple.sourcing.wizard
        :return: ID of a related.sourcing record or False
        """
        if wiz.related_sourcing_id and wiz.supplier_id and wiz.supplier_id.partner_type == 'esc' \
           and wiz.supplier_id.split_po == 'yes':
            return wiz.related_sourcing_id.id

        return False

    def save_lines(self, cr, uid, ids, context=None):
        """
        Set values defined on the wizard to the lines of the wizard.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of multiple.sourcing.wizard to save
        :param context: Context of the call
        :return: Close the wizard window
        """
        line_obj = self.pool.get('sale.order.line')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.type == 'make_to_order':
                if not wiz.po_cft:
                    raise osv.except_osv(
                        _('Error'),
                        _('The Procurement method should be filled !'),
                    )
                elif wiz.po_cft != 'cft' and not wiz.supplier_id:
                    raise osv.except_osv(
                        _('Error'),
                        _('You should select a supplier !'),
                    )

            errors = {}
            for line in wiz.line_ids:
                if line.order_id.procurement_request and wiz.po_cft == 'dpo':
                    err_msg = 'You cannot choose Direct Purchase Order as method to source Internal Request lines.'
                    errors.setdefault(err_msg, [])
                    errors[err_msg].append((line.id, '%s of %s' % (line.line_number, line.order_id.name)))
                else:
                    try:
                        line_obj.write(cr, uid, [line.id], {
                            'type': wiz.type,
                            'po_cft': wiz.po_cft,
                            'supplier': wiz.supplier_id and wiz.supplier_id.id or False,
                            'related_sourcing_id': self._get_related_sourcing_id(wiz),
                            'location_id': wiz.location_id.id and wiz.location_id.id or False,
                        }, context=context)
                    except osv.except_osv as e:
                        errors.setdefault(e.value, [])
                        errors[e.value].append((line.id, _('%s of %s') % (line.line_number, line.order_id.name)))

            if errors:
                error_msg = ''
                for e in errors:
                    if error_msg:
                        error_msg += '\n'
                    if len(errors[e]) > 1:
                        error_msg += _('Lines %s ') % ', '.join(str(x[1]) for x in errors[e])
                    else:
                        error_msg += _('Line %s ') % ', '.join(str(x[1]) for x in errors[e])
                    error_msg += ': %s' % e
                raise osv.except_osv(_('Errors'), _('There are some errors on sourcing lines : %s') % error_msg)

        # Commit the result to avoid problem confirmLine in thread with new cursor
        cr.commit()

        return {'type': 'ir.actions.act_window_close'}

    def source_lines(self, cr, uid, ids, context=None):
        """
        Confirm the sourcing of all the sale.order.line contained in the wizards.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of multiple.sourcing.wizard that contain lines to confirm
        :param context: Context of the call
        :return: Close the wizard window
        """
        # Objects
        line_obj = self.pool.get('sale.order.line')
        prod_obj = self.pool.get('product.product')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        lines_to_confirm = []
        errors = {}
        for wiz in self.browse(cr, uid, ids, context=context):
            for sol in wiz.line_ids:
                if sol.state in ['validated', 'validated_p']:
                    if sol.order_id.procurement_request and wiz.po_cft == 'dpo':
                        raise osv.except_osv(_('Error'), _('You cannot choose Direct Purchase Order as method to source Internal Request lines.'))
                    lines_to_confirm.append(sol.id)

                if wiz.type == 'make_to_order' and sol.order_id.order_type in ['loan', 'loan_return']:
                    raise osv.except_osv(_('Error'), _('Line #%s of %s You cannot cannot source a loan on order') % (sol.line_number, sol.order_id.name))

                if sol.product_id and wiz.type == 'make_to_order':
                    sourcing_not_donation = sol.order_id.order_type not in ['donation_prog', 'donation_exp', 'donation_st'] or False
                    restr_vals = {
                        'obj_type': 'purchase.order',
                        'partner_id': wiz.supplier_id.id,
                        'sourcing_not_donation': sourcing_not_donation
                    }
                    p_error, p_msg = prod_obj._test_restriction_error(cr, uid, [sol.product_id.id], vals=restr_vals, context=context)
                    if p_error:
                        errors.setdefault(p_msg, [])
                        errors[p_msg].append((sol.id, _('%s of %s') % (sol.line_number, sol.order_id.name)))

        if errors:
            error_msg = ''
            for e in errors:
                if error_msg:
                    error_msg += '\n'
                if len(errors[e]) > 1:
                    error_msg += _('Lines %s ') % ', '.join(str(x[1]) for x in errors[e])
                else:
                    error_msg += _('Line %s ') % ', '.join(str(x[1]) for x in errors[e])
                error_msg += ': %s' % e
            raise osv.except_osv(_('Errors'), _('There are some errors on sourcing lines : %s') % error_msg)

        line_obj.confirmLine(cr, uid, lines_to_confirm, context=context)

        return {'type': 'ir.actions.act_window_close'}

    def save_source_lines(self, cr, uid, ids, context=None):
        """
        Set values on sale.order.lines of the wizard and confirm them
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of multiple.sourcing.wizard that contain the lines to save and confirmed
        :param context: Context of the call
        :return: Close the wizard window
        """
        if context is None:
            context = {}

        context['multiple_sourcing'] = True

        self.save_lines(cr, uid, ids, context=context)
        self.source_lines(cr, uid, ids, context=context)

        if 'multiple_sourcing' in context:
            context.pop('multiple_sourcing')

        return {'type': 'ir.actions.act_window_close'}

    def get_same_seller(self, cr, uid, sols, context=None):
        if context is None:
            context = {}

        res = False
        for line in self.pool.get('sale.order.line').browse(cr, uid, sols[0][2], fields_to_fetch=['product_id'], context=context):
            if line.product_id and line.product_id.seller_id and (line.product_id.seller_id.supplier or
                                                                  line.product_id.seller_id.manufacturer or line.product_id.seller_id.transporter):
                if res and res != line.product_id.seller_id.id:
                    res = False
                    break
                else:
                    res = line.product_id.seller_id.id
            else:
                res = False
                break

        return res

    def change_type(self, cr, uid, ids, lines, l_type, supplier, context=None):
        """
        Unset the other fields if the type is 'from stock'
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of multiple.sourcing.wizard on which field values has to be changed
        :param l_type: Value of the field 'type'
        :param supplier: Value of the field 'supplier'
        :param context: Context of the call
        :return: A dictionary that contains the field names to change as keys and the value for these fields as values.
        """
        sol_obj = self.pool.get('sale.order.line')

        if context is None:
            context = {}

        if l_type == 'make_to_order':
            return {
                'value': {
                    'location_id': False,
                    'related_sourcing_ok': sol_obj._check_related_sourcing_ok(cr, uid, supplier, l_type, context=context),
                    'supplier_id': self.get_same_seller(cr, uid, lines, context=context),
                },
            }

        return {
            'value': {
                'po_cft': False,
                'supplier_id': False,
                'related_sourcing_ok': False,
                'related_sourcing_id': False,
            },
        }

    def change_po_cft(self, cr, uid, ids, po_cft, supplier_id, context=None):
        """
        Unset the supplier if tender is choose
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of multiple.sourcing.wizard on which field values has to be changed
        :param po_cft: Value of the field 'po_cft'
        :param context: Context of the call
        :return: A dictionary that contains the field names to change as keys and the value for these fields as values.
        """
        if po_cft == 'cft':
            return {'value': {'supplier_id': False}}

        if supplier_id:
            suppl_type = self.pool.get('res.partner').read(cr, uid, supplier_id, ['partner_type'], context=context)['partner_type']
            if po_cft == 'pli' and suppl_type != 'external':
                return {
                    'value': {'po_cft': False},
                    'warning': {
                        'title': _('Warning'),
                        'message': _("""You can't source with 'Purchase List' to a non-external partner."""),
                    },
                }

        return {}

    def change_supplier(self, cr, uid, ids, supplier, l_type, po_cft, line_ids, context=None):
        """
        Check if the partner has an address.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of multiple.sourcing.wizard on which field values has to be changed
        :param supplier: Value of the field 'supplier_id'
        :param l_type: Value of the field 'type'
        :param context: Context of the call
        :return: A dictionary that contains the field names to change as keys and the value for these fields as values.
        """
        partner_obj = self.pool.get('res.partner')
        sol_obj = self.pool.get('sale.order.line')

        if context is None:
            context = {}

        active_ids = line_ids and line_ids[0] and line_ids[0][2] or []
        result = {'value': {'line_ids': active_ids}}
        related_sourcing_ok = False
        if supplier:
            related_sourcing_ok = sol_obj._check_related_sourcing_ok(cr, uid, supplier, l_type, context=context)
            partner = partner_obj.browse(cr, uid, supplier, context)
            # Check if the partner has addresses
            if not partner.address:
                result['warning'] = {
                    'title': _('Warning'),
                    'message': _('The chosen partner has no address. Please define an address before continuing.'),
                }

            result['value'].update({
                'supplier_type': partner and partner.partner_type or False,
                'supplier_split_po': partner and partner.split_po or False,
            })

            # Look if the partner is the same res_partner as Local Market
            data_obj = self.pool.get('ir.model.data')
            is_loc_mar = data_obj.search_exists(cr, uid, [('module', '=', 'order_types'), ('model', '=', 'res.partner'),
                                                          ('name', '=', 'res_partner_local_market'), ('res_id', '=', partner.id)], context=context)
            if is_loc_mar:
                result['value'].update({'po_cft': 'pli'})
        else:
            result['value'].update({
                'supplier_type': False,
                'supplier_split_po': False,
            })

        result['value'].update({
            'related_sourcing_ok': related_sourcing_ok,
        })

        if not related_sourcing_ok:
            result['value']['related_sourcing_id'] = False

        # To refresh the data on screen, use update for performance
        cr.execute("""
            UPDATE sale_order_line SET type = %s, po_cft = %s, supplier = %s WHERE id IN %s
        """, (l_type, result['value'].get('po_cft') or po_cft, supplier or None, tuple(active_ids)))

        return result

    def change_location(self, cr, uid, ids, location_id, line_ids, context=None):
        """
        Update the stock value of lines according to given location.
        :param cr: Cursor to the database
        :param uid: ID of the user that calls this method
        :param ids: List of ID of multiple.sourcing.wizard that contain lines to change
        :param location_id: ID of stock.location selected in the wizard
        :param line_ids: List of ID of sale.order.line contained in the multiple.sourcing.wizard
        :param context: Context of the call
        :return: A dictionary that contains the field names to change as keys and the value for these fields as values.
        """
        line_obj = self.pool.get('sale.order.line')

        res = {}
        if not location_id or not line_ids or not line_ids[0] or not line_ids[0][2]:
            return res

        active_ids = line_ids[0][2]

        context = {
            'from_multiple_line_sourcing': False
        }
        for line in line_obj.browse(cr, uid, active_ids, context=context):
            line_obj.write(cr, uid, [line.id], {
                'type': 'make_to_stock',
                'po_cft': False,
                'supplier': False,
                'location_id': location_id,
            }, context=context)  # UTP-1021: Update loc and ask the view to refresh

        return {
            'value': {
                'line_ids': active_ids,
                'error_on_lines': False,
                'po_cft': False,
            },
        }


multiple_sourcing_wizard()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
