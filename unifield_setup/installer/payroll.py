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


class payroll_setup(osv.osv_memory):
    _name = 'payroll.setup'
    _inherit = 'res.config'
    
    _columns = {
        'payroll_ok': fields.boolean(string='Does the system manage Payrolls import from Homere ?'),
    }
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Display the default value for payroll
        '''
        setup_id = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        res = super(payroll_setup, self).default_get(cr, uid, fields, context=context)
        
        res['payroll_ok'] = setup_id.payroll_ok
        
        return res
        
    
    def execute(self, cr, uid, ids, context=None):
        '''
        Fill the payroll_ok field and active/de-activate the feature
        '''
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)
        
        setup_obj = self.pool.get('unifield.setup.configuration')
        setup_id = setup_obj.get_config(cr, uid)

        # Get menus
        payroll_ids = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_homere_interface', 'menu_finance_payroll')[1]
        not_payroll_ids = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_homere_interface', 'import_nat_staff')[1]
        
        # Write changes
        if not payload.payroll_ok:
            self.pool.get('ir.ui.menu').write(cr, uid, payroll_ids, {'active': False}, context=context)
            self.pool.get('ir.ui.menu').write(cr, uid, not_payroll_ids, {'active': True}, context=context)
        else:
            self.pool.get('ir.ui.menu').write(cr, uid, payroll_ids, {'active': True}, context=context)
            self.pool.get('ir.ui.menu').write(cr, uid, not_payroll_ids, {'active': False}, context=context)
    
        setup_obj.write(cr, uid, [setup_id.id], {'payroll_ok': payload.payroll_ok}, context=context)
        
payroll_setup()
