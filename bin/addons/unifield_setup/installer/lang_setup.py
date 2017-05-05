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
import pooler
from tools.translate import _
import threading


class lang_setup(osv.osv_memory):
    _name = 'lang.setup'
    _inherit = 'res.config'
    
    def _list_lang(self, cr, uid, context=None):
        lang_obj = self.pool.get('res.lang')
        lang_ids = lang_obj.search(cr, uid, [('code', 'like', '_MF')])
        res = []
        for lg in lang_obj.read(cr, uid, lang_ids, ['name']):
            res.append((lg['id'], lg['name']))
        return res

    _columns = {
        'lang_id': fields.selection(_list_lang, string='Language', size=-1, required=True),
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
            try:
                res['lang_id'] = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_profile', 'lang_msf_en')[1]
            except ValueError:
                res = False
        
        return res
        
    
    def execute(self, cr, uid, ids, context=None):
        '''
        Fill the default lang on the configuration and for the current user
        '''
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)

        lang_obj = self.pool.get('res.lang')
        lang = lang_obj.read(cr, uid, payload.lang_id, ['code', 'translatable'])
        lang_obj.write(cr, uid, [payload.lang_id], {'translatable': True})
        self.set_lang(cr, uid, lang['code'], context=context)

        count_term = self.pool.get('ir.translation').search(cr, uid, [('lang', '=', lang['code'])], limit=1)
        if not lang['translatable'] or not count_term:
            thread = threading.Thread(target=lang_obj._install_new_lang_bg, args=(cr.dbname, uid, lang['id'], lang['code'], context))
            thread.start()


    def set_lang(self, cr, uid, code, context=None):
        setup_obj = self.pool.get('unifield.setup.configuration')
        setup_id = setup_obj.get_config(cr, uid)
        setup_obj.write(cr, uid, [setup_id.id], {'lang_id': code}, context=context)
        self.pool.get('res.users').write(cr, uid, uid, {'context_lang': code}, context=context)
        values_obj = self.pool.get('ir.values')
        values_obj.set(cr, uid, 'default', False, 'lang', ['res.partner'], code)


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
