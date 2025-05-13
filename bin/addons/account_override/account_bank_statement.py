#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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

class account_bank_statement(osv.osv):
    _name = 'account.bank.statement'
    _inherit = 'account.bank.statement'

    _columns = {
        'prev_reg_id': fields.many2one('account.bank.statement', string="Previous register", required=False, readonly=True,
                                       help="This fields give the previous register from which this one is linked."),
        'next_reg_id': fields.one2many('account.bank.statement', 'prev_reg_id', string="Next register", readonly=True,
                                       help="This fields give the next register if exists."),
    }

account_bank_statement()

class account_bank_statement_line(osv.osv):
    _name = 'account.bank.statement.line'
    _inherit = 'account.bank.statement.line'

    def create(self, cr, uid, vals, context=None):
        """
        UTP-317: Check if partner is inactive or not. If inactive, raise an execption to the user.
        """
        # Some verification
        if not context:
            context = {}
        res = super(account_bank_statement_line, self).create(cr, uid, vals, context)
        # UTP-317: Check partner (if active or not)
        if res:
            absl = self.browse(cr, uid, [res], context)
            # UF-2300: for the case of sync, the line can also be created if the partner is inactive
            if not context.get('sync_update_execution', False) and absl and absl[0]:
                if absl[0].partner_id and not absl[0].partner_id.active:
                    raise osv.except_osv(_('Warning'), _("Partner '%s' is not active.") % (absl[0].partner_id.name or '',))
                # US-13963 Check also for inactive employees tagged as not to be used
                if absl[0].employee_id and absl[0].employee_id.not_to_be_used:
                    raise osv.except_osv(_('Warning'), _("Employee '%s' can not be used anymore.") % (absl[0].employee_id.name_resource or '',))
            self._check_on_regline_big_amounts(cr, uid, res, context=context)
        return res

    _columns = {
        'ref': fields.char('Reference', size=50), # UF-1613 - add reference field from 32 to 50 chars
        'invoice_id': fields.many2one('account.invoice', "Invoice", required=False),
        # NOTE: partner_move_ids is used for old entries until US-3874. Since then, entries use partner_move_line_ids.
        'partner_move_ids': fields.one2many('account.move', 'register_line_id', 'Payable Entries', readonly=True, required=False),
        'partner_move_line_ids': fields.one2many('account.move.line', 'partner_register_line_id', 'Automated Entries',
                                                 readonly=True, required=False,
                                                 help="Automated entries generated for expense/income register lines linked to a partner"),
    }

account_bank_statement_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
