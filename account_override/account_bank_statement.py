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

    def _get_partner_id_from_vals(self, cr, uid, vals, context=None):
        """
        Search for partner_id in given vals
        """
        # Prepare some values
        res = False
        # Do some checks
        if not vals:
            return res
        if not context:
            context = {}
        if vals.get('partner_id', False):
            res = vals.get('partner_id')
        elif vals.get('partner_type', False):
            p_type = vals.get('partner_type').split(',')
            if p_type[0] == 'res.partner' and p_type[1]:
                if isinstance(p_type[1], str):
                    p_type[1] = int(p_type[1])
                res = p_type[1]
        return res

    def create(self, cr, uid, vals, context=None):
        """
        UTP-317: Check if partner is inactive or not. If inactive, raise an execption to the user.
        """
        # Some verification
        if not context:
            context = {}
        partner_id = self._get_partner_id_from_vals(cr, uid, vals, context)
        if partner_id:
            partner = self.pool.get('res.partner').browse(cr, uid, [partner_id])
            if partner and partner[0] and not partner[0].active:
                raise osv.except_osv(_('Warning'), _("Partner '%s' is not active.") % (partner[0] and partner[0].name or '',))
        return super(account_bank_statement_line, self).create(cr, uid, vals, context)

    _columns = {
        'ref': fields.char('Reference', size=50), # UF-1613 - add reference field from 32 to 50 chars
    }

account_bank_statement_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
