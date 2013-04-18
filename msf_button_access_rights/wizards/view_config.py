#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Max Mumford
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

def _join_dictionary(dict, key_prefix, value_prefix, seperator):
    s = ''
    if dict:
        for k, v in dict.items():
            s += key_prefix + str(k) + value_prefix + str(v) + seperator
    return s

class view_config_install(osv.osv_memory):
    _name = 'msf_button_access_rights.view_config_wizard_install'
    _inherit = 'res.config'
    
    def action_next(self, cr, uid, ids, context=None):
        return self.execute(cr, uid, ids, context)

    def execute(self, cr, uid, ids, context=None):
        """
        Perform a write (With no updated values) on each view in the database to trigger the Button Access Rule create / update process. Keep a log of all errors and return a new wizard showing the results.
        """
        context = context or {}
        
        view_pool = self.pool.get('ir.ui.view')
        view_ids = view_pool.search(cr, uid, [])
        errors = {}
        for id in view_ids:
            try:
                view_pool.write(cr, uid, id, {})
            except Exception as e:
                errors[id] = e
                
        all = self.pool.get('msf_button_access_rights.button_access_rule').search(cr, 1, [])
        
        results = {
           'successes': str(len(view_ids) - len(errors)) + ' Views were processed successfully',
           'total': 'You now have ' + str(len(all)) + ' Button Access Rules in total',
           'errors': str(len(errors)) + ' error(s) occurred while processing the Views\n\n' + _join_dictionary(errors, 'View ID: ', ', Error: ', '\n')
        }
        
        results_id = self.pool.get('msf_button_access_rights.view_config_wizard_install_results').create(cr, 1, results, context=context)
        return {
            'name': 'Generation Results',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'msf_button_access_rights.view_config_wizard_install_results',
            'res_id' : results_id,
            'type': 'ir.actions.act_window',
            'context' : context,
            'target' : 'new',
        }

view_config_install()
        
class view_config_install_results(osv.osv_memory):
    _name = 'msf_button_access_rights.view_config_wizard_install_results'
    _inherit = 'res.config'
    _columns = {
        'successes': fields.text('Successes', readonly=True),
        'total': fields.text('Total', readonly=True),
        'errors': fields.text('Errors', readonly=True),
    }

    def execute(self, cr, uid, ids, context=None):
        pass
view_config_install_results()
