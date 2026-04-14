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


class email_signature_notification(osv.osv):
    _name = 'email.signature.notification'
    _description = 'Email Signature Notification'

    _columns = {
        'active': fields.boolean(string='Active'),
        'delay': fields.selection(string='Delay', selection=[(15, '15 minutes'), (30, '30 minutes'), (60, '60 minutes')], required=True),
        'cron_id': fields.many2one('ir.cron', string='Associated cron job', readonly=True),
        'reminder_active': fields.boolean(string='Reminder Active'),
        'reminder_cron_id': fields.many2one('ir.cron', string='Associated cron job for the reminder', readonly=True),
        'check_signature_expiry': fields.boolean(string='Signature Expiration Reminder', help='If checked, will add an additional message in the email when the signature is expired or will expire in the next 30 days'),
        'doc_applicability_ids': fields.one2many('email.signature.notification.doc.applicability', 'email_sign_notif_id', string='Document applicability', help='Documents impacted by the signature notifications'),
    }

    _defaults = {
        'active': False,
        'delay': 30,
        'reminder_active': False,
    }

    def create(self, cr, uid, vals, context=None):
        '''
        Create the email_signature_notification and the 2 ir_cron associated with it
        '''
        if context is None:
            context = {}

        cron_obj = self.pool.get('ir.cron')

        new_id = super(email_signature_notification, self).create(cr, uid, vals, context=context)

        # Generate new ir.cron
        cron_vals = {
            'name': _('Email Signature Notification'),
            'user_id': 1,
            'active': False,
            'interval_number': vals.get('delay') or 30,
            'interval_type': 'minutes',
            'numbercall': -1,
            'nextcall': vals.get('start_time') or time.strftime('%Y-%m-%d %H:%M:%S'),
            'model': self._name,
            'function': 'run_email_signature_notification',
            'args': '(%s,)' % new_id,
        }
        cron_id = cron_obj.create(cr, uid, cron_vals, context=context)

        # Generate new ir.cron for reminder
        reminder_cron_vals = {
            'name': _('Email Signature Notification Reminder'),
            'user_id': 1,
            'active': False,
            'interval_number': 1,
            'interval_type': 'days',
            'numbercall': -1,
            'nextcall': time.strftime('%Y-%m-%d %H:%M:%S'),
            'model': self._name,
            'function': 'run_email_signature_notification_reminder',
            'args': '(%s,)' % new_id,
        }
        reminder_cron_id = cron_obj.create(cr, uid, reminder_cron_vals, context=context)

        self.write(cr, uid, [new_id], {'cron_id': cron_id, 'reminder_cron_id': reminder_cron_id}, context=context)

        return new_id

    def write(self, cr, uid, ids, vals, context=None):
        """
        Write on the email_signature_notification and the 2 ir_cron associated with it
        """
        if not ids:
            return True

        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        cron_obj = self.pool.get('ir.cron')
        res = super(email_signature_notification, self).write(cr, uid, ids, vals, context=context)

        for email_sign_notif in self.browse(cr, uid, ids, context=context):
            to_write = {}

            cron_vals = {
                'active': email_sign_notif.active,
                'interval_number': email_sign_notif.delay,
                'interval_type': 'minutes',
            }
            if email_sign_notif.cron_id or vals.get('cron_id', False):
                cron_id = email_sign_notif.cron_id and email_sign_notif.cron_id.id or vals['cron_id']
                cron_obj.write(cr, uid, [cron_id], cron_vals, context=context)
            else:
                cron_vals.update({
                    'name': _('Email Signature Notification'),
                    'user_id': 1,
                    'numbercall': -1,
                    'nextcall': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'model': self._name,
                    'function': 'run_email_signature_notification_reminder',
                    'args': '(%s,)' % email_sign_notif.id
                })
                to_write['cron_id'] = cron_obj.create(cr, uid, cron_vals, context=context)

            reminder_cron_vals = {
                'active': email_sign_notif.active and email_sign_notif.reminder_active or False,
                'interval_number': 1,
                'interval_type': 'days',
            }
            if email_sign_notif.reminder_cron_id or vals.get('reminder_cron_id', False):
                reminder_cron_id = email_sign_notif.reminder_cron_id and email_sign_notif.reminder_cron_id.id \
                                   or vals['reminder_cron_id']
                cron_obj.write(cr, uid, [reminder_cron_id], reminder_cron_vals, context=context)
            else:
                reminder_cron_vals.update({
                    'name': _('Email Signature Notification Reminder'),
                    'user_id': 1,
                    'numbercall': -1,
                    'nextcall': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'model': self._name,
                    'function': 'run_email_signature_notification',
                    'args': '(%s,)' % email_sign_notif.id
                })
                to_write['reminder_cron_id'] = cron_obj.create(cr, uid, reminder_cron_vals, context=context)

            if to_write:
                self.write(cr, uid, [email_sign_notif.id], to_write, context=context)

        return res

    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        raise osv.except_osv(_('Error'), _('This task can not be deleted'))

    def manual_run_email_signature_notification(self, cr, uid, ids, context=None, params=None):
        if context is None:
            context = {}
        if params is None:
            params = {}
        if isinstance(ids, int):
            ids = [ids]

        return self.run_email_signature_notification(cr, uid, ids, context=context)

    def run_email_signature_notification(self, cr, uid, ids, context=None):
        """
        For each signable signature line, create a single mail for each user describing which document need to be signed
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        for email_sign_notif in self.browse(cr, uid, ids, context=context):
            sql_wheres = []
            for doc_type in email_sign_notif.doc_applicability_ids:
                if doc_type.active:
                    if doc_type.doc_type == 'sale.order.fo':
                        sql_wheres.append("""(sgn.signature_res_model = 'sale.order' AND s.procurement_request = 'f') AND
                        s.state IN ('draft', 'draft_p', 'validated', 'validated_p')""")
                    if doc_type.doc_type == 'sale.order.ir':
                        sql_wheres.append("""(sgn.signature_res_model = 'sale.order' AND s.procurement_request = 't') AND
                        s.state IN ('draft', 'draft_p', 'validated', 'validated_p')""")
                    if doc_type.doc_type == 'purchase.order':
                        sql_wheres.append("""(sgn.signature_res_model = 'purchase.order' AND po.rfq_ok = 'f' AND 
                        po.state IN ('draft', 'draft_p', 'validated', 'validated_p') AND 
                        (popar.partner_type != 'external' OR (sgn.doc_locked_for_sign = 't' AND popar.partner_type = 'external')))""")
                    if doc_type.doc_type == 'stock.picking.in':
                        sql_wheres.append("""(sgn.signature_res_model = 'stock.picking' AND p.type = 'in' AND p.subtype = 'standard' AND 
                        p.state = 'done')""")
                    if doc_type.doc_type == 'stock.picking.int':
                        sql_wheres.append("""(sgn.signature_res_model = 'stock.picking' AND p.type = 'internal' AND p.subtype = 'standard' AND 
                        p.state IN ('confirmed', 'assigned'))""")
                    if doc_type.doc_type == 'stock.picking.out':
                        sql_wheres.append("""(sgn.signature_res_model = 'stock.picking' AND p.type = 'out' AND p.subtype = 'standard')""")
                    if doc_type.doc_type == 'stock.picking.pick':
                        sql_wheres.append("""(sgn.signature_res_model = 'stock.picking' AND p.type = 'out' AND p.subtype = 'picking')""")
                    if doc_type.doc_type == 'account.bank.statement.cash':
                        sql_wheres.append("""(sgn.signature_res_model = 'account.bank.statement' AND acj.type = 'cash')""")
                    if doc_type.doc_type == 'account.bank.statement.bank':
                        sql_wheres.append("""(sgn.signature_res_model = 'account.bank.statement' AND acj.type = 'bank')""")
                    if doc_type.doc_type == 'account.bank.statement.cheque':
                        sql_wheres.append("""(sgn.signature_res_model = 'account.bank.statement' AND acj.type = 'cheque')""")
                    if doc_type.doc_type == 'account.invoice':
                        sql_wheres.append("""(sgn.signature_res_model = 'account.invoice' AND inv.type = 'in_invoice' AND invj.type = 'purchase')""")
                    if doc_type.doc_type == 'physical.inventory':
                        sql_wheres.append("""(sgn.signature_res_model = 'physical.inventory' AND phys.state IN ('validated', 'confirmed'))""")

            if not sql_wheres:
                raise osv.except_osv(_('Error'), _('There is no active Document Applicability type selected for the Email Signature Notification'))

            cr.execute("""
                SELECT sgnl.user_id, sgn.signature_res_model, sgnl.id
                       COALESCE(s.name, po.name, p.name, acbs.name, inv.number, inv.origin, inv.supplier_reference, phys.ref, NULL),
                       s.procurement_request, p.type, p.subtype, acj.type
                FROM signature_line sgnl
                    LEFT JOIN signature sgn ON sgnl.signature_id = sgn.id
                    LEFT JOIN signature_line osgnl ON osgnl.signature_id = sgnl.signature_id AND osgnl.is_active = 't' AND osgnl.signed = 'f'
                    LEFT JOIN sale_order s ON sgn.signature_res_id = s.id AND sgn.signature_res_model = 'sale.order'
                    LEFT JOIN purchase_order po ON sgn.signature_res_id = po.id AND sgn.signature_res_model = 'purchase.order'
                    LEFT JOIN res_partner popar ON po.partner_id = popar.id
                    LEFT JOIN stock_picking p ON sgn.signature_res_id = p.id AND sgn.signature_res_model = 'stock.picking'
                    LEFT JOIN account_bank_statement acbs ON sgn.signature_res_id = acbs.id AND sgn.signature_res_model = 'account.bank.statement'
                    LEFT JOIN account_journal acj ON acbs.journal_id = acj.id
                    LEFT JOIN account_invoice inv ON sgn.signature_res_id = inv.id AND sgn.signature_res_model = 'account.invoice'
                    LEFT JOIN account_journal invj ON inv.journal_id = invj.id
                    LEFT JOIN physical_inventory phys ON sgn.signature_res_id = phys.id AND sgn.signature_res_model = 'physical.inventory'
                WHERE sgnl.user_id IS NOT NULL AND sgnl.signed = 'f' AND sgnl.is_active = 't' AND sgn.signed_off_line = 'f'
                    AND sgn.signature_is_closed = 'f' AND (""" + ' OR '.join(sql_wheres) + """)
                GROUP BY sgnl.user_id, sgn.signature_res_model, sgn.signature_res_id, sgnl.id, sgnl.prio, s.procurement_request, 
                    s.name, po.name, p.name, acbs.name, inv.number, inv.origin, inv.supplier_reference, phys.ref, p.type, 
                    p.subtype, acj.type
                HAVING sgnl.prio <= MIN(osgnl.prio)
            """)

            to_sign_by_user = {}
            sgnl_to_update = []
            for sgnl in cr.fetchall():
                sgnl_to_update.append(sgnl[2])
                if not to_sign_by_user.get(sgnl[0]):
                    to_sign_by_user[sgnl[0]] = {'fo_names': [], 'ir_names': [], 'po_names': [], 'in_names': [],
                                             'int_names': [], 'out_names': [], 'pick_names': [], 'cash_names': [],
                                             'bank_names': [], 'cheque_names': [], 'inv_names': [], 'phys_names': []}
                if sgnl[1] == 'sale.order' and sgnl[4] is not None and sgnl[4] == False:
                    to_sign_by_user[sgnl[0]]['fo_names'].append(sgnl[3])
                elif sgnl[1] == 'sale.order' and sgnl[4] is not None and sgnl[4] == True:
                    to_sign_by_user[sgnl[0]]['ir_names'].append(sgnl[3])
                elif sgnl[1] == 'purchase.order':
                    to_sign_by_user[sgnl[0]]['po_names'].append(sgnl[3])
                elif sgnl[1] == 'stock.picking' and sgnl[5] is not None and sgnl[6] is not None:
                    if sgnl[5] == 'in' and sgnl[6] == 'standard':
                        to_sign_by_user[sgnl[0]]['in_names'].append(sgnl[3])
                    elif sgnl[5] == 'internal' and sgnl[6] == 'standard':
                        to_sign_by_user[sgnl[0]]['int_names'].append(sgnl[3])
                    elif sgnl[5] == 'out' and sgnl[6] == 'standard' and sgnl[3] not in to_sign_by_user[sgnl[0]]['out_names']:
                        to_sign_by_user[sgnl[0]]['out_names'].append(sgnl[3])
                    elif sgnl[5] == 'out' and sgnl[6] == 'picking' and sgnl[3] not in to_sign_by_user[sgnl[0]]['pick_names']:
                        to_sign_by_user[sgnl[0]]['pick_names'].append(sgnl[3])
                elif sgnl[1] == 'account.bank.statement' and sgnl[7] is not None:
                    if sgnl[7] == 'cash' and sgnl[3] not in to_sign_by_user[sgnl[0]]['cash_names']:
                        to_sign_by_user[sgnl[0]]['cash_names'].append(sgnl[3])
                    elif sgnl[7] == 'bank' and sgnl[3] not in to_sign_by_user[sgnl[0]]['bank_names']:
                        to_sign_by_user[sgnl[0]]['bank_names'].append(sgnl[3])
                    elif sgnl[7] == 'cheque' and sgnl[3] not in to_sign_by_user[sgnl[0]]['cheque_names']:
                        to_sign_by_user[sgnl[0]]['cheque_names'].append(sgnl[3])
                elif sgnl[1] == 'account.invoice' and sgnl[3] not in to_sign_by_user[sgnl[0]]['inv_names']:
                    to_sign_by_user[sgnl[0]]['inv_names'].append(sgnl[3])
                elif sgnl[1] == 'physical.inventory':
                    to_sign_by_user[sgnl[0]]['phys_names'].append(sgnl[3])

        return True


email_signature_notification()


class email_signature_notification_doc_applicability(osv.osv):
    _name = 'email.signature.notification.doc.applicability'
    _description = 'Email Signature Notification Document Applicability'

    _columns = {
        'doc_type': fields.selection(string='Document Type',
                                     selection=[
                                         ('sale.order.fo', 'Field Orders'),
                                         ('sale.order.ir', 'Internal Requests'),
                                         ('purchase.order', 'Purchase Orders'),
                                         ('stock.picking.in', 'Incoming Shipments'),
                                         ('stock.picking.int', 'Internal Moves'),
                                         ('stock.picking.out', 'Delivery Orders'),
                                         ('stock.picking.pick', 'Picking'),
                                         ('account.bank.statement.cash', 'Cash Registers'),
                                         ('account.bank.statement.bank', 'Bank Registers'),
                                         ('account.bank.statement.cheque', 'Cheque Registers'),
                                         ('account.invoice', 'Supplier Invoices'),
                                         ('physical.inventory', 'Physical Inventories'),
                                     ], readonly=True),
        'active': fields.boolean(string='Active'),
        'email_sign_notif_id': fields.many2one('email.signature.notification', string='Email Signature Notification', readonly=True),
    }

    _defaults = {
        'active': False,
    }


email_signature_notification_doc_applicability()
