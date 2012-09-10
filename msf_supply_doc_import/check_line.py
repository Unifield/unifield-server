# -*- coding: utf-8 -*-

"""
This module is dedicated to help checking lines of Excel file at importation.
"""
from tools.translate import _


def check_empty_line(**kwargs):
    """
    Check if a line is not empty.
    If all cells are empty, return False.
    """
    row = kwargs['row']
    col_count = kwargs['col_count']
    for cell in range(col_count):
        if row.cells[cell].data:
            return True


def get_log_message(**kwargs):
    """
    Define log message
    """
    obj = kwargs.get('obj', False)
    to_write = kwargs['to_write']
    # nb_lines_error and tender are just for tender
    nb_lines_error = kwargs.get('nb_lines_error', False)
    tender = kwargs.get('tender', False)
    # not for tender
    obj = kwargs.get('obj', False)
    msg_to_return = False
    # nb_lines_error => is just for tender
    if tender and nb_lines_error:
        msg_to_return = "The import of lines had errors, please correct the red lines below"
    # is for all but tender
    elif not tender and [x for x in obj.order_line if x.to_correct_ok]:
        msg_to_return = "The import of lines had errors, please correct the red lines below"
    # is for all but tender
    elif not to_write:
        msg_to_return = "The file doesn\'t contain valid line."
    return msg_to_return


def product_value(cr, uid, **kwargs):
    """
    Compute product value according to cell content.
    Return product_code, comment, msg.
    """
    msg = ''
    row = kwargs['row']
    product_obj = kwargs['product_obj']
    # Tender does not have comment, it is an empty string
    comment = kwargs['to_write'].get('comment', '')
    # Tender does not have proc_type, it is False
    proc_type = kwargs['to_write'].get('proc_type', False)
    # Tender does not have price_unit, it is False
    price_unit = kwargs['to_write'].get('price_unit', False)
    error_list = kwargs['to_write']['error_list']
    default_code = kwargs['to_write']['default_code']
    if row.cells[0] and row.cells[0].data:
        product_code = row.cells[0].data
        if product_code:
            try:
                product_code = product_code.strip()
                p_ids = product_obj.search(cr, uid, [('default_code', '=', product_code)])
                if not p_ids:
                    comment += ' Code: %s' % (product_code)
                    msg = 'The Product\'s Code is not found in the database.'
                else:
                    default_code = p_ids[0]
                    proc_type = product_obj.browse(cr, uid, [default_code])[0].procure_method
                    price_unit = product_obj.browse(cr, uid, [default_code])[0].list_price
            except Exception:
                msg = 'The Product Code has to be a string.'
    if not default_code:
        comment += ' Product Code to be defined'
        error_list.append(msg or 'The Product\'s Code has to be defined')
    return {'default_code': default_code, 'proc_type': proc_type, 'comment': comment, 'error_list': error_list, 'price_unit': price_unit}


def quantity_value(**kwargs):
    """
    Compute qty value of the cell.
    """
    row = kwargs['row']
    product_qty = kwargs['to_write']['product_qty']
    error_list = kwargs['to_write']['error_list']
    # with warning_list: the line does not appear in red, it is just informative
    warning_list = kwargs['to_write']['warning_list']
    if not row.cells[2]:
        warning_list.append('The Product Quantity was not set. It is set to 1 by default.')
    else:
        if row.cells[2].type in ['int', 'float']:
            product_qty = row.cells[2].data
        else:
            error_list.append('The Product Quantity was not a number and it is required to be greater than 0, it is set to 1 by default.')
    return {'product_qty': product_qty, 'error_list': error_list, 'warning_list': warning_list}


def compute_uom_value(cr, uid, **kwargs):
    """
    Retrieves product UOM from Excel file
    """
    row = kwargs['row']
    uom_obj = kwargs['uom_obj']
    obj_data = kwargs['obj_data']
    error_list = kwargs['to_write']['error_list']
    uom_id = False
    msg = None
    if row.cells[3]:
        try:
            uom_name = row.cells[3].data.strip()
            uom_ids = uom_obj.search(cr, uid, [('name', '=', uom_name)])
            if uom_ids:
                uom_id = uom_ids[0]
        except Exception:
            msg = 'The UOM Name has to be a string.'
    if not uom_id:
        error_list.append(msg or 'The UOM Name was not valid.')
        uom_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'uom_tbd')[1]
    return {'uom_id': uom_id, 'error_list': error_list}


def compute_price_value(**kwargs):
    """
    Retrieves Price Unit from Excel file and compute it if None.
    """
    row = kwargs['row']
    # the price_unit was updated in the product_value method if the product exists, else it was set to 1 by default.
    price_unit = kwargs['to_write']['price_unit']
    default_code = kwargs['to_write']['default_code']
    error_list = kwargs['to_write']['error_list']
    # with warning_list: the line does not appear in red, it is just informative
    warning_list = kwargs['to_write']['warning_list']
    context = kwargs['context']
    price = kwargs['price'] or 'Price'
    if not row.cells[4] or not row.cells[4].data:
        if default_code:
            warning_list.append('The Price Unit was not set, we have taken the default "%s" of the product.' % price)
        else:
            error_list.append('The Price and Product not found.')
    elif row.cells[4].type not in ['int', 'float'] and not default_code:
        error_list.append('The Price Unit was not a number and no product was found.')
    elif row.cells[4].type in ['int', 'float']:
        price_unit = row.cells[4].data
    else:
        error_list.append('The Price Unit was not defined properly.')
    return {'price_unit': price_unit, 'error_list': error_list, 'warning_list': warning_list}


def compute_date_value(**kwargs):
    """
    Retrieves Date from Excel file or take the one from the parent
    """
    row = kwargs['row']
    date_planned = kwargs['to_write']['date_planned']
    error_list = kwargs['to_write']['error_list']
    # with warning_list: the line does not appear in red, it is just informative
    warning_list = kwargs['to_write']['warning_list']
    if row.cells[5] and row.cells[5].type == 'datetime':
        date_planned = row.cells[5].data
    else:
        warning_list.append('The date format was not correct. The date from the header has been taken.')
    return {'date_planned': date_planned, 'error_list': error_list, 'warning_list': warning_list}


def compute_currency_value(cr, uid, **kwargs):
    """
    Retrieves Currency from Excel file or take the one from the parent
    """
    row = kwargs['row']
    functional_currency_id = kwargs['to_write']['functional_currency_id']
    warning_list = kwargs['to_write']['warning_list']
    currency_obj = kwargs['currency_obj']
    browse_sale = kwargs.get('browse_sale', False)
    browse_purchase = kwargs.get('browse_purchase', False)
    # the cell number change between Internal Request and Sale Order
    cell_nb = kwargs['cell']
    fc_id = False
    msg = None
    if row.cells[cell_nb]:
        curr = row.cells[cell_nb].data
        if curr:
            try:
                curr_name = curr.strip().upper()
                currency_ids = currency_obj.search(cr, uid, [('name', '=', curr_name)])
                if currency_ids and browse_sale:
                    if currency_ids[0] == browse_sale.pricelist_id.currency_id.id:
                        fc_id = currency_ids[0]
                    else:
                        imported_curr_name = currency_obj.browse(cr, uid, currency_ids)[0].name
                        default_curr_name = browse_sale.pricelist_id.currency_id.name
                        msg = "The imported currency '%s' was not consistent and has been replaced by the \
                            currency '%s' of the order, please check the price." % (imported_curr_name, default_curr_name)
                elif currency_ids and browse_purchase:
                    if currency_ids[0] == browse_purchase.pricelist_id.currency_id.id:
                        fc_id = currency_ids[0]
                    else:
                        imported_curr_name = currency_obj.browse(cr, uid, currency_ids)[0].name
                        default_curr_name = browse_purchase.pricelist_id.currency_id.name
                        msg = "The imported currency '%s' was not consistent and has been replaced by the \
                            currency '%s' of the order, please check the price." % (imported_curr_name, default_curr_name)
            except Exception:
                msg = 'The Currency Name was not valid.'
    if fc_id:
        functional_currency_id = fc_id
    else:
        warning_list.append(msg or 'The Currency Name was not found.')
    return {'functional_currency_id': functional_currency_id, 'warning_list': warning_list}


def comment_value(**kwargs):
    """
    Retrieves comment from Excel file
    """
    row = kwargs['row']
    comment = kwargs['to_write']['comment']
    warning_list = kwargs['to_write']['warning_list']
    # the cell number change between Internal Request and Sale Order
    cell_nb = kwargs['cell']
    if not row.cells[cell_nb]:
        warning_list.append("No comment was defined")
    else:
        if comment and row.cells[cell_nb].data:
            comment += ', %s' % row.cells[cell_nb].data
        elif row.cells[cell_nb].data:
            comment = row.cells[cell_nb].data
    return {'comment': comment, 'warning_list': warning_list}
