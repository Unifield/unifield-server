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


class vat_setup(osv.osv_memory):
    _name = 'vat.setup'
    _inherit = 'res.config'

    _columns = {
        'vat_ok': fields.boolean(string='Do you manage VAT locally ?'),
    }

    def default_get(self, cr, uid, fields, context=None):
        '''
        Display the default value for delivery process
        '''
        setup_id = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        res = super(vat_setup, self).default_get(cr, uid, fields, context=context)
        res['vat_ok'] = setup_id.vat_ok

        return res


    def execute(self, cr, uid, ids, context=None):
        '''
        Fill the vats_ok field and active/de-activate menu entries
        '''
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)

        setup_obj = self.pool.get('unifield.setup.configuration')
        data_obj = self.pool.get('ir.model.data')

        setup_id = setup_obj.get_config(cr, uid)

        # Get all menu ids concerned by this modification
        taxes_menu_id = data_obj.get_object_reference(cr, uid, 'account', 'next_id_27')[1]

        menu_ids = [taxes_menu_id]

        if payload.vat_ok:
            # If the feature is not activate, inactive the menu entries
            self.pool.get('ir.ui.menu').write(cr, uid, menu_ids, {'active': True}, context=context)
        else:
            self.pool.get('ir.ui.menu').write(cr, uid, menu_ids, {'active': False}, context=context)

        setup_obj.write(cr, uid, [setup_id.id], {'vat_ok': payload.vat_ok}, context=context)


vat_setup()
