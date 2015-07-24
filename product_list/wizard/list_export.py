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


class product_list_export(osv.osv_memory):
    _name = 'product.list.export'
    _description = 'Export of the product list'

    _columns = {
        'list_id': fields.many2one(
            'product.list',
            tring='List',
        ),
        'file': fields.binary(
            string='File to import',
            required=True,
            readonly=True,
        ),
        'filename': fields.char(
            size=128,
            string='Filename',
            required=True,
        ),
        'message': fields.char(
            size=256,
            string='Message',
            readonly=True,
        ),
    }

    def export_to_csv(self, cr, uid, ids, context=None):
        '''
        Builds and returns a file containing products list content
        '''
        if context is None:
            context = {}
        if len(context.get('active_ids', [])) == 0:
            raise osv.except_osv(
                _('Error'),
                _('You should choose one Product list to export !'),
            )
        if len(context.get('active_ids', [])) > 1:
            raise osv.except_osv(
                _('Error'),
                _('You should choose only one Product list to export !'),
            )

        active_id = context.get('active_ids')[0]

        list = self.pool.get('product.list').\
            browse(cr, uid, active_id, context=context)

        export = 'Product Code;Product Description;Comment'
        export += '\n'

        for line in list.product_ids:
            export += '%s;%s;%s' % (
                line.name.default_code,
                line.name.name,
                line.comment and line.comment or '',
            )
            export += '\n'

        file = base64.encodestring(export.encode("utf-8"))

        export_id = self.create(cr, uid, {
            'list_id': active_id, 'file': file,
            'filename': 'list_%s.csv' % (list.ref and list.ref.replace(' ', '_') or list.name.replace(' ', '_')),
            'message': 'The list has been exported. Please click on Save As button to download the file'})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.list.export',
            'res_id': export_id,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
        }

product_list_export()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
