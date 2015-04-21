#!/usr/bin/env python
# -*- coding: utf8 -*-
from __future__ import print_function
from unifield_test import UnifieldTestException
from unifield_test import UnifieldTest
from time import strftime
from random import randint
from oerplib import error

class FinanceTestException(UnifieldTestException):
    pass

class FinanceTest(UnifieldTest):

    def __init__(self, *args, **kwargs):
        '''
        Include some finance data in the databases (except sync one).
        Include/create them only if they have not been already created.
        To know this, we use the key: "finance_test_class"
        '''
        super(FinanceTest, self).__init__(*args, **kwargs)

    def _hook_db_process(self, name, database):
        '''
        Check that finance data are loaded into the given database
        '''
        keyword = 'finance_test_class'
        colors = self.colors
        # If no one, do some changes on DBs
        if not self.is_keyword_present(database, keyword):
            # 00 Open periods from january to today's one
            month = strftime('%m')
            today = strftime('%Y-%m-%d')
            fy_obj = database.get('account.fiscalyear')
            period_obj = database.get('account.period')
            # Fiscal years
            fy_ids = fy_obj.search([('date_start', '<=', today), ('date_stop', '>=', today)])
            if not fy_ids:
                raise Exception('error', 'No fiscalyear found!')
            # Sort periods by number
            periods = period_obj.search([('fiscalyear_id', 'in', fy_ids), ('number', '<=', month), ('state', '=', 'created')], 0, 16, 'number')
            for period in periods:
                try:
                    period_obj.action_set_state(period, context={'state': 'draft'})
                except error.RPCError as e:
                    print(e.oerp_traceback)
                    print(e.message)
                except Exception, e:
                    raise Exception('error', str(e))
            # Write the fact that data have been loaded
            database.get(self.test_module_obj_name).create({'name': keyword, 'active': True})
            print (database.colored_name + ' [' + colors.BGreen + 'OK'.center(4) + colors.Color_Off + '] %s: Data loaded' % (keyword))
        else:
            print (database.colored_name + ' [' + colors.BYellow + 'WARN'.center(4) + colors.Color_Off + '] %s: Data already exists' % (keyword))
        return super(FinanceTest, self)._hook_db_process(name, database)
        
    def create_journal(self, db, name, code, journal_type,
        analytic_journal_id=False, account_code=False, currency_name=False,
        bank_journal_id=False):
        """
        create journal
        if of type bank/cash/cheque: account_code and currency_name needed.

        :type db: oerplib object
        :param name: journal name
        :param code: journal code
        :param journal_type: journal type. available types::
         * accrual
         * bank
         * cash
         * cheque
         * correction
         * cur_adj
         * depreciation
         * general
         * hq
         * hr
         * inkind
         * intermission
         * migration
         * extra
         * situation
         * purchase
         * purchase_refund
         * revaluation
         * sale
         * sale_refund
         * stock
        :param analytic_journal_id: (optional) linked analytic journal id
            default attempt to search an analytic journal that have the same
            journal_type
        :param account_code: (mandatory for bank/cash/cheque) account
            code that will be used in debit/credit for the journal
        :param currency_name: (mandatory for bank/cash/cheque) journal
            currency name
        :param bank_journal_id: (mandatory for cheque) linked bank journal
        :return: journal id
        :rtype: int
        """
        # checks
        if not name:
            raise FinanceTestException("name missing")
        if not code:
            raise FinanceTestException("code missing")
        if not journal_type:
            raise FinanceTestException("journal type missing")
        # bank/cash/cheque
        if journal_type in ('bank', 'cheque', 'cash', ):
            if not account_code or not currency_name:
                tpl = "bank/cash/cheque: account code and a currency" \
                      " required. account: '%s', currency: '%s'"
                raise FinanceTestException(tpl % (account_code or '',
                    currency_name or '', ))
        # cheque journal
        if journal_type == 'cheque' and not bank_journal_id:
            tpl = "bank journal mandatory for cheque journal"
            raise FinanceTestException(tpl)
            
        aaj_obj = db.get('account.analytic.journal')
        aa_obj = db.get('account.account')
        ccy_obj =  db.get('res.currency')
        aj_obj = db.get('account.journal')

        # analytic journal
        if not analytic_journal_id:
            analytic_journal_type = journal_type
            if journal_type in ('bank', 'cheque', ):
                analytic_journal_type = 'cash'
            aaj_ids = aaj_obj.search([('type', '=', analytic_journal_type)])
            if not aaj_ids:
                tpl = "no analytic journal found with this type: %s"
                raise FinanceTestException(tpl % (journal_type, ))
            analytic_journal_id = aaj_ids[0]

        # prepare values
        vals = {
            'name': name,
            'code': code,
            'type': journal_type,
            'analytic_journal_id': analytic_journal_id,
        }
        if account_code:
            a_ids = aa_obj.search([('code', '=', account_code)])
            if not a_ids:
                tpl = "no account found for the given code: %s"
                raise FinanceTestException(tpl % (account_code, ))
            account_id = a_ids[0]
            vals.update({
                'default_debit_account_id': account_id,
                'default_credit_account_id': account_id,
            })
        if currency_name:
            c_ids = ccy_obj.search([('name', '=', currency_name)])
            if not c_ids:
                tpl = "currency not found: %s"
                raise FinanceTestException(tpl % (currency_name, ))
            vals.update({'currency': c_ids[0]})
        if bank_journal_id:
            vals['bank_journal_id'] = bank_journal_id
        # create the journal
        return aj_obj.create(vals)
        
    def create_register(self, db, name, code, register_type, account_code,
        currency_name, bank_journal_id=False):
        """
        create a register in the current period.
        (use create_journal)
        
        :type db: oerplib object
        :param name: register name (used as journal's name)
        :param code: register's code (used as journal's code)
        :param register_type: register available types::
         * bank
         * cash
         * cheque
        :param account_code: account code used for debit/credit account
            at journal creation. (so used by the register)
        :param currency_name: name of currency to use(must exists)
        :param bank_journal_id: (mandatory for cheque) linked bank journal
        :return: register_id and journal_id
        :rtype: tuple (registed id, journal id)
        """
        aaj_obj = db.get('account.analytic.journal')
        abs_obj = db.get('account.bank.statement')
        
        analytic_journal_code_map = {
            'cash': 'CAS',
            'bank': 'BNK',
            'cheque': 'CHK',
        }
        aaj_code = analytic_journal_code_map[register_type]
        aaj_ids = aaj_obj.search([('code', '=', aaj_code)])
        if not aaj_ids:
            tpl = "analytic journal code %s not found"
            raise FinanceTestException(tpl % (aaj_code, ))

        j_id = self.create_journal(db, name, code, register_type,
            account_code=account_code, currency_name=currency_name,
            bank_journal_id=bank_journal_id,
            analytic_journal_id=aaj_ids[0])
        # search the register (should be created by journal creation)
        reg_ids = abs_obj.search([('journal_id', '=', j_id)])
        return reg_ids and reg_ids[0] or False, j_id

    def create_journal_entry(self, database):
        '''
        Create a journal entry (account.move) with 2 lines: 
          - an expense one (with an analytic distribution)
          - a counterpart one
        Return the move ID, expense line ID, then counterpart ID
        '''
        # Prepare some values
        move_obj = database.get('account.move')
        aml_obj = database.get('account.move.line')
        period_obj = database.get('account.period')
        journal_obj = database.get('account.journal')
        partner_obj = database.get('res.partner')
        account_obj = database.get('account.account')
        distrib_obj = database.get('analytic.distribution')
        curr_date = strftime('%Y-%m-%d')
        # Search journal
        journal_ids = journal_obj.search([('type', '=', 'purchase')])
        self.assert_(journal_ids != [], "No purchase journal found!")
        # Search period
        period_ids = period_obj.get_period_from_date(curr_date)
        # Search partner
        partner_ids = partner_obj.search([('partner_type', '=', 'external')])
        # Create a random amount
        random_amount = randint(100, 10000)
        # Create a move
        move_vals = {
            'journal_id': journal_ids[0],
            'period_id': period_ids[0],
            'date': curr_date,
            'document_date': curr_date,
            'partner_id': partner_ids[0],
            'status': 'manu',
        }
        move_id = move_obj.create(move_vals)
        self.assert_(move_id != False, "Move creation failed with these values: %s" % move_vals)
        # Create some move lines
        account_ids = account_obj.search([('is_analytic_addicted', '=', True), ('code', '=', '6101-expense-test')])
        random_account = randint(0, len(account_ids) - 1)
        vals = {
            'move_id': move_id,
            'account_id': account_ids[random_account],
            'name': 'fp_changes expense',
            'amount_currency': random_amount,
        }
        # Search analytic distribution
        distribution_ids = distrib_obj.search([('name', '=', 'DISTRIB 1')])
        distribution_id = distrib_obj.copy(distribution_ids[0], {'name': 'distribution-test'})
        vals.update({'analytic_distribution_id': distribution_id})
        aml_expense_id = aml_obj.create(vals)
        counterpart_ids = account_obj.search([('is_analytic_addicted', '=', False), ('code', '=', '401-supplier-test'), ('type', '!=', 'view')])
        random_counterpart = randint(0, len(counterpart_ids) - 1)
        vals.update({
            'account_id': counterpart_ids[random_counterpart],
            'amount_currency': -1 * random_amount,
            'name': 'fp_changes counterpart',
            'analytic_distribution_id': False,
        })
        aml_counterpart_id = aml_obj.create(vals)
        # Validate the journal entry
        move_obj.button_validate([move_id]) # WARNING: we use button_validate so that it check the analytic distribution validity/presence
        return move_id, aml_expense_id, aml_counterpart_id

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
