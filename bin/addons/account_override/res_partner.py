#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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
from account_override import ACCOUNT_RESTRICTED_AREA
import tools


class res_partner(osv.osv):
    _name = 'res.partner'
    _inherit = 'res.partner'

    _columns = {
        'donation_payable_account': fields.many2one('account.account', "Donation Payable Account",
                                                    domain=ACCOUNT_RESTRICTED_AREA['partner_donation']),
    }

    def _is_linked_to_any_posted_accounting_entry(self, cr, uid, partner_id,
                                                  context=None):
        res = False
        sql = "select ml.id from account_move_line ml" \
            " left join account_move m on m.id=ml.move_id" \
            " where m.state='posted' and ml.partner_id=%s limit 1"

        cr.execute(sql, (partner_id,))
        res = cr.fetchone()
        return res and res[0] > 0 or False

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if 'name' in vals:
            current_name_recs = self.read(cr, uid, ids, ['name'],
                                          context=context)
            new_name = vals.get('name', False)
            for r in current_name_recs:
                #US-1350: convert both into the same format before comparing them
                if tools.ustr(new_name) != tools.ustr(r['name']):
                    # check if partner is linked to a posted entry
                    # if the case forbid its name modification
                    if self._is_linked_to_any_posted_accounting_entry(cr, uid,
                                                                      r['id'], context=context):
                        raise osv.except_osv(_('Error'),
                                             _('You can not rename a partner linked to posted' \
                                               ' accounting entries'))

        return super(res_partner, self).write(cr, uid, ids, vals,
                                              context=context)


res_partner()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
