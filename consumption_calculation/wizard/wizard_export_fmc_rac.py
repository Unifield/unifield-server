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


class wizard_export_fmc(osv.osv_memory):
    _name = 'wizard.export.fmc'
    _description = 'Export FMC lines'
    
    _columns = {
        'fmc_id': fields.many2one('monthly.review.consumption', string='FMC'),
        'file': fields.binary(string='File to export', required=True, readonly=True),
        'filename': fields.char(size=128, string='Filename', required=True),
        'message': fields.char(size=256, string='Message', readonly=True),
    }
    
    def close_window(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        res_id = self.browse(cr, uid, ids[0], context=context).fmc_id.id
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'monthly.review.consumption',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': res_id}   
        
wizard_export_fmc()

class wizard_export_rac(osv.osv_memory):
    _name = 'wizard.export.rac'
    _description = 'Export RAC lines'
    
    _columns = {
        'rac_id': fields.many2one('real.average.consumption', string='FMC'),
        'file': fields.binary(string='File to export', required=True, readonly=True),
        'filename': fields.char(size=128, string='Filename', required=True),
        'message': fields.char(size=256, string='Message', readonly=True),
    }
    
    def close_window(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        res_id = self.browse(cr, uid, ids[0], context=context).rac_id.id
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'real.average.consumption',
                'view_type': 'form',
                'view_mode': 'form,tree',
                'target': 'dummy',
                'context': context,
                'res_id': res_id}   
        
wizard_export_rac()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
