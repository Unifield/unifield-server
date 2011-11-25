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

def _get_addendum_line_account_id(self, cr, uid, ids, context={}):
    """
    Give addendum line account id.
    """
    # Some verifications
    if not context:
        context = {}
    if isinstance(ids, (int, long)):
        ids = [ids]
    # Retrieve 6308 account
    account_id = self.pool.get('account.account').search(cr, uid, [('code', '=', '6308')], context=context, limit=1)
    return account_id and account_id[0] or False

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
