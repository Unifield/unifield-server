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

from osv import osv
from osv import fields

import time


class catalogue_export_lines(osv.osv_memory):
    _name = 'catalogue.export.lines'
    _description = 'Supplier catalogue export lines'

    _columns = {
        'catalogue_id': fields.many2one('supplier.catalogue', string='Catalogue', required=True),
        'file_to_export': fields.binary(string='File to export'),
    }

    def export_file(self, cr, uid, ids, context=None):
        '''
        Export lines to file
        '''
        if not context:
            context = {}

        catalogue_ids = context.get('active_ids', [])

        catalogue = self.pool.get('supplier.catalogue').read(cr, uid, catalogue_ids[0], ['name'], context=context)

        report_name = 'supplier.catalogue.lines.xls'
        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': report_name,
            'report_name': report_name,
        }, context=context)

        context.update({
            'background_id': background_id,
            'background_time': 15,
        })

        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': {
                'ids': catalogue_ids,
                'context': context,
                'target_filename': 'SCLX_%s_%s' % (catalogue and catalogue['name'] or '', time.strftime('%Y%m%d_%H_%M')),
            },
            'nodestroy': True,
            'context': context,
        }

catalogue_export_lines()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
