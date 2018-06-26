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


class change_uom_wizard(osv.osv_memory):
    _name = 'ir.model.fields.change.uom'
    
    _columns = {
        'field_id': fields.many2one('ir.model.fields', string='Field', required=True),
        'uom_id': fields.many2one('product.uom', string='UoM'),
    }
    
    def write_on_field(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        context.update({'allow_uom_write': True})
        for wiz in self.browse(cr, uid, ids, context=context):
            self.pool.get('ir.model.fields').write(cr, uid, [wiz.field_id.id], {'uom_id': wiz.uom_id.id}, context=context)
        context.pop('allow_uom_write')
            
        return {'type': 'ir.actions.act_window_close'}
    
change_uom_wizard()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
