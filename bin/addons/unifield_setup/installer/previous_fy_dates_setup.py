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


class previous_fy_dates_setup(osv.osv_memory):
    _name = 'previous.fy.dates.setup'
    _inherit = 'res.config'
    
    _columns = {
        'previous_fy_dates_allowed': fields.boolean(string='Does the system allow document dates on previous Fiscal Year?'),
    }
    
    def default_get(self, cr, uid, fields, context=None):
        """
        Display the default/current value regarding the allowing of previous FY dates
        """
        if context is None:
            context = {}
        setup_id = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        res = super(previous_fy_dates_setup, self).default_get(cr, uid, fields, context=context)
        res['previous_fy_dates_allowed'] = setup_id.previous_fy_dates_allowed
        return res

    def execute(self, cr, uid, ids, context=None):
        """
        Fills in the previous_fy_dates_allowed field and activate/de-activate the allowing of Doc dates booked in previous FY
        """
        if context is None:
            context = {}
        if not isinstance(ids, list) or len(ids) != 1:
            raise osv.except_osv(_('Error'), _('An error has occurred with the item retrieved from the form. Please contact an administrator if the problem persists.'))
        payload = self.browse(cr, uid, ids[0], fields_to_fetch=['previous_fy_dates_allowed'], context=context)
        setup_obj = self.pool.get('unifield.setup.configuration')
        setup_id = setup_obj.get_config(cr, uid)
        setup_obj.write(cr, uid, [setup_id.id], {'previous_fy_dates_allowed': payload.previous_fy_dates_allowed}, context=context)


previous_fy_dates_setup()
