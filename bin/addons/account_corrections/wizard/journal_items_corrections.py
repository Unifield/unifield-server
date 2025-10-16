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
from tools.translate import _
from time import strftime
from lxml import etree

class journal_items_corrections_lines(osv.osv_memory):
    _name = 'wizard.journal.items.corrections.lines'
    _description = 'Journal items corrections lines'

    def _get_distribution_state(self, cr, uid, ids, name, args, context=None):
        """
        Get state of distribution:
         - if compatible with the line, then "valid"
         - if no distribution on line, then "none"
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
            res[line.id] = 'none'
            if line.analytic_distribution_id:
                amount = (line.debit_currency or 0.0) - (line.credit_currency or 0.0)
                res[line.id] = self.pool.get('analytic.distribution')._get_distribution_state(cr, uid, line.analytic_distribution_id.id,
                                                                                              False, line.account_id.id, amount=amount)
        return res

    def _get_is_analytic_target(self, cr, uid, ids, name, args,  context=None):
        res = {}
        if not ids:
            return res
        if isinstance(ids, int):
            ids = [ids]
        for line_br in self.browse(cr, uid, ids, context=context):
            res[line_br.id] = line_br.account_id and line_br.account_id.is_analytic_addicted and not line_br.account_id.is_not_ad_correctable or False
        return res

    def _get_is_account_correctible(self, cr, uid, ids, name, args,  context=None):
        res = {}
        if not ids:
            return res
        if isinstance(ids, int):
            ids = [ids]
        for line_br in self.browse(cr, uid, ids, context=context):
            res[line_br.id] = True
            if line_br.move_line_id \
                    and line_br.move_line_id.last_cor_was_only_analytic:
                res[line_br.id] = False
            elif line_br.account_id and line_br.account_id.is_not_hq_correctible:
                res[line_br.id] = False
        return res

    def _get_third_parties(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Gets the right Third Parties based on:
        - the partner / employee of the line if any (Journal 3d Party is excluded)
        - or on the line account type
        """
        res = {}
        if context is None:
            context = {}
        for line in self.browse(cr, uid, ids, context=context):
            if line.employee_id:
                res[line.id] = {'third_parties': 'hr.employee,%s' % line.employee_id.id}
                res[line.id]['partner_type'] = {'options': [('hr.employee', 'Employee')],
                                                'selection': 'hr.employee,%s' % line.employee_id.id}
            elif line.partner_id:
                res[line.id] = {'third_parties': 'res.partner,%s' % line.partner_id.id}
                res[line.id]['partner_type'] = {'options': [('res.partner', 'Partner')],
                                                'selection': 'res.partner,%s' % line.partner_id.id}
            else:
                res[line.id] = {'third_parties': False}
                if line.account_id:
                    acc_type = line.account_id.type_for_register
                    if acc_type == 'advance':
                        third_type = [('hr.employee', 'Employee')]
                        third_selection = 'hr.employee,'
                    elif acc_type == 'down_payment':
                        third_type = [('res.partner', 'Partner')]
                        third_selection = 'res.partner,'
                    else:
                        # by default when no restriction and for the "payroll" type
                        third_type = [('res.partner', 'Partner'), ('hr.employee', 'Employee')]
                        third_selection = 'res.partner,'
                    res[line.id]['partner_type'] = {'options': third_type, 'selection': third_selection}
        return res

    def _set_third_parties(self, cr, uid, obj_id, name=None, value=None, fnct_inv_arg=None, context=None):
        """
        Sets the chosen 3d Party to the wizard line (can be: a partner, an employee, or empty)
        """
        if context is None:
            context = {}
        if name == 'partner_type':
            employee_id = False
            partner_id = False
            element = False
            if value:
                fields = value.split(",")
                element = fields[0]
            if element == 'hr.employee':
                employee_id = fields[1] and int(fields[1]) or False
            elif element == 'res.partner':
                partner_id = fields[1] and int(fields[1]) or False
            vals = {
                'employee_id': employee_id,
                'partner_id': partner_id,
            }
            self.write(cr, uid, obj_id, vals, context=context)
        return True

    def _get_partner_txt_only(self, cr, uid, ids, name, args, context=None):
        """
        True if the JI to be corrected has got a partner_txt without any partner/employee/transfer_journal
        Ex.: coordo line with an internal partner synched to HQ
        """
        res = {}
        if not ids:
            return res
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}
        for corr_line in self.browse(cr, uid, ids, fields_to_fetch=['move_line_id'], context=context):
            res[corr_line.id] = False
            aml = corr_line.move_line_id
            if aml.partner_txt and not (aml.partner_id or aml.employee_id or aml.transfer_journal_id):
                res[corr_line.id] = True
        return res

    def onchange_correction_line_account_id(self, cr, uid, ids, account_id=False, current_tp=False):
        """
        Adapts the "Third Parties" selectable on the wizard line according to the account selected
        """
        vals = {}
        warning = {}
        if isinstance(account_id, (list, tuple)):
            account_id = account_id[0]
        acc_obj = self.pool.get('account.account')
        if account_id:
            third_type = [('res.partner', 'Partner'), ('hr.employee', 'Employee')]
            third_required = False
            third_selection = 'res.partner,0'
            account = acc_obj.browse(cr, uid, account_id, fields_to_fetch=['code', 'name', 'type_for_register'])
            acc_type = account.type_for_register
            if acc_type in ['transfer', 'transfer_same']:  # requires a journal 3d party on which corr. are forbidden
                warning = {
                    'title': _('Warning!'),
                    'message': _('The account %s - %s requires a Journal Third Party.') % (account.code, account.name)
                }
                vals.update({'account_id': False})  # empty the account
                third_type = [('res.partner', 'Partner'), ('hr.employee', 'Employee')]
                third_required = False
                third_selection = 'res.partner,0'
            elif acc_type == 'advance':
                third_type = [('hr.employee', 'Employee')]
                third_required = True
                third_selection = 'hr.employee,0'
            elif acc_type == 'down_payment':
                third_type = [('res.partner', 'Partner')]
                third_required = True
                third_selection = 'res.partner,0'
            elif acc_type == 'payroll':
                third_type = [('res.partner', 'Partner'), ('hr.employee', 'Employee')]
                third_required = True
                third_selection = 'res.partner,0'
            # keep the current Third Party if it is compatible with the new account selected
            if current_tp:
                current_tp_type = current_tp.split(',')[0]  # ex: 'res.partner'
                for th_type in third_type:
                    if current_tp_type == th_type[0]:
                        third_selection = current_tp
                        continue
            vals.update({'partner_type_mandatory': third_required,
                         'partner_type': {'options': third_type,
                                          'selection': third_selection}})
        return {'value': vals, 'warning': warning}

    _columns = {
        'move_line_id': fields.many2one('account.move.line', string="Account move line", readonly=True, required=True),
        'wizard_id': fields.many2one('wizard.journal.items.corrections', string="wizard"),
        'account_id': fields.many2one('account.account', string="Account", required=True),
        'move_id': fields.many2one('account.move', string="Entry sequence", readonly=True),
        'ref': fields.char(string="Reference", size=254, readonly=True),
        'journal_id': fields.many2one('account.journal', string="Journal Code", readonly=True),
        'period_id': fields.many2one('account.period', string="Period", readonly=True),
        'date': fields.date('Posting date', readonly=True),
        'partner_id': fields.many2one('res.partner', 'Partner'),
        'transfer_journal_id': fields.many2one("account.journal", "Journal"),
        'employee_id': fields.many2one("hr.employee", "Employee"),
        'debit_currency': fields.float('Book. Debit', readonly=True),
        'credit_currency': fields.float('Book. Credit', readonly=True),
        'currency_id': fields.many2one('res.currency', string="Book. Curr.", readonly=True),
        'analytic_distribution_id': fields.many2one('analytic.distribution', string="Analytic Distribution", readonly=True),
        'analytic_distribution_state': fields.function(_get_distribution_state, method=True, type='selection',
                                                       selection=[('none', 'None'), ('valid', 'Valid'),
                                                                  ('invalid', 'Invalid'), ('invalid_small_amount', 'Invalid')],
                                                       string="Distribution state", help="Informs from distribution state among 'none', 'valid', 'invalid."),
        'is_analytic_target': fields.function(_get_is_analytic_target, type='boolean', string='Is analytic target', method=True, invisible=True),
        'is_account_correctible': fields.function(_get_is_account_correctible,
                                                  type='boolean', string='Is account correctible',
                                                  method=True, invisible=True),
        'partner_type': fields.function(_get_third_parties, fnct_inv=_set_third_parties, type='reference', method=True,
                                        string="Third Parties", readonly=False,
                                        selection=[('res.partner', 'Partner'), ('hr.employee', 'Employee')],
                                        multi="third_parties_key"),
        'partner_type_mandatory': fields.boolean('Third Party Mandatory'),
        'third_parties': fields.function(_get_third_parties, type='reference', method=True,
                                         string="Third Parties",
                                         selection=[('res.partner', 'Partner'), ('hr.employee', 'Employee')],
                                         help="To use for python code when registering", multi="third_parties_key"),
        'partner_txt_only': fields.function(_get_partner_txt_only, type='boolean', method=True, invisible=True,
                                            string='Has a "partner_txt" without any related partner/employee/transfer journal',
                                            help="The Third Party of the line to be corrected hasn't been synched to this instance"),
    }

    _defaults = {
        'from_donation': lambda *a: False,
        'is_analytic_target': lambda *a: False,
        'is_account_correctible': lambda *a: True,
        'partner_type_mandatory': lambda *a: False,
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Change account_id domain if account is donation
        """
        if not context:
            context = {}
        view = super(journal_items_corrections_lines, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if context and context.get('from_donation_account', False):
            tree = etree.fromstring(view['arch'])
            fields = tree.xpath('//field[@name="account_id"]')
            for field in fields:
                field.set('domain', "[('type', '!=', 'view'), ('type_for_register', '=', 'donation'), ('user_type.code', '=', 'expense'), ('user_type.report_type', '=', 'none')]")
            view['arch'] = etree.tostring(tree, encoding='unicode')
        return view

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Open an analytic distribution wizard
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Add context in order to know we come from a correction wizard
        this_line = self.browse(cr, uid, ids[0], context=context)
        wiz = this_line.wizard_id
        context.update({'from': 'wizard.journal.items.corrections', 'wiz_id': wiz.id or False})
        # Get distribution
        distrib_id = False
        if wiz and wiz.move_line_id and wiz.move_line_id.analytic_distribution_id:
            distrib_id = wiz.move_line_id.analytic_distribution_id.id or False
        if not distrib_id:
            distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {})
            self.pool.get('account.move.line').write(cr, uid, wiz.move_line_id.id, {'analytic_distribution_id': distrib_id})
        # Prepare values
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = wiz.move_line_id.currency_id and wiz.move_line_id.currency_id.id or company_currency
        amount = wiz.move_line_id.amount_currency and wiz.move_line_id.amount_currency or 0.0
        vals = {
            'total_amount': amount,
            'move_line_id': wiz.move_line_id and wiz.move_line_id.id,
            'currency_id': currency or False,
            'old_account_id': wiz.move_line_id and wiz.move_line_id.account_id and wiz.move_line_id.account_id.id or False,
            'old_partner_id': wiz.move_line_id and wiz.move_line_id.partner_id and wiz.move_line_id.partner_id.id or False,
            'old_employee_id': wiz.move_line_id and wiz.move_line_id.employee_id and wiz.move_line_id.employee_id.id or False,
            'distribution_id': distrib_id,
            'state': 'dispatch', # Be very careful, if this state is not applied when creating wizard => no lines displayed
            'date': wiz.date or strftime('%Y-%m-%d'),
            'account_id': this_line.account_id and this_line.account_id.id or False,
            'new_partner_id': this_line.partner_id and this_line.partner_id.id or False,
            'new_employee_id': this_line.employee_id and this_line.employee_id.id or False,
            'document_date': wiz.move_line_id.document_date,
            'posting_date': wiz.date or wiz.move_line_id.date,
        }
        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
        # Change wizard state to 'correction' in order to display mandatory fields
        wiz_obj.write(cr, uid, [wiz_id], {'state': 'correction'}, context=context)
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

journal_items_corrections_lines()

class journal_items_corrections(osv.osv_memory):
    _name = 'wizard.journal.items.corrections'
    _description = 'Journal items corrections wizard'

    def _get_from_register(self, cr, uid, ids, field_name, arg, context):
        """
        Return true if the line comes from a journal entry that have links to a register line
        """
        res = {}
        for wiz in self.browse(cr, uid, ids, context):
            res[wiz.id] = False
            if wiz.move_line_id.move_id and wiz.move_line_id.move_id.line_id:
                for ml_line in wiz.move_line_id.move_id.line_id:
                    if ml_line.statement_id:
                        res[wiz.id] = True
                        break
        return res

    _columns = {
        'date': fields.date(string="Correction date", states={'open':[('required', True)]}),
        'move_line_id': fields.many2one('account.move.line', string="Move Line", required=True, readonly=True),
        'to_be_corrected_ids': fields.one2many('wizard.journal.items.corrections.lines', 'wizard_id', string='', help='Line to be corrected'),
        'state': fields.selection([('draft', 'Draft'), ('open', 'Open')], string="state"),
        'from_donation': fields.boolean('From Donation account?'),
        'from_register': fields.function(_get_from_register, type='boolean', string='From register?', method=True, store=False),
        'from_ji': fields.boolean('Opened from the JI view?'),
    }

    _defaults = {
        'state': lambda *a: 'draft',
    }

    def onchange_date(self, cr, uid, ids, date, context=None):
        """
        Write date on this wizard.
        NB: this is essentially for analytic distribution correction wizard
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        if not date:
            return False
        return self.write(cr, uid, ids, {'date': date}, context=context)

    def create(self, cr, uid, vals, context=None):
        """
        Fill in all elements in our wizard with given move_line_id field
        """
        # Verifications
        if not context:
            context = {}
        # Normal mechanism
        res = super(journal_items_corrections, self).create(cr, uid, vals, context=context)
        # Process given move line to complete wizard
        if 'move_line_id' in vals:
            move_line_id = vals.get('move_line_id')
            move_line = self.pool.get('account.move.line').browse(cr, uid, [move_line_id])[0]
            corrected_line_vals = {
                'wizard_id': res,
                'move_line_id': move_line.id,
                'account_id': move_line.account_id.id,
                'move_id': move_line.move_id.id,
                'ref': move_line.ref,
                'journal_id': move_line.journal_id.id,
                'date': move_line.date,
                'debit_currency': move_line.debit_currency,
                'credit_currency': move_line.credit_currency,
                'period_id': move_line.period_id.id,
                'currency_id': move_line.currency_id.id,
                'partner_id': move_line.partner_id and move_line.partner_id.id or None,
                'employee_id': move_line.employee_id and move_line.employee_id.id or None,
                'transfer_journal_id': move_line.transfer_journal_id and move_line.transfer_journal_id.id or None,
                'partner_type_mandatory': move_line.partner_type_mandatory or False,
                'analytic_distribution_id': move_line.analytic_distribution_id and move_line.analytic_distribution_id.id or None,
            }
            self.pool.get('wizard.journal.items.corrections.lines').create(cr, uid, corrected_line_vals, context=context)
        return res

    def compare_lines(self, cr, uid, old_line_id=None, new_line_id=None, context=None):
        """
        Compare an account move line to a wizard journal items corrections line regarding 2 fields:
         - account_id (1)
         - partner_type (partner_id, employee_id or transfer_journal_id) (2)
        Then return the sum.
        """
        if context is None:
            context = {}
        if not old_line_id or not new_line_id:
            raise osv.except_osv(_('Error'), _('An ID is missing!'))
        # Prepare some values
        res = 0
        # Lines
        old_line = self.pool.get('account.move.line').browse(cr, uid, [old_line_id], context=context)[0]
        new_line = self.pool.get('wizard.journal.items.corrections.lines').browse(cr, uid, [new_line_id], context=context)[0]
        # Fields
        old_account = old_line.account_id and old_line.account_id.id or False
        new_account = new_line.account_id and new_line.account_id.id or False
        old_third_party = old_line.partner_id or old_line.employee_id or old_line.transfer_journal_id or False
        new_third_party = new_line.partner_id or new_line.employee_id or new_line.transfer_journal_id or False
        if old_account != new_account:
            res += 1
        if old_third_party != new_third_party:
            res += 2
        return res

    def _check_account_partner_compatibility(self, cr, uid, account, aml, context):
        """
        Check the compatibility between the account and the aml Third Party: raise a warning if they are not compatible.
        :param account: new account selected in the Correction Wizard
        :param aml: Journal Item with the Third Party to check
        """
        if context is None:
            context = {}
        acc_obj = self.pool.get('account.account')
        employee_obj = self.pool.get('hr.employee')
        partner_obj = self.pool.get('res.partner')
        journal_obj = self.pool.get('account.journal')
        acc_type = account.type_for_register
        if acc_type != 'none':
            # get the right Third Party to check if there is a partner_txt ONLY (e.g.: correction made on HQ entry)
            partner_txt = aml.partner_txt
            partner_id = aml.partner_id and aml.partner_id.id or False
            employee_id = aml.employee_id and aml.employee_id.id or False
            partner_journal = aml.transfer_journal_id
            if partner_txt and not partner_id and not employee_id and not partner_journal:
                employee_ids = employee_obj.search(cr, uid, [('name', '=', partner_txt)], limit=1, context=context)
                if employee_ids:
                    employee_id = employee_ids[0]
                else:
                    partner_ids = partner_obj.search(cr, uid, [('name', '=', partner_txt), ('active', 'in', ['t', 'f'])],
                                                     limit=1, context=context)
                    if partner_ids:
                        partner_id = partner_ids[0]
                    else:
                        journal_ids = journal_obj.search(cr, uid, [('code', '=', partner_txt)], limit=1, context=context)
                        if journal_ids:
                            partner_journal = journal_obj.browse(cr, uid, journal_ids[0], context=context)
                # if there is a partner_txt but no related Third Party found:
                # ignore the check if "ignore_non_existing_tp" is in context (e.g. when validating HQ entries)
                if not partner_id and not employee_id and not partner_journal and context.get('ignore_non_existing_tp', False):
                    return True
            # Check the compatibility with the "Type For Specific Treatment" of the account
            if acc_type in ['transfer', 'transfer_same']:
                is_liquidity = partner_journal and partner_journal.type in ['cash', 'bank', 'cheque'] and partner_journal.currency
                if acc_type == 'transfer_same' and (not is_liquidity or partner_journal.currency.id != aml.currency_id.id):
                    raise osv.except_osv(_('Warning'),
                                         _('The account "%s - %s" is only compatible with a Liquidity Journal Third Party\n'
                                           'having the same currency as the booking one.') % (account.code, account.name))
                elif acc_type == 'transfer' and (not is_liquidity or partner_journal.currency.id == aml.currency_id.id):
                    raise osv.except_osv(_('Warning'),
                                         _('The account "%s - %s" is only compatible with a Liquidity Journal Third Party\n'
                                           'having a currency different from the booking one.') % (account.code, account.name))
            elif acc_type == 'advance' and not employee_id:
                raise osv.except_osv(_('Warning'), _('The account "%s - %s" is only compatible '
                                                     'with an Employee Third Party.') % (account.code, account.name))
            elif acc_type == 'down_payment' and not partner_id:
                raise osv.except_osv(_('Warning'), _('The account "%s - %s" is only compatible '
                                                     'with a Partner Third Party.') % (account.code, account.name))
            elif acc_type == 'payroll' and not partner_id and not employee_id:
                raise osv.except_osv(_('Warning'), _('The account "%s - %s" is only compatible '
                                                     'with a Partner or an Employee Third Party.') % (account.code, account.name))
        else:
            # Check the compatibility with the Allowed Partner Types
            # (according to US-1307 this check is done only when the account has no "Type For Specific Treatment")
            acc_obj.is_allowed_for_thirdparty(cr, uid, [account.id], partner_type=aml.partner_type or False, partner_txt=aml.partner_txt or False,
                                              employee_id=aml.employee_id or False, transfer_journal_id=aml.transfer_journal_id or False,
                                              partner_id=aml.partner_id or False, raise_it=True, context=context)
        return True

    def correct_manually(self, cr, uid, ids, context=None):
        """
        Gets the JI displayed in the wizard and sets it as Manually Corrected
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        aml_obj = self.pool.get('account.move.line')
        wizard = self.browse(cr, uid, ids[0], context=context)
        aml_obj.set_as_corrected(cr, uid, [wizard.move_line_id.id], context=context)
        return {'type': 'ir.actions.act_window_close'}

    def action_confirm(self, cr, uid, ids, context=None, distrib_id=False):
        """
        Do a correction from the given line
        """
        # Verification
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        aml_obj = self.pool.get('account.move.line')
        # Verify that date is superior to line's date
        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.move_line_id and wiz.move_line_id.date:
                if not wiz.date >= wiz.move_line_id.date:
                    raise osv.except_osv(_('Warning'), _('Please insert a correction date from the entry date onwards.'))
        # Retrieve values
        wizard = self.browse(cr, uid, ids[0], context=context)

        allow_extra = self.pool.get('res.company').extra_period_config(cr) == 'other'
        # UFTP-388: Check if the given period is valid: period open, or not close, if not just block the correction
        correction_period_id = self.pool.get('account.period').get_open_period_from_date(cr, uid, wizard.date, allow_extra=allow_extra)
        if not correction_period_id:
            raise osv.except_osv(_('Error'), _('No open period found for the given date: %s') % (wizard.date,))

        # Fetch old line
        old_line = wizard.move_line_id
        # Verify what have changed between old line and new one
        new_lines = wizard.to_be_corrected_ids
        # compare lines
        comparison = self.compare_lines(cr, uid, old_line.id, new_lines[0].id, context=context)
        if 1 <= comparison <= 3:  # corr. on account and 3d Party are currently handled the same way (REV/COR generated)
            if new_lines[0].partner_txt_only:
                # prevent change on 3d Party if the 3d Party of the initial line hasn't been synched to the current
                # instance (=> only partner_txt exists)
                new_tp = None
            else:
                new_tp = new_lines[0].partner_type
            res = aml_obj.correct_aml(cr, uid, [old_line.id], wizard.date, new_lines[0].account_id.id, distrib_id,
                                      new_third_party=new_tp, context=context)
            if not res:
                raise osv.except_osv(_('Error'), _('No change made!'))
        else:
            raise osv.except_osv(_('Warning'), _('No modifications seen!'))
        return {'type': 'ir.actions.act_window_close', 'success_move_line_ids': res}

journal_items_corrections()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
