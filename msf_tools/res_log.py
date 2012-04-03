# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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

from osv import fields, osv

class res_log(osv.osv):
    _inherit = 'res.log'
    _columns = {'domain': fields.text('Domain'),
                }
    _defaults = {'domain': "[]",
                 }
    
    def _hook_log_get(self, cr, uid, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the get method from base>res_log.py>res_log
        
        - allow to modify the list of fields available in web server
        - add the new domain attribute, in order to specify a domain for the displayed form
        '''
        return super(res_log, self)._hook_log_get(cr, uid, context=context, *args, **kwargs) + ['domain']
    
res_log()
