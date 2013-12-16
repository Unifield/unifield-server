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
import logging
from os import path
import tools

from tools.translate import _

class account_journal(osv.osv):
    _inherit = "account.journal"

    def init(self, cr):
        """
        Load demo.xml before addons
        """
        if hasattr(super(account_journal, self), 'init'):
            super(account_journal, self).init(cr)

        mod_obj = self.pool.get('ir.module.module')
        demo = False
        mod_id = mod_obj.search(cr, 1, [('name', '=', 'account_journal')])
        if mod_id:
            demo = mod_obj.read(cr, 1, mod_id, ['demo'])[0]['demo']

        if demo:
            # Search if an engagement journal exists
            eng_ids = self.pool.get('account.analytic.journal').search(cr, 1, [('type', '=', 'engagement')])
            if not len(eng_ids):
                logging.getLogger('init').info('HOOK: module account_journal: loading account_journal_demo.xml')
                pathname = path.join('account_journal', 'account_journal_demo.xml')
                file = tools.file_open(pathname)
                tools.convert_xml_import(cr, 'account_journal', file, {}, mode='init', noupdate=False)


    def get_journal_type(self, cursor, user_id, context=None):
        return [('accrual', 'Accrual'),
                ('bank', 'Bank'),
                ('cash','Cash'),
                ('cheque', 'Cheque'),
                ('correction','Correction'),
                ('cur_adj', 'Currency Adjustement'),
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
        ]
    
    _columns = {
        'type': fields.selection(get_journal_type, 'Type', size=32, required=True),
        'code': fields.char('Code', size=10, required=True, help="The code will be used to generate the numbers of the journal entries of this journal."),
    }

    _defaults = {
        'allow_date': False,
        'centralisation': False,
        'entry_posted': False,
        'update_posted': True,
        'group_invoice_lines': False,
    }
    
    def get_current_period(self, cr, uid, context=None):
        periods = self.pool.get('account.period').find(cr, uid, datetime.date.today())
        if periods:
            return periods[0]
        return False
    
    def name_get(self, cr, user, ids, context=None):
        """
        Get code for journals
        """
        result = self.read(cr, user, ids, ['code'])
        res = []
        for rs in result:
            txt = rs.get('code', '')
            res += [(rs.get('id'), txt)]
        return res
    
    def onchange_type(self, cr, uid, ids, type, currency, context=None):
        analytic_journal_obj = self.pool.get('account.analytic.journal')
#        value = super(account_journal, self).onchange_type(cr, uid, ids, type, currency, context)
        default_dom = [('type','<>','view'),('type','<>','consolidation')]
        value =  {'value': {}, 'domain': {}}
        if type in ('cash', 'bank', 'cheque'):
            try:
                xml_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'account_type_cash_moves')
                default_dom += [('user_type', '=', xml_id[1])]
            except KeyError:
                pass
        value['domain']['default_debit_account_id'] = default_dom
        value['domain']['default_credit_account_id'] = default_dom
        # Analytic journal associated
        if type == 'cash':
            analytic_cash_journal = analytic_journal_obj.search(cr, uid, [('code', '=', 'CAS'),
                                                                          ('is_current_instance', '=', True)], context=context)[0]
            value['value']['analytic_journal_id'] = analytic_cash_journal
        elif type == 'bank': 
            analytic_bank_journal = analytic_journal_obj.search(cr, uid, [('code', '=', 'BNK'),
                                                                          ('is_current_instance', '=', True)], context=context)[0]
            value['value']['analytic_journal_id'] = analytic_bank_journal
        elif type == 'cheque': 
            analytic_cheque_journal = analytic_journal_obj.search(cr, uid, [('code', '=', 'CHK'),
                                                                            ('is_current_instance', '=', True)], context=context)[0]
            value['value']['analytic_journal_id'] = analytic_cheque_journal
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
        sequence_id = self.pool.get('ir.sequence').create(cr, uid, seq)
        if not main_sequence:
            main_sequence = sequence_id
        self.pool.get('account.sequence.fiscalyear').create(cr, uid, {'sequence_id': sequence_id, 'fiscalyear_id': fiscalyear, 'sequence_main_id': main_sequence,})
        return True

    def create(self, cr, uid, vals, context=None):
        """
        Create the journal with its sequence, a sequence linked to the fiscalyear and some register if this journal type is bank, cash or cheque.
        """
        # Checks
        if context is None:
            context = {}
        # Prepare some values
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')
        seq_fiscal_pool = self.pool.get('account.sequence.fiscalyear')
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
        
        # if the journal can be linked to a register, the register is also created
        # UTP-182: but not create if the journal came from another instance via the synchronization 
        if vals['type'] in ('cash','bank','cheque') and not context.get('sync_update_execution', False):
            # 'from_journal_creation' in context permits to pass register creation that have a
            #  'prev_reg_id' mandatory field. This is because this register is the first register from this journal.
            context.update({'from_journal_creation': True})
            self.pool.get('account.bank.statement') \
                .create(cr, uid, {'journal_id': journal_id,
                                  'name': vals['name'],
                                  'period_id': self.get_current_period(cr, uid, context),
                                  'currency': vals.get('currency')}, \
                                  context=context)
        
        # Prevent user that default account for cur_adj type should be an expense account
        if vals['type'] in ['cur_adj']:
            account_id = vals['default_debit_account_id']
            user_type_code = self.pool.get('account.account').read(cr, uid, account_id, ['user_type_code']).get('user_type_code', False)
            if user_type_code != 'expense':
                raise osv.except_osv(_('Warning'), _('Default Debit Account should be an expense account for Adjustement Journals!'))
        return journal_id

    def write(self, cr, uid, ids, vals, context=None):
        """
        Verify default debit account for adjustement journals
        """
        res = super(account_journal, self).write(cr, uid, ids, vals, context=context)
        for j in self.browse(cr, uid, ids):
            if j.type == 'cur_adj' and j.default_debit_account_id.user_type_code != 'expense':
                raise osv.except_osv(_('Warning'), _('Default Debit Account should be an expense account for Adjustement Journals!'))
        return res

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

account_journal()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
