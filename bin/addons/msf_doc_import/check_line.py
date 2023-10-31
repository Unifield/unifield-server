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

"""
This module is dedicated to help checking lines of Excel file at importation.
"""
from msf_doc_import import MAX_LINES_NB
from tools.translate import _
from mx import DateTime
import logging
import pooler
import tools


def get_xml(value):
    new_value = []
    for v in list(value):
        if v == '&':
            v = '&amp;'
        elif v == '<':
            v = '&lt;'
        elif v == '>':
            v = 'glt;'
        elif v == '\'':
            v = '&apos;'
        elif v == '\"':
            v = '&quot;'
        new_value.append(v)
    return ''.join(new_value)

def check_nb_of_lines(**kwargs):
    """
    Compute number of lines in the xml file to import.
    """
    fileobj = kwargs['fileobj']
    rows = fileobj.getRows()
    i = 0
    for x in rows.__iter__():
        i = i + 1
        if i > MAX_LINES_NB + 1:
            return True
    return False


def check_empty_line(**kwargs):
    """
    Check if a line is not empty.
    If all cells are empty, return False.
    """
    row = kwargs['row']
    col_count = kwargs['col_count']
    line_num = kwargs['line_num']
    for cell in range(col_count):
        try:
            if row.cells and row.cells[cell] and row.cells[cell].data is not None:
                return True
        except TypeError as e:
            # Errors should never pass silently.
            logging.getLogger('check empty line').info('Line %s. Error %s' % (line_num, e))
        except ValueError:
            if row.cells[cell].data:
                return True


def get_log_message(**kwargs):
    """
    Define log message
    """
    to_write = kwargs['to_write']
    # nb_lines_error and tender are just for tender
    nb_lines_error = kwargs.get('nb_lines_error', False)
    tender = kwargs.get('tender', False)
    # not for tender
    obj = kwargs.get('obj', False)
    msg_to_return = False
    # nb_lines_error => is just for tender
    if tender and nb_lines_error:
        msg_to_return = _("The import of lines had errors, please correct the red lines below")
    # is for all but tender
    elif not tender and [x for x in obj.order_line if x.to_correct_ok]:
        msg_to_return = _("The import of lines had errors, please correct the red lines below")
    # is for all but tender
    elif not to_write:
        msg_to_return = _("The file doesn't contain valid line.")
    return msg_to_return


def compute_asset_value(cr, uid, **kwargs):
    """
    Retrieves asset_id from Excel file
    """
    row = kwargs['row']
    asset_obj = kwargs['asset_obj']
    error_list = kwargs['to_write']['error_list']
    product_id = kwargs['to_write'].get('product_id', False)
    cell_nb = kwargs['cell_nb']
    asset_id = None
    asset_name = None
    msg = ''
    if row.cells[cell_nb] and tools.ustr(row.cells[cell_nb]) != tools.ustr(None):
        if row.cells[cell_nb].type == 'str':
            asset_name = row.cells[cell_nb].data.strip()
            if asset_name and product_id:
                asset_ids = asset_obj.search(cr, uid, [('name', '=', asset_name), ('product_id', '=', product_id)])
                if asset_ids:
                    asset_id = asset_ids[0]
                else:
                    error_list.append('The Asset "%s" does not exist for this product.' % asset_name)
        else:
            msg = 'The Asset Name has to be a string.'
        if not asset_name:
            error_list.append(msg or 'The Asset was not valid.')
    return {'asset_id': asset_id, 'error_list': error_list}


def compute_batch_value(cr, uid, **kwargs):
    """
    Retrieves prodlot_id from Excel file
    """
    row = kwargs['row']
    prodlot_obj = kwargs['prodlot_obj']
    error_list = kwargs['to_write']['error_list']
    product_id = kwargs['to_write'].get('product_id', False)
    cell_nb = kwargs['cell_nb']
    prodlot_id = None
    expired_date = False
    msg = ''
    if row.cells[cell_nb] and tools.ustr(row.cells[cell_nb]) != tools.ustr(None):
        if row.cells[cell_nb].type == 'str':
            prodlot_name = row.cells[cell_nb].data.strip()
            if prodlot_name and product_id:
                prodlot_ids = prodlot_obj.search(cr, uid, [('name', '=', prodlot_name), ('product_id', '=', product_id)])
                if prodlot_ids:
                    prodlot_id = prodlot_ids[0]
                    expired_date = prodlot_obj.browse(cr, uid, prodlot_id).life_date
                else:
                    error_list.append('The Batch Number "%s" does not exist for this product.' % prodlot_name)
        else:
            msg = 'The Batch Number has to be string.'
        if not prodlot_id:
            error_list.append(msg or 'The Batch Number was not valid.')
    return {'prodlot_id': prodlot_id, 'expired_date': expired_date, 'error_list': error_list}


def compute_kit_value(cr, uid, **kwargs):
    """
    Retrieves kit_id from Excel file
    """
    row = kwargs['row']
    kit_obj = kwargs['kit_obj']
    error_list = kwargs['to_write']['error_list']
    product_id = kwargs['to_write'].get('product_id', False)
    cell_nb = kwargs['cell_nb']
    kit_id = None
    kit_name = None
    msg = ''
    if row.cells[cell_nb] and tools.ustr(row.cells[cell_nb]) != tools.ustr(None):
        if row.cells[cell_nb].type == 'str':
            kit_name = row.cells[cell_nb].data.strip()
            if kit_name and product_id:
                kit_ids = kit_obj.search(cr, uid, [('composition_type', '=', 'real'),
                                                   ('composition_reference', '=', kit_name),
                                                   ('composition_product_id', '=', product_id)])
                if kit_ids:
                    kit_id = kit_ids[0]
                else:
                    error_list.append(_('The Kit "%s" does not exist for this product.') % (kit_name,))
        else:
            msg = _('The Kit Name has to be a string')
        if not kit_name:
            error_list.append(msg or _('The kit was not valid.'))
    return {'kit_id': kit_id, 'error_list': error_list}


def compute_location_value(cr, uid, **kwargs):
    """
    Retrieves location_id and location_dest_id from Excel file
    """
    row = kwargs['row']
    loc_obj = kwargs['loc_obj']
    error_list = kwargs['to_write']['error_list']
    cell_nb = kwargs['cell_nb']
    check_type = kwargs.get('check_type')
    product_id = kwargs.get('product_id')
    pick_type = kwargs.get('pick_type')
    pick_subtype = kwargs.get('pick_subtype')
    pick_ext_cu = kwargs.get('pick_ext_cu')
    context = kwargs.get('context', {})
    loc_id = None
    loc_name = None
    msg = ''
    if row.cells[cell_nb] and tools.ustr(row.cells[cell_nb]) != tools.ustr(None):
        if row.cells[cell_nb].type == 'str':
            loc_name = row.cells[cell_nb].data.strip()
            if loc_name:
                domain = [('name', '=ilike', loc_name)]
                if check_type and product_id and check_type == 'src' and pick_type == 'internal':
                    domain.extend([('internal_src', '=', product_id), ('usage', '!=', 'view'), ('virtual_ok', '!=', 't')])
                elif check_type and product_id and check_type == 'dest' and pick_type == 'internal':
                    domain.extend([('internal_dest', '=', product_id), ('usage', '!=', 'view'), ('output_ok', '=', False), '|', ('virtual_ok', '!=', 't'), ('destruction_location', '=', 't')])
                elif check_type and product_id and check_type == 'src' and pick_type == 'in':
                    domain.extend([('usage', '=', 'supplier')])
                elif check_type and product_id and check_type == 'dest' and pick_type == 'in':
                    domain.extend([('incoming_dest', '=', product_id), ('usage', '!=', 'view')])
                elif check_type and product_id and check_type == 'src' and pick_type == 'out' and pick_subtype == 'standard':
                    domain.extend([('outgoing_src', '=', product_id), ('usage', '!=', 'view')])
                elif check_type and product_id and check_type == 'dest' and pick_type == 'out' and pick_subtype == 'standard':
                    domain.extend(['|', ('output_ok', '=', True), ('usage', '=', 'customer')])
                elif check_type and product_id and check_type == 'src' and pick_type == 'out' and pick_subtype == 'picking':
                    domain.extend([('picking_ticket_src', '=', product_id)])
                elif check_type and product_id and check_type == 'dest' and pick_type == 'out' and pick_subtype == 'picking':
                    pack_loc_id = loc_obj.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_outgoing', 'stock_location_packing')[1]
                    domain.extend([('id', '=', pack_loc_id)])

                loc_ids = loc_obj.search(cr, uid, domain, context=context)
                loc_by_name_ids = loc_obj.search(cr, uid, [('name', '=ilike', loc_name)], context=context)
                if pick_ext_cu:
                    if loc_ids and loc_ids[0] != pick_ext_cu.id:
                        error_list.append(
                            _('The Location "%s" on line level is not the same as the Location "%s" on header level.')
                            % (loc_name, pick_ext_cu.name))
                    elif loc_by_name_ids and loc_by_name_ids[0] != pick_ext_cu.id:
                        error_list.append(
                            _('The Location "%s" on line level is not the same as the Location "%s" on header level.')
                            % (loc_name, pick_ext_cu.name))
                    else:
                        loc_id = pick_ext_cu.id
                else:
                    if loc_ids:
                        loc_id = loc_ids[0]
                    elif loc_by_name_ids:
                        loc_by_name = loc_obj.browse(cr, uid, loc_by_name_ids[0], context=context)
                        if pick_type == 'in' and loc_by_name.location_category == 'consumption_unit' \
                                and loc_by_name.usage == 'customer':
                            loc_id = loc_by_name.id
                        else:
                            error_list.append(_('The Location "%s" is not compatible with the product of the stock move.') % loc_name)
                    else:
                        error_list.append(_('The Location "%s" does not exist on this instance.') % loc_name)

        else:
            msg = _('The Location Name has to be string.')
        if not loc_name:
            error_list.append(msg or _('The location was not valid.'))
    return {'location_id': loc_id, 'error_list': error_list}


def product_value(cr, uid, **kwargs):
    """
    Compute product value according to cell content.
    Return product_code, comment, msg.
    """
    msg = ''
    context = kwargs['context']
    row = kwargs['row']
    product_obj = kwargs['product_obj']
    # Tender does not have comment, it is an empty string
    comment = kwargs['to_write'].get('comment', '')
    # Tender does not have proc_type, it is False
    proc_type = kwargs['to_write'].get('proc_type', False)
    # Tender does not have price_unit, it is False
    price_unit = kwargs['to_write'].get('price_unit', False)
    cost_price = kwargs['to_write'].get('cost_price', False)
    product_code = kwargs['to_write'].get('product_code', False)
    error_list = kwargs['to_write']['error_list']
    default_code = kwargs['to_write']['default_code']
    p_id = False
    # The tender line may have a default product if it is not found
    obj_data = kwargs['obj_data']
    cell_nb = kwargs.get('cell_nb', 0)
    try:
        if row.cells[cell_nb] and row.cells[cell_nb].data:
            product_code = row.cells[cell_nb].data
            if product_code and row.cells[cell_nb].type == 'str':
                product_code = product_code.strip().upper()
                p_ids = product_obj.search(cr, uid, [('default_code', '=', product_code)], context=context)
                if not p_ids:
                    comment += _(' Code: %s') % (product_code)
                    msg = _('Product code %s doesn\'t exist in the DB.') % product_code
                else:
                    p_id = p_ids[0]
                    default_code = p_ids[0]
                    product = product_obj.browse(cr, uid, default_code)
                    proc_type = product.procure_method
                    price_unit = product.list_price
                    cost_price = product.standard_price
            else:
                msg = _('The Product Code has to be a string.')
        if not default_code or default_code == obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]:
            comment += _(' Product Code to be defined')
            error_list.append(msg or _('The Product\'s Code has to be defined'))
    # if the cell is empty
    except IndexError:
        comment += _(' Product Code to be defined')
        error_list.append(_('The Product\'s Code has to be defined'))
    return {
        'default_code': default_code, 'proc_type': proc_type, 'comment': comment, 'error_list': error_list, 'price_unit': price_unit,
        'cost_price': cost_price, 'product_code':product_code, 'product_id': p_id}


class ExceptionWrongQuantity(Exception):
    pass

def quantity_value(**kwargs):
    """
    Compute qty value of the cell.
    """
    row = kwargs['row']
    if kwargs.get('real_consumption', False):
        product_qty = kwargs['to_write']['consumed_qty']
    elif kwargs.get('monthly_consumption', False):
        product_qty = kwargs['to_write']['fmc']
    else:
        product_qty = kwargs['to_write']['product_qty']
    error_list = kwargs['to_write']['error_list']
    cell_nb = kwargs.get('cell_nb', 2)
    max_qty = kwargs.get('max_qty', 0)
    # with warning_list: the line does not appear in red, it is just informative
    warning_list = kwargs['to_write']['warning_list']
    try:
        if not row.cells[cell_nb]:
            warning_list.append(_('The Product Quantity was not set. It is set to 1 by default.'))
        else:
            if row.cells[cell_nb].type in ['int', 'float']:
                if not max_qty or row.cells[cell_nb].data < max_qty:
                    product_qty = row.cells[cell_nb].data
                else:
                    raise ExceptionWrongQuantity(_('The Product Quantity can not have more than 10 digits'))
            else:
                error_list.append(_('The Product Quantity was not a number and it is required to be greater than 0, it is set to 1 by default.'))
            if product_qty <= 0.00:
                error_list.append(_('The Product Quantity is required to be greater than 0, it is set to 1 by default'))
                product_qty = 1.00
    # if the cell is empty
    except IndexError:
        warning_list.append(_('The Product Quantity was not set. It is set to 1 by default.'))
    return {'product_qty': product_qty, 'error_list': error_list, 'warning_list': warning_list}


def number_value(**kwargs):
    """
    get/check value of a number cell
    kwargs must contains 'field_name' and 'cell_nb' values
    kwargs must contains 'to_write/error_list' and 'to_write/warning_list' values
    kwargs should contain a 'field_desc' value
    kwargs should contain a 'default' value (0 if not set)
    :rtype: dict
    """
    field_name = kwargs['field_name']  # let raise an except if missing bc mandatory
    cell_nb = kwargs['cell_nb']  # let raise an except if missing bc mandatory
    field_desc = kwargs.get('field_desc', 'Cell %d' % (cell_nb, ))
    default = kwargs.get('default', 0)
    res_val = default

    row = kwargs['row']
    error_list = kwargs['to_write']['error_list']
    # with warning_list: the line does not appear in red, it is just informative
    warning_list = kwargs['to_write']['warning_list']
    try:
        if not row.cells[cell_nb]:
            warning_list.append(_('%s was not set. It is set to %d by default.') % (field_desc, default, ))
        else:
            if row.cells[cell_nb].type in ['int', 'float']:
                res_val = row.cells[cell_nb].data
            else:
                error_list.append(_('%s was not a number, it is set to %d by default.') % (field_desc, default, ))
    # if the cell is empty
    except IndexError:
        warning_list.append(_('%s was not set. It is set to %d by default.') % (field_desc, default, ))
    res = {
        'error_list': error_list,
        'warning_list': warning_list
    }
    res[field_name] = res_val
    return res


def compute_uom_value(cr, uid, **kwargs):
    """
    Retrieves product UOM from Excel file
    """
    context = kwargs['context']
    row = kwargs['row']
    uom_obj = kwargs['uom_obj']
    product_obj = kwargs['product_obj']
    pool_obj = pooler.get_pool(cr.dbname)
    default_code = kwargs['to_write']['default_code']
    error_list = kwargs['to_write']['error_list']
    uom_id = kwargs['to_write'].get('uom_id', False)
    # The tender line may have a default UOM if it is not found
    obj_data = kwargs['obj_data']
    cell_nb = kwargs.get('cell_nb', 3)
    msg = ''
    try:
        if row.cells[cell_nb] and row.cells[cell_nb].data is not None:
            if row.cells[cell_nb].type == 'str':
                uom_name = row.cells[cell_nb].data.strip()
                uom_ids = uom_obj.search(cr, uid, [('name', '=ilike', uom_name)], context=context)
                if uom_ids:
                    uom_id = uom_ids[0]
                    # check the uom category consistency
                    if default_code:
                        if not pool_obj.get('uom.tools').check_uom(cr, uid, default_code, uom_id, context):
                            uom_id = product_obj.browse(cr, uid, [default_code])[0].uom_id.id
                            error_list.append(msg or _('The UOM imported was not in the same category than the UOM of the product so we took the UOM of the product instead.'))
            else:
                msg = _('The UOM Name has to be a string.')
            if not uom_id or uom_id == obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]:
                error_list.append(msg or _('The UOM Name was not valid.'))
                uom_id = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]
        else:
            error_list.append(msg or _('The UOM Name was empty.'))
            if default_code:
                uom_id = product_obj.browse(cr, uid, [default_code])[0].uom_id.id
            else:
                uom_id = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]
    # if the cell is empty
    except IndexError, e:
        error_list.append(_('The UOM Name was empty. (Details: %s)') % e)
        if default_code:
            uom_id = product_obj.browse(cr, uid, [default_code])[0].uom_id.id
        else:
            uom_id = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]
    return {'uom_id': uom_id, 'error_list': error_list}


def compute_price_value(**kwargs):
    """
    Retrieves Price Unit from Excel file and compute it if None.
    """
    row = kwargs['row']
    # the price_unit was updated in the product_value method if the product exists, else it was set to 1 by default.
    price_unit = kwargs['to_write']['price_unit']
    cost_price = kwargs['to_write'].get('cost_price')
    default_code = kwargs['to_write']['default_code']
    error_list = kwargs['to_write']['error_list']
    # with warning_list: the line does not appear in red, it is just informative
    warning_list = kwargs['to_write']['warning_list']
    price = kwargs['price'] or 'Price'
    is_rfq = kwargs.get('is_rfq', False)
    price_unit_defined = False
    cell_nb = kwargs.get('cell_nb', 3)
    try:
        if is_rfq:
            if row.cells[cell_nb].type in ['int', 'float']:
                price_unit_defined = True
                price_unit = row.cells[cell_nb].data
                cost_price = row.cells[cell_nb].data
        else:
            if not row.cells[cell_nb] or not row.cells[cell_nb].data:
                if default_code:
                    warning_list.append(_('The Price Unit was not set, we have taken the default "%s" of the product.') % price)
                else:
                    error_list.append(_('The Price and Product were not found.'))
            elif row.cells[cell_nb].type not in ['int', 'float'] and not default_code:
                error_list.append(_('The Price Unit was not a number and no product was found.'))
            elif row.cells[cell_nb].type in ['int', 'float']:
                price_unit_defined = True
                price_unit = row.cells[cell_nb].data
                cost_price = row.cells[cell_nb].data
            else:
                error_list.append(_('The Price Unit was not defined properly.'))
    # if nothing is found at the line index (empty cell)
    except IndexError:
        if default_code:
            warning_list.append(_('The Price Unit was not set, we have taken the default "%s" of the product.') % price)
        else:
            error_list.append(_('Neither Price nor Product found.'))
    return {'cost_price': cost_price, 'price_unit': price_unit, 'error_list': error_list, 'warning_list': warning_list, 'price_unit_defined': price_unit_defined}


def compute_date_value(**kwargs):
    """
    Retrieves Date from Excel file or take the one from the parent
    """
    row = kwargs['row']
    date_planned = kwargs['to_write']['date_planned']
    error_list = kwargs['to_write']['error_list']
    # with warning_list: the line does not appear in red, it is just informative
    warning_list = kwargs['to_write']['warning_list']
    cell_nb = kwargs.get('cell_nb', 5)
    try:
        if not row.cells[cell_nb].data:
            warning_list.append(_('Delivery requested date not found. The date from the header has been taken.'))
        elif row.cells[cell_nb] and row.cells[cell_nb].type == 'datetime':
            date_planned = row.cells[cell_nb].data.strftime('%Y-%m-%d')
        else:
            warning_list.append(_('The delivery requested date format was not correct. The date from the header has been taken.'))
    # if nothing is found at the line index (empty cell)
    except IndexError:
        warning_list.append(_('The delivery requested date format was not correct. The date from the header has been taken.'))
    return {'date_planned': date_planned, 'error_list': error_list, 'warning_list': warning_list}


def compute_confirmed_delivery_date_value(**kwargs):
    """
    Retrieves Date from Excel file or take the one from the parent
    """
    row = kwargs['row']
    confirmed_delivery_date = kwargs['to_write']['confirmed_delivery_date']
    error_list = kwargs['to_write']['error_list']
    # with warning_list: the line does not appear in red, it is just informative
    warning_list = kwargs['to_write']['warning_list']
    cell_nb = kwargs.get('cell_nb', 7)
    try:
        if row.cells[cell_nb] and row.cells[cell_nb].data:
            if row.cells[cell_nb].type == 'datetime':
                confirmed_delivery_date = row.cells[cell_nb].data.strftime('%Y-%m-%d')
            else:
                warning_list.append(_('The confirmed delivery date format was not correct. The date from the header has been taken (if any)'))
    # if nothing is found at the line index (empty cell)
    except IndexError:
        warning_list.append(_('The confirmed delivery date format was not correct. The date from the header has been taken (if any)'))
    return {'confirmed_delivery_date': confirmed_delivery_date, 'error_list': error_list, 'warning_list': warning_list}


def compute_batch_expiry_value(cr, uid, **kwargs):
    """
    Retrives Batch number and expiry date from Excel file
    """
    row = kwargs['row']
    bn_cell_nb = kwargs['bn_cell_nb']
    ed_cell_nb = kwargs['ed_cell_nb']
    bn_obj = kwargs['bn_obj']
    product_obj = kwargs['product_obj']
    product_id = kwargs['product_id']
    error_list = kwargs['to_write']['error_list']
    warning_list = kwargs['to_write']['warning_list']
    picking_type = kwargs.get('picking_type', 'internal')
    batch_name = None
    expiry_date = None
    batch_number = None
    bn_ids = []

    # Get batch number
    if row.cells[bn_cell_nb] and row.cells[bn_cell_nb].type in ('int', 'str') and row.cells[bn_cell_nb].data:
        batch_name = row.cells[bn_cell_nb].data

    if row.cells[ed_cell_nb] and row.cells[ed_cell_nb].data:
        if row.cells[ed_cell_nb].type == 'str':
            # if the cell is type str, cast it to DateTime
            try:
                expiry_date = DateTime.strptime(row.cells[ed_cell_nb].data, '%d/%m/%Y')
            except:
                error_list.append(_('Incorrectly formatted expiry date: %s. '
                                    'The expected date should be > 01/01/1900 in this format '
                                    'DD/MM/YYYY.') % row.cells[ed_cell_nb].data)
                expiry_date = False
        elif row.cells[ed_cell_nb].type == 'datetime':
            expiry_date = row.cells[ed_cell_nb].data
        if expiry_date:
            try:
                expiry_date = expiry_date.strftime('%Y-%m-%d')
            except:
                error_list.append(_('Incorrectly formatted expiry date: %s. '
                                    'The expected date should be > 01/01/1900 in this format '
                                    'DD/MM/YYYY.') % expiry_date)
                expiry_date = False

    prd_brw = product_id and product_obj and product_obj.browse(cr, uid, product_id) or False

    bn_mgmt = prd_brw and prd_brw.batch_management
    ed_mgmt = prd_brw and prd_brw.perishable

    if not bn_ids and product_id and batch_name and expiry_date:
        bn_ids = bn_obj.search(cr, uid, [('product_id', '=', product_id), ('name', '=', batch_name), ('life_date', '=', expiry_date)])
        if not bn_ids:
            if bn_obj.search(cr, uid, [('product_id', '=', product_id), ('name', '=', batch_name)]):
                if bn_mgmt:
                    error_list.append(_('The expiry date doesn\'t match with the expiry date of the batch. Batch not selected'))
                else:
                    error_list.append(_('The expiry date doesn\'t match with the expiry date of the batch. Expiry date not selected'))
            elif bn_mgmt and picking_type == 'in':
                bn_ids = [bn_obj.create(cr, uid, {
                    'product_id': product_id,
                    'name': batch_name,
                    'life_date': expiry_date,
                })]
            else:
                error_list.append(_('Batch not found'))
    elif not bn_ids and product_id and expiry_date:
        if bn_mgmt:
            error_list.append(_('The Batch number is not set.'))
        elif ed_mgmt:
            bn_ids = bn_obj.search(cr, uid, [('product_id', '=', product_id), ('life_date', '=', expiry_date)])
    elif not bn_ids and product_id and batch_name:
        if bn_mgmt:
            error_list.append(_('Expiry date is not set, so batch not selected.'))
        else:
            error_list.append(_('Expiry date is not set.'))

    if bn_ids:
        batch_number = bn_ids[0]

    return {'prodlot_id': batch_number, 'expired_date': expiry_date, 'error_list': error_list, 'warning_list': warning_list}


def compute_currency_value(cr, uid, **kwargs):
    """
    Retrieves Currency from Excel file or take the one from the parent
    """
    context = kwargs['context']
    row = kwargs['row']
    functional_currency_id = kwargs['to_write']['functional_currency_id']
    warning_list = kwargs['to_write']['warning_list']
    currency_obj = kwargs['currency_obj']
    browse_sale = kwargs.get('browse_sale', False)
    browse_purchase = kwargs.get('browse_purchase', False)
    # the cell number change between Internal Request and Sale Order
    cell_nb = kwargs['cell_nb']
    fc_id = False
    msg = ''
    try:
        if row.cells[cell_nb]:
            curr = row.cells[cell_nb].data
            if curr:
                if row.cells[cell_nb].type == 'str':
                    curr_name = curr.strip().upper()
                    currency_ids = currency_obj.search(cr, uid, [('name', '=', curr_name)], context=context)
                    if currency_ids and browse_sale:
                        if browse_sale.procurement_request:
                            order_cur_id = browse_sale.functional_currency_id.id
                        else:
                            # UFTP-395: just a small typo bug
                            order_cur_id = browse_sale.pricelist_id.currency_id.id
                        if currency_ids[0] == order_cur_id:
                            fc_id = currency_ids[0]
                        else:
                            imported_curr_name = currency_obj.browse(cr, uid, currency_ids)[0].name
                            if browse_sale.procurement_request:
                                default_curr_name = browse_sale.functional_currency_id.name
                            else:
                                default_curr_name = browse_sale.pricelist_id.currency_id.name
                            msg = _("The imported currency '%s' was not consistent and has been replaced by the \
                                currency '%s' of the order, please check the price.") % (imported_curr_name, default_curr_name)
                    elif currency_ids and browse_purchase:
                        if currency_ids[0] == browse_purchase.pricelist_id.currency_id.id:
                            fc_id = currency_ids[0]
                        else:
                            imported_curr_name = currency_obj.browse(cr, uid, currency_ids)[0].name
                            default_curr_name = browse_purchase.pricelist_id.currency_id.name
                            msg = _("The imported currency '%s' was not consistent and has been replaced by the \
                                currency '%s' of the order, please check the price.") % (imported_curr_name, default_curr_name)
                else:
                    msg = _('The Currency Name was not valid, it has to be a string.')
        if fc_id:
            functional_currency_id = fc_id
        else:
            warning_list.append(msg or _('The Currency Name was not found.'))
    # if the cell is empty
    except IndexError:
        warning_list.append(_('The Currency Name was not found.'))
    return {'functional_currency_id': functional_currency_id, 'warning_list': warning_list}


def comment_value(**kwargs):
    """
    Retrieves comment from Excel file
    """
    row = kwargs['row']
    comment = kwargs['to_write']['comment']
    warning_list = kwargs['to_write']['warning_list']
    # the cell number change between Internal Request and Sale Order
    cell_nb = kwargs['cell_nb']
    try:
        if not row.cells[cell_nb]:
            warning_list.append(_("No comment was defined"))
        else:
            if comment and row.cells[cell_nb].data:
                comment += ', %s' % row.cells[cell_nb].data
            elif row.cells[cell_nb].data:
                comment = row.cells[cell_nb].data
    except IndexError:
        warning_list.append(_("No comment was defined"))
    return {'comment': comment, 'warning_list': warning_list}


def line_number_value(**kwargs):
    '''
    Retrives line number from Excel file
    '''
    row = kwargs["row"]
    cell_nb = kwargs['cell_nb']
    line_number = kwargs['to_write']['line_number']
    warning_list = kwargs['to_write']['warning_list']
    try:
        if not row.cells[cell_nb]:
            warning_list.append(_("No line number present so generated by system"))
        elif not row.cells[cell_nb].data:
            warning_list.append(_("No line number present so generated by system"))
        elif row.cells[cell_nb].type != 'int':
            warning_list.append(_("The line number must be an integer, system has generated a new one"))
        else:
            line_number = row.cells[cell_nb].data
    except IndexError:
        warning_list.append(_("No line number present so generated by system"))
    return {'line_number': line_number, 'warning_list': warning_list}


def check_lines_currency(rows, ccy_col_index, ccy_expected_code):
    """
    check rows currency
    :param ccy_col_index: currency column index
    :param ccy_expected_code: currency code expected in all rows
    :return count of bad ccy lines or 0 if OK
    :rtype int
    """
    res = 0
    for row in rows:
        if row.cells:
            if len(row.cells) < ccy_col_index + 1:
                res += 1
            else:
                cell = row.cells[ccy_col_index]
                if cell.type == 'str':
                    if tools.ustr(cell).upper() != ccy_expected_code.upper():
                        res += 1
                else:
                    res += 1
    return res
