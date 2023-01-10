# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 MSF, TeMPO Consulting.
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
from lxml import etree
from tools.translate import _
from base import currency_date
import decimal_precision as dp
from time import strftime
import logging


class account_analytic_line(osv.osv):
    _name = "account.analytic.line"
    _inherit = "account.analytic.line"

    def _is_engi(self, cr, uid, ids, name, args, context=None):
        # BKLK-4: is line an intl commitment ? (of engagement ENGI journal)
        # (allowed to have a delete button)
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]
        aaj_obj = self.pool.get('account.analytic.journal')

        fields = ['imported_commitment', 'journal_id']
        for r in self.read(cr, uid, ids, fields, context=context):
            res[r['id']] = False
            if r['imported_commitment'] and r['journal_id']:
                rj = aaj_obj.read(cr, uid, [r['journal_id'][0]],
                                  ['type', 'code', ], context=context)[0]
                if rj:
                    res[r['id']]  = rj['type'] =='engagement' and \
                        rj['code'] == 'ENGI' or False
        return res

    def _get_is_free(self, cr, uid, ids, field_names, args, context=None):
        """
        Check if the line comes from a Free 1 or Free 2 analytic account category.
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for al in self.browse(cr, uid, ids, context=context):
            res[al.id] = False
            if al.account_id and al.account_id.category and al.account_id.category in ['FREE1', 'FREE2']:
                res[al.id] = True
        return res

    def _search_is_free(self, cr, uid, ids, field_names, args, context=None):
        """
        Returns a domain that, according to the args used, includes or excludes the Free1 / Free2 Analytic Accounts
        """
        domain = []
        if context is None:
            context = {}
        analytic_acc_obj = self.pool.get('account.analytic.account')
        if args:
            if args[0][1] != '=' or len(args[0]) < 3 or not isinstance(args[0][2], bool):
                raise osv.except_osv(_('Error'), _('Filter not implemented.'))
            if args[0][2] is True:
                operator = 'in'
            else:
                operator = 'not in'
            free_account_ids = analytic_acc_obj.search(cr, uid, [('category', 'in', ['FREE1', 'FREE2'])], order='NO_ORDER', context=context)
            domain.append(('account_id', operator, free_account_ids))
        return domain

    def _get_reversal_origin_txt(cr, uid, ids, field_names, args, context=None):
        ret = {}
        if not ids:
            return ret
        for id in ids:
            ret[id] = ''
        cr.execute('''select a1.id, a2.name from
            account_analytic_line a1, account_analytic_line a2
            where a2.id = a1.reversal_origin and
            a1.id in %s ''', (tuple(ids),)
                   )
        for x in cr.fetchall():
            ret[x[0]] = x[1]
        return ret

    def _get_analytic_reversal(self, cr, uid, ids, context=None):
        return self.search(cr, uid, [('reversal_origin', 'in', ids)])+ids

    _columns = {
        'distribution_id': fields.many2one('analytic.distribution', string='Analytic Distribution'),
        'cost_center_id': fields.many2one('account.analytic.account', string='Cost Center', domain="[('category', '=', 'OC'), ('type', '<>', 'view')]", m2o_order='code', ondelete='restrict', select=1),
        'from_write_off': fields.boolean(string='Write-off?', readonly=True, help="Indicates that this line come from a write-off account line."),
        'destination_id': fields.many2one('account.analytic.account', string="Destination", domain="[('category', '=', 'DEST'), ('type', '<>', 'view')]", ondelete='restrict', select=1),
        'distrib_line_id': fields.reference('Distribution Line ID', selection=[('funding.pool.distribution.line', 'FP'),('free.1.distribution.line', 'free1'), ('free.2.distribution.line', 'free2')], size=512),
        'free_account': fields.function(_get_is_free, fnct_search=_search_is_free, method=True, type='boolean', string='Free account?', help="Does that line come from a Free 1 or Free 2 account?"),
        'reversal_origin': fields.many2one('account.analytic.line', string="Reversal origin", readonly=True, help="Line that have been reversed.", select=1),
        'reversal_origin_txt': fields.function(_get_reversal_origin_txt, string="Reversal origin", type='char', size=256,
                                               store={
                                                   'account.analytic.line': (_get_analytic_reversal, ['name', 'reversal_origin'], 20),
                                               }),
        'source_date': fields.date('Source date', help="Date used for FX rate re-evaluation"),
        'is_reversal': fields.boolean('Reversal?'),
        'is_reallocated': fields.boolean('Reallocated?'),
        'ad_updated': fields.boolean('Analytic Distribution Updated'),
        'date': fields.date('Posting Date', required=True, select=True, readonly=True),
        'document_date': fields.date('Document Date', readonly=True, required=True),
        'functional_currency_id': fields.related('company_id', 'currency_id', string="Func. Currency", type="many2one", relation="res.currency", readonly=True, write_relate=False),
        'amount': fields.float('Func. Amount', required=True, digits_compute=dp.get_precision('Account'),
                               help='Calculated by multiplying the quantity and the price given in the Product\'s cost price. Always expressed in the company main currency.', readonly=True),
        'exported': fields.boolean("Exported"),
        'is_engi': fields.function(_is_engi, type='boolean', method=True,
                                   string='Is intl engagement'),
    }

    _defaults = {
        'from_write_off': lambda *a: False,
        'is_reversal': lambda *a: False,
        'is_reallocated': lambda *a: False,
        'exported': lambda *a: False,
        'is_engi': lambda *a: False,
    }

    def unlink(self, cr, uid, ids, context=None):
        # store_set_value is not called on unlink if target and source are the same obj
        if ids:
            if isinstance(ids, (int, long)):
                ids = [ids]
            cr.execute("update account_analytic_line set reversal_origin_txt='' where reversal_origin in %s", (tuple(ids),))
        return super(account_analytic_line, self).unlink(cr, uid, ids, context=context)

    def _check_date(self, cr, uid, vals, context=None):
        """
        Check if given account_id is active for given date. Except for mass reallocation ('from' = 'mass_reallocation' in context)
        """
        if not context:
            context = {}
        if not 'account_id' in vals:
            raise osv.except_osv(_('Error'), _('No account_id found in given values!'))
        if context.get('skip_ad_date_check', False):
            return True

        account_obj = self.pool.get('account.analytic.account')
        dest_cc_link_obj = self.pool.get('dest.cc.link')

        #US-419: Use the document date and not posting date when checking the validity of analytic account
        # tech: replaced all date by document_date
        if 'document_date' in vals and vals['document_date'] is not False:
            document_date = vals['document_date']
            account = account_obj.browse(cr, uid, vals['account_id'], context=context)
            # FIXME: refactoring of next code
            if document_date < account.date_start or (account.date != False and document_date >= account.date):
                if 'from' not in context or context.get('from') != 'mass_reallocation':
                    entry_name = self.get_entry_name(cr, uid, vals, context=context)
                    raise osv.except_osv(_('Error'), _("The analytic account '%s' %s is not active.") % (account.name or '', entry_name))
        if 'date' in vals and vals['date'] is not False:
            date = vals['date']
            dest = False
            cc = False
            if vals.get('cost_center_id', False):
                cc = account_obj.browse(cr, uid, vals['cost_center_id'], context=context)
                if date < cc.date_start or (cc.date != False and date >= cc.date):
                    if 'from' not in context or context.get('from') != 'mass_reallocation':
                        # US-9724
                        entry_name = self.get_entry_name(cr, uid, vals, context=context)
                        raise osv.except_osv(_('Error'),_("The analytic account '%s' %s is inactive.") % (cc.name or '', entry_name))
            if vals.get('destination_id', False):
                dest = account_obj.browse(cr, uid, vals['destination_id'], context=context)
                if date < dest.date_start or (dest.date != False and date >= dest.date):
                    if 'from' not in context or context.get('from') != 'mass_reallocation':
                        entry_name = self.get_entry_name(cr, uid, vals, context=context)
                        raise osv.except_osv(_('Error'), _("The analytic account '%s' %s is not active.") % (dest.name or '', entry_name))
            if context.get('from') != 'mass_reallocation' and dest and cc and \
                    dest_cc_link_obj.is_inactive_dcl(cr, uid, dest.id, cc.id, date, context=context):
                entry_name = self.get_entry_name(cr, uid, vals, context=context)
                raise osv.except_osv(_('Error'), _("The combination \"%s - %s\"  %s is not active.") % (dest.code or '', cc.code or '', entry_name))
        return True

    def get_entry_name(self, cr, uid, vals, context):
        """
        Return the sequence entry name
        """
        acc_move_obj = self.pool.get('account.move.line')
        if vals.get('move_id'):
            move_line = acc_move_obj.browse(cr, uid, vals['move_id'], fields_to_fetch=['move_id', 'name'], context=context)
            if move_line.move_id:
                if move_line.move_id.journal_id and move_line.move_id.journal_id.type == 'cur_adj':
                    return _(' selected for FXA ')
                if move_line.move_id.name:
                    return _(' selected in %s (description: %s)') % (move_line.move_id.name, move_line.name or '')
        return ''

    def _check_document_date(self, cr, uid, ids):
        """
        Check that document's date is done BEFORE posting date
        """
        for aal in self.browse(cr, uid, ids):
            self.pool.get('finance.tools').check_document_date(cr, uid,
                                                               aal.document_date, aal.date, show_date=True)
        return True

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Change account_id field name to "Funding Pool if we come from a funding pool
        """
        # Some verifications
        if context is None:
            context = {}
        is_funding_pool_view = False
        if context.get('display_fp', False) and context.get('display_fp') is True:
            is_funding_pool_view = True

        view = super(account_analytic_line, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if view_type in ('tree', 'search') and is_funding_pool_view:
            # commitments activated in configurator ?
            setup_br = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
            is_commitment = setup_br and setup_br.import_commitments or False

            tree = etree.fromstring(view['arch'])
            # Change OC field
            fields = tree.xpath('/' + view_type + '//field[@name="account_id"]')
            for field in fields:
                field.set('string', _("Funding Pool"))
                field.set('domain', "[('category', '=', 'FUNDING'), ('type', '<>', 'view')]")
            if "engagement_line_tree" in context:
                if is_commitment:
                    if view_type == 'tree':
                        # BKLG-4: comming from commitments list, allow delete of
                        # international commitments line (journal ENGI) but not
                        #  allow delete of other engagements line
                        etree.SubElement(tree, 'button',
                                         name='unlink',
                                         type='object',
                                         icon='gtk-del',
                                         context='context',
                                         attrs="{'invisible': [('is_engi', '!=', True)]}",
                                         confirm='Do you really want to delete selected record(s) ?'
                                         )

            if view_type == 'search' and not is_commitment:
                # BKLG-4/6: commitments desactivated, no ENGI filter
                filter_nodes = tree.xpath('/search/group[1]/filter[@name="intl_engagements"]')
                if filter_nodes:
                    filter_nodes[0].getparent().remove(filter_nodes[0])
            view['arch'] = etree.tostring(tree)
        return view

    def _round_amounts(self, vals):
        """
        Updates vals with the booking and fctal amounts rounded to 2 digits
        This avoids the rounding to be done in the SQL query as it would be different from the one done in Python
        Cf: round(1.125, 2) ==> 1.13 / '%.2lf' % 1.125 ==> 1.12
        """
        if vals.get('amount_currency'):
            vals['amount_currency'] = round(vals['amount_currency'], 2)
        if vals.get('amount'):
            vals['amount'] = round(vals['amount'], 2)

    def create(self, cr, uid, vals, context=None):
        entry_sequence_sync = None
        if vals.get('entry_sequence',False):
            entry_sequence_sync = vals['entry_sequence']
        """
        Check date for given date and given account_id
        Filled in 'document_date' if we come from synchronization
        """
        # Some verifications
        if not context:
            context = {}
        aml_obj = self.pool.get('account.move.line')
        invoice_line_obj = self.pool.get('account.invoice.line')
        aal_obj = self.pool.get('account.analytic.line')
        aal_account_obj = self.pool.get('account.analytic.account')
        self._round_amounts(vals)
        # SP-50: If data is synchronized from another instance, just create it with the given document_date
        if context.get('update_mode') in ['init', 'update']:
            if not context.get('sync_update_execution', False) or not vals.get('document_date', False):
                logging.getLogger('init').info('AAL: set document_date')
                vals['document_date'] = strftime('%Y-%m-%d')
        if vals.get('document_date', False) and vals.get('date', False):
            self.pool.get('finance.tools').check_document_date(cr, uid,
                                                               vals.get('document_date'), vals.get('date'), show_date=True,
                                                               context=context)
        # in case of a refund cancel/modify: update the reversal origin
        if vals.get('move_id'):
            related_ji = aml_obj.browse(cr, uid, vals['move_id'], fields_to_fetch=['invoice_line_id'], context=context)
            if related_ji.invoice_line_id and related_ji.invoice_line_id.reversed_invoice_line_id:
                vals['is_reversal'] = True
                reversed_inv_line = invoice_line_obj.browse(cr, uid, related_ji.invoice_line_id.reversed_invoice_line_id.id,
                                                            fields_to_fetch=['move_lines'], context=context)
                reversed_aml_id = reversed_inv_line.move_lines and reversed_inv_line.move_lines[0].id or False
                # use a Funding Pool as Free1/2 are not synched to HQ
                fp_account_ids = aal_account_obj.search(cr, uid, [('category', '=', 'FUNDING'), ('type', '=', 'normal')],
                                                        order='NO_ORDER', context=context)
                reversed_aal_dom = [('move_id', '=', reversed_aml_id), ('account_id', 'in', fp_account_ids)]
                # the reversal_origin is used to keep the chain with previous AJIs so if several AJIs are linked to a JI
                # the reversed AJI used is the same for all AJIs = the first one found by id
                reversed_aal_ids = reversed_aml_id and aal_obj.search(cr, uid, reversed_aal_dom, order='id', limit=1,
                                                                      context=context)
                if reversed_aal_ids:
                    vals['reversal_origin'] = reversed_aal_ids[0]  # reversal_origin_txt will be automatically updated
        self.pool.get('data.tools').replace_line_breaks_from_vals(vals, ['name', 'ref'], replace=['name'])
        # Default behaviour
        res = super(account_analytic_line, self).create(cr, uid, vals, context=context)
        # Check date
        self._check_date(cr, uid, vals, context=context)
        br = self.browse(cr, uid, res,context)
        if entry_sequence_sync is not None:
            if entry_sequence_sync != br.entry_sequence:
                cr.execute('''UPDATE account_analytic_line SET entry_sequence=%s WHERE id=%s''', (entry_sequence_sync, res))
        return res

    def write(self, cr, uid, ids, vals, context=None):
        """
        Verify date for all given ids with account.
        Check document_date and date validity.
        """
        if not ids:
            return True
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        self._round_amounts(vals)
        for l in self.browse(cr, uid, ids):
            vals2 = vals.copy()
            for el in ['account_id', 'cost_center_id', 'destination_id']:
                if not el in vals:
                    vals2.update({el: l[el] and l[el]['id'] or False})
            self._check_date(cr, uid, vals2, context=context)
        self.pool.get('data.tools').replace_line_breaks_from_vals(vals, ['name', 'ref'], replace=['name'])
        res = super(account_analytic_line, self).write(cr, uid, ids, vals, context=context)
        self._check_document_date(cr, uid, ids)
        return res

    def reverse(self, cr, uid, ids, posting_date=None, context=None):
        """
        Reverse an analytic line:
         - use as source_date the original one if any, or the doc/posting date depending on the OC
         - mark this line as reversal
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        period_obj = self.pool.get('account.period')
        if posting_date is None:
            posting_date = strftime('%Y-%m-%d')
        # US-945: deduce real period id from date
        # TO NOTE that, in correction wizard:
        # in December we are well in December, never in 13, 14, 15, 16
        period_ids = period_obj.get_period_from_date(
            cr, uid, date=posting_date, context=context)
        # (US-815) use the right period for December HQ Entries
        period_number = period_ids and period_obj.browse(cr, uid, period_ids, context)[0].number or False
        period_id_dec_hq_entry = False
        if period_number == 12 and context.get('period_id_for_dec_hq_entries', False):
            period_id_dec_hq_entry = context['period_id_for_dec_hq_entries']
        res = []
        for al in self.browse(cr, uid, ids, context=context):
            self.pool.get('finance.tools').check_correction_date_fy(al.date, posting_date, context=context)
            curr_date = currency_date.get_date(self, cr, al.document_date, al.date, source_date=al.source_date)
            vals = {
                'name': self.join_without_redundancy(al.name, 'REV'),
                'amount': al.amount * -1,
                'date': posting_date,
                'source_date': curr_date,
                'reversal_origin': al.id,
                'amount_currency': al.amount_currency * -1,
                'currency_id': al.currency_id.id,
                'is_reversal': True,
                'ref': al.entry_sequence,
                'real_period_id': period_id_dec_hq_entry or period_ids and period_ids[0] or False,  # US-945
            }
            new_al = self.copy(cr, uid, al.id, vals, context=context)
            res.append(new_al)

        return res

account_analytic_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
