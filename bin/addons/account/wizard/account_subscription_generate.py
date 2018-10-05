# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

import time

from osv import fields, osv
from tools.translate import _

class account_subscription_generate(osv.osv_memory):

    _name = "account.subscription.generate"
    _description = "Subscription Compute"
    _columns = {
       'date': fields.date('Date', required=True),
    }
    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d'),
    }
    def action_generate(self, cr, uid, ids, context=None):
        mod_obj = self.pool.get('ir.model.data')
        act_obj = self.pool.get('ir.actions.act_window')
        sub_line_obj = self.pool.get('account.subscription.line')
        account_obj = self.pool.get('account.account')
        moves_created=[]
        for data in  self.read(cr, uid, ids, context=context):
            cr.execute('select id from account_subscription_line where date<%s and move_id is null', (data['date'],))
            line_ids = map(lambda x: x[0], cr.fetchall())
            # check that the entry is valid before creating it
            for sub_line in sub_line_obj.browse(cr, uid, line_ids, context=context):
                acc_model = sub_line.subscription_id.model_id
                acc_model_lines = acc_model.lines_id or []
                if not acc_model_lines:
                    raise osv.except_osv(_('Warning'), _('The Recurring Model %s has no accounting lines!') % (acc_model.name))
                elif len(acc_model_lines) < 2:
                    raise osv.except_osv(_('Warning'), _('The Recurring Model %s must have at least two lines.') % (acc_model.name))
                else:
                    credit = 0.0
                    debit = 0.0
                    for line in acc_model_lines:
                        # Check account/Third Party compatibility
                        account_id = line.account_id.id
                        partner_id = line.partner_id and line.partner_id.id or False
                        account_obj.check_type_for_specific_treatment(cr, uid, [account_id], partner_id=partner_id, context=context)
                        account_obj.is_allowed_for_thirdparty(cr, uid, [account_id], partner_id=partner_id, raise_it=True, context=context)
                        credit += line.credit or 0.0
                        debit += line.debit or 0.0
                    if abs(debit - credit) > 10 ** -4:
                        raise osv.except_osv(_('Warning'), _('The entry is not balanced for the Recurring Model %s!') % (acc_model.name))
            moves = self.pool.get('account.subscription.line').move_create(cr, uid, line_ids, context=context)
            moves_created.extend(moves)
        result = mod_obj.get_object_reference(cr, uid, 'account', 'action_move_line_form')
        id = result and result[1] or False
        result = act_obj.read(cr, uid, [id], context=context)[0]
        result['domain'] = str([('id','in',moves_created)])
        return result

account_subscription_generate()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: