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
from account_period_closing_level import ACCOUNT_PERIOD_STATE_SELECTION

# account_period_state is on account_mcdb because it's depend to msf.instance
# and account.period.


class account_period_state(osv.osv):
    _name = "account.period.state"

    _columns = {
        'period_id': fields.many2one('account.period', 'Period', required=1, ondelete='cascade'),
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
        'state': fields.selection(ACCOUNT_PERIOD_STATE_SELECTION, 'State',
                                  readonly=True),
    }

    def get_period(self, cr, uid, ids, context=None):
        mod_obj = self.pool.get('ir.model.data')
        view_id = mod_obj.get_object_reference(cr, uid, 'account_mcdb',
                                               'account_period_state_view')
        view_id = view_id and view_id[1] or False

        search_id = mod_obj.get_object_reference(cr, uid, 'account_mcdb',
                                                 'account_period_state_filter')
        search_id = search_id and search_id[1] or False

        view = {
            'name': _('Period states'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.period.state',
            'view_type': 'form',
            'view_mode': 'tree',
            'search_view_id': search_id,
            'view_id': [view_id],
            'context': context,
            'domain': [],
            'target': 'current',
        }

        return view

    def update_state(self, cr, uid, period_ids, context=None):
        if isinstance(period_ids, (int, long)):
            period_ids = [period_ids]

        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        model_data = self.pool.get('ir.model.data')
        period_state = self.pool.get('account.period.state')
        parent = user.company_id.instance_id.id
        ids_to_write = []
        for period_id in period_ids:
            period = self.pool.get('account.period').read(cr, uid, period_id,
                                                          ['id', 'state'],
                                                          context=context)
            if parent and period and parent != '':
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
                    for period_state_id in ids:
                        period_state_xml_id = period_state.get_sd_ref(cr, uid, period_state_id)
                        ids_to_write.append(model_data._get_id(cr, uid, 'sd',
                            period_state_xml_id))

                else:
                    vals = {
                        'period_id': period['id'],
                        'instance_id': parent,
                        'state': period['state']}
                    self.create(cr, uid, vals, context=context)

        # US-649 : in context of synchro last_modification date must be updated
        # on account.period.state because they are created with synchro and
        # they need to be sync down to other instances
        if ids_to_write:
            model_data.write(cr, uid, ids_to_write, {'last_modification':fields.datetime.now()})

        return True
account_period_state()
