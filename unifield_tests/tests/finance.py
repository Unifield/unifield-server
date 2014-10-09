#!/usr/bin/env python
# -*- coding: utf8 -*-
from __future__ import print_function
from unifield_test import UnifieldTest
from time import strftime
from random import randint
from oerplib import error

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
