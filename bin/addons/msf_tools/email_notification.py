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


class email_notification(osv.osv):
    _name = 'email.notification'
    _description = 'Email Notification'

    _columns = {
        'active': fields.boolean(string='Active'),
        'delay': fields.selection(string='Delay', selection=[(15, '15 minutes'), (30, '30 minutes'), (60, '60 minutes')], required=True),
        'cron_id': fields.many2one('ir.cron', string='Associated cron job', readonly=True),
        'reminder_active': fields.boolean(string='Reminder Active'),
        'reminder_cron_id': fields.many2one('ir.cron', string='Associated cron job for the reminder', readonly=True),
        'check_signature_expiry': fields.boolean(string='Signature Expiration Reminder', help='If checked, will add an additional message in the email when the signature is expired or will expire in the next 30 days'),
    }

    _defaults = {
        'active': False,
        'delay': 30,
        'reminder_active': False,
    }

    def create(self, cr, uid, vals, context=None):
        '''
        Create the email_notification and the 2 ir_cron associated with it
        '''
        if context is None:
            context = {}

        cron_obj = self.pool.get('ir.cron')

        new_id = super(email_notification, self).create(cr, uid, vals, context=context)

        # Generate new ir.cron
        cron_vals = {
            'name': _('Email Notification'),
            'user_id': 1,
            'active': False,
            'interval_number': vals.get('delay') or 30,
            'interval_type': 'minutes',
            'numbercall': -1,
            'nextcall': vals.get('start_time') or time.strftime('%Y-%m-%d %H:%M:%S'),
            'model': self._name,
            'function': 'run_email_notification',
            'args': '(%s,)' % new_id,
        }
        cron_id = cron_obj.create(cr, uid, cron_vals, context=context)

        # Generate new ir.cron for reminder
        cron_vals = {
            'name': _('Email Notification Reminder'),
            'user_id': 1,
            'active': False,
            'interval_number': 1,
            'interval_type': 'days',
            'numbercall': -1,
            'nextcall': time.strftime('%Y-%m-%d %H:%M:%S'),
            'model': self._name,
            'function': 'run_email_notification_reminder',
            'args': '(%s,)' % new_id,
        }
        reminder_cron_id = cron_obj.create(cr, uid, cron_vals, context=context)

        self.write(cr, uid, [new_id], {'cron_id': cron_id, 'reminder_cron_id': reminder_cron_id}, context=context)

        return new_id

    def write(self, cr, uid, ids, vals, context=None):
        """
        Write on the deactivate_phase_out_partners and the 2 ir_cron associated with it
        """
        if not ids:
            return True

        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        cron_obj = self.pool.get('ir.cron')
        res = super(email_notification, self).write(cr, uid, ids, vals, context=context)

        for email_notif in self.browse(cr, uid, ids, context=context):
            to_write = {}

            cron_vals = {
                'active': email_notif.active,
                'interval_number': email_notif.delay,
                'interval_type': 'minutes',
            }
            if not vals.get('cron_id', False):
                cron_vals.update({
                    'name': _('Email Notification'),
                    'user_id': 1,
                    'numbercall': -1,
                    'nextcall': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'model': self._name,
                    'function': 'run_email_notification_reminder',
                    'args': '(%s,)' % email_notif.id
                })
                to_write['cron_id'] = cron_obj.create(cr, uid, cron_vals, context=context)
            else:
                cron_obj.write(cr, uid, [email_notif.cron_id.id], cron_vals, context=context)

            reminder_cron_vals = {
                'active': email_notif.active and email_notif.reminder_active or False,
                'interval_number': 1,
                'interval_type': 'days',
            }
            if not vals.get('reminder_cron_id', False):
                reminder_cron_vals.update({
                    'name': _('Email Notification Reminder'),
                    'user_id': 1,
                    'numbercall': -1,
                    'nextcall': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'model': self._name,
                    'function': 'run_email_notification',
                    'args': '(%s,)' % email_notif.id
                })
                to_write['reminder_cron_id'] = cron_obj.create(cr, uid, reminder_cron_vals, context=context)
            else:
                cron_obj.write(cr, uid, [email_notif.reminder_cron_id.id], reminder_cron_vals, context=context)

            if to_write:
                self.write(cr, uid, [email_notif.id], to_write, context=context)

        return res

    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        raise osv.except_osv(_('Error'), _('This task can not be deleted'))

    def manual_run_email_notification(self, cr, uid, ids, context=None, params=None):
        if context is None:
            context = {}
        if params is None:
            params = {}
        if isinstance(ids, int):
            ids = [ids]

        return self.run_email_notification(cr, uid, ids, context=context)

    def run_email_notification(self, cr, uid, ids, context=None):
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
                super(email_notification, self).write(cr, uid, task['id'], {'message': msg}, context=context)
                if create_log:
                    log_obj.create(cr, uid, {'user_id': uid, 'date': datetime.now(), 'message': msg}, context=context)

        return True


email_notification()
