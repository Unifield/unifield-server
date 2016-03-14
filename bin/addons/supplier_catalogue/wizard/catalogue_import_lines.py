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
from tools.translate import _


class catalogue_import_lines(osv.osv_memory):
    _name = 'catalogue.import.lines'
    _description = 'Supplier catalogue import lines'
    
    _columns = {
        'catalogue_id': fields.many2one('supplier.catalogue', string='Catalogue', required=True),
        'file_to_import': fields.binary(string='File to import'),
    }
    
    def import_file(self, cr, uid, ids, context=None):
        '''
        Import lines from file
        '''
        if not context:
            context = {}
        
        for wiz in self.browse(cr, uid, ids, context=context):
            if not wiz.file_to_import:
                raise osv.except_osv(_('Error'), _('Nothing to import.'))
            
            file = wiz.file_to_import
            # TODO: Import file            
        
        return {'type': 'ir.actions.act_window_close'}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
