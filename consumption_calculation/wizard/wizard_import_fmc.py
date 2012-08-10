# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

class wizard_import_fmc(osv.osv_memory):
    _name = 'wizard.import.fmc'
    _description = 'Import FMC from Excel sheet'
    
    _columns = {
        'file': fields.binary(string='File to import', required=True),
        'message': fields.text(string='Message', readonly=True),
        'rmc_id': fields.many2one('monthly.review.consumption', string='Monthly review consumption', required=True),
    }
    
    _defaults = {
        'message': lambda *a : """
        IMPORTANT : The first line will be ignored by the system.
        
        The file should be in CSV format (with ',' character as delimiter).
        The columns should be in this order :
          * Product Code
          * Product Description
          * FMC
          * Valid until (DD-MMM-YYYY)
        """
    }
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Set rmc_id with the active_id value in context
        '''
        if not context or not context.get('active_id'):
            raise osv.except_osv(_('Error !'), _('No Monthly review consumption found !'))
        else:
            rmc_id = context.get('active_id')
            res = super(wizard_import_fmc, self).default_get(cr, uid, fields, context=context)
            res['rmc_id'] = rmc_id
            
        return res
    
    def import_file(self, cr, uid, ids, context=None):
        '''
        Import file
        '''
        if context is None:
            context = {}
        product_obj = self.pool.get('product.product')
        line_obj = self.pool.get('monthly.review.consumption.line')
           
        import_fmc = self.browse(cr, uid, ids[0], context)
        rmc_id = import_fmc.rmc_id.id
        
        complete_lines = 0
        ignore_lines = 0

        fileobj = TemporaryFile('w+')
        fileobj.write(base64.decodestring(import_fmc.file))

        # now we determine the file format
        fileobj.seek(0)

        reader = csv.reader(fileobj, quotechar='"', delimiter=',')

        error = ''

        line_num = 0
        
        reader.next()

        for line in reader:
            line_num += 1
            if len(line) < 3:
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
            
            line_data = {'name': product_id,
                         'fmc': line[2].replace(',', '.'),
                         'mrc_id': rmc_id,}
            
            if len(line) == 4:
                #TODO : Fix the locale problem (use the locale of the server) 
                pass
                #line_data.update({'valid_until': time.strftime('%Y-%m-%d', time.strptime(line[3], '%d-%b-%Y'))})
            
            try:    
                line_obj.create(cr, uid, line_data, context=context)
                complete_lines += 1
            except:
                ignore_lines += 1
                
        self.write(cr, uid, ids, {'message': '''Importation completed !
                                                # of imported lines : %s
                                                # of ignored lines : %s
                                                
                                                Reported errors :
                                                %s
                                             ''' % (complete_lines, ignore_lines, error or 'No error !')}, context=context)
        
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'consumption_calculation', 'wizard_to_import_fmc_end')[1],
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.fmc',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': ids[0],
                'view_id': [view_id],
                }
        
    def close_import(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        res_id = self.browse(cr, uid, ids[0], context=context).rmc_id.id
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'monthly.review.consumption',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': res_id}    
    
wizard_import_fmc()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
