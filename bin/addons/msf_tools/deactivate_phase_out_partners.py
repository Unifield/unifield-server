##############################################################################
# -*- coding: utf-8 -*-
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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
import time
import tools
from datetime import datetime

from tools.translate import _


class deactivate_phase_out_partners(osv.osv):
    _name = 'deactivate.phase.out.partners'
    _description = 'Deactivate Phase Out Partners'

    _columns = {
        'name': fields.char('Name', size=128),
        'start_time': fields.datetime(string='Force Date and time of next execution'),
        'interval': fields.integer(string='Interval number', required=True),
        'interval_unit': fields.selection(selection=[('work_days', 'Work Days'), ('days', 'Days'), ('weeks', 'Weeks'), ('months', 'Months')], string='Interval Unit', required=True),
        'active': fields.boolean(string='Active', readonly=True),
        'cron_id': fields.many2one('ir.cron', string='Associated cron job', readonly=True),
        'next_scheduled_task': fields.related('cron_id', 'nextcall', type='datetime', readonly=1, string="Next Execution Date"),
        'message': fields.text(string='Last Execution Message', readonly=True),
    }

    _defaults = {
        'active': False,
    }

    def create(self, cr, uid, vals, context=None):
        '''
        Create the deactivate_phase_out_partners and the ir_cron associated with it
        '''
        if context is None:
            context = {}

        cron_obj = self.pool.get('ir.cron')

        new_id = super(deactivate_phase_out_partners, self).create(cr, uid, vals, context=context)

        # Generate new ir.cron
        cron_vals = {
            'name': vals.get('name') or _('Deactivate Phase Out Partners'),
            'user_id': 1,
            'active': False,
            'interval_number': vals.get('interval') or 6,
            'interval_type': vals.get('interval_unit') or 'months',
            'numbercall': 0,
            'nextcall': vals.get('start_time') or time.strftime('%Y-%m-%d %H:%M:%S'),
            'model': self._name,
            'function': 'run_phase_out_partner_deactivation',
            'args': '(%s,)' % new_id,
        }
        cron_id = cron_obj.create(cr, uid, cron_vals, context=context)
        to_write = {'cron_id': cron_id}
        self.write(cr, uid, [new_id], to_write, context=context)

        return new_id

    def write(self, cr, uid, ids, vals, context=None):
        """
        Write on the deactivate_phase_out_partners and the ir_cron associated with it
        """
        if not ids:
            return True

        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        cron_obj = self.pool.get('ir.cron')
        if 'interval' in vals and vals['interval'] <= 0:
            raise osv.except_osv(_('Error'), _('Interval number can not be negative or zero !'))
        res = super(deactivate_phase_out_partners, self).write(cr, uid, ids, vals, context=context)

        for partner_del in self.browse(cr, uid, ids, context=context):
            cron_vals = {
                'active': partner_del.active,
                'numbercall': partner_del.interval and -1 or 0,
                'interval_number': partner_del.interval,
                'interval_type': partner_del.interval_unit,
                'nextcall': partner_del.start_time or time.strftime('%Y-%m-%d %H:%M:%S'),
            }
            if partner_del.cron_id:
                if not partner_del.start_time and 'nextcall' in cron_vals:
                    del(cron_vals['nextcall'])
                cron_obj.write(cr, uid, [partner_del.cron_id.id], cron_vals, context=context)
            elif not vals.get('cron_id', False):
                cron_vals.update({
                    'name': partner_del.name or _('Deactivate Phase Out Partners'),
                    'user_id': 1,
                    'model': self._name,
                    'function': 'run_phase_out_partner_deactivation',
                    'args': '(%s,)' % partner_del.id
                })
                cron_id = cron_obj.create(cr, uid, cron_vals, context=context)
                self.write(cr, uid, [partner_del.id], {'cron_id': cron_id}, context=context)

        if partner_del.active and partner_del.start_time:
            super(deactivate_phase_out_partners, self).write(cr, uid, ids, {'start_time': False}, context=context)

        return res

    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        raise osv.except_osv(_('Error'), _('This task can not be deleted'))

    def manual_run_phase_out_partner_deactivation(self, cr, uid, ids, context=None, params=None):
        if context is None:
            context = {}
        if params is None:
            params = {}
        if isinstance(ids, int):
            ids = [ids]

        return self.run_phase_out_partner_deactivation(cr, uid, ids, context=context)

    def run_phase_out_partner_deactivation(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        partner_obj = self.pool.get('res.partner')
        log_obj = self.pool.get('log.phase.out.partner.deactivation')
        for task in self.read(cr, uid, ids, context=context):
            msg, cant_deactivate_msg = '', ''
            nb_cant_deactivate = 0
            to_deactivate_ids, to_deactivate_names = [], []
            create_log = True
            try:
                phase_out_partners_ids = partner_obj.search(cr, uid, [('active', '=', 't'), ('state', '=', 'phase_out')], context=context)
                if phase_out_partners_ids:
                    for partner in partner_obj.read(cr, uid, phase_out_partners_ids, ['name'], context=context):
                        objects_linked_to_partner = partner_obj.get_objects_for_partner(cr, uid, partner['id'], context=context)
                        if objects_linked_to_partner:
                            nb_cant_deactivate += 1
                            cant_deactivate_msg += '\n- %s: %s' % (partner['name'], objects_linked_to_partner)
                        else:
                            to_deactivate_ids.append(partner['id'])
                            to_deactivate_names.append(partner['name'])

                    if to_deactivate_names:
                        if len(to_deactivate_names) == 1:
                            deactivated_msg = _('1 Partner was deactivated: %s') % (to_deactivate_names[0],)
                        else:
                            deactivated_msg = _('%s Partners were deactivated: %s') % (len(to_deactivate_names), ', '.join(to_deactivate_names))
                    else:
                        deactivated_msg = _('No Phase Out Partners were deactivated')
                    linked_msg = ''
                    if cant_deactivate_msg:
                        linked_msg = _('\n\n%s Phase Out Partners could not be deactivated because of open documents:%s') \
                            % (nb_cant_deactivate, cant_deactivate_msg)
                    msg = """%s%s""" % (deactivated_msg, linked_msg)

                    partner_obj.write(cr, uid, to_deactivate_ids, {'active': False}, context=context)
                else:
                    msg = _('There is no Phase Out Partner to deactivate')
                    create_log = False
            except Exception as e:
                cr.rollback()
                msg = tools.misc.get_traceback(e)
            finally:
                # super is called to prevent the cron to be modified and have the message changed in the task
                super(deactivate_phase_out_partners, self).write(cr, uid, task['id'], {'message': msg}, context=context)
                if create_log:
                    log_obj.create(cr, uid, {'user_id': uid, 'date': datetime.now(), 'message': msg}, context=context)

        return True

    def activate_phase_out_partner_deactivation(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        return self.write(cr, uid, ids, {'active': True}, context=context)

    def deactivate_phase_out_partner_deactivation(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        return self.write(cr, uid, ids, {'active': False}, context=context)


deactivate_phase_out_partners()


class log_phase_out_partner_deactivation(osv.osv):
    _name ='log.phase.out.partner.deactivation'
    _order = 'date desc'

    _columns = {
        'user_id': fields.many2one('res.users', 'User', readonly=True),
        'date': fields.datetime('Creation Date', readonly=True, select=1),
        'message': fields.text('Message', help='The logging message.', readonly=True, select=1),
    }


log_phase_out_partner_deactivation()
