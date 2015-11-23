#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 TeMPO Consulting, MSF. All Rights Reserved
#    All Rigts Reserved
#    Developer: Fabien MORIN
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
from tools.translate import _
import decimal_precision as dp


class account_direct_invoice_wizard(osv.osv_memory):
    _name = 'account.direct.invoice.wizard'
    _description = 'Account Invoice Temp Object'
    _columns = {
            'account_id': fields.many2one('account.account', 'Account',
                required=True, readonly=True,
                states={'draft':[('readonly', False)]},
                help="The partner account used for this invoice."),
            'address_contact_id': fields.many2one('res.partner.address',
                'Contact Address', readonly=True,
                states={'draft':[('readonly',False)]}),
            'address_invoice_id': fields.many2one('res.partner.address',
                'Invoice Address', readonly=True, required=False),
            'amount_total':fields.float(string="Total amount", size=64,
                readonly=True),
            'analytic_distribution_id':
            fields.many2one('analytic.distribution', 'Analytic Distribution',
                select="1"),
            'check_total': fields.float('Total',
                digits_compute=dp.get_precision('Account'),
                states={'open':[('readonly', True)],
                        'close':[('readonly', True)],
                        'paid':[('readonly', True)]}),
            'comment': fields.text('Additional Information'),
            'company_id': fields.many2one('res.company', 'Company',
                required=True, change_default=True, readonly=True,
                states={'draft':[('readonly',False)]}),
            'currency_id': fields.many2one('res.currency', string="Currency"),
            'date_invoice': fields.date('Posting Date', select=True),
            'document_date': fields.date('Document date', readonly=True),
            'fake_currency_id': fields.many2one('res.currency',
                string="Currency"),
            'invoice_line': fields.one2many('account.direct.invoice.wizard.line',
                'invoice_id', 'Invoice Lines', readonly=True,
                states={'draft':[('readonly',False)]}),
            'is_direct_invoice': fields.boolean("Is direct invoice?",
                readonly=True, default=True),
            'is_temp_object': fields.boolean('is it a temp object in RAM',
                readonly=True, help='This is automatic field'),
            'journal_id': fields.many2one('account.journal', 'Journal',
                required=True, readonly=True),
            'name': fields.char('Description', size=64, select=True,
                readonly=True, states={'draft':[('readonly',False)]}),
            'number': fields.related('move_id','name', type='char',
                readonly=True, size=64, relation='account.move', store=True,
                string='Number'),
            'origin': fields.char('Source Document', size=512,
                help="Referencie of the document that produced this invoice.",
                readonly=True, states={'draft':[('readonly',False)]}),
            'partner_id': fields.many2one('res.partner', 'Partner',
                change_default=True, readonly=True, required=True),
            'partner_bank_id': fields.many2one('res.partner.bank',
                                               'Bank Account',
                    help='Bank Account Number, Company bank account if '
                    'Invoice is customer or supplier refund, otherwise '
                    'Partner bank account number.', readonly=True,
                            states={'draft':[('readonly',False)]}),
            'payment_term': fields.many2one('account.payment.term',
                'Payment Term',readonly=True, states={'draft':[('readonly',False)]},
                help="If you use payment terms, the due date will be computed "
                "automatically at the generation of accounting entries. If you"
                " keep the payment term and the due date empty, it means "
                "direct payment. The payment term may compute several due "
                "dates, for example 50% now, 50% in one month."),
            'reference': fields.char('Invoice Reference', size=64,
                help="The partner reference of this invoice."),
            'register_posting_date': fields.date(string=\
                    "Register posting date for Direct Invoice", required=False),
            'user_id': fields.many2one('res.users', 'Salesman', readonly=True),
            'state': fields.selection([
                ('draft','Draft'),
                ('proforma','Pro-forma'),
                ('proforma2','Pro-forma'),
                ('open','Open'),
                ('paid','Paid'),
                ('cancel','Cancelled')
                ],'State', select=True, readonly=True,),
            }


    def button_dummy_compute_total(self, cr, uid, ids, context=None):
        #XXX à écrire
        return True

    def button_close_direct_invoice(self, cr, uid, ids, context=None):
        #XXX ici on devra faire le taf de copier tous les éléments temporaires
        # dans de vrais élément puis d'appeler le vrais
        # button_close_direct_invoice ou au moins les fonction qu'il appelle
        # voir unifield_wm/register_accounting/invoice.py +363
        import pdb; pdb.set_trace()
        return True

account_direct_invoice_wizard()


class account_direct_invoice_wizard_line(osv.osv_memory):
    _name = 'account.direct.invoice.wizard.line'
    _description = 'Account Invoice Line Temp Object'

    def _get_distribution_state(self, cr, uid, ids, name, args, context=None):
        """
        Get state of distribution:
         - if compatible with the invoice line, then "valid"
         - if no distribution, take a tour of invoice distribution, if compatible, then "valid"
         - if no distribution on invoice line and invoice, then "none"
         - all other case are "invalid"
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse all given lines
        for line in self.browse(cr, uid, ids, context=context):
            if line.from_yml_test:
                res[line.id] = 'valid'
            else:
                # UF-2115: test for elements
                line_distribution_id = False
                invoice_distribution_id = False
                line_account_id = False
                if line.analytic_distribution_id:
                    line_distribution_id = line.analytic_distribution_id.id
                if line.invoice_id and line.invoice_id.analytic_distribution_id:
                    invoice_distribution_id = line.invoice_id.analytic_distribution_id.id
                if line.account_id:
                    line_account_id = line.account_id.id
                res[line.id] = self.pool.get('analytic.distribution')._get_distribution_state(cr, uid, line_distribution_id, invoice_distribution_id, line_account_id)
        return res

    def _get_distribution_state_recap(self, cr, uid, ids, name, arg, context=None):
        """
        Get a recap from analytic distribution state and if it come from header or not.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for invl in self.browse(cr, uid, ids):
            res[invl.id] = ''
            if not invl.is_allocatable:
                continue
            from_header = ''
            if invl.have_analytic_distribution_from_header:
                from_header = _(' (from header)')
            res[invl.id] = '%s%s' % (self.pool.get('ir.model.fields').get_browse_selection(cr, uid, invl, 'analytic_distribution_state', context), from_header)
        return res

    def _have_analytic_distribution_from_header(self, cr, uid, ids, name, arg, context=None):
        """
        If invoice have an analytic distribution, return False, else return True
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for inv in self.browse(cr, uid, ids, context=context):
            res[inv.id] = True
            if inv.analytic_distribution_id:
                res[inv.id] = False
        return res

    def _get_is_allocatable(self, cr, uid, ids, name, arg, context=None):
        """
        If analytic-a-holic account, then this account is allocatable.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for invl in self.browse(cr, uid, ids):
            res[invl.id] = True
            if invl.account_id and not invl.account_id.is_analytic_addicted:
                res[invl.id] = False
        return res

    def _get_inactive_product(self, cr, uid, ids, field_name, args, context=None):
        '''
        Fill the error message if the product of the line is inactive
        '''
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'inactive_product': False,
                            'inactive_error': ''}
            if line.invoice_id and line.invoice_id.state not in ('cancel', 'done') and line.product_id and not line.product_id.active:
                res[line.id] = {
                    'inactive_product': True,
                    'inactive_error': _('The product in line is inactive !')
                }
        return res

    def _have_been_corrected(self, cr, uid, ids, name, args, context=None):
        """
        Return True if ALL elements are OK:
         - a journal items is linked to this invoice line
         - the journal items is linked to an analytic line that have been reallocated
        """
        if context is None:
            context = {}
        res = {}

        def has_ana_reallocated(move):
            for ml in move.move_lines or []:
                for al in ml.analytic_lines or []:
                    if al.is_reallocated:
                        return True
            return False

        for il in self.browse(cr, uid, ids, context=context):
            res[il.id] = has_ana_reallocated(il)
        return res

    def _amount_line(self, cr, uid, ids, prop, unknow_none, unknow_dict):
        res = {}
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        for line in self.browse(cr, uid, ids):
            price = line.price_unit * (1-(line.discount or 0.0)/100.0)
            taxes = tax_obj.compute_all(cr, uid, line.invoice_line_tax_id, price, line.quantity, product=line.product_id, address_id=line.invoice_id.address_invoice_id, partner=line.invoice_id.partner_id)
            res[line.id] = taxes['total']
            if line.invoice_id:
                cur = line.invoice_id.currency_id
                res[line.id] = cur_obj.round(cr, uid, cur.rounding, res[line.id])
        return res

    def _get_lines(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for invoice in self.browse(cr, uid, ids, context=context):
            id = invoice.id
            res[id] = []
            if not invoice.move_id:
                continue
            data_lines = [x for x in invoice.move_id.line_id if x.account_id.id == invoice.account_id.id]
            partial_ids = []
            for line in data_lines:
                ids_line = []
                if line.reconcile_id:
                    ids_line = line.reconcile_id.line_id
                elif line.reconcile_partial_id:
                    ids_line = line.reconcile_partial_id.line_partial_ids
                l = map(lambda x: x.id, ids_line)
                partial_ids.append(line.id)
                res[id] =[x for x in l if x <> line.id and x not in partial_ids]
        return res

    _columns = {
        'move_id': fields.many2one('account.move', 'Journal Entry',
            readonly=True, select=1, ondelete='restrict',
            help="Link to the automatically generated Journal Items."),
        'analytic_distribution_id': fields.many2one('analytic.distribution',
            'Analytic Distribution', select="1"),
        'analytic_distribution_state': fields.function(_get_distribution_state,
            method=True, type='selection',
                        selection=[('none', 'None'),
                            ('valid', 'Valid'),
                            ('invalid', 'Invalid')],
            string="Distribution state",
            help="Informs from distribution state among 'none',"
                 " 'valid', 'invalid."),
        'analytic_distribution_state_recap': fields.function(_get_distribution_state_recap,
            method=True, type='char', size=30,
            string="Distribution",
            help="Informs you about analaytic distribution state among 'none',"
            " 'valid', 'invalid', from header or not, or no analytic distribution"),
        'from_yml_test': fields.boolean('Only used to pass addons unit test',
            readonly=True, help='Never set this field to true !'),
        'have_analytic_distribution_from_header': fields.function(_have_analytic_distribution_from_header,
            method=True, type='boolean', string='Header Distrib.?'),
        'inactive_product': fields.function(_get_inactive_product, method=True,
            type='boolean', string='Product is inactive', store=False,
            multi='inactive'),
        'is_allocatable': fields.function(_get_is_allocatable, method=True,
            type='boolean', string="Is allocatable?", readonly=True, store=False),
        'is_corrected': fields.function(_have_been_corrected, method=True,
            string="Have been corrected?", type='boolean',
            readonly=True, help="This informs system if this item have been "
            "corrected in analytic lines. Criteria: the invoice line is linked"
            "to a journal items that have analytic item which is reallocated.",
            store=False),
        'is_temp_object': fields.boolean('is it a temp object in RAM',
            readonly=True, help='This is automatic field'),
        'move_lines':fields.function(_get_lines, method=True, type='many2many',
            relation='account.move.line', string='Entry Lines'),
        'reference': fields.char(string="Reference", size=64),
        'name': fields.char('Description', size=256, required=True),
        'origin': fields.char('Origin', size=512,
            help="Reference of the document that produced this invoice."),
        'invoice_id': fields.many2one('account.direct.invoice.wizard', 'Invoice Reference',
            ondelete='cascade', select=True),
        'uos_id': fields.many2one('product.uom', 'Unit of Measure',
            ondelete='set null'),
        'product_id': fields.many2one('product.product', 'Product',
            ondelete='set null'),
        'account_id': fields.many2one('account.account', 'Account',
            required=True, domain=[('type','<>','view'), ('type', '<>',
                'closed')],
            help="The income or expense account related to the selected product."),
        'price_unit': fields.float('Unit Price', required=True,
            digits_compute=dp.get_precision('Account')),
        'price_subtotal': fields.function(_amount_line, method=True,
            string='Subtotal', type="float",
            digits_compute=dp.get_precision('Account'), store=True),
        'quantity': fields.float('Quantity', required=True),
        'discount': fields.float('Discount (%)',
            digits_compute=dp.get_precision('Account')),
        'invoice_line_tax_id': fields.many2many('account.tax',
            'account_invoice_line_tax', 'invoice_line_id', 'tax_id', 'Taxes',
            domain=[('parent_id','=',False)]),
        'note': fields.text('Notes'),
        'account_analytic_id':  fields.many2one('account.analytic.account',
            'Analytic Account'),
        'company_id': fields.related('invoice_id','company_id',type='many2one',
            relation='res.company', string='Company', store=True, readonly=True),
        'partner_id': fields.related('invoice_id','partner_id',type='many2one',
            relation='res.partner', string='Partner',store=True),
        'inactive_error': fields.function(_get_inactive_product, method=True, type='char', string='Comment', store=False, multi='inactive'),
        'newline': fields.boolean('New line'),
            }


    _defaults = {
        'newline': lambda *a: True,
        'have_analytic_distribution_from_header': lambda *a: True,
        'is_allocatable': lambda *a: True,
        'analytic_distribution_state_recap': lambda *a: '',
        'inactive_product': False,
        'inactive_error': lambda *a: '',
    }

    def onchange_account_id(self, cr, uid, ids, fposition_id, account_id):
        if not account_id:
            return {}
        taxes = self.pool.get('account.account').browse(cr, uid, account_id).tax_ids
        fpos = fposition_id and self.pool.get('account.fiscal.position').browse(cr, uid, fposition_id) or False
        res = self.pool.get('account.fiscal.position').map_tax(cr, uid, fpos, taxes)
        return {'value':{'invoice_line_tax_id': res}}


account_direct_invoice_wizard_line()
