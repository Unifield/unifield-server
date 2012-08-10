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

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

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
        Give matches period that are not draft and not HQ-closed from given date
        """
        # Some verifications
        if not context:
            context = {}
        if not inv:
            return False
        # NB: there is some period state. So we define that we choose only open period (so not draft and not done)
        res = self.pool.get('account.period').search(cr, uid, [('date_start','<=',inv.date_invoice or strftime('%Y-%m-%d')),
            ('date_stop','>=',inv.date_invoice or strftime('%Y-%m-%d')), ('state', 'not in', ['created', 'done']), 
            ('company_id', '=', inv.company_id.id)], context=context, order="date_start ASC, name ASC")
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
                line = sequence.get_id(test='id', context=context)
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
                    il_number = sequence.get_id(test='id', context=context)
                    vals.update({'line_number': il_number})
        return super(account_invoice_line, self).write(cr, uid, ids, vals, context)

account_invoice_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
