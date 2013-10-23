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
import logging
import pooler

def get_xml(value):
    new_value = []
    for v in list(value):
        if v == '&':
            v='&amp;'
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
    msg = ''
    if row.cells[cell_nb] and str(row.cells[cell_nb]) != str(None):
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
        if not asset_id:
            error_list.append(msg or 'The Asset was not valid.')
    return {'asset_id': asset_id, 'error_list': error_list}


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
    error_list = kwargs['to_write']['error_list']
    default_code = kwargs['to_write']['default_code']
    # The tender line may have a default product if it is not found
    obj_data = kwargs['obj_data']
    cell_nb = kwargs.get('cell_nb', 0)
    try:
        if row.cells[cell_nb] and row.cells[cell_nb].data:
            product_code = row.cells[cell_nb].data
            if product_code and row.cells[cell_nb].type == 'str':
                product_code = product_code.strip()
                p_ids = product_obj.search(cr, uid, [('default_code', '=', product_code)], context=context)
                if not p_ids:
                    comment += _(' Code: %s') % (product_code)
                    msg = _('Product code doesn\'t exist in the DB.')
                else:
                    default_code = p_ids[0]
                    proc_type = product_obj.browse(cr, uid, [default_code])[0].procure_method
                    price_unit = product_obj.browse(cr, uid, [default_code])[0].list_price
                    cost_price = product_obj.browse(cr, uid, [default_code])[0].standard_price
            else:
                msg = _('The Product Code has to be a string.')
        if not default_code or default_code == obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]:
            comment += _(' Product Code to be defined')
            error_list.append(msg or _('The Product\'s Code has to be defined'))
    # if the cell is empty
    except IndexError:
        comment += _(' Product Code to be defined')
        error_list.append(_('The Product\'s Code has to be defined'))
    return {'default_code': default_code, 'proc_type': proc_type, 'comment': comment, 'error_list': error_list, 'price_unit': price_unit, 'cost_price': cost_price}


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
    # with warning_list: the line does not appear in red, it is just informative
    warning_list = kwargs['to_write']['warning_list']
    cell_nb = kwargs.get('cell_nb', False)
    if not cell_nb:
        cell_nb = 2
    try:
        if not row.cells[cell_nb]:
            warning_list.append(_('The Product Quantity was not set. It is set to 1 by default.'))
        else:
            if row.cells[cell_nb].type in ['int', 'float']:
                product_qty = row.cells[cell_nb].data
            else:
                error_list.append(_('The Product Quantity was not a number and it is required to be greater than 0, it is set to 1 by default.'))
            if product_qty <= 0.00:
                error_list.append(_('The Product Quantity is required to be greater than 0, it is set to 1 by default'))
                product_qty = 1.00
    # if the cell is empty
    except IndexError:
        warning_list.append(_('The Product Quantity was not set. It is set to 1 by default.'))
    return {'product_qty': product_qty, 'error_list': error_list, 'warning_list': warning_list}


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
    cell_nb = kwargs.get('cell_nb', 3)
    try:
        if row.cells[cell_nb] and row.cells[cell_nb].data is not None:
            if row.cells[cell_nb].type == 'str':
                uom_name = row.cells[cell_nb].data.strip()
                uom_ids = uom_obj.search(cr, uid, [('name', '=', uom_name)], context=context)
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
    price_unit_defined = False
    cell_nb = kwargs.get('cell_nb', 4)
    try:
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
        if row.cells[cell_nb] and row.cells[cell_nb].type == 'datetime':
            date_planned = row.cells[cell_nb].data
        else:
            warning_list.append(_('The date format was not correct. The date from the header has been taken.'))
    # if nothing is found at the line index (empty cell)
    except IndexError:
        warning_list.append(_('The date format was not correct. The date from the header has been taken.'))
    return {'date_planned': date_planned, 'error_list': error_list, 'warning_list': warning_list}


def compute_expiry_date_value(**kwargs):
    """
    Retrieves Date from Excel file or take the one from the parent
    """
    row = kwargs['row']
    cell_nb = kwargs['cell_nb']
    error_list = kwargs['to_write']['error_list']
    expiry_date = None
    try:
        if row.cells[cell_nb] and row.cells[cell_nb].type == 'datetime' and row.cells[cell_nb].data:
            expiry_date = row.cells[cell_nb].data
        else:
            error_list.append('The date format was not correct.')
    except IndexError:
        pass
    return {'expiry_date': expiry_date, 'error_list': error_list}


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
                        if currency_ids[0] == browse_sale.pricelist_id.currency_id.id:
                            fc_id = currency_ids[0]
                        else:
                            imported_curr_name = currency_obj.browse(cr, uid, currency_ids)[0].name
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
