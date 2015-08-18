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

# account_period_state is on account_mcdb because it's depend to msf.instance
# and account.period.


class account_period_state(osv.osv):
    _name = "account.period.state"

    _columns = {
        'period_id': fields.many2one('account.period', 'Period'),
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
        'state': fields.char('State', size=64, required=True),
    }

    def get_period(self, cr, uid, ids, context=None):
        mod_obj = self.pool.get('ir.model.data')
        view_id = mod_obj.get_object_reference(cr, uid, 'account_mcdb',
                                               'account_period_state_view')
        view_id = view_id and view_id[1] or False

        view = {
            'name': _('Period states'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.period.state',
            'view_type': 'form',
            'view_mode': 'tree',
            'view_id': [view_id],
            'context': {},
            'domain': [('period_id', 'in', context['active_ids'])],
            'target': 'crush',
        }

        return view

    def update_state(self, cr, uid, period_ids, context=None):
        if isinstance(period_ids, (int, long)):
            period_ids = [period_ids]

        for period_id in period_ids:
            user = self.pool.get('res.users').browse(cr, uid, uid,
                                                     context=context)
            parent = user.company_id.instance_id.id
            period = self.pool.get('account.period').read(cr, uid, period_id,
                                                          ['id', 'state'],
                                                          context=context)
            if parent and period:
                args = [
                    ('instance_id', '=', parent),
                    ('period_id', '=', period['id'])
                ]
                ids = self.search(cr, uid, args, context=context)
                if ids:
                    vals = {
                        'state': period['state']
                    }
                    self.write(cr, uid, ids, vals, context=context)
                else:
                    vals = {
                        'period_id': period['id'],
                        'instance_id': parent,
                        'state': period['state']}
                    self.create(cr, uid, vals, context=context)
        return True
account_period_state()
