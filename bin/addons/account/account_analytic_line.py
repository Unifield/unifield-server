# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

import time

from osv import fields
from osv import osv
from tools.translate import _

class account_analytic_line(osv.osv):
    _inherit = 'account.analytic.line'
    _description = 'Analytic Line'
    _columns = {
        'product_uom_id': fields.many2one('product.uom', 'UoM'),
        'product_id': fields.many2one('product.product', 'Product'),
        'general_account_id': fields.many2one('account.account', 'General Account', required=True, ondelete='restrict'),
        'move_id': fields.many2one('account.move.line', 'Move Line', ondelete='restrict', select=True),
        'journal_id': fields.many2one('account.analytic.journal', 'Analytic Journal', required=True, ondelete='restrict', select=True),
        'code': fields.char('Code', size=8),
        'ref': fields.char('Ref.', size=64),
        'currency_id': fields.related('move_id', 'currency_id', type='many2one', relation='res.currency', string='Account currency', store=True, help="The related account currency if not equal to the company one.", readonly=True, required=True),
        'amount_currency': fields.related('move_id', 'amount_currency', type='float', string='Amount currency', store=True, help="The amount expressed in the related account currency if not equal to the company one.", readonly=True, required=True),
    }

    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'account.analytic.line', context=c),
    }
    _order = 'id desc'

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        if context is None:
            context = {}
        if context.get('from_date',False):
            args.append(['date', '>=', context['from_date']])
        if context.get('to_date',False):
            args.append(['date','<=', context['to_date']])
        return super(account_analytic_line, self).search(cr, uid, args, offset, limit,
                                                         order, context=context, count=count)

    def _check_company(self, cr, uid, ids, context=None):
        lines = self.browse(cr, uid, ids, context=context)
        for l in lines:
            if l.move_id and not l.account_id.company_id.id == l.move_id.account_id.company_id.id:
                return False
        return True

    def view_header_get(self, cr, user, view_id, view_type, context=None):
        if context is None:
            context = {}
        if context.get('account_id', False):
            # account_id in context may also be pointing to an account.account.id
            cr.execute('select name from account_analytic_account where id=%s', (context['account_id'],))
            res = cr.fetchone()
            if res:
                res = _('Entries: ')+ (res[0] or '')
            return res
        return False

    def get_related_entry_ids(self, cr, uid, ids=False, entry_seqs=None, context=None):
        """
        Returns the ids of all the AJIs related to the selected AJIs and/or Entry Sequences (list), i.e.:
        1) those having the same Entry Sequence as the selected ones (including the selected lines themselves)
        2) those having the same reference as one of the lines found in 1)
        3) those having an Entry Sequence matching exactly with the reference of one of the lines found in 1)
        4) those whose reference contains EXACTLY the Entry Sequence of one of the selected lines
        5) those having the same Entry Sequence as one of the lines found in 2), 3), or 4)
        """
        if context is None:
            context = {}
        if entry_seqs is None:
            entry_seqs = []
        analytic_acc_obj = self.pool.get('account.analytic.account')
        related_aals = set()

        categories = []
        if entry_seqs:
            aal_ids = self.search(cr, uid, [('entry_sequence', 'in', entry_seqs)], order='NO_ORDER', context=context)
            aals = self.browse(cr, uid, aal_ids, fields_to_fetch=['account_id'], context=context)
            categories = [aal.account_id.category or '' for aal in aals]
        if ids:
            if isinstance(ids, int):
                ids = [ids]
            selected_aals = self.browse(cr, uid, ids, fields_to_fetch=['entry_sequence', 'account_id'], context=context)
            for selected_aal in selected_aals:
                entry_seqs.append(selected_aal.entry_sequence or '')
                categories.append(selected_aal.account_id.category or '')
        if entry_seqs and categories:
            # get the ids of all the related lines

            categories = list(set(categories))
            entry_seqs = list(set(entry_seqs))
            analytic_account_ids = analytic_acc_obj.search(cr, uid, [('category', 'in', categories)],
                                                           order='NO_ORDER', context=context)
            # lines having the same Entry Sequence
            same_seq_domain = [('entry_sequence', 'in', entry_seqs),
                               ('account_id', 'in', analytic_account_ids)]
            same_seq_line_ids = self.search(cr, uid, same_seq_domain, order='NO_ORDER', context=context)
            related_aals.update(same_seq_line_ids)

            # check on ref
            set_of_refs = set()
            for aal in self.browse(cr, uid, same_seq_line_ids, fields_to_fetch=['ref'], context=context):
                aal.ref and set_of_refs.add(aal.ref)

            domain_related_lines = ['&', '|', '|',
                                    '&', ('ref', 'in', list(set_of_refs)), ('ref', '!=', ''),
                                    ('entry_sequence', 'in', list(set_of_refs)),
                                    ('ref', 'in', entry_seqs),
                                    ('account_id', 'in', analytic_account_ids)]
            related_line_ids = self.search(cr, uid, domain_related_lines, order='NO_ORDER', context=context)
            related_aals.update(related_line_ids)

            # check on Entry Seq. (compared with those of the related lines found)
            aal_seqs = set(aal.entry_sequence for aal in self.browse(cr, uid, related_line_ids,
                                                                     fields_to_fetch=['entry_sequence'], context=context))
            same_seq_related_line_domain = [('entry_sequence', 'in', list(aal_seqs)),
                                            ('account_id', 'in', analytic_account_ids)]
            same_seq_related_line_ids = self.search(cr, uid, same_seq_related_line_domain, order='NO_ORDER',
                                                    context=context)
            related_aals.update(same_seq_related_line_ids)
        return list(related_aals)

    def get_aal_related_entries(self, cr, uid, ids, context=None):
        """
        Returns a view with all the Analytic Lines related to the selected one (see get_related_entry_ids for details)
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        active_ids = context.get('active_ids', [])  # to detect if the user has selected several lines
        if len(ids) != 1 or len(active_ids) > 1:
            raise osv.except_osv(_('Error'),
                                 _('The related entries feature can only be used with one Analytic Line.'))
        ir_model_obj = self.pool.get('ir.model.data')
        selected_aal = self.browse(cr, uid, ids[0], fields_to_fetch=['entry_sequence', 'account_id'], context=context)
        selected_entry_seq = selected_aal.entry_sequence or ''
        selected_category = selected_aal.account_id.category or ''
        related_entry_ids = self.get_related_entry_ids(cr, uid, ids=ids, context=context)
        domain = [('id', 'in', related_entry_ids)]
        # same views whatever the category displayed (FP or Free1/2)
        view_id = ir_model_obj.get_object_reference(cr, uid, 'account', 'view_account_analytic_line_tree')
        view_id = view_id and view_id[1] or False
        search_view_id = ir_model_obj.get_object_reference(cr, uid, 'account', 'view_account_analytic_line_filter')
        search_view_id = search_view_id and search_view_id[1] or False
        if selected_category == 'FUNDING':
            context.update({'display_fp': True})
        return {
            'name': _('Related entries: Entry Sequence %s') % selected_entry_seq,
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': [view_id],
            'search_view_id': [search_view_id],
            'context': context,
            'domain': domain,
            'target': 'current',
        }


account_analytic_line()


class res_partner(osv.osv):
    """ Inherits partner and adds contract information in the partner form """
    _inherit = 'res.partner'

    _columns = {
        'contract_ids': fields.one2many('account.analytic.account', \
                                        'partner_id', 'Contracts', readonly=True),
    }

res_partner()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
