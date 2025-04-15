#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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

class res_company(osv.osv):
    _name = 'res.company'
    _inherit = 'res.company'

    _columns = {
        'instance_id': fields.many2one('msf.instance', string="Proprietary Instance",
                                       help="Representation of the current instance"),
        'second_time': fields.boolean('Config. Wizard launched for the second time'),
        'company_second_time': fields.boolean('Company Config. Wizard launched for the second time'),
    }

    _defaults = {
        'second_time': lambda *a: False,
        'company_second_time': lambda *a: False,
    }

    def _refresh_objects(self, cr, uid, object_name, old_instance_id, new_instance_id, context=None):
        object_ids = self.pool.get(object_name).search(cr,
                                                       uid,
                                                       [('instance_id', '=', old_instance_id)],
                                                       context=context)
        self.pool.get(object_name).write(cr,
                                         uid,
                                         object_ids,
                                         {'instance_id': new_instance_id},
                                         context=context)
        return

    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        Erase some unused data copied from the original object, which sometime could become dangerous, as in UF-1631/1632, 
        when duplicating a new partner (by button duplicate), or company, it creates duplicated currencies
        '''
        if default is None:
            default = {}
        if context is None:
            context = {}
        fields_to_reset = ['currency_ids'] # reset this value, otherwise the content of the field triggers the creation of a new company
        to_del = []
        for ftr in fields_to_reset:
            if ftr not in default:
                to_del.append(ftr)
        res = super(res_company, self).copy_data(cr, uid, id, default=default, context=context)
        for ftd in to_del:
            if ftd in res:
                del(res[ftd])
        return res

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if isinstance(ids, int):
            ids = [ids]

        instance_obj = self.pool.get('msf.instance')
        data_obj = self.pool.get('ir.model.data')
        menu_obj = self.pool.get('ir.ui.menu')
        check_menu = False
        if 'instance_id' in vals:
            # only one company (unicity)
            if len(ids) != 1:
                raise osv.except_osv(_('Error'), _("Only one company per instance!") or '')
            company = self.browse(cr, uid, ids[0], context=context)
            instance_data = {
                'instance': cr.dbname,
                'state': 'active',
                'instance_identifier': self.pool.get("sync.client.entity").get_entity(cr, uid, context=context).identifier,
            }
            if not company.instance_id:
                # An instance was not set; add DB name and activate it
                instance_obj.write(cr, uid, [vals['instance_id']], instance_data, context=context)
                check_menu = True
            elif company.instance_id.id != vals.get('instance_id'):
                check_menu = True
                # An instance was already set
                old_instance_id = company.instance_id.id
                # Deactivate the instance
                instance_obj.write(cr, uid, [old_instance_id], {'state': 'inactive', 'instance_identifier': False}, context=context)
                # add DB name and activate it
                instance_obj.write(cr, uid, [vals['instance_id']], instance_data, context=context)
                # refresh all objects
                for object in ['account.analytic.journal', 'account.journal', 'account.analytic.line', 'account.move', 'account.move.line', 'account.bank.statement']:
                    self._refresh_objects(cr, uid, object, old_instance_id, vals['instance_id'], context=context)

        ret = super(res_company, self).write(cr, uid, ids, vals, context=context)
        if check_menu:
            level = self._get_instance_level(cr, uid)
            oc = self._get_instance_oc(cr, uid)
            # Hide Stock & Pipe per Product and per Instance Report in Coordo and Project
            stock_pipe_report_menu_id = data_obj.get_object_reference(cr, uid, 'msf_tools', 'stock_pipe_per_product_instance_menu')[1]
            menu_obj.write(cr, uid, stock_pipe_report_menu_id, {'active': level == 'section'}, context=context)
            # Hide Product Status Inconsistencies in Project
            report_prod_inconsistencies_menu_id = data_obj.get_object_reference(cr, uid, 'product_attributes', 'export_report_inconsistencies_menu')[1]
            menu_obj.write(cr, uid, report_prod_inconsistencies_menu_id, {'active': level != 'project'}, context=context)
            # Hide Consolidated Mission Stock Report in HQ and Project
            consolidated_sm_report_menu_id = data_obj.get_object_reference(cr, uid, 'mission_stock', 'consolidated_mission_stock_wizard_menu')[1]
            menu_obj.write(cr, uid, consolidated_sm_report_menu_id, {'active': level == 'coordo'}, context=context)
            # Hide Import/Update Products in Project
            import_prod_menu_id = data_obj.get_object_reference(cr, uid, 'import_data', 'menu_action_import_products')[1]
            update_prod_menu_id = data_obj.get_object_reference(cr, uid, 'import_data', 'menu_action_update_products')[1]
            menu_obj.write(cr, uid, [import_prod_menu_id, update_prod_menu_id], {'active': level != 'project'}, context=context)
            # Hide Generate Asset Entries and Import Asset Entries in Project
            generate_asset_menu_id = data_obj.get_object_reference(cr, uid, 'product_asset', 'menu_product_asset_generate_entries')[1]
            import_asset_menu_id = data_obj.get_object_reference(cr, uid, 'product_asset', 'menu_product_asset_import_entries')[1]
            menu_obj.write(cr, uid, [generate_asset_menu_id, import_asset_menu_id], {'active': level != 'project'}, context=context)
        return ret

    def _get_instance_oc(self, cr, uid):
        entity_obj = self.pool.get('sync.client.entity')
        if not entity_obj:
            return False
        ids = entity_obj.search(cr, 1, [])
        if ids:
            return entity_obj.browse(cr, 1, ids[0], fields_to_fetch=['oc']).oc
        return False

    def _get_instance_level(self, cr, uid):
        instance = self._get_instance_record(cr, uid)
        return instance and instance.level or False

    def _get_instance_id(self, cr, uid):
        instance = self._get_instance_record(cr, uid)
        return instance and instance.id or False

    def _get_instance_record(self, cr, uid):
        user = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id'])
        return user and user.company_id and user.company_id.instance_id or False


res_company()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
