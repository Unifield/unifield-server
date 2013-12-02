#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013 TeMPO Consulting, MSF. All Rights Reserved
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

class account_account(osv.osv):
    _name = 'account.account'
    _inherit = 'account.account'

    def _get_is_intermission_counterpart(self, cr, uid, ids, field_names, args, context=None):
        """
        If this account is the same as default intermission counterpart, then return True. Otherwise return nothing.
        """
        if context is None:
            context = {}
        res = {}
        for account in self.browse(cr, uid, ids):
            res[account.id] = False
            intermission = self.pool.get('res.users').browse(cr, uid, uid).company_id.intermission_default_counterpart
            intermission_id = intermission and intermission.id or False
            if account.id == intermission_id:
                res[account.id] = True
        return res

    def _search_is_intermission_counterpart(self, cr, uid, ids, field_names, args, context=None):
        """
        Return the intermission counterpart ID.
        """
        if context is None:
            context = {}
        arg = []
        for x in args:
            if x[0] == 'is_intermission_counterpart' and x[2] is True:
                intermission = self.pool.get('res.users').browse(cr, uid, uid).company_id.intermission_default_counterpart
                intermission_id = intermission and intermission.id or False
                if intermission_id:
                  arg.append(('id', '=', intermission_id))
        return arg

    _columns = {
        'is_intermission_counterpart': fields.function(_get_is_intermission_counterpart, method=True, type='boolean', string='Is the intermission counterpart account?')
    }

account_account()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
