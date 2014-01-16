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
import logging
import datetime

import decimal_precision as dp

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    
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
    }

    _defaults = {
        'journal_id': _get_journal,
        'from_yml_test': lambda *a: False,
        'date_invoice': lambda *a: strftime('%Y-%m-%d'),
    }

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

    def create(self, cr, uid, vals, context=None):
        """
        Filled in 'from_yml_test' to True if we come from tests
        """
        if not context:
            context = {}
        if context.get('update_mode') in ['init', 'update']:
            logging.getLogger('init').info('INV: set from yml test to True')
            vals['from_yml_test'] = True
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
        if not self.action_date_assign(cr, uid, ids, context, args):
            return False
        if not self.action_move_create(cr, uid, ids, context, args):
            return False
        if not self.action_number(cr, uid, ids, context):
            return False
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

    def finalize_invoice_move_lines(self, cr, uid, inv, line):
        """
        Hook that changes move line data before write them.
        Add invoice document date to data.
        """
        res = super(account_invoice, self).finalize_invoice_move_lines(cr, uid, inv, line)
        new_line = []
        for el in line:
            if el[2]:
                el[2].update({'document_date': inv.document_date})
        return res

    def copy(self, cr, uid, id, default={}, context=None):
        """
        Delete period_id from invoice
        """
        if default is None:
            default = {}
        default.update({'period_id': False,})
        return super(account_invoice, self).copy(cr, uid, id, default, context)

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

    _columns = {
        'from_yml_test': fields.boolean('Only used to pass addons unit test', readonly=True, help='Never set this field to true !'),
        'line_number': fields.integer(string='Line Number'),
        'price_unit': fields.float('Unit Price', required=True, digits_compute= dp.get_precision('Account Computation')),
    }

    _defaults = {
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
        if context.get('update_mode') in ['init', 'update']:
            logging.getLogger('init').info('INV: set from yml test to True')
            vals['from_yml_test'] = True
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

account_invoice_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
