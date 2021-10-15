# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2019 TeMPO Consulting, MSF
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


class customer_commitment_setup(osv.osv_memory):
    _name = 'customer.commitment.setup'
    _inherit = 'res.config'

    _columns = {
        'customer_commitment': fields.boolean(string='Does the system allow Customer Commitment Vouchers ?'),
        'has_customer_commitment': fields.boolean('CCV already create'),
    }

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        """
        """
        if context is None:
            context = {}
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        res = super(customer_commitment_setup, self).default_get(cr, uid, fields, context=context, from_web=from_web)
        res['has_customer_commitment'] = self.pool.get('account.commitment').search_exists(cr, uid, [('state', '!=', 'done'), ('cv_flow_type', '=', 'customer')], context=context)
        res['customer_commitment'] = setup.customer_commitment
        return res

    def execute(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if not isinstance(ids, list) or len(ids) != 1:
            raise osv.except_osv(_('Error'), _('An error has occurred with the item retrieved from the form. Please contact an administrator if the problem persists.'))
        payload = self.browse(cr, uid, ids[0], fields_to_fetch=['customer_commitment'], context=context)
        setup_obj = self.pool.get('unifield.setup.configuration')
        cv_obj = self.pool.get('account.commitment')
        setup = setup_obj.get_config(cr, uid)
        if setup:
            menu_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'menu_account_commitment_from_fo')[1]
            self.pool.get('ir.ui.menu').write(cr, uid, menu_id, {'active': payload.customer_commitment}, context=context)
            if not payload.customer_commitment:
                set_as_done_ids = cv_obj.search(cr, uid, [('state', '!=', 'done'), ('cv_flow_type', '=', 'customer')], context=context)
                if set_as_done_ids:
                    cv_obj.action_commitment_done(cr, uid, set_as_done_ids, context=context)
            setup_obj.write(cr, uid, [setup.id], {'customer_commitment': payload.customer_commitment}, context=context)


customer_commitment_setup()
