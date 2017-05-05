# -*- coding: utf-8 -*-

from osv import osv
from osv import fields


class supplier_catalogue(osv.osv):
    _inherit = 'supplier.catalogue'

    def catalogue_import_lines(self, cr, uid, ids, context=None):
        res_id = self.pool.get('catalogue.import.lines.xls').create(cr, uid, {'catalogue_id': ids[0]}, context=context)
        return {'type': 'ir.actions.act_window',
            'res_model': 'catalogue.import.lines.xls',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'res_id': res_id,
            'context': context
        }

supplier_catalogue()
