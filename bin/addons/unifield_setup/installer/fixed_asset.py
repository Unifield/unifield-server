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


class fixed_asset_setup(osv.osv_memory):
    _name = 'fixed.asset.setup'
    _inherit = 'res.config'

    def _is_assets_inactivable(self, cr, uid, context=None):
        if context is None:
            context = {}
        pa_obj = self.pool.get('product.asset')
        al_obj = self.pool.get('product.asset.line')
        uf_config = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        asset_activated = uf_config.fixed_asset_ok
        if asset_activated:
            if pa_obj.search_exist(cr, uid, [('state', 'not in', ('done', 'cancel'))], context=context):
                return False
            if al_obj.search_exist(cr, uid, [('move_state', '=', 'draft')], context=context):
                return False
        return True

    def _get_is_inactivable(self, cr, uid, ids, field_name, arg, context=None):
        """
        return False if at least one Asset Form is not in done or cancel state or at least one asset entry is draft, return True otherwise.
        """
        if not ids:
            return {}
        res = {}
        if context is None:
            context = {}
        is_inactivable = self._is_assets_inactivable(cr, uid, context=context)
        for _id in ids:
            res[_id] = is_inactivable
        return res

    def onchange_asset(self, cr, uid, ids, fixed_asset_ok=False):
        '''
        We need the authorization of inactivation only when the assets are activated.
        '''
        if not fixed_asset_ok:
            return {'value': {'is_inactivable': True}}
        elif fixed_asset_ok:
            return {'value': {'is_inactivable': self._is_assets_inactivable(cr, uid)}}

    _columns = {
        'fixed_asset_ok': fields.boolean(string='Does the system manage Fixed assets ?'),
        'is_inactivable': fields.function(_get_is_inactivable, method=True, type='boolean', string='Are Fixed Assets inactivable now?', store=False, readonly=True),
    }

    _defaults = {
        'is_inactivable': True,
    }

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        '''
        Display the default value for fixed asset and
        update the value of is_inactivable.
        '''
        setup_id = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        res = super(fixed_asset_setup, self).default_get(cr, uid, fields, context=context, from_web=from_web)

        res['fixed_asset_ok'] = setup_id.fixed_asset_ok
        res['is_inactivable'] = not setup_id.fixed_asset_ok or self._is_assets_inactivable(cr, uid, context=context)
        return res

    def execute(self, cr, uid, ids, context=None):
        '''
        Fill the fixed_asset_ok field and active/de-activate the feature
        '''
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)

        setup_obj = self.pool.get('unifield.setup.configuration')
        setup_id = setup_obj.get_config(cr, uid)
        menu_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_asset', 'menu_asset_sales')[1]
        asset_menu_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_asset', 'asset_configuration')[1]
        if menu_id:
            self.pool.get('ir.ui.menu').write(cr, uid, menu_id, {'active': payload.fixed_asset_ok}, context=context)
        if asset_menu_id:
            self.pool.get('ir.ui.menu').write(cr, uid, asset_menu_id, {'active': payload.fixed_asset_ok}, context=context)
        setup_obj.write(cr, uid, [setup_id.id], {'fixed_asset_ok': payload.fixed_asset_ok}, context=context)
        if payload.fixed_asset_ok and self.pool.get('res.company')._get_instance_id(cr, uid):
            journal_obj = self.pool.get('account.journal')
            if not journal_obj.search_exist(cr, uid,
                                            [('code', '=', 'DEP'), ('type', '=', 'depreciation'),('is_current_instance', '=', True)], context=context):
                ana_dep_journal_id = self.pool.get('account.analytic.journal').search(cr, uid,
                                                                                      [('code', '=', 'DEP'), ('type', '=', 'depreciation'), ('is_current_instance', '=', True)],
                                                                                      context=context)
                if ana_dep_journal_id:
                    journal_obj.create(cr, 1, {
                        'code': 'DEP',
                        'name': 'Depreciation',
                        'type': 'depreciation',
                        'analytic_journal_id': ana_dep_journal_id[0]
                    }, context=context)


fixed_asset_setup()
