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
from account_period_closing_level import ACCOUNT_FY_STATE_SELECTION

# account_period_state is on account_mcdb because it's depend to msf.instance
# and account.period.


class account_period_state(osv.osv):
    _name = "account.period.state"
    _description = "Period States"

    _columns = {
        'period_id': fields.many2one('account.period', 'Period', required=1, ondelete='cascade', select=1),
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance', select=1),
        'state': fields.selection(ACCOUNT_PERIOD_STATE_SELECTION, 'State', readonly=True),
        'auto_export_vi': fields.boolean('Auto VI exported', select=1),
    }

    _defaults = {
        'auto_export_vi': True,
    }

    def clean_auto_export(self, cr, uid, vals, context=None):
        '''
        Set the account.period.state as ready for auto export if:
          1/ we are in a sync and
          2/ the state is mission-close and
          3/ auto export is enabled: we are on HQ OCA and the job is active
        '''
        if context is None:
            context = {}
        if context.get('sync_update_execution') and vals and vals.get('state') == 'mission-closed' and 'auto_export_vi' not in vals and self.pool.get('wizard.hq.report.oca').get_active_export_ids(cr, uid, context=context):
            vals['auto_export_vi'] = False

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if context.get('sync_update_execution') and not vals.get('period_id'):
            # US-841: period is required but we got
            # an update related to non existant period: ignore it
            return False
        self.clean_auto_export(cr, uid, vals, context)
        return super(account_period_state, self).create(cr, uid, vals, context=context)


    def write(self, cr, uid, ids, vals, context=None):
        self.clean_auto_export(cr, uid, vals, context)
        return super(account_period_state, self).write(cr, uid, ids, vals, context=context)

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
            'view_mode': 'tree,form',
            'search_view_id': search_id,
            'view_id': [view_id],
            'context': context,
            'domain': [],
            'target': 'current',
        }

        return view

    def update_state(self, cr, uid, period_ids, context=None):
        if isinstance(period_ids, int):
            period_ids = [period_ids]

        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        model_data = self.pool.get('ir.model.data')
        period_obj = self.pool.get('account.period')
        parent = user.company_id.instance_id.id
        if not parent:
            return True
        ids_to_write = []
        for period in period_obj.read(cr, uid, period_ids, ['id', 'state'], context=context):
            args = [
                ('instance_id', '=', parent),
                ('period_id', '=', period['id'])
            ]
            ids = self.search(cr, uid, args, context=context)
            if ids:
                vals = {
                    'state': period['state']
                }
                if self.search_exists(cr, uid, [('id', 'in', ids), ('state', '!=', period['state'])], context=context):
                    self.write(cr, uid, ids, vals, context=context)
                    for period_state_id in ids:
                        period_state_xml_id = self.get_sd_ref(cr, uid, period_state_id)
                        ids_to_write.append(model_data._get_id(cr, uid, 'sd',
                                                               period_state_xml_id))

            else:
                vals = {
                    'period_id': period['id'],
                    'instance_id': parent,
                    'state': period['state']}
                new_period_state_id = self.create(cr, uid, vals, context=context)
                new_period_state_xml_id = self.get_sd_ref(cr, uid,
                                                          new_period_state_id)
                ids_to_write.append(model_data._get_id(cr, uid, 'sd',
                                                       new_period_state_xml_id))

        # US-649 : in context of synchro last_modification date must be updated
        # on account.period.state because they are created with synchro and
        # they need to be sync down to other instances
        if ids_to_write:
            model_data.write(cr, uid, ids_to_write,
                             {'last_modification': fields.datetime.now(), 'touched': "['state']"})
        return True

account_period_state()


class account_fiscalyear_state(osv.osv):
    # model since US-822
    _name = "account.fiscalyear.state"
    _description = "Fiscal Year States"

    _columns = {
        'fy_id': fields.many2one('account.fiscalyear', 'Fiscal Year',
                                 required=True, ondelete='cascade', select=1),
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance', select=1),
        'state': fields.selection(ACCOUNT_FY_STATE_SELECTION, 'State',
                                  readonly=True),
    }

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if context.get('sync_update_execution') and not vals.get('fy_id'):
            # US-841: period is required but we got
            # an update related to non existant period: ignore it
            return False

        return super(account_fiscalyear_state, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        When the "FY HQ-closure" update is received via sync in coordo: if during FY mission-closure "Balance move to 0" lines
        had been generated, the system will reconcile each of these lines together with the lines there have balanced
        """
        if not ids:
            return True
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}
        aml_obj = self.pool.get('account.move.line')
        year_end_closing_obj = self.pool.get('account.year.end.closing')
        user_obj = self.pool.get('res.users')
        journal_code = 'EOY'
        period_number = 16
        company_instance = user_obj.browse(cr, uid, [uid], fields_to_fetch=['company_id'], context=context)[0].company_id.instance_id
        instance_ids = year_end_closing_obj._get_mission_ids_from_coordo(cr, uid, company_instance.id, context=context)
        if context.get('sync_update_execution', False) and vals.get('state', False) == 'done' and company_instance.level == 'coordo':
            sql = '''SELECT ml.id
                     FROM account_move_line ml
                     INNER JOIN account_move m ON m.id = ml.move_id
                     INNER JOIN account_period p ON ml.period_id = p.id
                     WHERE ml.instance_id in %s
                     AND ml.date >= %s AND ml.date <= %s AND m.period_id != %s
                     AND p.number != 0
                     AND ml.account_id = %s AND ml.currency_id = %s;
                  '''
            for fy_state_id in ids:
                fy_state = self.browse(cr, uid, fy_state_id, fields_to_fetch=['fy_id', 'instance_id'], context=context)
                if fy_state.instance_id.id != company_instance.id:
                    # trigger reconcile only if instance FY is closed, not when update is received from project
                    break
                fy = fy_state.fy_id
                period_id = year_end_closing_obj._get_period_id(cr, uid, fy.id, period_number, context=context)
                if not period_id:
                    raise osv.except_osv(_('Error'), _("FY 'Period %d' not found") % (period_number,))
                balance_line_domain = [('journal_id.code', '=', journal_code),
                                       ('period_id.number', '=', period_number),
                                       ('period_id.fiscalyear_id', '=', fy.id),
                                       ('account_id.include_in_yearly_move', '=', True)]
                balance_line_ids = aml_obj.search(cr, uid, balance_line_domain, context=context, order='NO_ORDER')
                # get the entries balanced by each "Balance move to 0" line
                for balance_line in aml_obj.browse(cr, uid, balance_line_ids,
                                                   fields_to_fetch=['account_id', 'currency_id'], context=context):
                    cr.execute(sql, (tuple(instance_ids), fy.date_start, fy.date_stop, period_id,
                                     balance_line.account_id.id,  balance_line.currency_id.id,))
                    aml_ids = [x[0] for x in cr.fetchall()]
                    aml_ids.append(balance_line.id)
                    # with 'fy_hq_closing' in context we don't check if the account is reconcilable
                    # (but the check that no entry is already reconciled is kept)
                    context['fy_hq_closing'] = True
                    aml_obj.reconcile(cr, uid, aml_ids, context=context)
        return super(account_fiscalyear_state, self).write(cr, uid, ids, vals, context=context)

    def get_fy(self, cr, uid, ids, context=None):
        mod_obj = self.pool.get('ir.model.data')
        view_id = mod_obj.get_object_reference(cr, uid, 'account_mcdb',
                                               'account_fiscalyear_state_view')
        view_id = view_id and view_id[1] or False

        search_id = mod_obj.get_object_reference(cr, uid, 'account_mcdb',
                                                 'account_fiscalyear_state_filter')
        search_id = search_id and search_id[1] or False

        view = {
            'name': _('Fiscal year states'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.fiscalyear.state',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'search_view_id': search_id,
            'view_id': [view_id],
            'context': context,
            'domain': [],
            'target': 'current',
        }

        return view

    def update_state(self, cr, uid, fy_ids, context=None):
        if isinstance(fy_ids, int):
            fy_ids = [fy_ids]

        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        model_data = self.pool.get('ir.model.data')
        fy_state_obj = self.pool.get('account.fiscalyear.state')
        parent = user.company_id.instance_id.id
        ids_to_write = []
        state_to_update = []
        for fy_id in fy_ids:
            user = self.pool.get('res.users').browse(cr, uid, uid,
                                                     context=context)
            parent = user.company_id.instance_id.id
            fy = self.pool.get('account.fiscalyear').read(cr, uid, fy_id,
                                                          ['id', 'state'], context=context)
            if parent and fy and parent != '':
                args = [
                    ('instance_id', '=', parent),
                    ('fy_id', '=', fy['id'])
                ]
                ids = self.search(cr, uid, args, context=context)
                if ids:
                    vals = {
                        'state': fy['state']
                    }
                    self.write(cr, uid, ids, vals, context=context)
                    state_to_update = ids[:]
                else:
                    vals = {
                        'fy_id': fy['id'],
                        'instance_id': parent,
                        'state': fy['state']
                    }
                    new_id = self.create(cr, uid, vals, context=context)
                    state_to_update.append(new_id)

        for fy_state_id in state_to_update:
            fy_state_xml_id = fy_state_obj.get_sd_ref(cr, uid, fy_state_id)
            ids_to_write.append(model_data._get_id(cr, uid, 'sd', fy_state_xml_id))

        # like for US-649 period state: in context of synchro last_modification
        # date must be updated on account.fisclayear.state because they are
        # created with synchro and they need to be sync down to other instances
        if ids_to_write:
            model_data.write(cr, uid, ids_to_write,
                             {'last_modification': fields.datetime.now(), 'touched': "['state']"})
        return True

account_fiscalyear_state()
