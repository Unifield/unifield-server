#!/usr/bin/env python
#-*- encoding:utf-8 -*-
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


from osv import osv
from osv import fields
from time import strftime
from tools.translate import _
from lxml import etree
import re

import decimal_precision as dp

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    def _get_invoice_report_name(self, cr, uid, ids, context=None):
        '''
        Returns the name of the invoice according to its type
        '''
        if isinstance(ids, list):
            ids = ids[0]

        inv = self.browse(cr, uid, ids, context=context)
        inv_name = inv.number or inv.name or 'No_description'
        prefix = 'STV_'

        if inv.type == 'out_refund': # Customer refund
            prefix = 'CR_'
        elif inv.type == 'in_refund': # Supplier refund
            prefix = 'SR_'
        elif inv.type == 'out_invoice':
            # Stock transfer voucher
            prefix = 'STV_'
            # Debit note
            if inv.is_debit_note and not inv.is_inkind_donation and not inv.is_intermission:
                prefix = 'DN_'
            # Intermission voucher OUT
            elif not inv.is_debit_note and not inv.is_inkind_donation and inv.is_intermission:
                prefix = 'IMO_'
        elif inv.type == 'in_invoice':
            # Supplier invoice
            prefix = 'SI_'
            # Intermission voucher IN
            if not inv.is_debit_note and not inv.is_inkind_donation and inv.is_intermission:
                prefix = 'IMI_'
            # Direct invoice
            elif inv.is_direct_invoice:
                prefix = 'DI_'
            # In-kind donation
            elif not inv.is_debit_note and inv.is_inkind_donation:
                prefix = 'DON_'
        return '%s%s' % (prefix, inv_name)

    def _get_journal(self, cr, uid, context=None):
        """
        WARNING: This method has been taken from account module from OpenERP
        """
        # @@@override@account.invoice.py
        if context is None:
            context = {}
        type_inv = context.get('type', 'out_invoice')
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        company_id = context.get('company_id', user.company_id.id)
        type2journal = {'out_invoice': 'sale', 'in_invoice': 'purchase', 'out_refund': 'sale_refund', 'in_refund': 'purchase_refund'}
        refund_journal = {'out_invoice': False, 'in_invoice': False, 'out_refund': True, 'in_refund': True}
        args = [('type', '=', type2journal.get(type_inv, 'sale')),
                ('company_id', '=', company_id),
                ('refund_journal', '=', refund_journal.get(type_inv, False))]
        if user.company_id.instance_id:
            args.append(('is_current_instance','=',True))
        journal_obj = self.pool.get('account.journal')
        res = journal_obj.search(cr, uid, args, limit=1)
        return res and res[0] or False

    def _get_fake(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Fake method for 'ready_for_import_in_debit_note' field
        """
        res = {}
        for i in ids:
            res[i] = False
        return res

    def _search_ready_for_import_in_debit_note(self, cr, uid, obj, name, args, context=None):
        if not args:
            return []
        account_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.import_invoice_default_account and \
            self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.import_invoice_default_account.id or False
        if not account_id:
            raise osv.except_osv(_('Error'), _('No default account for import invoice on Debit Note!'))
        dom1 = [
            ('account_id','=',account_id),
            ('reconciled','=',False),
            ('state', '=', 'open'),
            ('type', '=', 'out_invoice'),
            ('journal_id.type', 'in', ['sale']),
            ('partner_id.partner_type', '=', 'section'),
        ]
        return dom1+[('is_debit_note', '=', False)]

    def _get_fake_m2o_id(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Get many2one field content
        """
        res = {}
        name = field_name.replace("fake_", '')
        for i in self.browse(cr, uid, ids):
            if context and context.get('is_intermission', False):
                res[i.id] = False
                if name == 'account_id':
                    user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)
                    if user[0].company_id.intermission_default_counterpart:
                        res[i.id] = user[0].company_id.intermission_default_counterpart.id
                elif name == 'journal_id':
                    int_journal_id = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'intermission')], context=context)
                    if int_journal_id:
                        if isinstance(int_journal_id, (int, long)):
                            int_journal_id = [int_journal_id]
                        res[i.id] = int_journal_id[0]
                elif name == 'currency_id':
                    user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)
                    if user[0].company_id.currency_id:
                        res[i.id] = user[0].company_id.currency_id.id
            else:
                res[i.id] = getattr(i, name, False) and getattr(getattr(i, name, False), 'id', False) or False
        return res

    def onchange_company_id(self, cr, uid, ids, company_id, part_id, type, invoice_line, currency_id):
        """
        This is a method to redefine the journal_id domain with the current_instance taken into account
        """
        res = super(account_invoice, self).onchange_company_id(cr, uid, ids, company_id, part_id, type, invoice_line, currency_id)
        if company_id and type:
            res.setdefault('domain', {})
            res.setdefault('value', {})
            ass = {
                'out_invoice': 'sale',
                'in_invoice': 'purchase',
                'out_refund': 'sale_refund',
                'in_refund': 'purchase_refund',
            }
            journal_ids = self.pool.get('account.journal').search(cr, uid, [
                ('company_id','=',company_id), ('type', '=', ass.get(type, 'purchase')), ('is_current_instance', '=', True)
            ])
            if not journal_ids:
                raise osv.except_osv(_('Configuration Error !'), _('Can\'t find any account journal of %s type for this company.\n\nYou can create one in the menu: \nConfiguration\Financial Accounting\Accounts\Journals.') % (ass.get(type, 'purchase'), ))
            res['value']['journal_id'] = journal_ids[0]
            # TODO: it's very bad to set a domain by onchange method, no time to rewrite UniField !
            res['domain']['journal_id'] = [('id', 'in', journal_ids)]
        return res

    _columns = {
        'from_yml_test': fields.boolean('Only used to pass addons unit test', readonly=True, help='Never set this field to true !'),
        'sequence_id': fields.many2one('ir.sequence', string='Lines Sequence', ondelete='cascade',
            help="This field contains the information related to the numbering of the lines of this order."),
        'date_invoice': fields.date('Posting Date', states={'paid':[('readonly',True)], 'open':[('readonly',True)],
            'close':[('readonly',True)]}, select=True),
        'document_date': fields.date('Document Date', states={'paid':[('readonly',True)], 'open':[('readonly',True)],
            'close':[('readonly',True)]}, select=True),
        'is_debit_note': fields.boolean(string="Is a Debit Note?"),
        'is_inkind_donation': fields.boolean(string="Is an In-kind Donation?"),
        'is_intermission': fields.boolean(string="Is an Intermission Voucher?"),
        'ready_for_import_in_debit_note': fields.function(_get_fake, fnct_search=_search_ready_for_import_in_debit_note, type="boolean",
            method=True, string="Can be imported as invoice in a debit note?",),
        'imported_invoices': fields.one2many('account.invoice.line', 'import_invoice_id', string="Imported invoices", readonly=True),
        'partner_move_line': fields.one2many('account.move.line', 'invoice_partner_link', string="Partner move line", readonly=True),
        'fake_account_id': fields.function(_get_fake_m2o_id, method=True, type='many2one', relation="account.account", string="Account", readonly="True"),
        'fake_journal_id': fields.function(_get_fake_m2o_id, method=True, type='many2one', relation="account.journal", string="Journal", readonly="True"),
        'fake_currency_id': fields.function(_get_fake_m2o_id, method=True, type='many2one', relation="res.currency", string="Currency", readonly="True"),
    }

    _defaults = {
        'journal_id': _get_journal,
        'from_yml_test': lambda *a: False,
        'date_invoice': lambda *a: strftime('%Y-%m-%d'),
        'is_debit_note': lambda obj, cr, uid, c: c.get('is_debit_note', False),
        'is_inkind_donation': lambda obj, cr, uid, c: c.get('is_inkind_donation', False),
        'is_intermission': lambda obj, cr, uid, c: c.get('is_intermission', False),
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):
        """
        Rename Supplier/Customer to "Donor" if view_type == tree
        """
        if not context:
            context = {}
        res = super(account_invoice, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        if view_type == 'tree' and (context.get('journal_type', False) == 'inkind' or context.get('journal_type', False) == 'intermission'):
            doc = etree.XML(res['arch'])
            nodes = doc.xpath("//field[@name='partner_id']")
            name = _('Donor')
            if context.get('journal_type') == 'intermission':
                name = _('Partner')
            for node in nodes:
                node.set('string', name)
            res['arch'] = etree.tostring(doc)
        return res

    def copy_data(self, cr, uid, inv_id, default=None, context=None):
        """
        Copy an invoice line without its move lines
        """
        if default is None:
            default = {}
        default.update({'move_lines': False,})
        return super(account_invoice_line, self).copy_data(cr, uid, inv_id, default, context)

    def default_get(self, cr, uid, fields, context=None):
        """
        Fill in fake account and fake currency for intermission invoice (in context).
        """
        defaults = super(account_invoice, self).default_get(cr, uid, fields, context=context)
        if context and context.get('is_intermission', False):
            intermission_type = context.get('intermission_type', False)
            if intermission_type in ('in', 'out'):
                # UF-2270: manual intermission (in or out)
                if defaults is None:
                    defaults = {}
                user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)
                if user and user[0] and user[0].company_id:
                    # get company default currency
                    if user[0].company_id.currency_id:
                        defaults['fake_currency_id'] = user[0].company_id.currency_id.id
                        defaults['currency_id'] = defaults['fake_currency_id']
                    # get 'intermission counter part' account
                    if user[0].company_id.intermission_default_counterpart:
                        defaults['fake_account_id'] = user[0].company_id.intermission_default_counterpart.id
                        defaults['account_id'] = defaults['fake_account_id']
                    else:
                        raise osv.except_osv("Error","Company Intermission Counterpart Account must be set")
                # 'INT' intermission journal
                int_journal_id = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'intermission')], context=context)
                if int_journal_id:
                    if isinstance(int_journal_id, (int, long)):
                        int_journal_id = [int_journal_id]
                    defaults['fake_journal_id'] = int_journal_id[0]
                    defaults['journal_id'] = defaults['fake_journal_id']
        return defaults

    def create_sequence(self, cr, uid, vals, context=None):
        """
        Create new entry sequence for every new invoice
        """
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        name = 'Invoice L' # For Invoice Lines
        code = 'account.invoice'

        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)

        seq = {
            'name': name,
            'code': code,
            'prefix': '',
            'padding': 0,
        }
        return seq_pool.create(cr, uid, seq)

    def log(self, cr, uid, inv_id, message, secondary=False, context=None):
        """
        Change first "Invoice" word from message into "Debit Note" if this invoice is a debit note.
        Change it to "In-kind donation" if this invoice is an In-kind donation.
        """
        if not context:
            context = {}
        # Prepare some values
        # Search donation view and return it
        try:
            # try / except for runbot
            debit_res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_msf', 'view_debit_note_form')
            inkind_res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_msf', 'view_inkind_donation_form')
            intermission_res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_msf', 'view_intermission_form')
            supplier_invoice_res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'invoice_supplier_form')
            customer_invoice_res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'invoice_form')
        except ValueError:
            return super(account_invoice, self).log(cr, uid, inv_id, message, secondary, context)
        debit_view_id = debit_res and debit_res[1] or False
        debit_note_ctx = {'view_id': debit_view_id, 'type':'out_invoice', 'journal_type': 'sale', 'is_debit_note': True}
        # Search donation view and return it
        inkind_view_id = inkind_res and inkind_res[1] or False
        inkind_ctx = {'view_id': inkind_view_id, 'type':'in_invoice', 'journal_type': 'inkind', 'is_inkind_donation': True}
        # Search intermission view
        intermission_view_id = intermission_res and intermission_res[1] or False
        intermission_ctx = {'view_id': intermission_view_id, 'journal_type': 'intermission', 'is_intermission': True}
        customer_view_id = customer_invoice_res[1] or False
        customer_ctx = {'view_id': customer_view_id, 'type': 'out_invoice', 'journal_type': 'sale'}
        message_changed = False
        pattern = re.compile('^(Invoice)')
        for el in [('is_debit_note', 'Debit Note', debit_note_ctx), ('is_inkind_donation', 'In-kind Donation', inkind_ctx), ('is_intermission', 'Intermission Voucher', intermission_ctx)]:
            if self.read(cr, uid, inv_id, [el[0]]).get(el[0], False) is True:
                m = re.match(pattern, message)
                if m and m.groups():
                    message = re.sub(pattern, el[1], message, 1)
                    message_changed = True
                context.update(el[2])
        # UF-1112: Give all customer invoices a name as "Stock Transfer Voucher".
        if not message_changed and self.read(cr, uid, inv_id, ['type']).get('type', False) == 'out_invoice':
            message = re.sub(pattern, 'Stock Transfer Voucher', message, 1)

            context.update(customer_ctx)
        # UF-1307: for supplier invoice log (from the incoming shipment), the context was not
        # filled with all the information; this leaded to having a "Sale" journal in the supplier
        # invoice if it was saved after coming from this link. Here's the fix.
        if (not context.get('journal_type', False) and context.get('type', False) == 'in_invoice'):
            supplier_view_id = supplier_invoice_res and supplier_invoice_res[1] or False
            context.update({'journal_type': 'purchase',
                            'view_id': supplier_view_id})
        return super(account_invoice, self).log(cr, uid, inv_id, message, secondary, context)

    def onchange_partner_id(self, cr, uid, ids, type, partner_id,\
        date_invoice=False, payment_term=False, partner_bank_id=False, company_id=False, is_inkind_donation=False, is_intermission=False):
        """
        Update fake_account_id field regarding account_id result.
        Get default donation account for Donation invoices.
        Get default intermission account for Intermission Voucher IN/OUT invoices.
        Get default currency from partner if this one is linked to a pricelist.
        Ticket utp917 - added code to avoid currency cd change if a direct invoice
        """
        res = super(account_invoice, self).onchange_partner_id(cr, uid, ids, type, partner_id, date_invoice, payment_term, partner_bank_id, company_id)
        if is_inkind_donation and partner_id:
            partner = self.pool.get('res.partner').browse(cr, uid, partner_id)
            account_id = partner and partner.donation_payable_account and partner.donation_payable_account.id or False
            res['value']['account_id'] = account_id
        if is_intermission and partner_id:
            intermission_default_account = self.pool.get('res.users').browse(cr, uid, uid).company_id.intermission_default_counterpart
            account_id = intermission_default_account and intermission_default_account.id or False
            if not account_id:
                raise osv.except_osv(_('Error'), _('Please configure a default intermission account in Company configuration.'))
            res['value']['account_id'] = account_id
        if res.get('value', False) and 'account_id' in res['value']:
            res['value'].update({'fake_account_id': res['value'].get('account_id')})
        if partner_id and type:
            p = self.pool.get('res.partner').browse(cr, uid, partner_id)
            if ids: #utp917
                ai = self.browse(cr, uid, ids)[0]
            if p:
                c_id = False
                if type in ['in_invoice', 'out_refund'] and p.property_product_pricelist_purchase:
                    c_id = p.property_product_pricelist_purchase.currency_id.id
                elif type in ['out_invoice', 'in_refund'] and p.property_product_pricelist:
                    c_id = p.property_product_pricelist.currency_id.id
                if ids:
                    if c_id and not ai.is_direct_invoice:   #utp917
                        if not res.get('value', False):
                            res['value'] = {'currency_id': c_id}
                        else:
                            res['value'].update({'currency_id': c_id})
        return res

    def _check_document_date(self, cr, uid, ids):
        """
        Check that document's date is done BEFORE posting date
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        for i in self.browse(cr, uid, ids):
            if i.document_date and i.date_invoice and i.date_invoice < i.document_date:
                raise osv.except_osv(_('Error'), _('Posting date should be later than Document Date.'))
        return True

    def _refund_cleanup_lines(self, cr, uid, lines):
        """
        Remove useless fields
        """
        for line in lines:
            del line['move_lines']
            del line['import_invoice_id']
        res = super(account_invoice, self)._refund_cleanup_lines(cr, uid, lines)
        return res

    def create(self, cr, uid, vals, context=None):
        """
        Filled in 'from_yml_test' to True if we come from tests
        """
        if not context:
            context = {}
        # Create a sequence for this new invoice
        res_seq = self.create_sequence(cr, uid, vals, context)
        vals.update({'sequence_id': res_seq,})
        # UTP-317 # Check that no inactive partner have been used to create this invoice
        if 'partner_id' in vals:
            partner_id = vals.get('partner_id')
            if isinstance(partner_id, (str)):
                partner_id = int(partner_id)
            partner = self.pool.get('res.partner').browse(cr, uid, [partner_id])
            active = True
            if partner and partner[0] and not partner[0].active:
                raise osv.except_osv(_('Warning'), _("Partner '%s' is not active.") % (partner[0] and partner[0].name or '',))
        return super(account_invoice, self).create(cr, uid, vals, context)

    def action_reconcile_imported_invoice(self, cr, uid, ids, context=None):
        """
        Reconcile each imported invoice with its attached invoice line
        """
        # some verifications
        if isinstance(ids, (int, long)):
            ids = [ids]
        # browse all given invoices
        for inv in self.browse(cr, uid, ids):
            for invl in inv.invoice_line:
                if not invl.import_invoice_id:
                    continue
                imported_invoice = invl.import_invoice_id
                # reconcile partner line from import invoice with this invoice line attached move line
                import_invoice_partner_move_lines = self.pool.get('account.move.line').search(cr, uid, [('invoice_partner_link', '=', imported_invoice.id)])
                invl_move_lines = [x.id or None for x in invl.move_lines]
                rec = self.pool.get('account.move.line').reconcile_partial(cr, uid, [import_invoice_partner_move_lines[0], invl_move_lines[0]], 'auto', context=context)
                if not rec:
                    return False
        return True

    def action_cancel(self, cr, uid, ids, *args):
        """
        Reverse move if this object is a In-kind Donation. Otherwise do normal job: cancellation.
        """
        to_cancel = []
        for i in self.browse(cr, uid, ids):
            if i.is_inkind_donation:
                move_id = i.move_id.id
                tmp_res = self.pool.get('account.move').reverse(cr, uid, [move_id], strftime('%Y-%m-%d'))
                # If success change invoice to cancel and detach move_id
                if tmp_res:
                    # Change invoice state
                    self.write(cr, uid, [i.id], {'state': 'cancel', 'move_id':False})
                continue
            to_cancel.append(i.id)
        return super(account_invoice, self).action_cancel(cr, uid, to_cancel, args)

    def action_date_assign(self, cr, uid, ids, *args):
        """
        Check Document date.
        Add it if we come from a YAML test.
        """
        # Default behaviour to add date
        res = super(account_invoice, self).action_date_assign(cr, uid, ids, args)
        # Process invoices
        for i in self.browse(cr, uid, ids):
            if not i.date_invoice:
                self.write(cr, uid, i.id, {'date_invoice': strftime('%Y-%m-%d')})
                i = self.browse(cr, uid, i.id) # This permit to refresh the browse of this element
            if not i.document_date and i.from_yml_test:
                self.write(cr, uid, i.id, {'document_date': i.date_invoice})
            if not i.document_date and not i.from_yml_test:
                raise osv.except_osv(_('Warning'), _('Document Date is a mandatory field for validation!'))
        # Posting date should not be done BEFORE document date
        self._check_document_date(cr, uid, ids)
        return res

    def action_open_invoice(self, cr, uid, ids, context=None, *args):
        """
        Give function to use when changing invoice to open state
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not self.action_date_assign(cr, uid, ids, context, args):
            return False
        if not self.action_move_create(cr, uid, ids, context, args):
            return False
        if not self.action_number(cr, uid, ids, context):
            return False
        if not self.action_reconcile_imported_invoice(cr, uid, ids, context):
            res = False
        return True

    def _hook_period_id(self, cr, uid, inv, context=None):
        """
        Give matches period that are not draft and not HQ-closed from given date.
        Do not use special periods as period 13, 14 and 15.
        """
        # Some verifications
        if not context:
            context = {}
        if not inv:
            return False
        # NB: there is some period state. So we define that we choose only open period (so not draft and not done)
        res = self.pool.get('account.period').search(cr, uid, [('date_start','<=',inv.date_invoice or strftime('%Y-%m-%d')),
            ('date_stop','>=',inv.date_invoice or strftime('%Y-%m-%d')), ('state', 'not in', ['created', 'done']),
            ('company_id', '=', inv.company_id.id), ('special', '=', False)], context=context, order="date_start ASC, name ASC")
        return res

    def line_get_convert(self, cr, uid, x, part, date, context=None):
        """
        Add these field into invoice line:
        - invoice_line_id
        """
        if not context:
            context = {}
        res = super(account_invoice, self).line_get_convert(cr, uid, x, part, date, context)
        res.update({'invoice_line_id': x.get('invoice_line_id', False)})
        return res

    def finalize_invoice_move_lines(self, cr, uid, inv, line):
        """
        Hook that changes move line data before write them.
        Add a link between partner move line and invoice.
        Add invoice document date to data.
        """
        def is_partner_line(dico):
            if isinstance(dico, dict):
                if dico:
                    # In case where no amount_currency filled in, then take debit - credit for amount comparison
                    amount = dico.get('amount_currency', False) or (dico.get('debit', 0.0) - dico.get('credit', 0.0))
                    if amount == inv.amount_total and dico.get('partner_id', False) == inv.partner_id.id:
                        return True
            return False
        new_line = []
        for el in line:
            if el[2]:
                el[2].update({'document_date': inv.document_date})
            if el[2] and is_partner_line(el[2]):
                el[2].update({'invoice_partner_link': inv.id})
                new_line.append((el[0], el[1], el[2]))
            else:
                new_line.append(el)
        return super(account_invoice, self).finalize_invoice_move_lines(cr, uid, inv, new_line)

    def button_debit_note_import_invoice(self, cr, uid, ids, context=None):
        """
        Launch wizard that permits to import invoice on a debit note
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse all given invoices
        for inv in self.browse(cr, uid, ids):
            if inv.type != 'out_invoice' or inv.is_debit_note == False:
                raise osv.except_osv(_('Error'), _('You can only do import invoice on a Debit Note!'))
            w_id = self.pool.get('debit.note.import.invoice').create(cr, uid, {'invoice_id': inv.id, 'currency_id': inv.currency_id.id,
                'partner_id': inv.partner_id.id}, context=context)
            context.update({
                'active_id': inv.id,
                'active_ids': ids,
            })
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'debit.note.import.invoice',
                'name': 'Import invoice',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': w_id,
                'context': context,
                'target': 'new',
            }

    def button_split_invoice(self, cr, uid, ids, context=None):
        """
        Launch the split invoice wizard to split an invoice in two elements.
        """
        # Some verifications
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some value
        wiz_lines_obj = self.pool.get('wizard.split.invoice.lines')
        inv_lines_obj = self.pool.get('account.invoice.line')
        # Creating wizard
        wizard_id = self.pool.get('wizard.split.invoice').create(cr, uid, {'invoice_id': ids[0]}, context=context)
        # Add invoices_lines into the wizard
        invoice_line_ids = self.pool.get('account.invoice.line').search(cr, uid, [('invoice_id', '=', ids[0])], context=context)
        # Some other verifications
        if not len(invoice_line_ids):
            raise osv.except_osv(_('Error'), _('No invoice line in this invoice or not enough elements'))
        for invl in inv_lines_obj.browse(cr, uid, invoice_line_ids, context=context):
            wiz_lines_obj.create(cr, uid, {'invoice_line_id': invl.id, 'product_id': invl.product_id.id, 'quantity': invl.quantity,
                'price_unit': invl.price_unit, 'description': invl.name, 'wizard_id': wizard_id}, context=context)
        # Return wizard
        if wizard_id:
            return {
                'name': "Split Invoice",
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.split.invoice',
                'target': 'new',
                'view_mode': 'form,tree',
                'view_type': 'form',
                'res_id': [wizard_id],
                'context':
                {
                    'active_id': ids[0],
                    'active_ids': ids,
                    'wizard_id': wizard_id,
                }
            }
        return False

    def copy(self, cr, uid, id, default={}, context=None):
        """
        Delete period_id from invoice.
        Check context for splitting invoice.
        """
        # Some checks
        if context is None:
            context = {}
        if default is None:
            default = {}
        default.update({
            'period_id': False,
            'partner_move_line': False,
            'imported_invoices': False
        })
        # Default behaviour
        new_id = super(account_invoice, self).copy(cr, uid, id, default, context)
        # Case where you split an invoice
        if 'split_it' in context:
            purchase_obj = self.pool.get('purchase.order')
            sale_obj = self.pool.get('sale.order')
            if purchase_obj:
                # attach new invoice to PO
                purchase_ids = purchase_obj.search(cr, uid, [('invoice_ids', 'in', [id])], context=context)
                if purchase_ids:
                    purchase_obj.write(cr, uid, purchase_ids, {'invoice_ids': [(4, new_id)]}, context=context)
            if sale_obj:
                # attach new invoice to SO
                sale_ids = sale_obj.search(cr, uid, [('invoice_ids', 'in', [id])], context=context)
                if sale_ids:
                    sale_obj.write(cr, uid, sale_ids, {'invoice_ids': [(4, new_id)]}, context=context)
        return new_id

    def __hook_lines_before_pay_and_reconcile(self, cr, uid, lines):
        """
        Add document date to account_move_line before pay and reconcile
        """
        for line in lines:
            if line[2] and 'date' in line[2] and not line[2].get('document_date', False):
                line[2].update({'document_date': line[2].get('date')})
        return lines

    def write(self, cr, uid, ids, vals, context=None):
        """
        Check document_date
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(account_invoice, self).write(cr, uid, ids, vals, context=context)
        self._check_document_date(cr, uid, ids)
        return res

account_invoice()

class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    def _uom_constraint(self, cr, uid, ids, context=None):
        for obj in self.browse(cr, uid, ids, context=context):
            if not self.pool.get('uom.tools').check_uom(cr, uid, obj.product_id.id, obj.uos_id.id, context):
                raise osv.except_osv(_('Error'), _('You have to select a product UOM in the same category than the purchase UOM of the product !'))
        return True

    _constraints = [(_uom_constraint, 'Constraint error on Uom', [])]

    _columns = {
        'from_yml_test': fields.boolean('Only used to pass addons unit test', readonly=True, help='Never set this field to true !'),
        'line_number': fields.integer(string='Line Number'),
        'price_unit': fields.float('Unit Price', required=True, digits_compute= dp.get_precision('Account Computation')),
        'import_invoice_id': fields.many2one('account.invoice', string="From an import invoice", readonly=True),
        'move_lines': fields.one2many('account.move.line', 'invoice_line_id', string="Journal Item", readonly=True),
    }

    _defaults = {
        'price_unit': lambda *a: 0.00,
        'from_yml_test': lambda *a: False,
    }

    _order = 'line_number'

    def create(self, cr, uid, vals, context=None):
        """
        Filled in 'from_yml_test' to True if we come from tests.
        Give a line_number to invoice line.
        NB: This appends only for account invoice line and not other object (for an example direct invoice line)
        """
        if not context:
            context = {}
        # Create new number with invoice sequence
        if vals.get('invoice_id') and self._name in ['account.invoice.line']:
            invoice = self.pool.get('account.invoice').browse(cr, uid, vals['invoice_id'])
            if invoice and invoice.sequence_id:
                sequence = invoice.sequence_id
                line = sequence.get_id(code_or_id='id', context=context)
                vals.update({'line_number': line})
        return super(account_invoice_line, self).create(cr, uid, vals, context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Give a line_number in invoice_id in vals
        NB: This appends only for account invoice line and not other object (for an example direct invoice line)
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if vals.get('invoice_id') and self._name in ['account.invoice.line']:
            for il in self.browse(cr, uid, ids):
                if not il.line_number and il.invoice_id.sequence_id:
                    sequence = il.invoice_id.sequence_id
                    il_number = sequence.get_id(code_or_id='id', context=context)
                    vals.update({'line_number': il_number})
        return super(account_invoice_line, self).write(cr, uid, ids, vals, context)

    def copy(self, cr, uid, id, default=None, context=None):
        """
        Check context to see if we come from a split. If yes, we create the link between invoice and PO/FO.
        """
        if not context:
            context = {}
        if not default:
            default = {}

        new_id = super(account_invoice_line, self).copy(cr, uid, id, default, context)

        if 'split_it' in context:
            purchase_lines_obj = self.pool.get('purchase.order.line')
            sale_lines_obj = self.pool.get('sale.order.line')

            if purchase_lines_obj:
                purchase_line_ids = purchase_lines_obj.search(cr, uid, [('invoice_lines', 'in', [id])])
                if purchase_line_ids:
                    purchase_lines_obj.write(cr, uid, purchase_line_ids, {'invoice_lines': [(4, new_id)]})

            if sale_lines_obj:
                sale_lines_ids =  sale_lines_obj.search(cr, uid, [('invoice_lines', 'in', [id])])
                if sale_lines_ids:
                    sale_lines_obj.write(cr, uid,  sale_lines_ids, {'invoice_lines': [(4, new_id)]})

        return new_id

    def move_line_get_item(self, cr, uid, line, context=None):
        """
        Add a link between move line and its invoice line
        """
        # some verification
        if not context:
            context = {}
        # update default dict with invoice line ID
        res = super(account_invoice_line, self).move_line_get_item(cr, uid, line, context=context)
        res.update({'invoice_line_id': line.id})
        return res

account_invoice_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
