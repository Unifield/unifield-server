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
import time

class stock_forecast_export(osv.osv_memory):
    _name = 'stock.forecast.export'
    _description = 'Export of the forecast list'
    
    _columns = {
        'list_id': fields.many2one('stock.forecast', string='List'),
        'file': fields.binary(string='File to export', required=True, readonly=True),
        'filename': fields.char(size=128, string='Filename', required=True),
        'message': fields.char(size=256, string='Message', readonly=True),
    }
    
    def do_back(self, cr, uid, ids, context=None):
        '''
        button was removed following the 'popup' solution 
        <button name='do_back' string='Back to Forecast' type='object' icon='gtk-back' />
        '''
        back_id = context['stock_forecast_id'][0]
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.forecast',
                'res_id': back_id,
                'view_mode': 'form',
                'view_type': 'form',
                'target': 'new',
                }
    
    def get_selection_text(self, cr, uid, obj, field, id, context=None):
        '''
        get the text for selection id
        '''
        tuples = obj._columns[field].selection
        if hasattr(tuples, '__call__'):
            line_obj = self.pool.get('stock.forecast.line')
            tuples = tuples(line_obj, cr, uid, context=context)
        
        result = [x[1] for x in tuples if x[0] == id]
        
        if result:
            return result[0]
        
        return False
    
    def export_to_csv(self, cr, uid, ids, context=None):
        '''
        Builds and returns a file containing products list content
        '''
        active_id = ids[0]
        
        list = self.pool.get('stock.forecast').browse(cr, uid, active_id, context=context)
        
        if not list.stock_forecast_lines:
            raise osv.except_osv(_('Warning !'), _('The forecast does not contain any moves.'))
        
        line_obj = self.pool.get('stock.forecast.line')
        
        export = 'Date;Doc;Order Type;Reference;State;Quantity;Stock Situation'
        export += '\n'
        
        for line in list.stock_forecast_lines:
            export += '%s;%s;%s;%s;%s;%s;%s' % (line.date.split(' ')[0] or '',
                                                line.doc or '',
                                                self.get_selection_text(cr, uid, line_obj, 'order_type', line.order_type, context=context) or '',
                                                line.reference and line.reference.name_get()[0][1] or '',
                                                self.get_selection_text(cr, uid, line_obj, 'state', line.state, context=context) or '',
                                                line.qty or '0.0',
                                                line.stock_situation or '0.0',)
            export += '\n'
            
        file = base64.encodestring(export.encode("utf-8"))
        
        export_id = self.create(cr, uid, {'list_id': active_id,
                                          'file': file, 
                                          'filename': 'list_%s_%s.csv' % (list.product_id.code, time.strftime('%Y-%m-%d-%H:%M:%S')),
                                          'message': 'The list has been exported. Please click on Save As button to download the file'}, context=context)
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.forecast.export',
                'res_id': export_id,
                'view_mode': 'form',
                'view_type': 'form',
                'target': 'new',
                'context': context,
                }

stock_forecast_export()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
