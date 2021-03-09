# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2021 MSF, TeMPO Consulting.
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

from osv import fields
from osv import osv


class multiple_cc_selection_wizard(osv.osv_memory):
    _name = 'multiple.cc.selection.wizard'

    _columns = {
        'dest_id': fields.many2one('account.analytic.account', string="Destination", required=True,
                                   domain="[('category', '=', 'DEST'), ('type', '!=', 'view')]"),
        'cc_ids': fields.many2many('account.analytic.account', 'multiple_cc_wiz_rel', 'wizard_id', 'cost_center_id',
                                   string="Cost Centers", domain="[('category', '=', 'OC'), ('type', '!=', 'view')]"),
    }

    def multiple_cc_add(self, cr, uid, ids, context=None):
        """
        Adds the Cost Centers selected in the wizard to the current destination
        without filling in the inactivation date of the related combinations.
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        dest_cc_link_obj = self.pool.get('dest.cc.link')
        wiz = self.browse(cr, uid, ids[0], context=context)
        for cc in wiz.cc_ids:
            dest_cc_link_obj.create(cr, uid, {'dest_id': wiz.dest_id.id, 'cc_id': cc.id}, context=context)
        return {'type': 'ir.actions.act_window_close'}


multiple_cc_selection_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
