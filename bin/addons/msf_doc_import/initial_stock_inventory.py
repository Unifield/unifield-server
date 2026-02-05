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
import tools
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
from datetime import datetime


class stock_inventory(osv.osv):
    _inherit = 'stock.inventory'

    def _get_import_error(self, cr, uid, ids, fields, arg, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
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
        'import_error_ok':fields.function(_get_import_error,  method=True, type="boolean", string="Error in Import", store=False),
    }

    def _check_active_product(self, cr, uid, ids, context=None):
        '''
        Check if the stock inventory contains a line with an inactive products
        '''
        inactive_lines = self.pool.get('stock.inventory.line').search(cr, uid, [('product_id.active', '=', False),
                                                                                ('inventory_id', 'in', ids),
                                                                                ('inventory_id.state', 'not in', ['draft', 'cancel', 'done'])],
                                                                      order='NO_ORDER',
                                                                      limit=2, context=context)

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

        vals = {}
        vals['inventory_line_id'] = []
        msg_to_return = _("All lines successfully imported")

        obj = self.browse(cr, uid, ids, context=context)[0]
        if not obj.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))
        if obj.state != 'draft':
            raise osv.except_osv(_('Error'), _('You can only import on a Draft Previous Physical Inventory; import file is ignored'))

        product_cache = {}

        fileobj = SpreadsheetXML(xmlstring=base64.b64decode(obj.file_to_import))

        # iterator on rows
        reader = fileobj.getRows()

        # ignore the first row
        next(reader)
        line_num = 1
        product_error = []
        no_product_error = []
        for row in reader:
            line_num += 1
            # Check length of the row
            if len(row) != 6:
                raise osv.except_osv(_('Error'), _("""You should have exactly 7 columns in this order:
Product Code, Product Description, Location, Batch, Expiry Date, Quantity"""))

            # default values
            product_id = False
            currency_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
            location_id = False
            location_not_found = False
            batch = False
            batch_name = False
            expiry = False
            product_qty = 0.00
            product_uom = False
            comment = ''
            bad_expiry = None
            bad_batch_name = None
            to_correct_ok = False

            # Product code
            product_code = row.cells[0].data
            if not product_code:
                to_correct_ok = True
                no_product_error.append(line_num)
                continue
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
                    to_correct_ok = True

                # Product name
                if not product_id:
                    to_correct_ok = True
                    product_error.append(line_num)
                    continue

            # Location
            loc_id = row.cells[2].data
            if not loc_id:
                location_id = False
                to_correct_ok = True
            else:
                try:
                    location_name = loc_id.strip()
                    loc_ids = location_obj.search(cr, uid, [('name', '=', location_name)], context=context)
                    if not loc_ids:
                        location_id = False
                        to_correct_ok = True
                        location_not_found = True
                    else:
                        location_id = loc_ids[0]
                except Exception:
                    location_id = False

            product = False
            if product_id:
                product = product_obj.browse(cr, uid, product_id)

            # Batch
            batch = row.cells[3].data
            if batch:
                if isinstance(batch, int):
                    batch = tools.ustr(batch)
                try:
                    batch = batch.strip()
                    batch_ids = batch_obj.search(cr, uid, [('product_id', '=', product_id), ('name', '=', batch)], context=context)
                    if not batch_ids:
                        batch_name = batch
                        batch = False
                        to_correct_ok = True
                    else:
                        batch = batch_ids[0]
                except Exception:
                    batch = False

            # Expiry date
            date_tools = self.pool.get('date.tools')
            date_format = date_tools.get_date_format(cr, uid, context=context)
            if row.cells[4].data:
                if row.cells[4].type == 'datetime':
                    try:
                        expiry = row.cells[4].data.strftime('%Y-%m-%d')
                        if datetime.strptime(expiry, '%Y-%m-%d') < datetime(1900, 0o1, 0o1, 0, 0, 0):
                            comment = _('You cannot set an expiry date before %s\n') % (
                                datetime(1900, 0o1, 0o1, 0, 0, 0).strftime(date_format),
                            )
                            bad_expiry = True
                            to_correct_ok = True
                            expiry = False
                    except:
                        comment += _('Incorrectly formatted expiry date. The '
                                     'expected date should be > 01/01/1900 in this format DD/MM/YYYY.\n')
                        bad_expiry = True
                        to_correct_ok = True
                elif row.cells[4].type == 'datetime_error':
                    comment = _('Incorrectly formatted expiry date: %s. The '
                                'expected date should be > 01/01/1900 in this format DD/MM/YYYY.\n') % row.cells[4].data
                    bad_expiry = True
                    to_correct_ok = True
                elif row.cells[4].type == 'str':
                    try:
                        expiry = datetime.strptime(row.cells[4].data, '%d/%m/%Y')
                        if expiry < datetime(1900, 0o1, 0o1, 0, 0, 0):
                            comment += _('You cannot set an expiry date before %s\n') % (
                                datetime(1900, 0o1, 0o1, 0, 0, 0).strftime(date_format),
                            )
                            bad_expiry = True
                            to_correct_ok = True
                            expiry = False
                    except:
                        comment += _('Incorrectly formatted expiry date. The expected'
                                     ' date should be > 01/01/1900 in this format DD/MM/YYYY.\n')
                        bad_expiry = True
                        to_correct_ok = True
                        expiry = False
                else:
                    comment += _('Incorrectly formatted expiry date. The '
                                 'expected date should be > 01/01/1900 in this format DD/MM/YYYY.\n')
                    bad_expiry = True
                    to_correct_ok = True
                if expiry and not batch:
                    batch_ids = batch_obj.search(cr, uid, [('product_id', '=', product_id), ('life_date', '=', expiry)], context=context)
                    if batch_ids:
                        comment += _('Other batch with the same expiry date exist.\n')
                    if product.batch_management and batch_name:
                        batch = batch_obj.create(cr, uid, {
                            'product_id': product_id,
                            'life_date': expiry,
                            'name': batch_name,
                        }, context=context)
                        to_correct_ok = False
                    elif product.batch_management and not batch_name:
                        batch = False
                        to_correct_ok = True
                elif expiry and batch:
                    b_expiry = batch_obj.browse(cr, uid, batch, context=context).life_date
                    if expiry != b_expiry:
                        if product.batch_management:
                            err_exp_message = _('Expiry date inconsistent with %s.\n') % row.cells[3].data
                            comment += err_exp_message
                            comment += '\n'
                            expiry = False
                        elif product.perishable:
                            batch = False

            # Quantity
            p_qty = row.cells[5].data
            product_qty = 0.00
            if p_qty:
                if row.cells[5].type in ['int', 'float']:
                    product_qty = row.cells[5].data
                    if product_qty < 0:
                        comment += _('Product Qty cannot be < 0. It has been reset to 0.')
                        product_qty = 0.00
                        to_correct_ok = True
                else:
                    comment += _('Incorrect number format: %s. It has been reset to 0.') % row.cells[5].data
                    to_correct_ok = True

            if not location_id and not location_not_found:
                comment += _('Location is missing.\n')
            elif location_not_found:
                comment += _('Location not found.\n')
            if product:
                product_uom = product.uom_id.id
                hidden_batch_management_mandatory = product.batch_management
                hidden_perishable_mandatory = product.perishable
                if hidden_batch_management_mandatory and not batch:
                    if batch_name:
                        comment += _('Batch not found.\n')
                    else:
                        comment += _('Batch is missing.\n')
                if hidden_perishable_mandatory and not expiry and not bad_expiry:
                    comment += _('Expiry date is missing.\n')
                if not hidden_perishable_mandatory and not hidden_batch_management_mandatory and (batch_name or batch or bad_batch_name):
                    batch = False
                    bad_batch_name = False
                    expiry = False
                    bad_expiry = False
                    # Remove the res.log that indicates errors on import
                    if to_correct_ok and location_id and not location_not_found:
                        to_correct_ok = False
                        comment = ''
                    comment += _('This product is not Batch Number managed.\n')
                if not hidden_perishable_mandatory and (expiry or bad_expiry):
                    batch = False
                    bad_batch_name = False
                    expiry = False
                    bad_expiry = False
                    # Remove the res.log that indicates errors on import
                    if to_correct_ok and location_id and not location_not_found:
                        to_correct_ok = False
                        comment = ''
                    comment += _('This product is not Expiry Date managed.\n')
            else:
                product_uom = self.pool.get('product.uom').search(cr, uid, [], context=context)[0]
                hidden_batch_management_mandatory = False
                hidden_perishable_mandatory = False


            if product_uom and product_qty:
                product_qty = self.pool.get('product.uom')._compute_round_up_qty(cr, uid, product_uom, product_qty)

            discrepancy_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_discrepancy')[1]

            to_write = {
                'product_id': product_id,
                'batch_name': batch_name,
                'reason_type_id': discrepancy_id,
                'currency_id': currency_id,
                'location_id': location_id,
                'location_not_found': location_not_found,
                'prod_lot_id': batch,
                'expiry_date': expiry,
                'bad_expiry': bad_expiry,
                'bad_batch_name': bad_batch_name,
                'product_qty': product_qty,
                'product_uom': product_uom,
                'hidden_batch_management_mandatory': hidden_batch_management_mandatory,
                'hidden_perishable_mandatory': hidden_perishable_mandatory,
                'comment': comment,
                'to_correct': to_correct_ok,
            }

            vals['inventory_line_id'].append((0, 0, to_write))

        if product_error:
            raise osv.except_osv(
                _('Error'),
                _('Product not found in the database for %s line%s: %s') % (
                    len(product_error) > 1 and 'these' or 'this',
                    len(product_error) > 1 and 's' or '',
                    ' / '.join(tools.ustr(x) for x in product_error)),
            )
        if no_product_error:
            raise osv.except_osv(
                _('Error'),
                _('Product not defined on %s line%s: %s') % (
                    len(no_product_error) > 1 and 'these' or 'this',
                    len(no_product_error) > 1 and 's' or '',
                    ' / '.join(tools.ustr(x) for x in no_product_error)),
            )

        # write order line on Inventory
        context['import_in_progress'] = True
        vals.update({'file_to_import': False})
        self.write(cr, uid, ids, vals, context=context)
        context['import_in_progress'] = False

        view_id = obj_data.get_object_reference(cr, uid, 'specific_rules','stock_initial_inventory_form_view')[1]

        if any(x[2]['to_correct'] for x in vals['inventory_line_id']):
            msg_to_return = _("The import of lines had errors, please correct the red lines below")

        return self.log(cr, uid, obj.id, msg_to_return, context={'view_id': view_id,})

    def check_lines_to_fix(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
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
        'batch_name': fields.char(size=128, string='Batch name'),
        'inv_expiry_date': fields.date(string='Invisible expiry date'),
        'to_correct_ok': fields.boolean('To correct'),
        'inactive_product': fields.function(_get_inactive_product, method=True, type='boolean', string='Product is inactive', store=False, multi='inactive'),
        'inactive_error': fields.function(_get_inactive_product, method=True, type='char', string='Comment', store=False, multi='inactive'),
    }

    _defaults = {
        'inactive_product': False,
        'inactive_error': lambda *a: '',
    }

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        comment = ''
        just_warn = False
        pl_obj = self.pool.get('stock.production.lot')
        hidden_batch_management_mandatory = False
        hidden_perishable_mandatory = False

        if vals.get('product_id', False):
            product = self.pool.get('product.product').browse(cr, uid, vals.get('product_id'), context=context)
            hidden_batch_management_mandatory = product.batch_management
            hidden_perishable_mandatory = not product.batch_management and product.perishable
            vals['hidden_batch_management_mandatory'] = hidden_batch_management_mandatory
            vals['hidden_perishable_mandatory'] = hidden_perishable_mandatory

        location_id = vals.get('location_id')
        location_not_found = vals.get('location_not_found')

        if 'location_not_found' in vals:
            del vals['location_not_found']

        if not vals.get('expiry_date') and vals.get('inv_expiry_date'):
            vals['expiry_date'] = vals.get('inv_expiry_date')

        batch = vals.get('prod_lot_id')
        expiry = vals.get('expiry_date')
        batch_name = vals.get('batch_name')
        bad_expiry = vals.get('bad_expiry')
        bad_batch_name = vals.get('bad_batch_name')

        if 'bad_expiry' in vals:
            del vals['bad_expiry']

        if 'bad_batch_name' in vals:
            del vals['bad_batch_name']

        if location_id and not self.pool.get('stock.location').search_exist(cr, uid, [('id', '=', location_id), ('active', '=', True)], context=context):
            location_id = False
            vals['location_id'] = False
            location_not_found = True
            vals['location_not_found'] = True
            vals['to_correct_ok'] = True
            vals['comment'] = _('Location is inactive')

        if not location_id and not location_not_found:
            comment += _('Location is missing.\n')
        elif location_not_found:
            comment += _('Location not found.\n')


        if hidden_batch_management_mandatory and not batch:
            if bad_batch_name:
                comment += _('Incorrect batch number format.\n')
                vals['expiry_date'] = False
            elif batch_name and not bad_expiry and expiry:
                comment += _('Batch not found.\n')
            elif batch_name and not bad_expiry and not expiry:
                comment += _('Expiry date is missing.\n')
            elif batch_name and bad_expiry:
                comment += _('Incorrectly formatted expiry date. The expected'
                             ' date should be > 01/01/1900 in this format DD/MM/YYYY. Batch not created.\n')
                vals['expiry_date'] = False
            else:
                comment += _('Batch is missing.\n')
                vals['expiry_date'] = False

        if hidden_perishable_mandatory and not expiry and not batch and batch_name:
            if bad_batch_name:
                comment += _('Incorrect batch number format.\n')
            elif bad_expiry:
                comment += _('Incorrectly formatted expiry date.\n')
            else:
                comment += _('Batch not found.\n')
        elif hidden_perishable_mandatory and not expiry:
            if not bad_expiry:
                comment += _('Expiry date is missing.\n')
            else:
                comment += _('Incorrectly formatted expiry date.\n')
            vals['expiry_date'] = False

        #if hidden_perishable_mandatory and ((batch and expiry and pl_obj.read(cr, uid, batch, ['life_date'], context=context)['life_date'] != expiry) \
        #    or (not batch and expiry and not bad_expiry)):
        #    comment += _('Expiry date will be created (with its internal batch).\n')
        #    just_warn = True
        #    vals.update({
        #        'prod_lot_id': False,
        #        'to_correct_ok': False,
        #    })

        if hidden_batch_management_mandatory and batch and not expiry:
            expiry = pl_obj.read(cr, uid, batch, ['life_date'], context=context)['life_date']
            comment += _('Please check Expiry Date is correct!.\n')
            vals['to_correct_ok'] = True

        if not comment:
            if vals.get('comment'):
                comment = vals.get('comment')
            vals.update({'comment': comment, 'to_correct_ok': False})
        elif context.get('import_in_progress'):
            if just_warn:
                vals.update({'comment': comment, 'to_correct_ok': False})
            else:
                vals.update({'comment': comment, 'to_correct_ok': True})

        res = super(stock_inventory_line, self).create(cr, uid, vals, context=context)
        return res

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        comment = ''

        line = self.browse(cr, uid, ids[0], context=context)

        if vals.get('product_id', False):
            product = self.pool.get('product.product').browse(cr, uid, vals.get('product_id'), context=context)
        else:
            product = line.product_id

        location_id = vals.get('location_id') or line.location_id
        batch = vals.get('prod_lot_id') or line.prod_lot_id
        expiry = vals.get('expiry_date') or line.expiry_date
        batch_name = vals.get('batch_name') or line.batch_name

        hidden_batch_management_mandatory = product.batch_management
        hidden_perishable_mandatory = not product.batch_management and product.perishable
        vals['hidden_batch_management_mandatory'] = hidden_batch_management_mandatory
        vals['hidden_perishable_mandatory'] = hidden_perishable_mandatory

        if not location_id:
            comment += _('Location is missing.\n')
        if hidden_batch_management_mandatory and not batch:
            if batch_name:
                comment += _('Batch not found.\n')
            else:
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
        if isinstance(ids, int):
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


        vals = {}
        vals['inventory_line_id'] = []
        msg_to_return = _("All lines successfully imported")

        obj = self.browse(cr, uid, ids, context=context)[0]
        if not obj.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))
        if obj.state != 'draft':
            raise osv.except_osv(_('Error'), _('You can only import on a Draft Initial Stock Inventory; import file is ignored'))

        product_cache = {}
        product_non_stockable_cache = {}
        product_error = []
        no_product_error = []
        wrong_location = []

        fileobj = SpreadsheetXML(xmlstring=base64.b64decode(obj.file_to_import))

        # iterator on rows
        reader = fileobj.getRows()

        # ignore the first row
        next(reader)
        line_num = 1
        for row in reader:
            line_num += 1
            # Check length of the row
            if len(row) != 7:
                raise osv.except_osv(_('Error'), _("""You should have exactly 7 columns in this order:
Product Code, Product Description, Initial Average Cost, Location, Batch, Expiry Date, Quantity"""))

            # default values
            product_id = False
            product_cost = 1.00
            currency_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
            location_id = False
            location_not_found = False
            batch = False
            expiry = False
            bad_expiry = None
            batch_name = None
            bad_batch_name = None
            product_qty = 0.00
            product_uom = False
            comment = ''
            to_correct_ok = False

            # Product code
            product_code = row.cells[0].data
            if not product_code:
                to_correct_ok = True
                no_product_error.append(line_num)
                continue
            else:
                try:
                    product_code = product_code.strip()
                    if product_code in product_cache:
                        product_id = product_cache.get(product_code)
                    elif product_code in product_non_stockable_cache:
                        product_id = product_non_stockable_cache(product_code)
                    if not product_id:
                        product_ids = product_obj.search(cr, uid, ['|', ('default_code', '=', product_code.upper()), ('default_code', '=', product_code), ('type', 'not in', ['service_recep', 'consu'])], context=context)
                        if product_ids:
                            product_id = product_ids[0]
                            product_cache.update({product_code: product_id})
                        else:
                            product_ids = product_obj.search(cr, uid, ['|', ('default_code', '=', product_code.upper()), ('default_code', '=', product_code), ('type', 'in', ['service_recep', 'consu'])], context=context)
                            if product_ids:
                                product_id = product_ids[0]
                                product_non_stockable_cache[product_code] = product_id
                    if product_code in product_non_stockable_cache:
                        to_correct_ok = True
                        comment += _('Impossible to import non-stockable products.')

                except Exception:
                    to_correct_ok = True

                if not product_id:  # Product name
                    to_correct_ok = True
                    product_error.append(line_num)
                    continue
            # Average cost
            cost = row.cells[2].data
            if not cost:
                if product_id:
                    product_cost = product_obj.browse(cr, uid, product_id).standard_price
                else:
                    product_cost = 1.00
            else:
                if row.cells[2].type in ('int', 'float'):
                    product_cost = cost
                    if product_cost < 0:
                        comment += _('Product Cost cannot be < 0. It has been reset to 1.')
                        product_cost = 1.00
                        to_correct_ok = True
                else:
                    if product_id:
                        product_cost = product_obj.browse(cr, uid, product_id).standard_price
                        comment += _('Wrong Initial Average Cost format. It has been reset to the related product Cost Price.')
                    else:
                        comment += _('Wrong Initial Average Cost format. It has been reset to 1.')
                        product_cost = 1.00
                    to_correct_ok = True

            # Location
            loc_id = row.cells[3].data
            if not loc_id:
                location_id = False
                to_correct_ok = True
            else:
                try:
                    location_name = loc_id.strip()
                    loc_ids = location_obj.search(cr, uid, [('name', '=', location_name)], context=context)
                    if not loc_ids:
                        location_id = False
                        to_correct_ok = True
                        location_not_found = True
                    else:
                        location_id = loc_ids[0]
                        loc = location_obj.browse(cr, uid, location_id, fields_to_fetch=['initial_stock_inv_display', 'usage'],
                                                  context=context)
                        if not loc.initial_stock_inv_display or loc.usage != 'internal':
                            wrong_location.append(_('Line #%s: The location "%s" is not allowed') % (line_num, location_name))
                except Exception:
                    location_id = False

            # Batch
            batch = row.cells[4].data

            # Expiry date
            date_tools = self.pool.get('date.tools')
            date_format = date_tools.get_date_format(cr, uid, context=context)
            if row.cells[5].data:
                if row.cells[5].type == 'str':
                    try:
                        expiry = datetime.strptime(row.cells[5].data, '%d/%m/%Y')
                        if expiry < datetime(1900, 0o1, 0o1, 0, 0, 0):
                            comment += _('You cannot set an expiry date before %s\n') % (
                                datetime(1900, 0o1, 0o1, 0, 0, 0).strftime(date_format),
                            )
                            bad_expiry = True
                            to_correct_ok = True
                            expiry = False
                    except:
                        comment += _('Incorrectly formatted expiry date. The expected'
                                     ' date should be > 01/01/1900 in this format DD/MM/YYYY.\n')
                        bad_expiry = True
                        to_correct_ok = True
                        expiry = False
                elif row.cells[5].type == 'datetime':
                    expiry = row.cells[5].data
                    if expiry:
                        try:
                            if expiry < datetime(1900, 0o1, 0o1, 0, 0, 0):
                                comment += _('You cannot set an expiry date before %s\n') % (
                                    datetime(1900, 0o1, 0o1, 0, 0, 0).strftime(date_format),
                                )
                                bad_expiry = True
                                to_correct_ok = True
                                expiry = False
                            else:
                                expiry = expiry.strftime('%Y-%m-%d')
                        except:
                            comment += _('Incorrectly formatted expiry date.\n')
                            bad_expiry = True
                            to_correct_ok = True
                elif row.cells[5].type == 'datetime_error':
                    comment = _('Incorrectly formatted expiry date: %s\n') % row.cells[5].data
                    bad_expiry = True
                    to_correct_ok = True
                else:
                    comment += _('Incorrectly formatted expiry date.\n')
                    bad_expiry = True
                    to_correct_ok = True

            # Quantity
            p_qty = row.cells[6].data
            product_qty = 0.00
            if p_qty:
                if row.cells[6].type in ['int', 'float']:
                    product_qty = row.cells[6].data
                    if product_qty < 0:
                        comment += _('Product Qty cannot be < 0. It has been reset to 0.')
                        product_qty = 0.00
                        to_correct_ok = True
                else:
                    comment += _('Incorrect number format: %s. It has been reset to 0.') % row.cells[6].data
                    to_correct_ok = True

            if not location_id and not location_not_found:
                comment += _('Location is missing.\n')
            elif location_not_found:
                comment += _('Location not found.\n')
            if product_id:
                product = product_obj.browse(cr, uid, product_id)
                product_uom = product.uom_id.id
                hidden_batch_management_mandatory = product.batch_management
                hidden_perishable_mandatory = product.perishable

                if hidden_perishable_mandatory and not hidden_batch_management_mandatory and (batch or bad_batch_name):
                    batch_name = False
                    bad_batch_name = False

                if hidden_batch_management_mandatory and not batch:
                    if batch_name:
                        comment += _('Batch not found.\n')
                    else:
                        comment += _('Batch is missing.\n')
                if hidden_perishable_mandatory and not expiry and not bad_expiry:
                    comment += _('Expiry date is missing.\n')
                if not hidden_perishable_mandatory and not hidden_batch_management_mandatory and (batch or bad_batch_name):
                    batch = False
                    bad_batch_name = False
                    expiry = False
                    bad_expiry = False
                    # Remove the res.log that indicates errors on import
                    if to_correct_ok and location_id and not location_not_found:
                        to_correct_ok = False
                        comment = ''
                    comment += _('This product is not Batch Number managed.\n')
                if not hidden_perishable_mandatory and (expiry or bad_expiry):
                    batch = False
                    bad_batch_name = False
                    expiry = False
                    bad_expiry = False
                    # Remove the res.log that indicates errors on import
                    if to_correct_ok and location_id and not location_not_found:
                        to_correct_ok = False
                        comment = ''
                    comment += _('This product is not Expiry Date managed.\n')
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
                'location_not_found': location_not_found,
                'prodlot_name': batch,
                'expiry_date': expiry or False,
                'bad_expiry': bad_expiry,
                'bad_batch_name': bad_batch_name,
                'product_qty': product_qty,
                'product_uom': product_uom,
                'hidden_batch_management_mandatory': hidden_batch_management_mandatory,
                'hidden_perishable_mandatory': hidden_perishable_mandatory,
                'comment': comment,
                'to_correct': to_correct_ok,
            }

            vals['inventory_line_id'].append((0, 0, to_write))

        if product_error:
            raise osv.except_osv(
                _('Error'),
                _('Product not found in the database for %s line%s: %s') % (
                    len(product_error) > 1 and 'these' or 'this',
                    len(product_error) > 1 and 's' or '',
                    ' / '.join(tools.ustr(x) for x in product_error)),
            )
        if no_product_error:
            raise osv.except_osv(
                _('Error'),
                _('Product not defined on %s line%s: %s') % (
                    len(no_product_error) > 1 and 'these' or 'this',
                    len(no_product_error) > 1 and 's' or '',
                    ' / '.join(tools.ustr(x) for x in no_product_error)),
            )
        if wrong_location:
            raise osv.except_osv(
                _('Error'),
                '\n'.join(wrong_location)
            )

        # write order line on Inventory
        vals.update({'file_to_import': False})
        context['import_in_progress'] = True
        self.write(cr, uid, ids, vals, context=context)
        context['import_in_progress'] = False

        view_id = obj_data.get_object_reference(cr, uid, 'specific_rules','stock_initial_inventory_form_view')[1]

        if any(x[2]['to_correct'] for x in vals['inventory_line_id']):
            msg_to_return = _("The import of lines had errors, please correct the red lines below")

        return self.log(cr, uid, obj.id, msg_to_return, context={'view_id': view_id,})

    def check_lines_to_fix(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
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
        'mml_status': fields.function(tools.misc._get_std_mml_status, method=True, type='selection', selection=[('T', 'Yes'), ('F', 'No'), ('na', '')], string='MML', multi='mml'),
        'msl_status': fields.function(tools.misc._get_std_mml_status, method=True, type='selection', selection=[('T', 'Yes'), ('F', 'No'), ('na', '')], string='MSL', multi='mml'),

    }

    _defaults = {
        'inactive_product': False,
        'inactive_error': lambda *a: '',
        'mml_status': 'na',
        'msl_status': 'na',
    }

    def create(self, cr, uid, vals, context=None):
        pl_obj = self.pool.get('stock.production.lot')
        comment = ''
        just_warn = False
        hidden_batch_management_mandatory = False
        hidden_perishable_mandatory = False

        if vals.get('product_id', False):
            product = self.pool.get('product.product').browse(cr, uid, vals.get('product_id'), context=context)
            hidden_batch_management_mandatory = product.batch_management
            hidden_perishable_mandatory = product.perishable

        location_id = vals.get('location_id')
        location_not_found = vals.get('location_not_found')

        if 'location_not_found' in vals:
            del vals['location_not_found']

        batch = vals.get('prodlot_name')
        batch_numer = vals.get('prod_lot_id', False)
        if batch_numer and not batch: # for the sync case, sometime only the prodlot id is given but not the name, so search for name
            batch = self.pool.get('stock.production.lot').browse(cr, uid, batch_numer, context=context).name
            vals.update({'prodlot_name':batch})
        expiry = vals.get('expiry_date')
        batch_name = vals.get('prodlot_name')
        bad_expiry = vals.get('bad_expiry')
        bad_batch_name = vals.get('bad_batch_name')

        if 'bad_expiry' in vals:
            del vals['bad_expiry']

        if 'bad_batch_name' in vals:
            del vals['bad_batch_name']

        if location_id and not self.pool.get('stock.location').search_exist(cr, uid, [('id', '=', location_id), ('active', '=', True)], context=context):
            location_id = False
            vals['location_id'] = False
            location_not_found = True
            vals['location_not_found'] = True
            vals['to_correct_ok'] = True
            vals['comment'] = _('Location is inactive')


        if not location_id and not location_not_found:
            comment += _('Location is missing.\n')
        elif location_not_found:
            comment += _('Location not found.\n')

        if hidden_batch_management_mandatory and not batch:
            if bad_batch_name:
                comment += _('Incorrect batch number format.\n')
            elif batch_name and not bad_expiry:
                comment += _('Batch not found.\n')
            elif batch_name and bad_expiry:
                comment += _('Incorrectly formatted expiry date. Batch not created.\n')
            else:
                comment += _('Batch is missing.\n')
        elif hidden_batch_management_mandatory and batch and expiry:
            batch_ids = pl_obj.search(cr, uid, [
                ('product_id', '=', product.id),
                ('life_date', '=', expiry),
                ('name', '!=', batch),
            ], context=context)
            if batch_ids:
                comment += _('Other batch exists for this expiry date')
                just_warn = True

        if not product.batch_management and hidden_perishable_mandatory:
            if expiry and batch:
                batch_ids = pl_obj.search(cr, uid, [
                    ('product_id', '=', product.id),
                    ('life_date', '=', expiry),
                    ('name', '=', batch),
                ], context=context)
                if batch_ids:
                    batch = pl_obj.browse(cr, uid, batch_ids[0], context=context).name
                    vals['prodlot_name'] = batch
                else:
                    batch = False
                    vals['prodlot_name'] = False
            if expiry and not batch:
                batch_ids = pl_obj.search(cr, uid, [
                    ('product_id', '=', product.id),
                    ('life_date', '=', expiry),
                ], context=context)
                if batch_ids:
                    batch = False
                    vals['prodlot_name'] = False
                    comment += _('Other batch exists for this expiry date')
                    just_warn = True
#            if expiry and not batch:
#                comment += _('Expiry date will be created (with its internal batch).\n')
#                just_warn = True
#                vals.update({
#                    'to_correct_ok': False,
#                    'prodlot_name': False,
#                })
#            if expiry and batch:
#                comment += _('Expiry date selected (with its internal batch).\n')
#                just_warn = True
            if not expiry:
                if bad_expiry:
                    comment += _('Incorrectly formatted expiry date.\n')
                    vals['prodlot_name'] = False
                else:
                    comment += _('Expiry date is missing.\n')

        if not comment:
            if vals.get('comment'):
                comment = vals.get('comment')
            vals.update({'comment': comment, 'to_correct_ok': False})
        elif context.get('import_in_progress'):
            if just_warn:
                vals.update({'comment': comment, 'to_correct_ok': False})
            else:
                vals.update({'comment': comment, 'to_correct_ok': True})


        res = super(initial_stock_inventory_line, self).create(cr, uid, vals, context=context)
        return res

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
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

