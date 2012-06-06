# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

class test(osv.osv_memory):
    _name = "sync.server.test"
    
    def check_register(self, cr, uid, name, context=None):
        """
            return true if the entity name exist and is in state pending
        """
        ids = self.pool.get('sync.server.entity').search(cr, uid, [('name', '=', name), ('state', '=', 'pending')], context=context)
        return bool(ids)

    def check_validated(self, cr, uid, name, context=None):
        """
            return true if the entity name exist and is in state validated
        """
        ids = self.pool.get('sync.server.entity').search(cr, uid, [('name', '=', name), ('state', '=', 'validated')], context=context)
        return bool(ids)
        
    def change_rule_group(self, cr, uid, rule_name, group_name, context=None):
        rule_obj = self.pool.get('sync_server.sync_rule')
        ids = rule_obj.search(cr, uid, [('name', '=', rule_name)], context=context)
        g_ids = self.pool.get('sync.server.entity_group').search(cr, uid, [('name', '=', group_name)], context=context)
        if not ids or not g_ids:
            return False
        rule_obj.write(cr, uid, ids, {'group_id' : g_ids[0]}, context=context)
        return True
test()

