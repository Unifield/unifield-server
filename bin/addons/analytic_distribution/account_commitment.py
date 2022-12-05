#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
from tools.translate import _
from time import strftime
from time import strptime
import decimal_precision as dp
from account_override.period import get_period_from_date
from tools.misc import flatten
import netsvc

class account_commitment(osv.osv):
    _name = 'account.commitment'
    _description = "Account Commitment Voucher"
    _order = 'is_draft desc, id desc'
    _trace = True

    def import_cv(self, cr, uid, ids, data, context=None):
        """
        Opens the Import CV wizard
        """
        if isinstance(ids, int):
            ids = [ids]
        wiz_id = self.pool.get('account.cv.import').create(cr, uid, {'commit_id': ids[0]}, context=context)
        return {
            'name': _('Import CV'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.cv.import',
            'target': 'new',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'res_id': [wiz_id],
        }

    def export_cv(self, cr, uid, ids, data, context=None):
        """
        Opens the Export CV report
        """
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.export_cv',
            'datas': data,
        }

    def _get_total(self, cr, uid, ids, name, args, context=None):
        """
        Give total of given commitments
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
        res = {}
        for _id in ids:
            res[_id] = 0
        # Browse commitments
        if ids:
            cr.execute('''
                select
                    commit_id, sum(amount)
                from
                    account_commitment_line
                where
                    commit_id in %s
                group by
                    commit_id
            ''', (tuple(ids),))
            for x in cr.fetchall():
                res[x[0]] = round(x[1], 2)

        return res

    def _get_cv(self, cr, uid, ids, context=None):
        """
        Get CV linked to given lines
        """
        res = []
        if not context:
            context = {}
        for cvl in self.pool.get('account.commitment.line').browse(cr, uid, ids):
            if cvl.commit_id.id not in res:
                res.append(cvl.commit_id.id)
        return res

    def get_cv_type(self, cr, uid, context=None):
        """
        Returns the list of possible types for the Commitment Vouchers
        """
        return [('manual', _('Manual')),
                ('external', _('Automatic - External supplier')),
                ('esc', _('Manual - ESC supplier')),
                ('intermission', _('Automatic - Intermission')),
                ('intersection', _('Automatic - Intersection')),
                ]

    def get_current_cv_version(self, cr, uid, context=None):
        """
        Version 2 since US-7449
        """
        return 2

    def _display_super_done_button(self, cr, uid, ids, name, arg, context=None):
        """
        The "Super" Done button, which allows to always set a CV to Done whatever its state and origin, is displayed:
        - when the standard Done button isn't usable.
        - only for some "admin" users (the restriction is made by User Rights).
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        for cv in self.read(cr, uid, ids, ['state', 'type'], context=context):
            other_done_button_usable = cv['state'] == 'open' and cv['type'] not in ('external', 'intermission', 'intersection')
            res[cv['id']] = not other_done_button_usable and cv['state'] != 'done'
        return res

    def _get_line_count(self, cr, uid, ids, field_name, args, context=None):
        """
        Returns the number of lines for each selected commitment voucher
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        for commit in self.browse(cr, uid, ids, fields_to_fetch=['line_ids'], context=context):
            res[commit.id] = len(commit.line_ids)
        return res

    _columns = {
        'journal_id': fields.many2one('account.analytic.journal', string="Journal", readonly=True, required=True),
        'name': fields.char(string="Number", size=64, readonly=True, required=True),
        'currency_id': fields.many2one('res.currency', string="Currency", required=True),
        'line_count': fields.function(_get_line_count, string='Line count', method=True, type='integer', store=False),
        'partner_id': fields.many2one('res.partner', string="Partner", required=True),
        'period_id': fields.many2one('account.period', string="Period", readonly=True, required=True),
        'state': fields.selection([('draft', 'Draft'), ('open', 'Validated'), ('done', 'Done')], readonly=True, string="State", required=True),
        'is_draft': fields.boolean('Is draft', help='used to sort CVs (draft on top)', readonly=1, select=1),
        'date': fields.date(string="Commitment Date", readonly=True, required=True, states={'draft': [('readonly', False)], 'open': [('readonly', False)]}),
        'line_ids': fields.one2many('account.commitment.line', 'commit_id', string="Commitment Voucher Lines"),
        'total': fields.function(_get_total, type='float', method=True, digits_compute=dp.get_precision('Account'), readonly=True, string="Total",
                                 store={
                                 'account.commitment.line': (_get_cv, ['amount'],10),
                                 }),
        'analytic_distribution_id': fields.many2one('analytic.distribution', string="Analytic distribution"),
        'type': fields.selection(get_cv_type, string="Type", readonly=True),
        'notes': fields.text(string="Comment"),
        'cv_flow_type': fields.selection([('customer', 'Customer'), ('supplier', 'Supplier')], string="Type of CV"),
        'purchase_id': fields.many2one('purchase.order', string="Source document", readonly=True),
        'sale_id': fields.many2one('sale.order', string="Source document", readonly=True),
        'description': fields.char(string="Description", size=256),
        'version': fields.integer('Version', required=True,
                                  help="Technical field to distinguish old CVs from new ones which have a different behavior."),
        'display_super_done_button': fields.function(_display_super_done_button, method=True, type='boolean',
                                                     store=False, invisible=True,
                                                     string='Display the button allowing to always set a CV to Done'),
    }

    _defaults = {
        'state': lambda *a: 'draft',
        'is_draft': True,
        'date': lambda *a: strftime('%Y-%m-%d'),
        'type': lambda *a: 'manual',
        'version': get_current_cv_version,
        'journal_id': lambda s, cr, uid, c: s.pool.get('account.analytic.journal').search(cr, uid, [('type', '=', 'engagement'),
                                                                                                    ('instance_id', '=', s.pool.get('res.users').browse(cr, uid, uid, c).company_id.instance_id.id)], limit=1, context=c)[0]
    }

    def create(self, cr, uid, vals, context=None):
        """
        Update period_id regarding date.
        Add sequence.
        """
        # Some verifications
        if not context:
            context = {}
        if not 'period_id' in vals:
            period_ids = get_period_from_date(self, cr, uid, vals.get('date', strftime('%Y-%m-%d')), context=context)
            vals.update({'period_id': period_ids and period_ids[0]})
        if 'state' not in vals:
            # state by default at creation time = Draft: add it in vals to make it appear in the Track Changes
            vals['state'] = 'draft'
        vals['is_draft'] = vals.get('state', 'draft') == 'draft'
        # UTP-317 # Check that no inactive partner have been used to create this commitment
        if 'partner_id' in vals:
            partner_id = vals.get('partner_id')
            if isinstance(partner_id, (str)):
                partner_id = int(partner_id)
            partner = self.pool.get('res.partner').browse(cr, uid, [partner_id])
            if partner and partner[0] and not partner[0].active:
                raise osv.except_osv(_('Warning'), _("Partner '%s' is not active.") % (partner[0] and partner[0].name or '',))
        if vals.get('sale_id'):
            vals['cv_flow_type'] = 'customer'
        elif vals.get('purchase_id'):
            vals['cv_flow_type'] = 'supplier'
        # Add sequence
        sequence_number = self.pool.get('ir.sequence').get(cr, uid, self._name)
        instance = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.instance_id
        if not instance:
            raise osv.except_osv(_('Error'), _('No instance found!'))
        journal_ids = self.pool.get('account.analytic.journal').search(cr, uid, [('type', '=', 'engagement'), ('instance_id', '=', instance.id)], limit=1, context=context)
        if not journal_ids:
            raise osv.except_osv(_('Error'), _('No Engagement journal found!'))
        journal_id = journal_ids[0]
        journal = self.pool.get('account.analytic.journal').browse(cr, uid, [journal_id])
        if not journal:
            raise osv.except_osv(_('Error'), _('No Engagement journal found!'))
        journal_name = journal[0].code
        # UF-2139: add fiscal year last 2 numbers in sequence
        fy_numbers = vals.get('date', False) and strftime('%Y', strptime(vals.get('date'), '%Y-%m-%d'))[2:4] or False
        if instance and sequence_number and journal_name and fy_numbers:
            vals.update({'name': "%s-%s-%s%s" % (instance.move_prefix, journal_name, fy_numbers, sequence_number)})
        else:
            raise osv.except_osv(_('Error'), _('Error creating commitment sequence!'))
        return super(account_commitment, self).create(cr, uid, vals, context=context)

    def _update_aal_desc(self, cr, uid, ids, vals, context=None):
        """
        Updates AJI desc. with the new description of the CV if any, else with its Entry Sequence
        """
        if context is None:
            context = {}
        aal_obj = self.pool.get('account.analytic.line')
        if 'description' in vals:
            for cv in self.browse(cr, uid, ids, fields_to_fetch=['state', 'name', 'line_ids'], context=context):
                if cv.state == 'open':
                    desc = vals.get('description') or cv.name
                    for cv_line in cv.line_ids:
                        analytic_lines = cv_line.analytic_lines
                        if analytic_lines:
                            aal_obj.write(cr, uid, [analytic_l.id for analytic_l in analytic_lines], {'name': desc}, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Update analytic lines date if date in vals for validated commitment voucher.
        Update AJI description if the CV desc. has been changed.
        """
        # Some verifications
        if not ids:
            return True
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        aal_obj = self.pool.get('account.analytic.line')
        curr_obj = self.pool.get('res.currency')
        user_obj = self.pool.get('res.users')
        dest_cc_link_obj = self.pool.get('dest.cc.link')
        if 'state' in vals:
            vals['is_draft'] = vals['state'] == 'draft'
        # Browse elements if 'date' in vals
        if vals.get('date', False):
            date = vals.get('date')
            period_ids = get_period_from_date(self, cr, uid, date, context=context)
            vals.update({'period_id': period_ids and period_ids[0]})
            for c in self.browse(cr, uid, ids, context=context):
                if c.state == 'open':
                    cv_currency = vals.get('currency_id') or c.currency_id.id
                    fctal_currency = user_obj.browse(cr, uid, uid, fields_to_fetch=['company_id'], context=context).company_id.currency_id.id
                    for cl in c.line_ids:
                        # Verify that date is compatible with all analytic account from distribution
                        distrib = False
                        if cl.analytic_distribution_id:
                            distrib = cl.analytic_distribution_id
                        elif cl.commit_id and cl.commit_id.analytic_distribution_id:
                            distrib = cl.commit_id.analytic_distribution_id
                        if distrib:
                            for distrib_lines in [distrib.cost_center_lines, distrib.funding_pool_lines,
                                                  distrib.free_1_lines, distrib.free_2_lines]:
                                for distrib_line in distrib_lines:
                                    if distrib_line.analytic_id and \
                                        (distrib_line.analytic_id.date_start and date < distrib_line.analytic_id.date_start or
                                         distrib_line.analytic_id.date and date >= distrib_line.analytic_id.date):
                                        raise osv.except_osv(_('Error'), _('The analytic account %s is not active for given date.') %
                                                             (distrib_line.analytic_id.name,))
                            dest_cc_tuples = set()  # check each Dest/CC combination only once
                            for distrib_cc_l in distrib.cost_center_lines:
                                if distrib_cc_l.analytic_id:  # non mandatory field
                                    dest_cc_tuples.add((distrib_cc_l.destination_id, distrib_cc_l.analytic_id))
                            for distrib_fp_l in distrib.funding_pool_lines:
                                dest_cc_tuples.add((distrib_fp_l.destination_id, distrib_fp_l.cost_center_id))
                            for dest, cc in dest_cc_tuples:
                                if dest_cc_link_obj.is_inactive_dcl(cr, uid, dest.id, cc.id, date, context=context):
                                    raise osv.except_osv(_('Error'), _("The combination \"%s - %s\" is not active at this date: %s") %
                                                         (dest.code or '', cc.code or '', date))
                        # update the dates and fctal amounts of the related analytic lines
                        context.update({'currency_date': date})  # same date used for doc, posting and source date of all lines
                        for aal in cl.analytic_lines:
                            new_aal_amount = curr_obj.compute(cr, uid, cv_currency, fctal_currency, aal.amount_currency or 0.0,
                                                              round=False, context=context)
                            aal_vals = {'date': date,
                                        'source_date': date,
                                        'document_date': date,
                                        'amount': new_aal_amount,
                                        }
                            aal_obj.write(cr, uid, aal.id, aal_vals, context=context)
        self._update_aal_desc(cr, uid, ids, vals, context=context)
        # Default behaviour
        res = super(account_commitment, self).write(cr, uid, ids, vals, context=context)
        return res

    def copy(self, cr, uid, c_id, default=None, context=None):
        """
        Copy analytic_distribution
        """
        # Some verifications
        if not context:
            context = {}
        if not default:
            default = {}
        # Update default values
        default.update({
            'name': self.pool.get('ir.sequence').get(cr, uid, 'account.commitment'),
            'state': 'draft',
            'version': self.get_current_cv_version(cr, uid, context=context),
        })
        # Default method
        res = super(account_commitment, self).copy(cr, uid, c_id, default, context)
        # Update analytic distribution
        if res:
            c = self.browse(cr, uid, res, context=context)
        if res and c.analytic_distribution_id:
            new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, c.analytic_distribution_id.id, {}, context=context)
            if new_distrib_id:
                self.write(cr, uid, [res], {'analytic_distribution_id': new_distrib_id}, context=context)
        return res

    def unlink(self, cr, uid, ids, context=None):
        """
        Only delete "done" state commitments
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        new_ids = []
        # Check that elements are in done state
        for co in self.browse(cr, uid, ids):
            if co.state == 'done':
                new_ids.append(co.id)
        # Give user a message if no done commitments found
        if not new_ids:
            raise osv.except_osv(_('Warning'), _('You can only delete done commitments!'))
        return super(account_commitment, self).unlink(cr, uid, new_ids, context)

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch analytic distribution wizard on a commitment
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
        commitment = self.browse(cr, uid, ids[0], context=context)
        amount = commitment.total or 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = commitment.currency_id and commitment.currency_id.id or company_currency
        # Get analytic_distribution_id
        distrib_id = commitment.analytic_distribution_id and commitment.analytic_distribution_id.id
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'commitment_id': commitment.id,
            'currency_id': currency or False,
            'state': 'dispatch',
            'posting_date': commitment.date,
            'document_date': commitment.date,
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id,})
        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
        # Update some context values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Open it!
        return {
            'name': _('Global analytic distribution'),
            'type': 'ir.actions.act_window',
            'res_model': 'analytic.distribution.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': [wiz_id],
            'context': context,
        }

    def button_analytic_distribution_2(self, cr, uid, ids, context=None):
        """
        This is just an alias for button_analytic_distribution (used to have different names and attrs on both buttons)
        """
        return self.button_analytic_distribution(cr, uid, ids, context=context)

    def button_reset_distribution(self, cr, uid, ids, context=None):
        """
        Reset analytic distribution on all commitment lines.
        To do this, just delete the analytic_distribution id link on each invoice line.
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
        commit_obj = self.pool.get(self._name + '.line')
        # Search commitment lines
        to_reset = commit_obj.search(cr, uid, [('commit_id', 'in', ids)])
        commit_obj.write(cr, uid, to_reset, {'analytic_distribution_id': False})
        return True

    def button_compute(self, cr, uid, ids, context=None):
        """
        Compute commitment voucher total.
        """
        # trick to refresh view and update total amount
        return self.write(cr, uid, ids, [], context=context)

    def get_engagement_lines(self, cr, uid, ids, context=None):
        """
        Return all engagement lines from given commitments (in context)
        """
        # Some verifications
        if not context:
            context = {}
        if context.get('active_ids', False):
            ids = context.get('active_ids')
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
        valid_ids = []
        # Search valid ids
        for co in self.browse(cr, uid, ids):
            for line in co.line_ids:
                if line.analytic_lines:
                    valid_ids.append([x.id for x in line.analytic_lines])
        valid_ids = flatten(valid_ids)
        domain = [('id', 'in', valid_ids), ('account_id.category', '=', 'FUNDING')]
        # Permit to only display engagement lines
        context.update({'search_default_engagements': 1, 'display_fp': True})
        return {
            'name': 'Analytic Entries',
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'context': context,
            'domain': domain,
            'target': 'current',
        }

    def onchange_date(self, cr, uid, ids, date, period_id=False, context=None):
        """
        Update period regarding given date
        """
        # Some verifications
        if not context:
            context = {}
        if not date:
            return False
        # Prepare some values
        vals = {}
        periods = get_period_from_date(self, cr, uid, date, context=context)
        if periods:
            vals['period_id'] = periods[0]
        return {'value': vals}

    def create_analytic_lines(self, cr, uid, ids, context=None):
        """
        Create analytic line for given commitment voucher.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Browse commitments
        for c in self.browse(cr, uid, ids, context=context):
            sign = 1
            if c.cv_flow_type == 'customer':
                sign = -1
            for cl in c.line_ids:
                # Verify that analytic distribution is present
                if cl.analytic_distribution_state != 'valid':
                    raise osv.except_osv(_('Error'), _('Commitment Voucher %s: the Analytic Distribution is not valid '
                                                       'for the account "%s %s".') %
                                         (c.name, cl.account_id.code, cl.account_id.name))
                # Take analytic distribution either from line or from commitment voucher
                distrib_id = cl.analytic_distribution_id and cl.analytic_distribution_id.id or c.analytic_distribution_id and c.analytic_distribution_id.id or False
                if not distrib_id:
                    raise osv.except_osv(_('Error'), _('No analytic distribution found!'))
                # Search if analytic lines exists for this commitment voucher line
                al_ids = self.pool.get('account.analytic.line').search(cr, uid, [('commitment_line_id', '=', cl.id)], context=context)
                if not al_ids:
                    # Create engagement journal lines
                    self.pool.get('analytic.distribution').\
                        create_account_analytic_lines(cr, uid, [distrib_id], c.description or c.name, c.date, sign * cl.amount,
                                                      c.journal_id and c.journal_id.id,
                                                      c.currency_id and c.currency_id.id, c.date or False,
                                                      (c.purchase_id and c.purchase_id.name or c.sale_id and c.sale_id.name) or c.name or False, c.date,
                                                      cl.account_id and cl.account_id.id or False, False, False, cl.id, period_id=c.period_id.id, context=context)
        return True

    def action_commitment_open(self, cr, uid, ids, context=None):
        """
        To do when we validate a commitment.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Browse commitments and create analytic lines
        self.create_analytic_lines(cr, uid, ids, context=context)
        # Validate commitment voucher
        return self.write(cr, uid, ids, {'state': 'open'}, context=context)

    def action_commitment_done(self, cr, uid, ids, context=None):
        """
        To do when a commitment is done.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Browse commitments
        for c in self.browse(cr, uid, ids, context=context):
            # Search analytic lines that have commitment line ids
            search_ids = self.pool.get('account.analytic.line').search(cr, uid, [('commitment_line_id', 'in', [x.id for x in c.line_ids])], context=context)
            # Delete them
            if search_ids:
                res = self.pool.get('account.analytic.line').unlink(cr, uid, search_ids, context=context)
                if not res:
                    raise osv.except_osv(_('Error'), _('An error occurred on engagement lines deletion.'))
            # And finally update commitment voucher state and lines amount
            self.pool.get('account.commitment.line').write(cr, uid, [x.id for x in c.line_ids], {'amount': 0}, context=context)
            self.write(cr, uid, [c.id], {'state':'done'}, context=context)
        return True

    def test_and_close_cv_so(self, cr, uid, ids, invoice_ids=None, context=None):
        """
            set amout=0 on CV lines linked to closed, cancelled(-r) FO line (no more invoices expected)
            and with no draft invoice


            invoice_ids: list of draft invoices to ignore (state will be changed later in the code)
        """

        if invoice_ids is None:
            invoice_ids = []

        iv_ids = invoice_ids[:]
        if not iv_ids:
            iv_ids.append(0)

        cv_line_obj = self.pool.get('account.commitment.line')
        cr.execute('''
            select
                line.id, line.amount
            from
                account_commitment_line line
            left join
                sale_order_line sol on sol.id = line.so_line_id
            left join
                account_invoice_line inv_line on inv_line.sale_order_line_id = sol.id and inv_line.invoice_id not in %s
            left join
                account_invoice inv on inv_line.invoice_id = inv.id and inv.type = 'out_invoice' and inv.from_supply = 't'
            where
                sol.state in ('done', 'cancel', 'cancel_r') and
                line.amount != 0 and
                line.commit_id in %s
            group by
                line.id, line.amount
            having (count(inv.state='draft' or NULL) = 0)
        ''', (tuple(iv_ids), tuple(ids)))
        # from_supply + out_invoice : to ignore draft refund

        for x in cr.fetchall():
            cv_line_obj._update_so_commitment_line(cr, uid, x[0], x[1], from_cancel=True, context=context)

        return True


account_commitment()

class account_commitment_line(osv.osv):
    _name = 'account.commitment.line'
    _description = "Account Commitment Voucher Line"
    _order = "line_number, id desc"
    _rec_name = 'account_id'
    _trace = True

    def _get_distribution_state(self, cr, uid, ids, name, args, context=None):
        """
        Get state of distribution:
         - if compatible with the commitment voucher line, then "valid"
         - if no distribution, take a tour of commitment voucher distribution, if compatible, then "valid"
         - if no distribution on commitment voucher line and commitment voucher, then "none"
         - all other case are "invalid"
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse all given lines
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = self.pool.get('analytic.distribution')._get_distribution_state(cr, uid, line.analytic_distribution_id.id, line.commit_id.analytic_distribution_id.id, line.account_id.id)
        return res

    def _have_analytic_distribution_from_header(self, cr, uid, ids, name, arg, context=None):
        """
        If Commitment have an analytic distribution, return False, else return True
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        for co in self.browse(cr, uid, ids, context=context):
            res[co.id] = True
            if co.analytic_distribution_id:
                res[co.id] = False
        return res

    def get_cv_type(self, cr, uid, context=None):
        """
        Gets the possible CV types
        """
        return self.pool.get('account.commitment').get_cv_type(cr, uid, context)

    _columns = {
        'account_id': fields.many2one('account.account', string="Account", required=True),
        'amount': fields.float(string="Amount left", digits_compute=dp.get_precision('Account'), required=False),
        'initial_amount': fields.float(string="Initial amount", digits_compute=dp.get_precision('Account'), required=True),
        'commit_id': fields.many2one('account.commitment', string="Commitment Voucher", ondelete="cascade"),
        'commit_number': fields.related('commit_id', 'name', type='char', size=64,
                                        readonly=True, store=False, string="Commitment Voucher Number"),
        'commit_type': fields.related('commit_id', 'type', string="Commitment Voucher Type", type='selection', readonly=True,
                                      store=False, invisible=True, selection=get_cv_type, write_relate=False),
        'analytic_distribution_id': fields.many2one('analytic.distribution', string="Analytic distribution"),
        'analytic_distribution_state': fields.function(_get_distribution_state, method=True, type='selection',
                                                       selection=[('none', 'None'), ('valid', 'Valid'), ('invalid', 'Invalid')],
                                                       string="Distribution state", help="Informs from distribution state among 'none', 'valid', 'invalid."),
        'have_analytic_distribution_from_header': fields.function(_have_analytic_distribution_from_header, method=True, type='boolean',
                                                                  string='Header Distrib.?'),
        'analytic_lines': fields.one2many('account.analytic.line', 'commitment_line_id', string="Analytic Lines"),
        'first': fields.boolean(string="Is not created?", help="Useful for onchange method for views. Should be False after line creation.",
                                readonly=True),
        # for CV in version 1
        'purchase_order_line_ids': fields.many2many('purchase.order.line', 'purchase_line_commitment_rel', 'commitment_id', 'purchase_id',
                                                    string="Purchase Order Lines (deprecated)", readonly=True),
        # for CV starting from version 2
        'po_line_id': fields.many2one('purchase.order.line', "PO Line"),
        'so_line_id': fields.many2one('sale.order.line', "SO Line"),
        'line_product_id': fields.many2one('product.product', string="Product", readonly=True),
        'line_number': fields.integer_null('Line', readonly=True),
    }

    _defaults = {
        'initial_amount': lambda *a: 0.0,
        'amount': lambda *a: 0.0,
        'first': lambda *a: True,
    }

    def onchange_initial_amount(self, cr, uid, ids, first, amount):
        """
        """
        # Prepare some values
        res = {}
        # Some verification
        if first and amount:
            res['value'] = {'amount': amount}
        return res

    def update_analytic_lines(self, cr, uid, ids, amount, account_id=False, context=None):
        """
        Update analytic lines from given commitment lines with an ugly method: delete all analytic lines and recreate them…
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
        for cl in self.browse(cr, uid, ids, context=context):
            # Browse distribution
            sign = 1
            if cl.commit_id.cv_flow_type == 'customer':
                sign = -1
            distrib_id = cl.analytic_distribution_id and cl.analytic_distribution_id.id or False
            if not distrib_id:
                distrib_id = cl.commit_id and cl.commit_id.analytic_distribution_id and cl.commit_id.analytic_distribution_id.id or False
            if distrib_id:
                analytic_line_ids = self.pool.get('account.analytic.line').search(cr, uid, [('commitment_line_id', '=', cl.id)], context=context)
                self.pool.get('account.analytic.line').unlink(cr, uid, analytic_line_ids, context=context)
                ref = cl.commit_id and cl.commit_id.purchase_id and cl.commit_id.purchase_id.name or cl.commit_id.sale_id and cl.commit_id.sale_id.name or False
                if cl.commit_id:
                    desc = cl.commit_id.description or cl.commit_id.name
                else:
                    desc = 'Commitment voucher line'
                self.pool.get('analytic.distribution').\
                    create_account_analytic_lines(cr, uid, [distrib_id], desc,
                                                  cl.commit_id.date, sign * amount, cl.commit_id.journal_id.id, cl.commit_id.currency_id.id,
                                                  cl.commit_id and cl.commit_id.date or False, ref, cl.commit_id.date,
                                                  account_id or cl.account_id.id, move_id=False, invoice_line_id=False,
                                                  commitment_line_id=cl.id, period_id=cl.commit_id.period_id.id, context=context)
        return True

    def create(self, cr, uid, vals, context=None):
        """
        Verify that given account_id (in vals) is not 'view'.
        Update initial amount with those given by 'amount' field.
        Verify amount sign.
        """
        # Some verifications
        if not context:
            context = {}
        # Change 'first' value to False (In order view correctly displayed)
        if not 'first' in vals:
            vals.update({'first': False})
        # Copy initial_amount to amount
        vals.update({'amount': vals.get('initial_amount', 0.0)})
        if 'account_id' in vals:
            account_id = vals.get('account_id')
            account = self.pool.get('account.account').browse(cr, uid, [account_id], context=context)[0]
            if account.type in ['view']:
                raise osv.except_osv(_('Error'), _("You cannot create a commitment voucher line on a 'view' account type!"))
        # Verify amount validity
        if 'amount' in vals and vals.get('amount', 0.0) < 0.0:
            raise osv.except_osv(_('Warning'), _('Total amount should be equal or superior to 0!'))
        if 'initial_amount' in vals and vals.get('initial_amount', 0.0) <= 0.0:
            raise osv.except_osv(_('Warning'), _('Initial Amount should be superior to 0!'))
        if 'initial_amount' in vals and 'amount' in vals:
            if vals.get('initial_amount') < vals.get('amount'):
                raise osv.except_osv(_('Warning'), _('Initial Amount should be superior to Amount Left'))
        res = super(account_commitment_line, self).create(cr, uid, vals, context={})
        if res:
            for cl in self.browse(cr, uid, [res], context=context):
                if 'amount' in vals and cl.commit_id and cl.commit_id.state and cl.commit_id.state == 'open':
                    self.update_analytic_lines(cr, uid, [cl.id], vals.get('amount'), context=context)
        return res

    def write(self, cr, uid, ids, vals, context=None):
        """
        Verify that given account_id is not 'view'.
        Update initial_amount if amount in vals and type is 'manual' and state is 'draft'.
        Update analytic distribution if amount in vals.
        Verify amount sign.
        """
        # Some verifications
        if not ids:
            return True
        if not context:
            context = {}
        if 'account_id' in vals:
            account_id = vals.get('account_id')
            account = self.pool.get('account.account').browse(cr, uid, [account_id], context=context)[0]
            if account.type in ['view']:
                raise osv.except_osv(_('Error'), _("You cannot write a commitment voucher line on a 'view' account type!"))
        # Update analytic distribution if needed and initial_amount
        for line in self.browse(cr, uid, ids, context=context):
            # Verify amount validity
            if 'amount' in vals and vals.get('amount', 0.0) < 0.0:
                raise osv.except_osv(_('Warning'), _('Amount Left should be equal or superior to 0!'))
            if 'initial_amount' in vals and vals.get('initial_amount', 0.0) <= 0.0:
                raise osv.except_osv(_('Warning'), _('Initial Amount should be superior to 0!'))
            message = _('Initial Amount should be superior to Amount Left')

            # verify that initial amount is superior to amount left
            if 'amount' in vals and 'initial_amount' in vals:
                if vals.get('initial_amount') < vals.get('amount'):
                    raise osv.except_osv(_('Warning'), message)
            elif 'amount' in vals:
                if line.initial_amount < vals.get('amount'):
                    raise osv.except_osv(_('Warning'), message)
            elif 'initial_amount' in vals:
                if vals.get('initial_amount') < line.amount:
                    raise osv.except_osv(_('Warning'), message)
            # verify analytic distribution only on 'open' commitments
            if line.commit_id and line.commit_id.state and line.commit_id.state == 'open':
                # Search distribution
                distrib_id = line.analytic_distribution_id and line.analytic_distribution_id.id or False
                if not distrib_id:
                    distrib_id = line.commit_id.analytic_distribution_id and line.commit_id.analytic_distribution_id.id or False
                # Verify amount
                if 'amount' in vals and vals.get('amount', 0.0) == '0.0':
                    # delete analytic lines that are null
                    if distrib_id:
                        distrib = self.pool.get('analytic.distribution').browse(cr, uid, [distrib_id], context=context)[0]
                        if distrib and distrib.analytic_lines:
                            self.pool.get('account.analytic.line').unlink(cr, uid, [x.id for x in distrib.analytic_lines], context=context)
                elif 'amount' in vals:
                    # Verify expense account
                    account_id = False
                    if 'account_id' in vals and vals.get('account_id', False) and line.account_id.id != vals.get('account_id'):
                        account_id = vals.get('account_id')
                    # Update analytic lines
                    if distrib_id:
                        self.update_analytic_lines(cr, uid, [line.id], vals.get('amount'), account_id, context=context)
        return super(account_commitment_line, self).write(cr, uid, ids, vals, context={})

    def copy_data(self, cr, uid, cv_line_id, default=None, context=None):
        """
        Duplicates a CV line: resets the link to PO line
        """
        if context is None:
            context = {}
        if default is None:
            default = {}
        default.update({
            'po_line_id': False,
        })
        return super(account_commitment_line, self).copy_data(cr, uid, cv_line_id, default, context)

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch analytic distribution wizard on a commitment voucher line
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        if not ids:
            raise osv.except_osv(_('Error'), _('No invoice line given. Please save your commitment voucher line before.'))
        # Prepare some values
        commitment_voucher_line = self.browse(cr, uid, ids[0], context=context)
        amount = commitment_voucher_line.amount or 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = commitment_voucher_line.commit_id.currency_id and commitment_voucher_line.commit_id.currency_id.id or company_currency
        # Get analytic distribution id from this line
        distrib_id = commitment_voucher_line and commitment_voucher_line.analytic_distribution_id and commitment_voucher_line.analytic_distribution_id.id or False
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'commitment_line_id': commitment_voucher_line.id,
            'currency_id': currency or False,
            'state': 'dispatch',
            'account_id': commitment_voucher_line.account_id and commitment_voucher_line.account_id.id or False,
            'posting_date': commitment_voucher_line.commit_id.date,
            'document_date': commitment_voucher_line.commit_id.date,
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id,})
        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
        # Update some context values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Open it!
        return {
            'name': _('Analytic distribution'),
            'type': 'ir.actions.act_window',
            'res_model': 'analytic.distribution.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': [wiz_id],
            'context': context,
        }

    def _update_so_commitment_line(self, cr, uid, id, amount, from_cancel=True, context=None):
        """
            reduce amount on CV line from SO
            called when:
              * FO line is canceled(-r)
              * SI is opened or canceled
        """
        if context is None:
            context = {}
        wf_service = netsvc.LocalService("workflow")
        cv_obj = self.pool.get('account.commitment')

        cv_line = self.browse(cr, uid, id, context=context)
        if not from_cancel and cv_line.commit_id.state == 'draft':
            wf_service.trg_validate(uid, 'account.commitment', cv_line.commit_id.id, 'commitment_open', cr)

        amount_left = max(round(cv_line.amount - amount, 2), 0)
        # this will trigger AJIs update
        self.write(cr, uid, [id], {'amount': amount_left}, context=context)

        cv = cv_obj.read(cr, uid, cv_line.commit_id.id, ['total'], context=context)
        if abs(cv['total']) < 0.001:
            cv_obj.action_commitment_done(cr, uid, [cv_line.commit_id.id], context=context)

        return True


account_commitment_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
