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


class wizard_account_end_year_closing(osv.osv_memory):
    _name="wizard.account.end.year.closing"

    _columns = {
        'fy_id': fields.many2one('account.fiscalyear', "Fiscal Year", required=True, domain=[('state', '=', 'draft')]),
        'has_move_regular_bs_to_0': fields.boolean("Move regular B/S account to 0"),
        'has_book_pl_results': fields.boolean("Book the P&L results"),
    }

    _defaults = {
        'has_move_regular_bs_to_0': False,
        'has_book_pl_results': False,
    }

    def _check_before_process(self, cr, uid, ids, context=None):
        level = self.pool.get('res.users').browse(cr, uid, [uid], context=context)[0].company_id.instance_id.level
        if level not in ('section', 'coordo', ):
            raise osv.except_osv(_('Warning'), _('You can only close FY at HQ or Coordo'))

        if ids:
            rec = self.browse(cr, uid, ids, context=context)[0]
            if fy_id.state != 'draft':
                raise osv.except_osv(_('Warning'), _('You can only close an opened FY'))

    def default_get(self, cr, uid, vals, context=None):
        self._check_before_process(cr, uid, False, context=context)
        super(wizard_account_end_year_closing, self).default_get(cr, uid, vals, context=context)

    def btn_close_fy(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        self._check_before_process(cr, uid, ids, context=context)

wizard_account_end_year_closing()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
