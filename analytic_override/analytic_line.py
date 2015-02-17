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

    _columns = {
        'distribution_id': fields.many2one('analytic.distribution', string='Analytic Distribution'),
        'cost_center_id': fields.many2one('account.analytic.account', string='Cost Center', domain="[('category', '=', 'OC'), ('type', '<>', 'view')]"),
        'from_write_off': fields.boolean(string='Write-off?', readonly=True, help="Indicates that this line come from a write-off account line."),
        'destination_id': fields.many2one('account.analytic.account', string="Destination", domain="[('category', '=', 'DEST'), ('type', '<>', 'view')]"),
        'distrib_line_id': fields.reference('Distribution Line ID', selection=[('funding.pool.distribution.line', 'FP'),('free.1.distribution.line', 'free1'), ('free.2.distribution.line', 'free2')], size=512),
        'free_account': fields.function(_get_is_free, method=True, type='boolean', string='Free account?', help="Is that line comes from a Free 1 or Free 2 account?"),
        'reversal_origin': fields.many2one('account.analytic.line', string="Reversal origin", readonly=True, help="Line that have been reversed."),
        'source_date': fields.date('Source date', help="Date used for FX rate re-evaluation"),
        'is_reversal': fields.boolean('Reversal?'),
        'is_reallocated': fields.boolean('Reallocated?'),
        'date': fields.date('Posting Date', required=True, select=True, readonly=True),
        'document_date': fields.date('Document Date', readonly=True, required=True),
        'functional_currency_id': fields.related('company_id', 'currency_id', string="Func. Currency", type="many2one", relation="res.currency", readonly=True),
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

    def _check_date(self, cr, uid, vals, context=None):
        """
        Check if given account_id is active for given date. Except for mass reallocation ('from' = 'mass_reallocation' in context)
        """
        if not context:
            context = {}
        if not 'account_id' in vals:
            raise osv.except_osv(_('Error'), _('No account_id found in given values!'))
        if 'date' in vals and vals['date'] is not False:
            account_obj = self.pool.get('account.analytic.account')
            date = vals['date']
            account = account_obj.browse(cr, uid, vals['account_id'], context=context)
            # FIXME: refactoring of next code
            if date < account.date_start or (account.date != False and date >= account.date):
                if 'from' not in context or context.get('from') != 'mass_reallocation':
                    raise osv.except_osv(_('Error'), _("The analytic account selected '%s' is not active.") % (account.name or '',))
            if vals.get('cost_center_id', False):
                cc = account_obj.browse(cr, uid, vals['cost_center_id'], context=context)
                if date < cc.date_start or (cc.date != False and date >= cc.date):
                    if 'from' not in context or context.get('from') != 'mass_reallocation':
                        raise osv.except_osv(_('Error'), _("The analytic account selected '%s' is not active.") % (cc.name or '',))
            if vals.get('destination_id', False):
                dest = account_obj.browse(cr, uid, vals['destination_id'], context=context)
                if date < dest.date_start or (dest.date != False and date >= dest.date):
                    if 'from' not in context or context.get('from') != 'mass_reallocation':
                        raise osv.except_osv(_('Error'), _("The analytic account selected '%s' is not active.") % (dest.name or '',))
        return True

    def _check_document_date(self, cr, uid, ids):
        """
        Check that document's date is done BEFORE posting date
        """
        for aal in self.browse(cr, uid, ids):
            if aal.document_date and aal.date and aal.date < aal.document_date:
                raise osv.except_osv(_('Error'), _('Posting date (%s) should be later than Document Date (%s).') % (aal.date, aal.document_date))
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
        # SP-50: If data is synchronized from another instance, just create it with the given document_date
        if context.get('update_mode') in ['init', 'update']:
            if not context.get('sync_update_execution', False) or not vals.get('document_date', False):
                logging.getLogger('init').info('AAL: set document_date')
                vals['document_date'] = strftime('%Y-%m-%d')
        if vals.get('document_date', False) and vals.get('date', False) and vals.get('date') < vals.get('document_date'):
            raise osv.except_osv(_('Error'), _('Posting date (%s) should be later than Document Date (%s).') % (vals.get('date', False), vals.get('document_date', False)))
        # Default behaviour
        res = super(account_analytic_line, self).create(cr, uid, vals, context=context)
        # Check date
        self._check_date(cr, uid, vals, context=context)
        br = self.browse(cr, uid, res,context)
        if entry_sequence_sync is not None:
            if entry_sequence_sync != br.entry_sequence:
                cr.execute('''update account_analytic_line set entry_sequence = '%s' where id = %s''' % (entry_sequence_sync,res))
        return res

    def write(self, cr, uid, ids, vals, context=None):
        """
        Verify date for all given ids with account.
        Check document_date and date validity.
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for l in self.browse(cr, uid, ids):
            vals2 = vals.copy()
            for el in ['account_id', 'cost_center_id', 'destination_id']:
                if not el in vals:
                    vals2.update({el: l[el] and l[el]['id'] or False})
            self._check_date(cr, uid, vals2, context=context)
        res = super(account_analytic_line, self).write(cr, uid, ids, vals, context=context)
        self._check_document_date(cr, uid, ids)
        return res

    def reverse(self, cr, uid, ids, posting_date=strftime('%Y-%m-%d'), context=None):
        """
        Reverse an analytic line:
         - keep date as source_date
         - mark this line as reversal
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = []
        for al in self.browse(cr, uid, ids, context=context):
            vals = {
                'name': self.join_without_redundancy(al.name, 'REV'),
                'amount': al.amount * -1,
                'date': posting_date,
                'source_date': al.source_date or al.date,
                'reversal_origin': al.id,
                'amount_currency': al.amount_currency * -1,
                'currency_id': al.currency_id.id,
                'is_reversal': True,
            }
            new_al = self.copy(cr, uid, al.id, vals, context=context)
            res.append(new_al)
        return res

account_analytic_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
