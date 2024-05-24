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

import datetime
from osv import osv, fields

from tools.translate import _

from account_override import ACCOUNT_RESTRICTED_AREA
from msf_field_access_rights.osv_override import _get_instance_level
from tools.misc import fakeUid

class account_journal(osv.osv):
    _inherit = "account.journal"

    def get_journal_type(self, cursor, user_id, context=None):
        return [('accrual', 'Accrual'),
                ('bank', 'Bank'),
                ('cash','Cash'),
                ('cheque', 'Cheque'),
                ('correction', 'Correction Auto'),
                ('correction_hq', 'Correction HQ'),
                ('correction_manual', 'Correction Manual'),
                ('cur_adj', 'Currency Adjustment'),
                ('depreciation', 'Depreciation'),
                ('general', 'General'),
                ('hq', 'HQ'),
                ('hr', 'HR'),
                ('inkind', 'In-kind Donation'),
                ('intermission', 'Intermission'),
                ('migration', 'Migration'),
                ('extra', 'OD-Extra Accounting'),
                ('situation', 'Opening/Closing Situation'),
                ('purchase', 'Purchase'),
                ('purchase_refund','Purchase Refund'),
                ('revaluation', 'Revaluation'),
                ('sale', 'Sale'),
                ('sale_refund','Sale Refund'),
                ('stock', 'Stock'),
                ('system', 'System'),
                ]

    def _get_has_entries(self, cr, uid, ids, field_name, arg, context=None):
        def count_entries(journal_id):
            return am_obj.search(cr, uid, [('journal_id', '=', journal_id)],
                                 limit=1, context=context)

        res = {}
        if not ids:
            return res
        am_obj = self.pool.get('account.move')
        if isinstance(ids, int):
            ids = [ids]
        for id in ids:
            res[id] = bool(count_entries(id))
        return res

    def _get_has_non_draft_register(self, cr, uid, ids, field_name, arg, context=None):
        def has_non_draft_reg(journal_id):
            return abs_obj.search(cr, uid, [('journal_id', '=', journal_id), ('state', '!=', 'draft')], limit=1, context=context)
        res = {}
        if not ids:
            return res
        abs_obj = self.pool.get('account.bank.statement')
        if isinstance(ids, int):
            ids = [ids]
        for id in ids:
            res[id] = bool(has_non_draft_reg(id))
        return res

    _columns = {
        'type': fields.selection(get_journal_type, 'Type', size=32, required=True, select=1),
        'code': fields.char('Code', size=10, required=True, help="The code will be used to generate the numbers of the journal entries of this journal."),
        'bank_journal_id': fields.many2one('account.journal', _("Corresponding bank journal"),
                                           domain="[('type', '=', 'bank'), ('currency', '=', currency), ('is_active', '=', True)]"),
        'cheque_journal_id': fields.one2many('account.journal', 'bank_journal_id', 'Linked cheque'),
        'has_entries': fields.function(_get_has_entries, type='boolean', method=True, string='Has journal entries'),
        'has_non_draft_register': fields.function(_get_has_non_draft_register, type='boolean', method=True, string='Has non-draft register'),
    }

    _defaults = {
        'allow_date': False,
        'centralisation': False,
        'entry_posted': False,
        'update_posted': True,
        'group_invoice_lines': False,
    }

    def _check_correction_type(self, cr, uid, ids, context=None):
        """
        Check that only one "Correction" and one "Correction HQ" journals exist per instance
        """
        if context is None:
            context = {}
        for journal in self.browse(cr, uid, ids, fields_to_fetch=['type', 'instance_id'], context=context):
            if journal.type in ('correction', 'correction_hq') and journal.instance_id:
                journal_dom = [('type', '=', journal.type), ('instance_id', '=', journal.instance_id.id), ('id', '!=', journal.id)]
                if self.search_exist(cr, uid, journal_dom, context=context):
                    return False
        return True

    def _check_correction_analytic_journal(self, cr, uid, ids, context=None):
        """
        In case of Correction journal or Correction HQ journal, check that the analytic journal selected is the right one
        """
        if context is None:
            context = {}
        for journal in self.browse(cr, uid, ids, fields_to_fetch=['type', 'analytic_journal_id', 'instance_id'], context=context):
            if journal.type in ('correction', 'correction_hq'):
                if not journal.analytic_journal_id:
                    return False
                elif journal.type != journal.analytic_journal_id.type or journal.instance_id != journal.analytic_journal_id.instance_id:
                    return False
        return True

    def _check_hq_correction(self, cr, uid, ids, context=None):
        """
        Check that the prop. instance of the "Correction HQ" journal is a coordo
        """
        if context is None:
            context = {}
        for journal in self.browse(cr, uid, ids, fields_to_fetch=['type', 'instance_id'], context=context):
            if journal.type == 'correction_hq' and (not journal.instance_id or journal.instance_id.level != 'coordo'):
                return False
        return True

    _constraints = [
        (_check_correction_type, 'A journal with this type already exists for this instance.', ['type', 'instance_id']),
        (_check_correction_analytic_journal, 'The analytic journal selected must have the same type and prop. instance as this journal.',
                                             ['type', 'analytic_journal_id', 'instance_id']),
        (_check_hq_correction, 'The prop. instance of the "Correction HQ" journal must be a coordination.', ['type', 'instance_id']),
    ]

    def get_current_period(self, cr, uid, context=None):
        periods = self.pool.get('account.period').find(cr, uid, datetime.date.today())
        if periods:
            return periods[0]
        return False

    def name_get(self, cr, uid, ids, context=None):
        """
        Get code for journals
        """
        result = self.read(cr, uid, ids, ['code', 'instance_id'])
        res = []
        is_manual_view = context.get('from_manual_entry', False)
        for rs in result:
            txt = rs.get('code', '')
            if is_manual_view:
                if rs.get('instance_id', False):
                    instance = self.pool.get('msf.instance').read(cr, uid, [rs.get('instance_id')[0]], ['code'])
                    if instance and instance[0] and instance[0].get('code', False):
                        instance_code = instance[0].get('code')
                        txt += ' - ' + str(instance_code)
            res += [(rs.get('id'), txt)]
        return res

    def onchange_type(self, cr, uid, ids, type, currency, context=None):
        analytic_journal_obj = self.pool.get('account.analytic.journal')
        company = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id
#        value = super(account_journal, self).onchange_type(cr, uid, ids, type, currency, context)
        default_dom = [('type','<>','view'),('type','<>','consolidation')]
        value =  {'value': {}, 'domain': {}}
        value['domain']['default_debit_account_id'] = default_dom
        value['domain']['default_credit_account_id'] = default_dom
        # Analytic journal associated
        if type == 'cash':
            analytic_cash_journal = analytic_journal_obj.search(cr, uid, [('code', '=', 'CAS'),
                                                                          ('is_current_instance', '=', True)], context=context)[0]
            value['value']['analytic_journal_id'] = analytic_cash_journal
            value['domain']['default_debit_account_id'] = ACCOUNT_RESTRICTED_AREA['journals']
            value['domain']['default_credit_account_id'] = ACCOUNT_RESTRICTED_AREA['journals']
            if company.cash_debit_account_id:
                value['value']['default_debit_account_id'] = company.cash_debit_account_id.id
            if company.cash_credit_account_id:
                value['value']['default_credit_account_id'] = company.cash_credit_account_id.id
        elif type == 'bank':
            analytic_bank_journal = analytic_journal_obj.search(cr, uid, [('code', '=', 'BNK'),
                                                                          ('is_current_instance', '=', True)], context=context)[0]
            value['value']['analytic_journal_id'] = analytic_bank_journal
            value['domain']['default_debit_account_id'] = ACCOUNT_RESTRICTED_AREA['journals']
            value['domain']['default_credit_account_id'] = ACCOUNT_RESTRICTED_AREA['journals']
            if company.bank_debit_account_id:
                value['value']['default_debit_account_id'] = company.bank_debit_account_id.id
            if company.bank_credit_account_id:
                value['value']['default_credit_account_id'] = company.bank_credit_account_id.id
        elif type == 'cheque':
            analytic_cheque_journal = analytic_journal_obj.search(cr, uid, [('code', '=', 'CHK'),
                                                                            ('is_current_instance', '=', True)], context=context)[0]
            value['value']['analytic_journal_id'] = analytic_cheque_journal
            value['domain']['default_debit_account_id'] = ACCOUNT_RESTRICTED_AREA['journals']
            value['domain']['default_credit_account_id'] = ACCOUNT_RESTRICTED_AREA['journals']
            if company.cheque_debit_account_id:
                value['value']['default_debit_account_id'] = company.cheque_debit_account_id.id
            if company.cheque_credit_account_id:
                value['value']['default_credit_account_id'] = company.cheque_credit_account_id.id
        elif type == 'cur_adj':
            debit_default_dom = [('type','<>','view'),('type','<>','consolidation')]
            credit_default_dom = [('type','<>','view'),('type','<>','consolidation')]
            try:
                xml_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'account_type_expense')
                debit_default_dom += [('user_type', '=', xml_id[1])]
            except KeyError:
                pass
            try:
                xml_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'account_type_income')
                credit_default_dom += [('user_type', '=', xml_id[1])]
            except KeyError:
                pass
            value['domain']['default_debit_account_id'] = debit_default_dom
            value['domain']['default_credit_account_id'] = credit_default_dom
        return value

    def create_fiscalyear_sequence(self, cr, uid, fiscalyear, name, code, date, main_sequence=False, context=None):
        """
        Create a fiscalyear sequence between journal and fiscalyear.
        """
        # Some checks
        if context is None:
            context = {}
        if not fiscalyear:
            raise osv.except_osv(_('Error'), _('Fiscalyear is missing'))
        if not name:
            raise osv.except_osv(_('Error'), _('Name is missing!'))
        if not code:
            raise osv.except_osv(_('Error'), _('Code is missing!'))
        if not date:
            raise osv.except_osv(_('Error'), _('Date is missing!'))
        # create a new sequence
        seq = {
            'name': name,
            'code': code,
            'active': True,
            'prefix': "%s" % str(date)[2:4], # take last 2 number of year
            'padding': 4,
            'number_increment': 1
        }
        # check if code exists
        if not self.pool.get('ir.sequence.type').search(cr, uid, [('code', '=' , code)], limit=1, context=context):
            self.pool.get('ir.sequence.type').create(cr, uid, {'name': code, 'code': code}, context=context)
        sequence_id = self.pool.get('ir.sequence').create(cr, uid, seq)
        if not main_sequence:
            main_sequence = sequence_id
        self.pool.get('account.sequence.fiscalyear').create(cr, uid, {'sequence_id': sequence_id, 'fiscalyear_id': fiscalyear, 'sequence_main_id': main_sequence,})
        return True

    def _create_linked_register(self, cr, uid, journal_id, vals, context):
        """
        If the journal is a liquidity journal creates the register linked to it if it doesn't exist yet
        """
        reg_obj = self.pool.get('account.bank.statement')
        # UTP-182: the register isn't created if the journal comes from another instance via the synchronization
        if 'type' in vals and vals['type'] in ('cash', 'bank', 'cheque') \
                and not context.get('sync_update_execution', False) and \
                not reg_obj.search_exist(cr, uid, [('journal_id', '=', journal_id)], context=context):

            if _get_instance_level(self, cr, uid) == 'project' and self.search_exist(cr, uid, [('id', '=', journal_id), ('is_current_instance', '=', False)], context=context):
                # no way: you are on P1 and you're trying to create a P2 register !
                return False

            # 'from_journal_creation' in context permits to pass register creation that have a
            #  'prev_reg_id' mandatory field. This is because this register is the first register from this journal.
            context.update({'from_journal_creation': True})

            #BKLG-53 get the next draft period from today
            current_date = datetime.date.today().strftime('%Y-%m-%d')
            periods = self.pool.get('account.period').search(cr, uid, [
                ('date_stop', '>=',current_date),
                ('state', '=', 'draft'),
                ('special', '=', False),
            ], context=context, limit=1, order='date_stop')
            if not periods:
                raise osv.except_osv(_('Warning'), _('Sorry, No open period for creating the register!'))
            reg_obj.create(cr, uid, {'journal_id': journal_id,
                                     'name': vals['name'],
                                     'period_id': periods[0],
                                     'currency': vals.get('currency')}, context=context)

    def create(self, cr, uid, vals, context=None):
        """
        Create the journal with its sequence, a sequence linked to the fiscalyear and some register if this journal type is bank, cash or cheque.
        """
        # Checks
        if context is None:
            context = {}

        if not context.get('sync_update_execution', False) and \
            not context.get('allow_journal_system_create', False) and \
                vals.get('type', '') == 'system':
                    # user not allowed to create 'system' journal
            raise osv.except_osv(_('Warning'),
                                 _('You can not create a System journal'))

        # Prepare some values
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')
        name = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.name
        code = vals['code'].lower()
        fy_ids = self.pool.get('account.fiscalyear').search(cr, uid, [('state', '=', 'draft')])
        types = {
            'name': name,
            'code': code
        }
        # Create main sequence
        seq_typ_pool.create(cr, uid, types)
        main_seq = {
            'name': name,
            'code': code,
            'active': True,
            # UF-433: sequence is now only the number, no more prefix
            'prefix': "",
            'padding': 4,
            'number_increment': 1
        }
        vals['sequence_id'] = seq_pool.create(cr, uid, main_seq)
        if fy_ids:
            for fy in self.pool.get('account.fiscalyear').browse(cr, uid, fy_ids, context=context):
                # Create associated sequence FY/JOURNAL
                self.create_fiscalyear_sequence(cr, uid, fy.id, name, code, fy.date_start, main_sequence=vals['sequence_id'], context=context)
        # View is set by default, since every journal will display the same thing
        obj_data = self.pool.get('ir.model.data')
        data_id = obj_data.search(cr, uid, [('model','=','account.journal.view'), ('name','=','account_journal_view')])
        data = obj_data.browse(cr, uid, data_id[0], context=context)
        vals['view_id'] = data.res_id

        # Create journal
        journal_id = super(account_journal, self).create(cr, uid, vals, context)

        # Some verification for cash, bank, cheque and cur_adj type
        if vals['type'] in ['cash', 'bank', 'cheque', 'cur_adj']:
            if not vals.get('default_debit_account_id'):
                raise osv.except_osv(_('Warning'), _('Default Debit Account is missing.'))
        # if it is a liquidity journal create the linked register
        self._create_linked_register(cr, uid, journal_id, vals, context)

        # Prevent user that default account for cur_adj type should be an expense account
        if vals['type'] in ['cur_adj']:
            account_id = vals['default_debit_account_id']
            user_type_code = self.pool.get('account.account').read(cr, uid, account_id, ['user_type_code']).get('user_type_code', False)
            if user_type_code != 'expense':
                raise osv.except_osv(_('Warning'), _('Default Debit Account should be an expense account for Adjustment Journals!'))
        return journal_id

    def write(self, cr, uid, ids, vals, context=None):
        """
        Verify default debit account for adjustement journals
        """
        if not ids:
            return True
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}

        if not context.get('sync_update_execution', False):
            if vals.get('type', '') == 'system':
                # not from sync, user not allowed to update 'system' journal
                # (note: noteditable not usable on journal form)
                raise osv.except_osv(_('Warning'),
                                     _('System journal not updatable'))

        res = super(account_journal, self).write(cr, uid, ids, vals, context=context)
        for j in self.browse(cr, uid, ids):
            if j.type == 'cur_adj' and j.default_debit_account_id.user_type_code != 'expense':
                raise osv.except_osv(_('Warning'), _('Default Debit Account should be an expense account for Adjustment Journals!'))
            self._create_linked_register(cr, uid, j.id, vals, context)
            # US-265: Check account bank statements if name change
            if not context.get('sync_update_execution'):
                if vals.get('name', False):
                    if hasattr(uid, 'realUid'):
                        fake_uid = uid
                    else:
                        fake_uid = fakeUid(1, uid)
                    abs_obj = self.pool.get('account.bank.statement')
                    s_ids = abs_obj.search(cr, fake_uid, [('journal_id', '=', j.id), ('name', '!=', vals['name'])], context=context)
                    if s_ids:
                        abs_obj.write(cr, fake_uid, s_ids, {'name': vals['name']}, context=context)
        return res

    def unlink(self, cr, uid, ids, context=None):
        if not ids:
            return False
        if isinstance(ids, int):
            ids = [ids]

        is_system = [ rec.type == 'system' \
                      for rec in self.browse(cr, uid, ids, context=context) ]
        if any(is_system):
            raise osv.except_osv(_('Warning'),
                                 _('System journal not deletable'))

        if any([j['is_default'] for j in self.read(cr, uid, ids, ['is_default'], context=context)]):
            raise osv.except_osv(_('Warning'),
                                 _("The journals imported by default at instance creation can't be deleted."))

        return super(account_journal, self).unlink(cr, uid, ids,
                                                   context=context)

    def button_delete_journal(self, cr, uid, ids, context=None):
        """
        Delete all linked register and this journal except:
        - if another register is linked to one of attached register
        - if one of register's balance is not null
        - if one of register is not draft
        """
        if not context:
            context = {}
        for id in ids:
            all_register_ids = self.pool.get('account.bank.statement').search(cr, uid, [('journal_id', '=', id)])
            criteria_register_ids = self.pool.get('account.bank.statement').search(cr, uid, [('journal_id', '=', id), ('state', '=', 'draft'), ('balance_end', '=', 0)])
            if not all_register_ids:
                raise osv.except_osv(_('Error'), _('No register found. You can manually delete this journal.'))
            if all_register_ids != criteria_register_ids:
                raise osv.except_osv(_('Warning'), _('Deletion is not possible. All registers are not in draft state!'))
            # Delete all registers
            context.update({'from': 'journal_deletion'})
            self.pool.get('account.bank.statement').unlink(cr, uid, all_register_ids, context) # Needs context to permit register deletion
            # Delete this journal
            self.unlink(cr, uid, id)
        # Return to the journal view list
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'view_account_journal_tree')
        view_id = view_id and view_id[1] or False
        search_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'view_account_journal_search')
        search_view_id = search_view_id and search_view_id[1] or False
        return {
            'name': _('Journal list'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.journal',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': [view_id],
            'search_view_id': search_view_id,
            'target': 'crush',
        }

    def get_correction_journal(self, cr, uid, corr_type=False, context=None):
        """
        Returns the correction journal of the current instance (or False if not found):
        - by default => standard Correction journal
        - corr_type 'hq' => Correction HQ journal
        - corr_type 'extra' => OD-Extra Accounting journal
        - corr_type 'manual' => Correction Manual journal
        """
        if context is None:
            context = {}
        if corr_type == 'hq':
            journal_type = 'correction_hq'
        elif corr_type == 'extra':
            journal_type = 'extra'
        elif corr_type == 'manual':
            journal_type = 'correction_manual'
        else:
            journal_type = 'correction'
        journal_ids = self.search(cr, uid, [('type', '=', journal_type), ('is_current_instance', '=', True), ('is_active', '=', True)],
                                  order='id', limit=1, context=context)
        return journal_ids and journal_ids[0] or False


account_journal()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
