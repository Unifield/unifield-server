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

from osv import osv
from osv import fields

from tools.translate import _


class commitment_import_setup(osv.osv_memory):
    _name = 'commitment.import.setup'
    _inherit = 'res.config'
    
    _columns = {
        'import_commitments': fields.boolean(string='Manage commitments corresponding to international order through specific import ?'),
    }

    _defaults = {
        'import_commitments': lambda *a: True,
    }
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Display the default value for commitment import
        '''
        setup_id = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        res = super(commitment_import_setup, self).default_get(cr, uid, fields, context=context)
        res['import_commitments'] = setup_id.import_commitments
        
        return res
        
    
    def execute(self, cr, uid, ids, context=None):
        '''
        Fill the import_commitments field and active/de-activate ESC partner CV generation
        '''
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)
        
        setup_obj = self.pool.get('unifield.setup.configuration')
        journal_obj = self.pool.get('account.analytic.journal')
        line_obj = self.pool.get('account.analytic.line')
        
        setup_id = setup_obj.get_config(cr, uid)
        
        # Get import menu reference
        menu_ids = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'menu_import_commitment')[1]
            
        if payload.import_commitments != setup_id.import_commitments:
            if payload.import_commitments:
                # If activated, create analytic journal
                journal_obj.create(cr, uid, {'name': 'Engagement - intl orders',
                                             'code': 'ENGI',
                                             'type': 'engagement'})
                
                self.pool.get('ir.ui.menu').write(cr, uid, menu_ids, {'active': True}, context=context)
            else:
                #If de-activated, remove analytic items from the journal + the journal
                journal_ids = journal_obj.search(cr, uid, [('code', '=', 'ENGI')], context=context)
                if len(journal_ids) > 0:
                    line_ids = line_obj.search(cr, uid, [('imported_commitment', '=', True)], context=context)
                    line_obj.unlink(cr, uid, line_ids, context=context),
                    journal_obj.unlink(cr, uid, journal_ids, context=context)
                    
                self.pool.get('ir.ui.menu').write(cr, uid, menu_ids, {'active': False}, context=context)
                    
        setup_obj.write(cr, uid, [setup_id.id], {'import_commitments': payload.import_commitments}, context=context)

commitment_import_setup()
