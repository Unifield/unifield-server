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
from dateutil.relativedelta import relativedelta

from osv import osv
from osv import fields
import time
import tools
from datetime import datetime

from tools.translate import _


class email_signature_notification(osv.osv):
    _name = 'email.signature.notification'
    _description = 'Email Notification for Signatures'

    _columns = {
        'active': fields.boolean(string='Active'),
        'delay': fields.selection(string='Delay', selection=[(15, '15 minutes'), (30, '30 minutes'), (60, '60 minutes')], required=True),
        'cron_id': fields.many2one('ir.cron', string='Associated cron job', readonly=True),
        'reminder_active': fields.boolean(string='Reminder Active'),
        'reminder_cron_id': fields.many2one('ir.cron', string='Associated cron job for the reminder', readonly=True),
        'check_signature_expiry': fields.boolean(string='Signature Expiration Reminder', help='If checked, will add an additional message in the email when the signature is expired or will expire in the next 30 days'),
        'doc_applicability_ids': fields.one2many('email.signature.notification.doc.applicability', 'email_sign_notif_id', string='Document Applicability', help='Documents impacted by the signature notifications', domain=[('active', 'in', ['t', 'f'])]),
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
            'name': _('Email Notification for Signatures'),
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
            'name': _('Email Notification Reminder for Signatures'),
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

        if not vals.get('active'):
            vals['reminder_active'] = False
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
                    'name': _('Email Notification for Signatures'),
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
                    'name': _('Email Notification Reminder for Signatures'),
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

    def run_email_signature_notification_reminder(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        return self.run_email_signature_notification(cr, uid, ids, context=context, is_reminder=True)

    def run_email_signature_notification(self, cr, uid, ids, context=None, is_reminder=False):
        """
        For each signable signature line, create a single mail for each user describing which document need to be signed
        A log will be added to the signature of each signature line affected
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        signl_obj = self.pool.get('signature.line')
        user_obj = self.pool.get('res.users')

        for email_sign_notif in self.browse(cr, uid, ids, context=context):
            if is_reminder:
                # Only send a new reminder to signature lines that had their first reminder less than 30 days ago
                sql_date_where = """signl.latest_reminder_sent_date IS NOT NULL AND EXTRACT(DAY FROM (NOW() - signl.latest_reminder_sent_date)) <= 30"""
            else:
                sql_date_where = """signl.first_reminder_sent_date IS NULL"""

            sql_doc_wheres = []
            for doc_type in email_sign_notif.doc_applicability_ids:
                if doc_type.active:
                    # Each active type + same behavior as signature field "allowed_to_be_signed_unsigned"
                    if doc_type.doc_type == 'sale.order.fo':
                        sql_doc_wheres.append("""(sign.signature_res_model = 'sale.order' AND s.procurement_request = 'f' AND
                        s.state IN ('draft', 'draft_p', 'validated', 'validated_p'))""")
                    if doc_type.doc_type == 'sale.order.ir':
                        sql_doc_wheres.append("""(sign.signature_res_model = 'sale.order' AND s.procurement_request = 't' AND
                        s.state IN ('draft', 'draft_p', 'validated', 'validated_p'))""")
                    if doc_type.doc_type == 'purchase.order':
                        sql_doc_wheres.append("""(sign.signature_res_model = 'purchase.order' AND po.rfq_ok = 'f' AND
                        po.state IN ('draft', 'draft_p', 'validated', 'validated_p') AND 
                        (popar.partner_type != 'external' OR (sign.doc_locked_for_sign = 't' AND popar.partner_type = 'external')))""")
                    if doc_type.doc_type == 'stock.picking.in':
                        sql_doc_wheres.append("""(sign.signature_res_model = 'stock.picking' AND p.type = 'in' AND
                        p.subtype = 'standard' AND p.state = 'done')""")
                    if doc_type.doc_type == 'stock.picking.int':
                        sql_doc_wheres.append("""(sign.signature_res_model = 'stock.picking' AND p.type = 'internal' AND
                        p.subtype = 'standard' AND p.state IN ('confirmed', 'assigned'))""")
                    if doc_type.doc_type == 'stock.picking.out':
                        sql_doc_wheres.append("""(sign.signature_res_model = 'stock.picking' AND p.type = 'out' AND p.subtype = 'standard')""")
                    if doc_type.doc_type == 'stock.picking.pick':
                        sql_doc_wheres.append("""(sign.signature_res_model = 'stock.picking' AND p.type = 'out' AND p.subtype = 'picking')""")
                    if doc_type.doc_type == 'account.bank.statement.cash':
                        sql_doc_wheres.append("""(sign.signature_res_model = 'account.bank.statement' AND acj.type = 'cash')""")
                    if doc_type.doc_type == 'account.bank.statement.bank':
                        sql_doc_wheres.append("""(sign.signature_res_model = 'account.bank.statement' AND acj.type = 'bank')""")
                    if doc_type.doc_type == 'account.bank.statement.cheque':
                        sql_doc_wheres.append("""(sign.signature_res_model = 'account.bank.statement' AND acj.type = 'cheque')""")
                    if doc_type.doc_type == 'account.invoice':
                        sql_doc_wheres.append("""(sign.signature_res_model = 'account.invoice' AND inv.type = 'in_invoice' AND
                        invj.type = 'purchase')""")
                    if doc_type.doc_type == 'physical.inventory':
                        sql_doc_wheres.append("""(sign.signature_res_model = 'physical.inventory' AND
                        phys.state IN ('validated', 'confirmed'))""")

            if not sql_doc_wheres:
                raise osv.except_osv(_('Error'), _('There is no active Document Applicability type selected in the Email Notification for Signatures'))

            cr.execute("""
                SELECT signl.user_id, u.name, u.user_email, u.signature_to, sign.id, sign.signature_res_model, signl.id,
                       COALESCE(s.name, po.name, p.name, acbs.name, inv.number, inv.origin, inv.supplier_reference, phys.ref, NULL),
                       s.procurement_request, p.type, p.subtype, acj.type
                FROM signature_line signl
                    LEFT JOIN signature sign ON signl.signature_id = sign.id
                    LEFT JOIN signature_line osignl ON osignl.signature_id = signl.signature_id AND osignl.is_active = 't' AND osignl.signed = 'f'
                    LEFT JOIN res_users u ON signl.user_id = u.id
                    LEFT JOIN sale_order s ON sign.signature_res_id = s.id AND sign.signature_res_model = 'sale.order'
                    LEFT JOIN purchase_order po ON sign.signature_res_id = po.id AND sign.signature_res_model = 'purchase.order'
                    LEFT JOIN res_partner popar ON po.partner_id = popar.id
                    LEFT JOIN stock_picking p ON sign.signature_res_id = p.id AND sign.signature_res_model = 'stock.picking'
                    LEFT JOIN account_bank_statement acbs ON sign.signature_res_id = acbs.id AND sign.signature_res_model = 'account.bank.statement'
                    LEFT JOIN account_journal acj ON acbs.journal_id = acj.id
                    LEFT JOIN account_invoice inv ON sign.signature_res_id = inv.id AND sign.signature_res_model = 'account.invoice'
                    LEFT JOIN account_journal invj ON inv.journal_id = invj.id
                    LEFT JOIN physical_inventory phys ON sign.signature_res_id = phys.id AND sign.signature_res_model = 'physical.inventory'
                WHERE signl.user_id IS NOT NULL AND u.signature_enabled = 't' AND signl.signed = 'f' AND signl.is_active = 't'
                    AND sign.signed_off_line = 'f' AND sign.signature_is_closed = 'f' AND """ + sql_date_where + """
                    AND (""" + ' OR '.join(sql_doc_wheres) + """)
                GROUP BY signl.user_id, u.name, u.user_email, u.signature_to, sign.id, sign.signature_res_model,
                    sign.signature_res_id, signl.id, signl.prio, s.procurement_request, s.name, po.name, p.name, acbs.name,
                    inv.number, inv.origin, inv.supplier_reference, phys.ref, p.type, p.subtype, acj.type
                HAVING signl.prio <= MIN(osignl.prio)
            """)

            to_sign_by_user = {}
            for signl in cr.fetchall():
                if not to_sign_by_user.get(signl[0]):
                    to_sign_by_user[signl[0]] = {'user_name': signl[1], 'user_email': signl[2], 'user_sign_end_date': signl[3],
                                                'sign_ids': [], 'signl_ids': [], 'fo_names': [], 'ir_names': [], 'po_names': [],
                                                'in_names': [], 'int_names': [], 'out_names': [], 'pick_names': [], 'cash_names': [],
                                                'bank_names': [], 'cheque_names': [], 'inv_names': [], 'phys_names': []}
                to_sign_by_user[signl[0]]['signl_ids'].append(signl[6])
                if signl[4] not in to_sign_by_user[signl[0]]['sign_ids']:
                    to_sign_by_user[signl[0]]['sign_ids'].append(signl[4])
                if signl[5] == 'sale.order' and signl[8] is not None and signl[8] == False:
                    to_sign_by_user[signl[0]]['fo_names'].append(signl[7])
                elif signl[5] == 'sale.order' and signl[8] is not None and signl[8] == True:
                    to_sign_by_user[signl[0]]['ir_names'].append(signl[7])
                elif signl[5] == 'purchase.order':
                    to_sign_by_user[signl[0]]['po_names'].append(signl[7])
                elif signl[5] == 'stock.picking' and signl[9] is not None and signl[10] is not None:
                    if signl[9] == 'in' and signl[10] == 'standard':
                        to_sign_by_user[signl[0]]['in_names'].append(signl[7])
                    elif signl[9] == 'internal' and signl[10] == 'standard':
                        to_sign_by_user[signl[0]]['int_names'].append(signl[7])
                    elif signl[9] == 'out' and signl[10] == 'standard' and signl[7] not in to_sign_by_user[signl[0]]['out_names']:
                        to_sign_by_user[signl[0]]['out_names'].append(signl[7])
                    elif signl[9] == 'out' and signl[10] == 'picking' and signl[7] not in to_sign_by_user[signl[0]]['pick_names']:
                        to_sign_by_user[signl[0]]['pick_names'].append(signl[7])
                elif signl[5] == 'account.bank.statement' and signl[11] is not None:
                    if signl[11] == 'cash' and signl[7] not in to_sign_by_user[signl[0]]['cash_names']:
                        to_sign_by_user[signl[0]]['cash_names'].append(signl[7])
                    elif signl[11] == 'bank' and signl[7] not in to_sign_by_user[signl[0]]['bank_names']:
                        to_sign_by_user[signl[0]]['bank_names'].append(signl[7])
                    elif signl[11] == 'cheque' and signl[7] not in to_sign_by_user[signl[0]]['cheque_names']:
                        to_sign_by_user[signl[0]]['cheque_names'].append(signl[7])
                elif signl[5] == 'account.invoice' and signl[7] not in to_sign_by_user[signl[0]]['inv_names']:
                    to_sign_by_user[signl[0]]['inv_names'].append(signl[7])
                elif signl[5] == 'physical.inventory':
                    to_sign_by_user[signl[0]]['phys_names'].append(signl[7])

            instance_name = user_obj.browse(cr, uid, [uid], context=context)[0].company_id.instance_id.instance
            expired_sign_user_names = []
            for user_id in to_sign_by_user:
                user_signl = to_sign_by_user[user_id]
                error_msg = ''
                current_date = datetime.now()
                try:
                    if not user_signl.get('user_email'):
                        raise osv.except_osv(_('Error'), _('User %s does not have an Email') % (user_signl.get('user_name', _('UniField user')),))
                    if user_signl.get('user_sign_end_date') and current_date.strftime('%Y-%m-%d') > user_signl['user_sign_end_date']:
                        # Fill the list with usernames to send a list of users that have an expired signature but need
                        # to sign to users with the rights Sign_document_creator_finance and Sign_document_creator_supply
                        if user_signl.get('user_name', _('UniField user')) not in expired_sign_user_names:
                            expired_sign_user_names.append(user_signl.get('user_name', _('UniField user')))
                        continue

                    docs_string = """"""
                    if user_signl.get('fo_names'):
                        docs_string += _('\nDocument type: Field Orders (FO):')
                        for doc_name in user_signl['fo_names']:
                            docs_string += '\n  • %s' % (doc_name,)
                    if user_signl.get('ir_names'):
                        docs_string += _('\nDocument type: Internal Requests (IR):')
                        for doc_name in user_signl['ir_names']:
                            docs_string += '\n  • %s' % (doc_name,)
                    if user_signl.get('po_names'):
                        docs_string += _('\nDocument type: Purchase Orders (PO):')
                        for doc_name in user_signl['po_names']:
                            docs_string += '\n  • %s' % (doc_name,)
                    if user_signl.get('in_names'):
                        docs_string += _('\nDocument type: Incoming Shipments (IN):')
                        for doc_name in user_signl['in_names']:
                            docs_string += '\n  • %s' % (doc_name,)
                    if user_signl.get('int_names'):
                        docs_string += _('\nDocument type: Internal Moves (INT):')
                        for doc_name in user_signl['int_names']:
                            docs_string += '\n  • %s' % (doc_name,)
                    if user_signl.get('out_names'):
                        docs_string += _('\nDocument type: Delivery Orders (OUT):')
                        for doc_name in user_signl['out_names']:
                            docs_string += '\n  • %s' % (doc_name,)
                    if user_signl.get('pick_names'):
                        docs_string += _('\nDocument type: Picking Lists & Picking Tickets (PICK):')
                        for doc_name in user_signl['pick_names']:
                            docs_string += '\n  • %s' % (doc_name,)
                    if user_signl.get('cash_names'):
                        docs_string += _('\nDocument type: Cash Registers:')
                        for doc_name in user_signl['cash_names']:
                            docs_string += '\n  • %s' % (doc_name,)
                    if user_signl.get('bank_names'):
                        docs_string += _('\nDocument type: Bank Registers:')
                        for doc_name in user_signl['bank_names']:
                            docs_string += '\n  • %s' % (doc_name,)
                    if user_signl.get('cheque_names'):
                        docs_string += _('\nDocument type: Cheque Registers:')
                        for doc_name in user_signl['cheque_names']:
                            docs_string += '\n  • %s' % (doc_name,)
                    if user_signl.get('inv_names'):
                        docs_string += _('\nDocument type: Supplier Invoices (SI):')
                        for doc_name in user_signl['inv_names']:
                            docs_string += '\n  • %s' % (doc_name,)
                    if user_signl.get('phys_names'):
                        docs_string += _('\nDocument type: Physical Inventories (PI):')
                        for doc_name in user_signl['phys_names']:
                            docs_string += '\n  • %s' % (doc_name,)

                    sign_expiry_text = ''
                    if email_sign_notif.check_signature_expiry and user_signl.get('user_sign_end_date') and \
                            (datetime.now() + relativedelta(days=30)).strftime('%Y-%m-%d') > user_signl['user_sign_end_date']:
                        sign_expiry_text = _('\nSignature status: Your signature will expire the %s, please take the necessary actions to either take care of the pending signatures or update your signature.') \
                                           % (datetime.strptime(user_signl['user_sign_end_date'], '%Y-%m-%d').strftime('%d/%m/%Y'),)

                    if is_reminder:
                        email_subject = _('UniField Reminder - Pending electronic signatures summary')
                        first_line = _('This is a reminder that you still have pending electronic signatures in UniField.')
                    else:
                        email_subject = _('UniField - Pending electronic signatures summary')
                        first_line = _('You have pending electronic signatures in UniField.')

                    email_body = _("""Dear %s,

%s
Below is a summary of documents currently awaiting your signature. Only document types that are active in the configuration and for which at least one document is pending are displayed.

Instance: %s
%s
%s
Please log in to UniField to review and complete the required electronic signatures.

This is an automated notification. If you have already signed a document after this e-mail was generated, no further action is required for that document.

Thank you,
UniField Team""") % (user_signl.get('user_name', _('UniField user')), first_line, instance_name, docs_string, sign_expiry_text)

                    tools.email_send(False, [user_signl['user_email']], email_subject, email_body)
                except Exception as e:
                    if isinstance(e, osv.except_osv):
                        error_msg = e.value
                    else:
                        error_msg = e.args and '. '.join(e.args) or e
                finally:
                    # Logs to be displayed on the signature tab
                    email_log_vals = {
                        'recipients': user_signl.get('user_email') or user_signl.get('user_name', _('UniField user')),
                        'recipient_names': user_signl.get('user_name', _('UniField user')),
                        'state': error_msg and 'error' or 'success',
                        'result': error_msg and _('Some error(s) occurred while trying to send the email: %s') % (error_msg,) \
                                  or _('The email was sent successfully'),
                        'sender_model_id': self.pool.get('ir.model').search(cr, 1, [('model', '=', self._name)])[0],
                        'signature_ids': [(6, 0, user_signl.get('sign_ids', []))],
                        'date_sent': current_date,
                        'user_id': hasattr(uid, 'realUid') and uid.realUid or uid,
                    }
                    self.pool.get('email.log').create(cr, uid, email_log_vals, context=context)
                    # Put the necessary date on the affected signature lines
                    if is_reminder:
                        signl_obj.write(cr, uid, user_signl.get('signl_ids', []), {'latest_reminder_sent_date': current_date}, context=context)
                    else:
                        signl_obj.write(cr, uid, user_signl.get('signl_ids', []), {'first_reminder_sent_date': current_date,
                                                                                   'latest_reminder_sent_date': current_date}, context=context)

            if expired_sign_user_names:
                self.email_expired_signatures(cr, uid, ids, expired_sign_user_names, context=context)

        return True

    def email_expired_signatures(self, cr, uid, ids, usernames, context=None):
        if context is None:
            context = {}

        user_obj = self.pool.get('res.users')

        group_ids = self.pool.get('res.groups').search(cr, uid, [('name', 'in', ['Sign_document_creator_finance', 'Sign_document_creator_supply'])])
        user_domain = [('id', '!=', 1), ('user_email', '!=', False), ('groups_id', 'in', group_ids)]
        sign_doc_creator_ids = user_obj.search(cr, uid, user_domain, context=context)
        if sign_doc_creator_ids:
            error_msg = ''
            name_doc_creators, email_doc_creators = [], []
            for user in user_obj.read(cr, uid, sign_doc_creator_ids, ['user_name', 'user_email'], context=context):
                name_doc_creators.append(user['user_name'])
                email_doc_creators.append(user['user_email'])
            try:
                exp_sign_user_list = ''
                for exp_user_name in usernames:
                    exp_sign_user_list += '\n  • %s' % (exp_user_name,)
                email_subject = _('UniField - Expired signatures for users with pending signatures')
                email_body = _("""Dear Document Creator,

The following users have pending electronic signatures in UniField but can not sign because their signature is expired:%s

Please ensure that the necessary actions are taken to resolve the issue.

This is an automated notification. If you have already resolved the issue after this e-mail was generated, no further action is required.

Thank you,
UniField Team""") % (exp_sign_user_list,)

                tools.email_send(False, [], email_subject, email_body, email_bcc=email_doc_creators)
            except Exception as e:
                if isinstance(e, osv.except_osv):
                    error_msg = e.value
                else:
                    error_msg = e.args and '. '.join(e.args) or e
            finally:
                msg = error_msg and _('Some error(s) occurred while trying to send the email: %s') % (error_msg,) or\
                      _('The signature of %s is expired. The email was sent to users in the "Sign_document_creator_finance" and "Sign_document_creator_supply" successfully') % (', '.join(usernames)),
                email_log_vals = {
                    'recipients': '; '.join(email_doc_creators),
                    'recipient_names': '; '.join(name_doc_creators),
                    'state': error_msg and 'error' or 'success',
                    'result': msg,
                    'sender_model_id': self.pool.get('ir.model').search(cr, 1, [('model', '=', self._name)])[0],
                    'date_sent': datetime.now(),
                    'user_id': hasattr(uid, 'realUid') and uid.realUid or uid,
                }
                self.pool.get('email.log').create(cr, uid, email_log_vals, context=context)

        return True


email_signature_notification()


class email_signature_notification_doc_applicability(osv.osv):
    _name = 'email.signature.notification.doc.applicability'
    _description = 'Email Notification for Signatures Document Applicability'

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
        'email_sign_notif_id': fields.many2one('email.signature.notification', string='Email Notification for Signatures', readonly=True),
    }

    _defaults = {
        'active': False,
    }

    def active_doc_type(self, cr, uid, doc_type, doc_id, context=None):
        """
        Return True if the given document type is applicable for email notification for signatures
        """
        if context is None:
            context = {}
        res = False
        if doc_type and doc_id:
            doc_obj = self.pool.get(doc_type)
            doc = doc_obj.browse(cr, uid, doc_id, context=context)
            if doc:
                doc_applicability_type = ''
                if doc_type == 'sale.order':
                    if doc.procurement_request:
                        doc_applicability_type = 'sale.order.ir'
                    else:
                        doc_applicability_type = 'sale.order.fo'
                elif doc_type == 'purchase.order':
                    doc_applicability_type = 'purchase.order'
                elif doc_type == 'stock.picking':
                    if doc.type == 'in' and doc.subtype == 'standard':
                        doc_applicability_type = 'stock.picking.in'
                    elif doc.type == 'internal' and doc.subtype == 'standard':
                        doc_applicability_type = 'stock.picking.int'
                    elif doc.type == 'out' and doc.subtype == 'standard':
                        doc_applicability_type = 'stock.picking.out'
                    elif doc.type == 'out' and doc.subtype == 'picking':
                        doc_applicability_type = 'stock.picking.pick'
                elif doc_type == 'account.bank.statement':
                    if doc.journal_id.type == 'cash':
                        doc_applicability_type = 'account.bank.statement.cash'
                    elif doc.journal_id.type == 'bank':
                        doc_applicability_type = 'account.bank.statement.bank'
                    elif doc.journal_id.type == 'cheque':
                        doc_applicability_type = 'account.bank.statement.cheque'
                elif doc_type == 'account.invoice':
                    doc_applicability_type = 'account.invoice'
                elif doc_type == 'physical.inventory':
                    doc_applicability_type = 'physical.inventory'

                if doc_applicability_type:
                    res = self.search_exist(cr, uid, [('active', '=', 't'), ('doc_type', '=', doc_applicability_type)], context=context)

        return res


email_signature_notification_doc_applicability()
