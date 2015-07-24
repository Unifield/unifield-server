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

from tempfile import TemporaryFile

import base64
import csv


class product_list_import(osv.osv_memory):
    _name = 'product.list.import'
    _description = 'Products list import'

    _columns = {
        'file_to_import': fields.binary(
            string='File to import',
            required=True,
        ),
        'type': fields.selection(
            selection=[
                ('exist', 'Existing list'),
                ('new', 'New list'),
                ('replace', 'Replace list'),
            ],
            string='Existed/New list',
            required=True,
        ),
        'list_id': fields.many2one(
            'product.list',
            string='Existing list',
        ),
        'new_list_name': fields.char(
            size=128,
            string='Name of the new list',
        ),
        'new_list_type': fields.selection(
            selection=[
                ('list', 'List'),
                ('sublist', 'Sublist'),
            ],
            string='Type of the new list',
        ),
        'message': fields.text(
            string='Message',
            readonly=True,
        ),
    }

    _defaults = {
        'message': lambda *a: """
        The file should be in CSV format (with ';' character as delimiter).
        The columns should be in this order :
          * Product Code
          * Product Description
          * Comment
        """,
        'type': lambda *a: 'exist',
        'list_id': lambda self, cr, uid, context: context.get('active_ids', False) and context.get('active_ids', [])[0],
    }

    def close_window(self, cr, uid, ids, context=None):
        '''
        Simply close the wizard
        '''
        if context is None:
            context = {}
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.list',
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': context.get('list_id'),
            'target': 'crush',
        }

    def import_csv(self, cr, uid, ids, context=None):
        '''
        Import data on the CSV file on new or existing list
        '''
        if not context:
            context = {}

        list_obj = self.pool.get('product.list')
        line_obj = self.pool.get('product.list.line')
        product_obj = self.pool.get('product.product')

        list_id = False
        line_ids = []

        for file in self.browse(cr, uid, ids, context=context):
            if file.type == 'new':
                list_id = list_obj.create(cr, uid, {
                    'name': file.new_list_name,
                    'type': file.new_list_type,
                }, context=context)
            else:
                list_id = file.list_id.id

                # Remove all old lines
                if file.type == 'replace':
                    list_brw = list_obj.\
                        browse(cr, uid, list_id, context=context).product_ids
                    for list_line in list_brw:
                        line_obj.unlink(cr, uid, list_line.id, context=context)

            fileobj = TemporaryFile('w+')
            fileobj.write(base64.decodestring(file.file_to_import))

            # now we determine the file format
            fileobj.seek(0)

            reader = csv.reader(fileobj, quotechar='\'', delimiter=';')

            error = ''

            line_num = 0

            for line in reader:
                line_num += 1
                if len(line) < 2:
                    error += 'Line %s is not valid !' % (line_num)
                    error += '\n'
                    continue

                product_ids = product_obj.search(cr, uid, [
                    ('default_code', '=', line[0]),
                ], context=context)
                if not product_ids:
                    product_ids = product_obj.search(cr, uid, [
                        ('name', '=', line[1]),
                    ], context=context)

                if not product_ids and line_num == 1:
                    continue
                elif not product_ids:
                    error += 'Product [%s] %s not found !' % (line[0], line[1])
                    error += '\n'
                    continue

                product_id = product_ids[0]

                # Check if the product is already in list
                prd_lines = line_obj.search(cr, uid, [
                    ('name', '=', product_id),
                    ('list_id', '=', list_id),
                ], context=context)

                if not prd_lines:
                    line_ids.append(line_obj.create(cr, uid, {
                        'name': product_id,
                        'comment': len(line) > 2 and line[2] or '',
                        'list_id': list_id,
                    }, context=context))
                elif len(line) > 2:
                    line_obj.write(cr, uid, prd_lines, {'comment': line[2]})

            if error and error != '':
                self.write(cr, uid, ids, {'message': error})
                context.update({'import_error': True})

                line_obj.unlink(cr, uid, line_ids, context=context)
                if file.type == 'new_list':
                    list_obj.unlink(cr, uid, list_id, context=context)

                view_id = self.pool.get('ir.model.data').\
                    get_object_reference(cr, uid,
                                         'product_list',
                                         'product_list_import_error_view')[1]
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'product.list.import',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'res_id': ids[0],
                    'view_id': [view_id],
                    'context': context,
                }

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'product.list',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'dummy',
                'res_id': list_id,
                'context': context,
            }

product_list_import()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
