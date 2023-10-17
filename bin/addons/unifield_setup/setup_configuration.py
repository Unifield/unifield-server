# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO consulting, MSF
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


# Class to save all configuration value
class unifield_setup_configuration(osv.osv):
    _name = 'unifield.setup.configuration'

    def _check_uniqueness(self, cr, uid, ids, context=None):
        '''
        Limit the creation of one and only one instance configuration
        '''
        setup_ids = self.pool.get('unifield.setup.configuration').search(cr, uid, [], context=context)
        if len(setup_ids) > 1:
            return False

        return True

    def _non_uniqueness_msg(self, cr, uid, ids, context=None):
        return _('An instance of Unifield setup is already running.')

    _columns = {
        'name': fields.char(size=64, string='Name'),
        'delivery_process': fields.selection([('simple', 'Simple OUT'), ('complex', 'PICK/PACK/SHIP')], string='Delivery process'),
        'allocation_setup': fields.selection([('allocated', 'Allocated'),
                                              ('unallocated', 'Unallocated'),
                                              ('mixed', 'Mixed')], string='Allocated stocks'),
        'unallocated_ok': fields.boolean(string='System uses the unallocated stocks ?'),
        'fixed_asset_ok': fields.boolean(string='System manages fixed asset ?'),
        'sale_price': fields.float(digits=(16,2), string='Fields price percentage',
                                   help='This percentage will be applied on field price from product form view.'),
        'restrict_country_ids': fields.many2many('res.country', 'restrictive_countries', 'wizard_id', 'country_id',
                                                 string='Restrictive countries'),
        'field_orders_ok': fields.boolean(string='Activate the Field Orders feature ?'),
        'lang_id': fields.char(size=5, string='Default language'),
        'payroll_ok': fields.boolean(string='System manages payrolls ?'),
        'import_commitments': fields.boolean(string='Manage commitments corresponding to international order through specific import ?'),
        'vat_ok': fields.boolean(string='System manages VAT locally ?'),
        'previous_fy_dates_allowed': fields.boolean(string='Does the system allow document dates on previous Fiscal Year?'),
        'customer_commitment': fields.boolean(string='Does the system allow Customer Commitment Vouchers ?'),
        'signature': fields.boolean(string='Activate Electronic Validation ?'),
        'esc_line': fields.boolean(string='Activate International Invoices Lines ?'),
    }

    _defaults = {
        'name': lambda *a: 'Unifield setup',
        'delivery_process': lambda *a: 'complex',
        'allocation_setup': lambda *a: 'mixed',
        'sale_price': lambda *a: 0.00,
        'field_orders_ok': lambda *a: True,
        'lang_id': lambda *a: 'en_MF',
        'unallocated_ok': lambda *a: False,
        'fixed_asset_ok': lambda *a: False,
        'payroll_ok': lambda *a: True,
        'import_commitments': lambda *a: True,
        'vat_ok': lambda *a: True,
        'previous_fy_dates_allowed': lambda *a: False,
        'customer_commitment': False,
        'signature': False,
        'esc_line': False,
    }

    _constraints = [
        (_check_uniqueness, _non_uniqueness_msg, ['id'])
    ]

    def get_config(self, cr, uid, key=None):
        '''
        Return the current config or create a new one
        '''
        setup_ids = self.search(cr, uid, [])
        if not setup_ids:
            setup_id = self.create(cr, uid, {})
        else:
            setup_id = setup_ids[0]

        if not setup_id:
            raise osv.except_osv(_('Error'), _('No configuration found !'))

        if key:
            return self.browse(cr, uid, setup_id, fields_to_fetch=[key])[key]

        return self.browse(cr, uid, setup_id)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        On write,  update the list_price = Field Price of Product according to the sale_price of the configurator
        '''
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        if vals.get('sale_price', 0.0) or vals.get('sale_price') == 0.0:
            percentage = vals.get('sale_price', 0.0)
            cr.execute("UPDATE product_template SET list_price = standard_price * %s", ((1 + (percentage/100.00)),))
        return super(unifield_setup_configuration, self).write(cr, uid, ids, vals, context=context)


unifield_setup_configuration()

class res_config_view(osv.osv_memory):
    _name = 'res.config.view'
    _inherit = 'res.config.view'

    _defaults={
        'view': 'extended',
    }

res_config_view()

class res_config(osv.osv_memory):
    _inherit = 'res.config'

    def _next(self, cr, uid, context=None):
        res = super(res_config, self)._next(cr, uid, context=context)
        if isinstance(res, dict) and res.get('res_model') == 'restrictive.country.setup' and not res.get('res_id'):
            wiz_id = self.pool.get('restrictive.country.setup').create(cr, uid, {}, context=context)
            res['res_id'] = wiz_id
            res['active_id'] = wiz_id
        return res

res_config()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
