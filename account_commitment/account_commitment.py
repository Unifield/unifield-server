#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
from time import strftime

class account_commitment(osv.osv):
    _name = 'account.commitment'
    _description = "Account Commitment"
    _order = "id desc"

    _columns = {
        'name': fields.char(string="Number", size=64),
        'state': fields.selection([('draft', 'Draft'), ('open', 'Open'), ('done', 'Closed'), ('cancel', 'Cancel')]),
        'date': fields.date(string="Commitment Date", readonly=True, required=True, states={'draft': [('readonly', False)], 'open': [('readonly', False)]}),
        'line_ids': fields.one2many('account.commitment.line', 'commit_id', string="Commitment Items"),
    }

    _defaults = {
        'name': '/',
        'state': lambda *a: 'draft',
        'date': lambda *a: strftime('%Y-%m-%d'),
    }

account_commitment()

class account_commitment_line(osv.osv):
    _name = 'account.commitment.line'
    _description = "Account Commitment Line"
    _order = "id desc"

    _columns = {
        'account_id': fields.many2one('account.account', string="Account"),
        'commit_id': fields.many2one('account.commitment', string="Commitment Entry"),
    }

account_commitment_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
