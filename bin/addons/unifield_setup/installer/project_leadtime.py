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

class project_leadtime_setup(osv.osv_memory):
    _name = 'project.leadtime.setup'
    _inherit = 'res.config'
    
    _columns = {
        'preparation_leadtime': fields.integer(string='Preparation lead time', help='In days'),
        'shipment_leadtime': fields.integer(string='Shipment lead time', help='In days.'),
    }
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Load data in company
        '''
        res = super(project_leadtime_setup, self).default_get(cr, uid, fields, context=context)
        company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        res.update({'preparation_leadtime': company.preparation_lead_time,
                    'shipment_leadtime': company.shipment_lead_time})
        
        return res
    
    def onchange_leadtime(self, cr, uid, ids, leadtime, field='preparation_leadtime', context=None):
        '''
        Check the value of the leadtime and display warning message if
        the value is not between 0 and 9
        '''
        v = {}
        m = {}
        
        if leadtime and leadtime < 0:
            v.update({field: 0})
            m.update({'title': _('Error'),
                      'message': _('You cannot have a negative lead time !')})
        elif leadtime and leadtime > 9:
            v.update({field: 9})
            m.update({'title': _('Error'),
                      'message': _('You cannot have a lead time greater than 9 !')})
            
        return {'value': v, 'warning': m}
    
    def execute(self, cr, uid, ids, context=None):
        '''
        Fill the lead times in the company
        '''
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)
        company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        
        self.pool.get('res.company').write(cr, 1, company.id, {'preparation_lead_time': payload.preparation_leadtime,
                                                                 'shipment_lead_time': payload.shipment_leadtime}, context=context)
    
project_leadtime_setup()
