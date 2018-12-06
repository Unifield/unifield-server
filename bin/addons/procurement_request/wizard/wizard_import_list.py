#!/usr/bin/env python
# -*- encoding: utf-8 -*-
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

from osv import osv
from osv import fields

from tools.translate import _

from tempfile import TemporaryFile

import base64
import csv



class wizard_import_list(osv.osv_memory):
    _name = 'procurement.request.import'
    _description = 'Import of Internal Request'

    _columns = {
        'file': fields.binary(strign='File to import', required=True),
        'message': fields.text(string='Message', readonly=True),
        'info': fields.text(string='Info', readonly=True),
    }

    _defaults = {
        'info': lambda s, cr, uid, context : _("""
        The file should be in CSV format (with ';' character as delimiter).
        The columns should be in this order :
          * Product Code
          * Product Description
          * UoM
          * Quantity
          * Comment
          * From stock ? (Write True if you want that the product will be supply from stock, leave blank if not)
        """)
    }

    def close_window(self, cr, uid, ids, context=None):
        '''
        Simply close the wizard
        '''
        if context is None:
            context = {}
        return {'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_id': context.get('list_id'),
                'target': 'crush'}

    def default_get(self, cr, uid, fields, context=None):
        '''
        Check if the Procurement List is saved and 
        set the error message
        '''
        if context is None:
            context = {}
        res = super(wizard_import_list, self).default_get(cr, uid, fields, context=context)

        # If we are after the importation
        if context.get('step', False) and context.get('step', False) == 'import':
            res['message'] = context.get('message', '')

            return res
        else:
            if not context.get('active_id', False):
                raise osv.except_osv(_('Warning'), _('Please save the Internal Request before importing lines'))

            # We check if the Procurement List is in 'Draft' state
            list_id = self.pool.get('sale.order').browse(cr, uid, context.get('active_id', []))
            if not list_id.procurement_request:
                raise osv.except_osv(_('Error'), _('You cannot import lines in a Sale Order'))
            elif not list_id or list_id.state != 'draft':
                raise osv.except_osv(_('Warning'), _('You cannot import lines in a confirmed Internal Request'))

        return res


    def import_file(self, cr, uid, ids, context=None):
        '''
        Import the file passed on the wizard in the
        Procurement List
        '''
        if context is None:
            context = {}
        list_line_obj = self.pool.get('sale.order.line')
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        model_data_obj = self.pool.get('ir.model.data')

        list_id = context.get('active_id', False)

        if not list_id:
            raise osv.except_osv(_('Error'), _('The system hasn\'t found a Internal Request to import lines'))

        import_list = self.browse(cr, uid, ids[0], context)

        fileobj = TemporaryFile('w+')
        fileobj.write(base64.decodestring(import_list.file))

        # now we determine the file format
        fileobj.seek(0)

        reader = csv.reader(fileobj, quotechar='\'', delimiter=';')

        error = ''

        line_num = 0

        for line in reader:
            line_num += 1
            if len(line) < 6:
                error += 'Line %s is not valid !' % (line_num)
                error += '\n'
                continue
            # Get the product
            product_ids = product_obj.search(cr, uid, [('default_code', '=', line[0])], context=context)
            if not product_ids:
                product_ids = product_obj.search(cr, uid, [('name', '=', line[1])], context=context)

            if not product_ids:
                error += 'Product [%s] %s not found !' % (line[0], line[1])
                error += '\n'
                continue

            product_id = product_ids[0]

            # Get the UoM
            uom_ids = uom_obj.search(cr, uid, [('name', '=', line[2])])
            if not uom_ids:
                error += 'Uom %s not found !' % line[2]
                error += '\n'
                continue

            uom_id = uom_ids[0]

            # Get the quantity
            product_qty = float(line[3].replace(',', '.'))

            # Get the comment
            comment = line[4]

            # Get the method
            from_stock = 'make_to_stock'
            if line[5] == 'True':
                from_stock = 'make_to_order'


            list_line_obj.create(cr, uid, {'product_id': product_id,
                                           'product_uom': uom_id,
                                           'product_uom_qty': product_qty,
                                           'notes': comment,
                                           'type': from_stock,
                                           'procurement_request': True,
                                           'order_id': list_id})

        view_ids = model_data_obj.search(cr, uid,
                                         [('module', '=', 'procurement_request'),
                                          ('name', '=', 'wizard_import_list_done')],
                                         offset=0, limit=1)[0]
        view_id = model_data_obj.browse(cr, uid, view_ids).res_id

        if error and error != '':
            context['message'] = error
        else:
            context['message'] = _('All lines have been succesfully imported !')

        context['step'] = 'import'
        context['list_id'] = list_id

        return {'type': 'ir.actions.act_window',
                'res_model': 'procurement.request.import',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'view_id': [view_id],
                'context': context,
                }

wizard_import_list()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

