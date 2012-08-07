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


class lang_setup(osv.osv_memory):
    _name = 'lang.setup'
    _inherit = 'res.config'
    
    _columns = {
        'lang_id': fields.many2one('res.lang', string='Language', required=True),
    }
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Display the default value for system language
        '''
        setup_id = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        res = super(lang_setup, self).default_get(cr, uid, fields, context=context)

        lang_ids = self.pool.get('res.lang').search(cr, uid, [('code', '=', setup_id.lang_id)], context=context)
        if lang_ids:
            res['lang_id'] = lang_ids[0]
        else:
            res['lang_id'] = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'base', 'lang_en')[1]
        
        return res
        
    
    def execute(self, cr, uid, ids, context=None):
        '''
        Fill the default lang on the configuration and for the current user
        '''
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)
        
        setup_obj = self.pool.get('unifield.setup.configuration')
        user_obj = self.pool.get('res.users')
        
        setup_id = setup_obj.get_config(cr, uid)
            
        if payload.lang_id:
            user_obj.write(cr, uid, uid, {'context_lang': payload.lang_id.code}, context=context)
    
        setup_obj.write(cr, uid, [setup_id.id], {'lang_id': payload.lang_id.code}, context=context)
        
lang_setup()


class config_users(osv.osv):
    _name = 'res.config.users'
    _inherit = 'res.config.users'
    
    def default_get(self, cr, uid, fields, context=False):
        '''
        If no lang defined, get this of the configuration setup
        '''
        setup_id = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        
        res = super(config_users, self).default_get(cr, uid, fields, context=context)
            
        if not setup_id:
            res['context_lang'] = 'en_MF'
        else:
            res['context_lang'] = setup_id.lang_id
        
        return res
    
config_users()