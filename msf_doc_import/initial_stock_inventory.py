# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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
import base64
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML


class stock_inventory(osv.osv):
    _inherit = 'stock.inventory'

    def _get_import_error(self, cr, uid, ids, fields, arg, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for var in self.browse(cr, uid, ids, context=context):
            res[var.id] = False
            if var.inventory_line_id:
                for var in var.inventory_line_id:
                    if var.to_correct_ok:
                        res[var.id] = True
        return res

    _columns = {
        'file_to_import': fields.binary(string='File to import', filters='*.xml',
                                        help="""You can use the template of the export for the format that you need to use. \n The file should be in XML Spreadsheet 2003 format.
                                        \n The columns should be in this order : Product Code*, Product Description*, Location*, Batch, Expiry Date, Quantity"""),
        'import_error_ok':fields.function(_get_import_error,  method=True, type="boolean", string="Error in Import", store=True),
    }

    def _check_active_product(self, cr, uid, ids, context=None):
        '''
        Check if the stock inventory contains a line with an inactive products
        '''
        inactive_lines = self.pool.get('stock.inventory.line').search(cr, uid, [('product_id.active', '=', False),
                                                                                ('inventory_id', 'in', ids),
                                                                                ('inventory_id.state', 'not in', ['draft', 'cancel', 'done'])], context=context)

        if inactive_lines:
            plural = len(inactive_lines) == 1 and _('A product has') or _('Some products have')
            l_plural = len(inactive_lines) == 1 and _('line') or _('lines')
            p_plural = len(inactive_lines) == 1 and _('this inactive product') or _('those inactive products')
            raise osv.except_osv(_('Error'), _('%s been inactivated. If you want to validate this document you have to remove/correct the %s containing %s (see red %s of the document)') % (plural, l_plural, p_plural, l_plural))
            return False
        return True

    _constraints = [
        (_check_active_product, "You cannot confirm this stock inventory because it contains a line with an inactive product", ['order_line', 'state'])
    ]

    def import_file(self, cr, uid, ids, context=None):
        '''
        Import lines form file
        '''
        if not context:
            context = {}

        product_obj = self.pool.get('product.product')
        location_obj = self.pool.get('stock.location')
        batch_obj = self.pool.get('stock.production.lot')
        obj_data = self.pool.get('ir.model.data')
        import_to_correct = False

        vals = {}
        vals['inventory_line_id'] = []
        msg_to_return = _("All lines successfully imported")

        obj = self.browse(cr, uid, ids, context=context)[0]
        if not obj.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))

        product_cache = {}

        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(obj.file_to_import))

        # iterator on rows
        reader = fileobj.getRows()

        # ignore the first row
        reader.next()
        line_num = 1
        for row in reader:
            line_num += 1
            # Check length of the row
            if len(row) != 6:
                raise osv.except_osv(_('Error'), _("""You should have exactly 7 columns in this order:
Product Code*, Product Description*, Location*, Batch*, Expiry Date*, Quantity*"""))

            # default values
            product_id = False
            product_cost = 1.00
            currency_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
            location_id = False
            batch = False
            expiry = False
            product_qty = 0.00
            product_uom = False
            comment = ''
            to_correct_ok = False
            error_list = []

            # Product code
            product_code = row.cells[0].data
            if not product_code:
                to_correct_ok = True
                import_to_correct = True
                error_list.append('No Product Code.')
            else:
                try:
                    product_code = product_code.strip()
                    if product_code in product_cache:
                        product_id = product_cache.get(product_code)
                    if not product_id:
                        product_ids = product_obj.search(cr, uid, ['|', ('default_code', '=', product_code.upper()), ('default_code', '=', product_code)], context=context)
                        if product_ids:
                            product_id = product_ids[0]
                            product_cache.update({product_code: product_id})
                except Exception:
                    error_list.append(_('The Product Code has to be a string.'))
                    to_correct_ok = True
                    import_to_correct = True

            # Product name
            p_name = row.cells[1].data
            if not product_id and not p_name:
                to_correct_ok = True
                import_to_correct = True
                error_list.append(_('No Product Description'))
            else:
                try:
                    p_name = p_name.strip()
                    product_ids = product_obj.search(cr, uid, [('name', '=', p_name)], context=context)
                    if not product_ids:
                        to_correct_ok = True
                        import_to_correct = True
                        error_list.append(_('The Product was not found in the list of the products.'))
                    else:
                        product_id = product_ids[0]
                except Exception:
                     error_list.append(_('The Product Description has to be a string.'))
                     to_correct_ok = True
                     import_to_correct = True

            if not product_id:
                if not product_code and not p_name:
                    raise osv.except_osv(_('Error'), _('You have to fill at least the product code or the product name on each line'))
                raise osv.except_osv(_('Error'), _('The Product [%s] %s was not found in the list of the products') % (product_code or '', p_name or ''))

            # Location
            loc_id = row.cells[2].data
            if not loc_id:
                location_id = False
                to_correct_ok = True
                import_to_correct = True
                error_list.append('No location')
            else:
                try:
                    location_name = loc_id.strip()
                    loc_ids = location_obj.search(cr, uid, [('name', '=', location_name)], context=context)
                    if not loc_ids:
                        location_id = False
                        to_correct_ok = True
                        import_to_correct = True
                        error_list.append(_('The location was not found in the of the locations.'))
                    else:
                        location_id = loc_ids[0]
                except Exception:
                    error_list.append(_('The Location has to be a string.'))
                    location_id = False

            # Batch
            batch = row.cells[3].data
            if batch:
                if isinstance(batch, int):
                    batch = str(batch)
                try:
                    batch = batch.strip()
                    batch_ids = batch_obj.search(cr, uid, [('product_id', '=', product_id), ('name', '=', batch)], context=context)
                    if not batch_ids:
                        batch_name = batch
                        batch = False
                        to_correct_ok = True
                        import_to_correct = True
                        error_list.append(_('The batch %s was not found in the database.') % batch_name)
                    else:
                        batch = batch_ids[0]
                except Exception:
                    batch = False
                    error_list.append(_('The Batch has to be a string.'))

            # Expiry date
            if row.cells[4].data:
                if row.cells[4].type == 'datetime':
                    expiry = row.cells[4].data.strftime('%Y-%m-%d')
                else:
                    error_list.append(_('The date format was not good so we took the date from the parent.'))
                    to_correct_ok = True
                    import_to_correct = True
                if expiry and not batch:
                    batch_ids = batch_obj.search(cr, uid, [('product_id', '=', product_id), ('life_date', '=', expiry)], context=context)
                    if not batch_ids:
                        batch = False
                        to_correct_ok = True
                        import_to_correct = True
                        error_list.append(_('No batch found for the expiry date %s.') % (expiry,))
                    else:
                        batch = batch_ids[0]
                elif expiry and batch:
                    b_expiry = batch_obj.browse(cr, uid, batch, context=context).life_date
                    if expiry != b_expiry:
                        err_exp_message = _('Expiry date inconsistent with %s') % row.cells[3].data
                        error_list.append(err_exp_message)
                        comment += err_exp_message
                        comment += '\n'

            # Quantity
            p_qty = row.cells[5].data
            if not p_qty:
                product_qty = 0.00
                error_list.append(_('The Product Quantity was not set, we set it to 0.00.'))
            else:
                if row.cells[5].type in ['int', 'float']:
                    product_qty = row.cells[5].data
                else:
                    product_qty = 0.00
                    error_list.append(_('The Product Quantity was not set, we set it to 0.00.'))

            if not location_id:
                comment += _('Location is missing.\n')
            if product_id:
                product = product_obj.browse(cr, uid, product_id)
                product_uom = product.uom_id.id
                hidden_batch_management_mandatory = product.batch_management
                hidden_perishable_mandatory = product.perishable
                if hidden_batch_management_mandatory and not batch:
                    comment += _('Batch is missing.\n')
                if hidden_perishable_mandatory and not expiry:
                    comment += _('Expiry date is missing.\n')
                if not hidden_perishable_mandatory and not hidden_batch_management_mandatory and batch:
                    comment += _('This product is not Batch Number managed.')
                    batch = False
                if not hidden_perishable_mandatory and expiry:
                    comment += _('This product is not Expiry Date managed.')
                    expiry = False
            else:
                product_uom = self.pool.get('product.uom').search(cr, uid, [], context=context)[0]
                hidden_batch_management_mandatory = False
                hidden_perishable_mandatory = False

            if product_uom and product_qty:
                product_qty = self.pool.get('product.uom')._compute_round_up_qty(cr, uid, product_uom, product_qty)

            discrepancy_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_discrepancy')[1]

            to_write = {
                'product_id': product_id,
                'reason_type_id': discrepancy_id,
                'currency_id': currency_id,
                'location_id': location_id,
                'prod_lot_id': batch,
                'expiry_date': expiry,
                'product_qty': product_qty,
                'product_uom': product_uom,
                'hidden_batch_management_mandatory': hidden_batch_management_mandatory,
                'hidden_perishable_mandatory': hidden_perishable_mandatory,
                'comment': comment,
                'to_correct': to_correct_ok,
            }

            vals['inventory_line_id'].append((0, 0, to_write))

        # write order line on Inventory
        vals.update({'file_to_import': False})
        self.write(cr, uid, ids, vals, context=context)

        view_id = obj_data.get_object_reference(cr, uid, 'specific_rules','stock_initial_inventory_form_view')[1]

        if import_to_correct:
            msg_to_return = _("The import of lines had errors, please correct the red lines below")

        return self.log(cr, uid, obj.id, msg_to_return, context={'view_id': view_id,})

    def check_lines_to_fix(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        message = ''
        plural= ''

        for var in self.browse(cr, uid, ids, context=context):
            if var.inventory_line_id:
                for var in var.inventory_line_id:
                    if var.to_correct_ok:
                        if message:
                            message += ', '
                        message += self.pool.get('product.product').name_get(cr, uid, [var.product_id.id])[0][1]
                        if len(message.split(',')) > 1:
                            plural = 's'
        if message:
            raise osv.except_osv(_('Warning !'), _('You need to correct the following line%s : %s')% (plural, message))
        return True

stock_inventory()


class stock_inventory_line(osv.osv):
    _inherit = 'stock.inventory.line'

    def _get_inactive_product(self, cr, uid, ids, field_name, args, context=None):
        '''
        Fill the error message if the product of the line is inactive
        '''
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'inactive_product': False,
                            'inactive_error': ''}
            if line.comment:
                res[line.id].update({'inactive_error': line.comment})
            if line.inventory_id and line.inventory_id.state not in ('cancel', 'done') and line.product_id and not line.product_id.active:
                res[line.id] = {
                    'inactive_product': True,
                    'inactive_error': _('The product in line is inactive !')
                }

        return res

    _columns = {
        'to_correct_ok': fields.boolean('To correct'),
        'comment': fields.text('Comment', readonly=True),
        'inactive_product': fields.function(_get_inactive_product, method=True, type='boolean', string='Product is inactive', store=False, multi='inactive'),
        'inactive_error': fields.function(_get_inactive_product, method=True, type='char', string='Comment', store=False, multi='inactive'),
    }

    _defaults = {
        'inactive_product': False,
        'inactive_error': lambda *a: '',
    }

    def create(self, cr, uid, vals, context=None):
        comment = ''
        hidden_batch_management_mandatory = False
        hidden_perishable_mandatory = False

        if vals.get('product_id', False):
            product = self.pool.get('product.product').browse(cr, uid, vals.get('product_id'), context=context)
            hidden_batch_management_mandatory = product.batch_management
            hidden_perishable_mandatory = product.perishable

        location_id = vals.get('location_id')
        batch = vals.get('prod_lot_id')
        expiry = vals.get('expiry_date')


        if not location_id:
            comment += _('Location is missing.\n')

        if hidden_batch_management_mandatory and not batch:
            comment += _('Batch is missing.\n')
        if hidden_perishable_mandatory and not expiry:
            comment += _('Expiry date is missing.\n')

        if not comment:
            if vals.get('comment'):
                comment = vals.get('comment')
            vals.update({'comment': comment, 'to_correct_ok': False})
        else:
            vals.update({'comment': comment, 'to_correct_ok': True})

        res = super(stock_inventory_line, self).create(cr, uid, vals, context=context)
        return res

    def write(self, cr, uid, ids, vals, context=None):
        comment = ''

        line = self.browse(cr, uid, ids[0], context=context)

        if vals.get('product_id', False):
            product = self.pool.get('product.product').browse(cr, uid, vals.get('product_id'), context=context)
        else:
            product = line.product_id

        location_id = vals.get('location_id') or line.location_id
        batch = vals.get('prod_lot_id') or line.prod_lot_id
        expiry = vals.get('expiry_date') or line.expiry_date

        hidden_batch_management_mandatory = product.batch_management
        hidden_perishable_mandatory = product.perishable

        if not location_id:
            comment += _('Location is missing.\n')
        if hidden_batch_management_mandatory and not batch:
            comment += _('Batch is missing.\n')
        if hidden_perishable_mandatory and not expiry:
            comment += _('Expiry date is missing.\n')

        if not comment:
            vals.update({'comment': comment, 'to_correct_ok': False})
        else:
            vals.update({'comment': comment, 'to_correct_ok': True})

        res = super(stock_inventory_line, self).write(cr, uid, ids, vals, context=context)
        return res

stock_inventory_line()

class initial_stock_inventory(osv.osv):
    _inherit = 'initial.stock.inventory'

    def _get_import_error(self, cr, uid, ids, fields, arg, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for var in self.browse(cr, uid, ids, context=context):
            res[var.id] = False
            if var.inventory_line_id:
                for var in var.inventory_line_id:
                    if var.to_correct_ok:
                        res[var.id] = True
        return res

    _columns = {
        'file_to_import': fields.binary(string='File to import', filters='*.xml',
                                        help="""You can use the template of the export for the format that you need to use. \n The file should be in XML Spreadsheet 2003 format.
                                        \n The columns should be in this order : Product Code*, Product Description*, Initial Average Cost, Location*, Batch, Expiry Date, Quantity"""),
        'import_error_ok':fields.function(_get_import_error,  method=True, type="boolean", string="Error in Import", store=True),
    }

    def _check_active_product(self, cr, uid, ids, context=None):
        '''
        Check if the initial stock inventory contains a line with an inactive products
        '''
        inactive_lines = self.pool.get('initial.stock.inventory.line').search(cr, uid, [('product_id.active', '=', False),
                                                                                        ('inventory_id', 'in', ids),
                                                                                        ('inventory_id.state', 'not in', ['draft', 'cancel', 'done'])], context=context)

        if inactive_lines:
            plural = len(inactive_lines) == 1 and _('A product has') or _('Some products have')
            l_plural = len(inactive_lines) == 1 and _('line') or _('lines')
            p_plural = len(inactive_lines) == 1 and _('this inactive product') or _('those inactive products')
            raise osv.except_osv(_('Error'), _('%s been inactivated. If you want to validate this document you have to remove/correct the %s containing %s (see red %s of the document)') % (plural, l_plural, p_plural, l_plural))
            return False
        return True

    _constraints = [
        (_check_active_product, "You cannot confirm this stock inventory because it contains a line with an inactive product", ['order_line', 'state'])
    ]

    def import_file(self, cr, uid, ids, context=None):
        '''
        Import lines form file
        '''
        if not context:
            context = {}

        product_obj = self.pool.get('product.product')
        location_obj = self.pool.get('stock.location')
        obj_data = self.pool.get('ir.model.data')
        import_to_correct = False

        vals = {}
        vals['inventory_line_id'] = []
        msg_to_return = _("All lines successfully imported")

        obj = self.browse(cr, uid, ids, context=context)[0]
        if not obj.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))

        product_cache = {}

        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(obj.file_to_import))

        # iterator on rows
        reader = fileobj.getRows()

        # ignore the first row
        reader.next()
        line_num = 1
        for row in reader:
            line_num += 1
            # Check length of the row
            if len(row) != 7:
                raise osv.except_osv(_('Error'), _("""You should have exactly 7 columns in this order:
Product Code*, Product Description*, Initial Average Cost*, Location*, Batch*, Expiry Date*, Quantity*"""))

            # default values
            product_id = False
            product_cost = 1.00
            currency_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
            location_id = False
            batch = False
            expiry = False
            product_qty = 0.00
            product_uom = False
            comment = ''
            to_correct_ok = False
            error_list = []

            # Product code
            product_code = row.cells[0].data
            if not product_code:
                to_correct_ok = True
                import_to_correct = True
                error_list.append('No Product Code.')
            else:
                try:
                    product_code = product_code.strip()
                    if product_code in product_cache:
                        product_id = product_cache.get(product_code)
                    if not product_id:
                        product_ids = product_obj.search(cr, uid, ['|', ('default_code', '=', product_code.upper()), ('default_code', '=', product_code)], context=context)
                        if product_ids:
                            product_id = product_ids[0]
                            product_cache.update({product_code: product_id})
                except Exception:
                    error_list.append(_('The Product Code has to be a string.'))
                    to_correct_ok = True
                    import_to_correct = True

            # Product name
            p_name = row.cells[1].data
            if not product_id:
                to_correct_ok = True
                import_to_correct = True
                error_list.append(_('The Product was not found in the list of the products.'))
                raise osv.except_osv(_('Error'), _('The Product [%s] %s was not found in the list of the products') % (product_code or '', p_name or ''))

            # Average cost
            cost = row.cells[2].data
            if not cost:
                if product_id:
                    product_cost = product_obj.browse(cr, uid, product_id).standard_price
                    error_list.append(_('The Average Cost was not set, we set it to the standard price of the product.'))
                else:
                    product_cost = 1.00
                    error_list.append(_('The Average Cost was not set, we set it to 1.00.'))
            else:
                if row.cells[2].type in ('int', 'float'):
                    product_cost = cost
                elif product_id:
                    product_cost = product_obj.browse(cr, uid, product_id).standard_price
                    error_list.append(_('The Average Cost was not set, we set it to the standard price of the product.'))
                else:
                    product_cost = 1.00
                    error_list.append(_('The Average Cost was not set, we set it to 1.00.'))


            # Location
            loc_id = row.cells[3].data
            if not loc_id:
                location_id = False
                to_correct_ok = True
                import_to_correct = True
                error_list.append('No location')
            else:
                try:
                    location_name = loc_id.strip()
                    loc_ids = location_obj.search(cr, uid, [('name', '=', location_name)], context=context)
                    if not loc_ids:
                        location_id = False
                        to_correct_ok = True
                        import_to_correct = True
                        error_list.append(_('The location was not found in the of the locations.'))
                    else:
                        location_id = loc_ids[0]
                except Exception:
                    error_list.append(_('The Location has to be a string.'))
                    location_id = False

            # Batch
            batch = row.cells[4].data
            if batch:
                try:
                    batch = batch.strip()
                except Exception:
                    error_list.append(_('The Batch has to be a string.'))

            # Expiry date
            if row.cells[5].data:
                if row.cells[5].type == 'datetime':
                    expiry = row.cells[5].data
                else:
                    error_list.append(_('The date format was not good so we took the date from the parent.'))
                    to_correct_ok = True
                    import_to_correct = True
            else:
                error_list.append(_('The date was not specified or so we took the one from the parent.'))
                to_correct_ok = True
                import_to_correct = True

            # Quantity
            p_qty = row.cells[6].data
            if not p_qty:
                product_qty = 0.00
                error_list.append(_('The Product Quantity was not set, we set it to 0.00.'))
            else:
                if row.cells[6].type in ['int', 'float']:
                    product_qty = row.cells[6].data
                else:
                    product_qty = 0.00
                    error_list.append(_('The Product Quantity was not set, we set it to 0.00.'))

            if not location_id:
                comment += _('Location is missing.\n')
            if product_id:
                product = product_obj.browse(cr, uid, product_id)
                product_uom = product.uom_id.id
                hidden_batch_management_mandatory = product.batch_management
                hidden_perishable_mandatory = product.perishable
                if hidden_batch_management_mandatory and not batch:
                    comment += _('Batch is missing.\n')
                if hidden_perishable_mandatory and not expiry:
                    comment += _('Expiry date is missing.\n')
            else:
                product_uom = self.pool.get('product.uom').search(cr, uid, [], context=context)[0]
                hidden_batch_management_mandatory = False
                hidden_perishable_mandatory = False

            if product_uom and product_qty:
                product_qty = self.pool.get('product.uom')._compute_round_up_qty(cr, uid, product_uom, product_qty)

            to_write = {
                'product_id': product_id,
                'average_cost': product_cost,
                'currency_id': currency_id,
                'location_id': location_id,
                'prodlot_name': batch,
                'expiry_date': expiry,
                'product_qty': product_qty,
                'product_uom': product_uom,
                'hidden_batch_management_mandatory': hidden_batch_management_mandatory,
                'hidden_perishable_mandatory': hidden_perishable_mandatory,
                'comment': comment,
                'to_correct': to_correct_ok,
            }

            vals['inventory_line_id'].append((0, 0, to_write))

        # write order line on Inventory
        vals.update({'file_to_import': False})
        self.write(cr, uid, ids, vals, context=context)

        view_id = obj_data.get_object_reference(cr, uid, 'specific_rules','stock_initial_inventory_form_view')[1]

        if import_to_correct:
            msg_to_return = _("The import of lines had errors, please correct the red lines below")

        return self.log(cr, uid, obj.id, msg_to_return, context={'view_id': view_id,})

    def check_lines_to_fix(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        message = ''
        plural= ''

        for var in self.browse(cr, uid, ids, context=context):
            if var.inventory_line_id:
                for var in var.inventory_line_id:
                    if var.to_correct_ok:
                        if message:
                            message += ', '
                        message += self.pool.get('product.product').name_get(cr, uid, [var.product_id.id])[0][1]
                        if len(message.split(',')) > 1:
                            plural = 's'
        if message:
            raise osv.except_osv(_('Warning !'), _('You need to correct the following line%s : %s')% (plural, message))
        return True

initial_stock_inventory()

class initial_stock_inventory_line(osv.osv):
    '''
    override of initial_stock_inventory_line class
    '''
    _inherit = 'initial.stock.inventory.line'

    def _get_inactive_product(self, cr, uid, ids, field_name, args, context=None):
        '''
        Fill the error message if the product of the line is inactive
        '''
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'inactive_product': False,
                            'inactive_error': ''}
            if line.comment:
                res[line.id].update({'inactive_error': line.comment})
            if line.inventory_id and line.inventory_id.state not in ('cancel', 'done') and line.product_id and not line.product_id.active:
                res[line.id] = {
                    'inactive_product': True,
                    'inactive_error': _('The product in line is inactive !')
                }

        return res

    _columns = {
        'to_correct_ok': fields.boolean('To correct'),
        'comment': fields.text('Comment', readonly=True),
        'inactive_product': fields.function(_get_inactive_product, method=True, type='boolean', string='Product is inactive', store=False, multi='inactive'),
        'inactive_error': fields.function(_get_inactive_product, method=True, type='char', string='Comment', store=False, multi='inactive'),
    }

    _defaults = {
        'inactive_product': False,
        'inactive_error': lambda *a: '',
    }

    def create(self, cr, uid, vals, context=None):
        comment = ''
        hidden_batch_management_mandatory = False
        hidden_perishable_mandatory = False

        if vals.get('product_id', False):
            product = self.pool.get('product.product').browse(cr, uid, vals.get('product_id'), context=context)
            hidden_batch_management_mandatory = product.batch_management
            hidden_perishable_mandatory = product.perishable

        location_id = vals.get('location_id')

        batch = vals.get('prodlot_name')
        batch_numer = vals.get('prod_lot_id', False)
        if batch_numer and not batch: # for the sync case, sometime only the prodlot id is given but not the name, so search for name
            batch = self.pool.get('stock.production.lot').browse(cr, uid, batch_numer, context=context).name
            vals.update({'prodlot_name':batch})
        expiry = vals.get('expiry_date')

        if not location_id:
            comment += _('Location is missing.\n')

        if hidden_batch_management_mandatory and not batch:
            comment += _('Batch is missing.\n')
        if hidden_perishable_mandatory and not expiry:
            comment += _('Expiry date is missing.\n')

        if not comment:
            vals.update({'comment': comment, 'to_correct_ok': False})
        else:
            vals.update({'comment': comment, 'to_correct_ok': True})

        res = super(initial_stock_inventory_line, self).create(cr, uid, vals, context=context)
        return res

    def write(self, cr, uid, ids, vals, context=None):
        comment = ''

        line = self.browse(cr, uid, ids[0], context=context)

        if vals.get('product_id', False):
            product = self.pool.get('product.product').browse(cr, uid, vals.get('product_id'), context=context)
        else:
            product = line.product_id

        location_id = vals.get('location_id') or line.location_id
        batch = vals.get('prodlot_name') or line.prodlot_name
        expiry = vals.get('expiry_date') or line.expiry_date

        hidden_batch_management_mandatory = product.batch_management
        hidden_perishable_mandatory = product.perishable

        if not location_id:
            comment += _('Location is missing.\n')
        if hidden_batch_management_mandatory and not batch:
            comment += _('Batch is missing.\n')
        if hidden_perishable_mandatory and not expiry:
            comment += _('Expiry date is missing.\n')

        if not comment:
            vals.update({'comment': comment, 'to_correct_ok': False})
        else:
            vals.update({'comment': comment, 'to_correct_ok': True})

        res = super(initial_stock_inventory_line, self).write(cr, uid, ids, vals, context=context)
        return res

initial_stock_inventory_line()

