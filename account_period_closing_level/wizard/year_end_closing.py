# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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

from osv import fields, osv
from tools.translate import _


class wizard_account_year_end_closing(osv.osv_memory):
    _name="wizard.account.year.end.closing"

    _columns = {
        'fy_id': fields.many2one('account.fiscalyear', "Fiscal Year",
            required=True, domain=[('state', '=', 'draft')]),
        'has_move_regular_bs_to_0': fields.boolean(
                "Move regular B/S account to 0"),
        'has_book_pl_results': fields.boolean("Book the P&L results"),
    }

    _defaults = {
        'has_move_regular_bs_to_0': False,
        'has_book_pl_results': False,
    }


    def default_get(self, cr, uid, vals, context=None):
        fy_id = context and context.get('fy_id', False) or False
        self.pool.get('account.year.end.closing').check_before_closing_process(
            cr, uid, fy_id=fy_id, context=context)
        res = super(wizard_account_year_end_closing, self).default_get(cr, uid,
            vals, context=context)
        res['fy_id'] = fy_id
        return res

    def btn_close_fy(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        rec = self.browse(cr, uid, ids[0], context=context)
        self.pool.get('account.year.end.closing').check_before_closing_process(
            cr, uid, fy_id=rec.fy_id, context=context)
        return {}

wizard_account_year_end_closing()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
