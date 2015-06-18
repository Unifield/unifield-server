#!/usr/bin/env python
# -*- coding: utf8 -*-
from __future__ import print_function
from unifield_test import UnifieldTestException
from unifield_test import UnifieldTest
from datetime import datetime
from time import strftime
from random import randint
from random import randrange
from oerplib import error

FINANCE_TEST_MASK = {
    'register': "%s %s",
    'register_line': "%d/%s %s",  # "(register_id)/(date) uuid"
    'je': "JE %s",
    'ji': "JI %s",
    'ad': "AD %s",
    'cheque_number': "cheque %s",
    'invoice_line': "%d/L%03d %s",  # "(invoice id)/L(line number) (account)"
}

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
            self.assert_(fy_ids != False, 'No fiscalyear found!')

            # Sort periods by number
            periods = period_obj.search([
                ('fiscalyear_id', 'in', fy_ids),
                ('number', '<=', month),
                ('state', '=', 'created')
            ], 0, 16, 'number')
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
        
    def get_journal_ids(self, db, journal_type, is_of_instance=False,
        is_analytic=False):
        model = 'account.analytic.journal' if is_analytic \
            else 'account.journal'
        domain = [('type', '=', journal_type)]
        if is_of_instance:
            domain.append(('is_current_instance', '=', True))
    
        ids = db.get(model).search(domain)
        self.assert_(
            ids != False,
            "no %s journal(s) found" % (journal_type, )
        )
        return ids
        
    def get_account_from_code(self, db, code, is_analytic=False):
        model = 'account.analytic.account' if is_analytic \
            else 'account.account'
        ids = db.get(model).search([('code', '=', code)])
        return ids and ids[0] or False
        
    def get_account_code(self, db, id, is_analytic=False):
        model = 'account.analytic.account' if is_analytic \
            else 'account.account'
        return db.get(model).browse(id).code
        
    def get_random_amount(self, is_expense=False):
        amount = float(randrange(100, 10000))
        if is_expense:
            amount *= -1.
        return amount
        
    def journal_create(self, db, name, code, journal_type,
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
        self.assert_(
            name and code and journal_type,
            "name or/and code or/and journal type missing"
        )
        # bank/cash/cheque
        if journal_type in ('bank', 'cheque', 'cash', ):
            self.assert_(
                account_code and currency_name,
                "bank/cash/cheque: account code and currency required." \
                    " account: '%s', currency: '%s'" % (
                        account_code or '', currency_name or '', )
            )
        # cheque journal
        if journal_type == 'cheque':
            self.assert_(
                bank_journal_id != False,
                "bank journal mandatory for cheque journal"
            )
            
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
            self.assert_(
                aaj_ids != False,
                "no analytic journal found with this type: %s" % (
                    journal_type, )
            )
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
            self.assert_(
                a_ids != False,
                "no account found for the given code: %s" % (account_code, )
            )
            account_id = a_ids[0]
            vals.update({
                'default_debit_account_id': account_id,
                'default_credit_account_id': account_id,
            })
        if currency_name:
            c_ids = ccy_obj.search([('name', '=', currency_name)])
            self.assert_(
                c_ids != False,
                "currency not found: %s" % (currency_name, )
            )
            vals.update({'currency': c_ids[0]})
        if bank_journal_id:
            vals['bank_journal_id'] = bank_journal_id
        # create the journal
        return aj_obj.create(vals)
        
    def register_create(self, db, name, code, register_type, account_code,
        currency_name, bank_journal_id=False):
        """
        create a register in the current period.
        (use journal_create)
        
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
        self.assert_(
            aaj_ids != False,
            "analytic journal code %s not found" % (aaj_code, )
        )

        j_id = self.journal_create(db, name, code, register_type,
            account_code=account_code, currency_name=currency_name,
            bank_journal_id=bank_journal_id,
            analytic_journal_id=aaj_ids[0])
        # search the register (should be created by journal creation)
        reg_ids = abs_obj.search([('journal_id', '=', j_id)])
        return reg_ids and reg_ids[0] or False, j_id
        
    def register_create_line(self, db, regbr_or_id, account_code_or_id, amount,
            ad_breakdown_data=False,
            date=False, document_date=False,
            third_partner_id=False, third_employee_id=False,
            third_journal_id=False,
            do_temp_post=False, do_hard_post=False):
        """
        create a register line in the given register
        
        :type db: oerplib object
        :param regbr_or_id: parent register browsed object or id
        :type regbr_or_id: object/int/long
        :param account_code_or_id: account code to search or account_id
        :type code_or_id: str/int/long
        :param amount: > 0 amount IN, < 0 amount OUT
        :param ad_breakdown_data: (optional) see analytic_distribution_create 
            breakdown_data param help
        :param datetime date: posting date
        :param datetime document_date: document date
        :param third_partner_id: partner id
        :param third_employee_id: emp id (operational advance)
        :param third_journal_id: journal id (internal transfer)
        :return: register line id and AD id and first expense ji 
            (expense ji given if hard host or temp post)
        :rtype: tuple (register_line_id, ad_id/False, ji_id)
        """
        # register
        self.assert_(regbr_or_id != False, "register missing")
        self.assert_(
            not (do_hard_post and do_temp_post) ,
            "you can not temp post and hard post at the same time"
        )
            
        abs_obj = db.get('account.bank.statement')
        absl_obj = db.get('account.bank.statement.line')
        aa_obj = db.get('account.account')
            
        if isinstance(regbr_or_id, (int, long)):
            register_br = abs_obj.browse(regbr_or_id)
        else:
            register_br = regbr_or_id

        # general account
        if isinstance(account_code_or_id, (str, unicode)):
            # check account code
            code_ids = aa_obj.search([
                '|',
                ('name', 'ilike', account_code_or_id),
                ('code', 'ilike', account_code_or_id)]
            )
            self.assert_(
                code_ids != False,
                "error searching for this account code: %s" % (
                    account_code_or_id, )
            )
            self.assert_(
                len(code_ids) == 1,
                "error more than 1 account with code: %s" % (
                    account_code_or_id, )
            )
            account_id = code_ids[0]
        else:
            account_id = account_code_or_id
        account_br = aa_obj.browse(account_id)

        # check dates
        if not date:
            date_start = register_br.period_id.date_start or False
            date_stop = register_br.period_id.date_stop or False
            self.assert_(
                date_start and date_stop,
                "no date found for the period %s" % (
                    register_br.period_id.name, )
            )
            random_date = self.random_date(
                datetime.strptime(str(date_start), '%Y-%m-%d'),
                datetime.strptime(str(date_stop), '%Y-%m-%d')
            )
            date = datetime.strftime(random_date, '%Y-%m-%d')
        if not document_date:
            document_date = date

        # vals
        name = FINANCE_TEST_MASK['register_line'] % (register_br.id, date,
            self.get_uuid(), )
        vals = {
            'statement_id': register_br.id,
            'account_id': account_id,
            'document_date': document_date,
            'date': date,
            'amount': amount,
            'name': name,
        }
        if third_partner_id:
            vals['partner_id'] = third_partner_id
        if third_employee_id:
            vals['employee_id'] = third_employee_id
        if third_journal_id:
            vals['transfer_journal_id'] = third_journal_id
        if register_br.journal_id.type == 'cheque':
            vals['cheque_number'] = FINANCE_TEST_MASK['cheque_number'] % (
                self.proxy.get_uuid(), )

        # create
        regl_id = absl_obj.create(vals)
        
        # optional AD
        if ad_breakdown_data and account_br.is_analytic_addicted:
            distrib_id = self.analytic_distribution_create(db,
                breakdown_data=ad_breakdown_data)
            absl_obj.write([regl_id],
                {'analytic_distribution_id': distrib_id}, {})
        else:
            distrib_id = False
        
        expense_ji_id = False
        if do_temp_post:
            self.register_line_temp_post(db, regl_id)
        if do_hard_post:
            self.register_line_hard_post(db, regl_id)
        if do_temp_post or do_hard_post:
            expense_ji_id = self.register_line_get_first_expense_ji(db, regl_id)
 
        return (regl_id, distrib_id, expense_ji_id, )
        
    def register_line_temp_post(self, db, regl_id):
        db.get('account.bank.statement.line').button_temp_posting([regl_id], {})
        
    def register_line_hard_post(self, db, regl_id):
        db.get('account.bank.statement.line').button_hard_posting([regl_id], {})
        
    def register_line_get_first_expense_ji(self, db, regl_id):
        """ the reg line need to be temp or hard posted """
        absl_obj = db.get('account.bank.statement.line')
        aml_obj = db.get('account.move.line')
        
        aml_ids = aml_obj.search([
            ('name', '=', absl_obj.browse(regl_id).name), 
            ('account_id.is_analytic_addicted', '=', 'True')  # expense account
        ])
        return aml_ids and aml_ids[0] or False
        
    def register_close(self, db, ids):
        if isinstance(ids, (int, long, )):
            ids = [ids]
        abs_obj = db.get('account.bank.statement')
        wcb_obj = db.get('wizard.confirm.bank')
        
        for abs_br in abs_obj.browse(ids):
            abs_ids = [abs_br.id]
            # set fake balance amount...
            abs_obj.write(abs_ids, {
                'balance_end_real': abs_br.balance_end,
            })
            abs_obj.button_confirm_closing_bank_balance(abs_ids)
            
            # ...then close
            abs_obj.write(abs_ids, {
                'state': 'confirm',
                'closing_date': self.get_orm_date_now(),
            })
            
    def register_reopen(self, db, ids):
        if isinstance(ids, (int, long, )):
            ids = [ids]
        db.get('account.bank.statement').write(ids, {
                'state': 'open',
                'closing_date': False,
            })
            
    def analytic_distribution_set_fp_account_dest(self, db,
        fp_name, account_code, dest_code):
        """
        add account/dest tuple to FP
        """
        if fp_name and fp_name == 'PF':
            return  # nothing to do
        self.assert_(
            fp_name and account_code and dest_code,
            "you must give fp name and account/dest codes"
        )
                
        fp_id = self.get_account_from_code(db, fp_name, is_analytic=True)
        self.assert_(
            fp_id != False,
            "FP '%s' not found" % (fp_name, )
        )
        account_id = self.get_account_from_code(db, account_code,
            is_analytic=False)
        self.assert_(
            account_id != False,
            "account '%s' not found" % (account_code, )
        )
        dest_id = self.get_account_from_code(db, dest_code, is_analytic=True)
        self.assert_(
            dest_id != False,
            "dest '%s' not found" % (dest_code, )
        )
            
        aaa_obj = db.get('account.analytic.account')
        fp_br = aaa_obj.browse(fp_id)
        
        # search account/dest tuple in FP ?
        for tda in fp_br.tuple_destination_account_ids:
            if tda.account_id.id == account_id and \
                tda.destination_id.id == dest_id:
                    return  # account/dest tuple already in FP
        
        aaa_obj.unit_test_add_account_destination_to_fp(account_id, dest_id,
            fp_id, {'unit_test': 1})
        
    def analytic_distribution_create(self, db,
        breakdown_data=[(100., 'OPS', False, False)]):
        """
        create analytic distribution
        
        :type db: oerplib object
        :param account_id: related account._id (if not set search for a random
            destination)
        :type account_id: int
        :param breakdown_data: [(purcent, dest, cc, fp)]
            - for breakdown of lines list: percent, dest code, cc code, fp code
            - False cc for default company top cost center
            - False FP for PF
        :return: ad id
        """
        comp_obj = db.get('res.company')
        aaa_obj = db.get('account.analytic.account')
        ad_obj = db.get('analytic.distribution')
        
        company = comp_obj.browse(comp_obj.search([])[0])
        funding_pool_pf_id = self.get_record_id_from_xmlid(db,
            'analytic_distribution', 'analytic_account_msf_private_funds', )
        self.assert_(funding_pool_pf_id != False, 'PF funding pool not found')

        # DEST/CC/FP
        if not breakdown_data:
            breakdown_data  = [(100., 'OPS', 'HT101', 'PF', ), ]
             
        # create ad
        name = FINANCE_TEST_MASK['ad'] % (self.get_uuid(), )
        distrib_id = ad_obj.create({'name': name})
        
        for purcent, dest, cc, fp in breakdown_data:
            dest_id = aaa_obj.search([
                ('category', '=', 'DEST'),
                ('type', '=', 'normal'),
                ('code', '=', dest),
            ])
            self.assert_(
                dest_id != False,
                'no destination found %s' % (dest, )
            )
            dest_id = dest_id[0]
            
            if cc:
                cost_center_id = aaa_obj.search([
                    ('category', '=', 'OC'),
                    ('type', '=', 'normal'),
                    ('code', '=', cc),
                ])
                self.assert_(
                    cost_center_id != False,
                    'no cost center found %s' % (cc, )
                )
                cost_center_id = cost_center_id[0]
            else:
                cost_center_id = company.instance_id.top_cost_center_id \
                    and company.instance_id.top_cost_center_id.id or False
                self.assert_(
                    cost_center_id != False,
                    'no top cost center found for instance %s' % (
                        company.name or '', )
                )
            if fp:
                funding_pool_id = aaa_obj.search([
                    ('category', '=', 'FUNDING'),
                    ('type', '=', 'normal'),
                    ('code', '=', fp),
                ])
                self.assert_(
                    funding_pool_id != False,
                    'no funding pool found %s' % (fp, )
                )
                funding_pool_id = funding_pool_id[0]
            else:
                funding_pool_id = funding_pool_pf_id  # default PF
            
            # relating ad line dimension distribution lines (1 cc, 1fp)                
            data = [
                ('cost.center.distribution.line', cost_center_id, False),
                ('funding.pool.distribution.line', funding_pool_id,
                    cost_center_id),
            ]
            for ad_dim_analytic_obj, val, fpdim_cc_id in data:
                vals = {
                    'distribution_id': distrib_id,
                    'name': name,
                    'analytic_id': val,
                    'cost_center_id': fpdim_cc_id,
                    'percentage': purcent,
                    'currency_id': company.currency_id.id,
                    'destination_id': dest_id,
                }
                db.get(ad_dim_analytic_obj).create(vals)
        return distrib_id
        
    def simulation_correction_wizard(self, db, ji_to_correct_id,
        cor_date=False,
        new_account_code=False,
        new_ad_breakdown_data=False, ad_replace_data=False):
        """
        :param new_account_code: new account code for a G/L correction
        :param new_ad_breakdown_data: new ad lines to replace all ones (delete)
        :param ad_replace_data: {'dest/cc/fp/per': [(old, new), ], }
        choose between delete and recreate AD with new_ad_breakdown_data
        or to replace dest/cc/fp/percentage values with ad_replace_data
        """
        if not cor_date:
            cor_date = self.get_orm_date_now()
        
        wizard_cor_obj = db.get('wizard.journal.items.corrections')
        wizard_corl_obj = db.get('wizard.journal.items.corrections.lines')
        wizard_ad_obj = db.get('analytic.distribution.wizard')
        wizard_adl_obj = db.get('analytic.distribution.wizard.lines')
        wizard_adfpl_obj = db.get('analytic.distribution.wizard.fp.lines')
        
        aa_obj = db.get('account.account')
        aml_obj = db.get('account.move.line')
        aaa_obj = db.get('account.analytic.account')
    
        # check valid correction
        self.assert_(
            new_account_code or new_ad_breakdown_data or ad_replace_data,
            'no correction changes: required G/L or AD or both'
        )
        # check valid correction
        self.assert_(
            not (new_ad_breakdown_data and ad_replace_data),
            'you can not both redefine full AD and replace attributes'
        )
                
        # get new account id for a G/L correction
        new_account_id = False
        if new_account_code:
            account_ids = aa_obj.search([('code', '=', new_account_code)])
            self.assert_(
                account_ids != False,
                'account %s for a G/L correction not found' % (
                    new_account_code, )
            )
            new_account_id = account_ids[0]
                
        # get ji and checks
        ji_br = aml_obj.browse(ji_to_correct_id)
        self.assert_(
            ji_br != False,
            'journal item not found'
        )
        if new_account_code:
            self.assert_(
                ji_br.account_id.code != new_account_code,
                'you can not do a G/L correction with same account code'
            )
        old_account_id = ji_br.account_id and ji_br.account_id.id or False
        ji_amount = ji_br.debit_currency and ji_br.debit_currency * -1 or \
            ji_br.credit_currency
        
        # set wizard header (will generate in create the correction lines)
        vals = {
            'date': cor_date,
            'move_line_id': ji_to_correct_id,
            'state': 'draft',
            'from_donation': False,
        }
        wiz_br = wizard_cor_obj.browse(wizard_cor_obj.create(vals))

        # set the generated correction line
        wiz_cor_line = self.get_first(wiz_br.to_be_corrected_ids)
        self.assert_(
            wiz_cor_line != False,
            'error generating a correction line'
        )
            
        vals = {}
        if new_account_id:  # G/L correction
            wizard_corl_obj.write([wiz_cor_line.id],
                {'account_id' : new_account_id})
                
        if new_ad_breakdown_data or ad_replace_data:
            # AD correction
            action = wizard_corl_obj.button_analytic_distribution(
                [wiz_cor_line.id], {'fake': 1})
            # read the AD wizard
            wizard_ad_id = action['res_id'][0]
            wizard_ad_br = wizard_ad_obj.browse(wizard_ad_id)
            self.assert_(
                wizard_ad_br != False,
                "error getting AD wizard record from action: %s" % (
                    str(action), )
            )
            
            total_amount = 0.
            ad_replace_data_by_id = {}
            if ad_replace_data:                
                for k in ad_replace_data:
                    if k != 'per':
                        old_new_values = [] 
                        for old, new in ad_replace_data[k]:
                            old_new_values.append((
                                self.get_account_from_code(db, old,
                                    is_analytic=True),
                                self.get_account_from_code(db, new,
                                    is_analytic=True),
                            ))
                        ad_replace_data_by_id[k] = old_new_values
                
                fields = [
                    'percentage',
                    'cost_center_id',
                    'destination_id',
                    'analytic_id',
                ]
                
                if wizard_ad_br.line_ids:
                    # CC lines: 'cost_center_id' False, 'destination_id' dest,
                    # 'analytic_id' <=> CC
                    # as rpc browse failed here: dirty workaround with read
                    line_ids = [ l.id for l in wizard_ad_br.line_ids ]
                    for adwl_r in wizard_adl_obj.read(line_ids, fields):
                        ad_line_val = {}
                        percent = adwl_r['percentage']
                        
                        if 'dest' in ad_replace_data_by_id:
                            # destination replace
                            for old, new in ad_replace_data_by_id['dest']:
                                if adwl_r['destination_id'] == old:
                                    ad_line_val['destination_id'] = new
                                    break
                                    
                        if 'cc' in ad_replace_data_by_id:
                            # cost center replace
                            for old, new in ad_replace_data_by_id['cc']:
                                if adwl_r['analytic_id'] == old:
                                    ad_line_val['analytic_id'] = new
                                    break
                                    
                        if 'per' in ad_replace_data:
                            # percentage replace
                            for old, new in ad_replace_data['per']:
                                if percent == old:
                                    percent = new
                                    break
                                    
                        if ad_line_val:
                            ad_line_val['percentage'] = percent  # line write workarround (always needed percentage in vals)
                            wizard_adl_obj.write([adwl_r['id']], ad_line_val)
                            
                    # supply update amount from cc lines
                    # NOTE: for finance (state != 'cc') the amount is to be
                    # computed from amount of fp lines
                    if wizard_ad_br.state != 'cc':
                        for adwl_r in wizard_adl_obj.read(line_ids, ['amount']):
                            total_amount += adwl_r['amount']
            
                if wizard_ad_br.fp_line_ids:
                    # FP LINES: 'cost_center_id', 'destination_id',
                    # 'analytic_id' <=> FP
                    # as rpc browse failed here: dirty workaround with read
                    fp_line_ids = [ l.id for l in wizard_ad_br.fp_line_ids ]
                    for adwl_r in wizard_adfpl_obj.read(fp_line_ids, fields):
                        ad_line_val = {}
                        percent = adwl_r['percentage']
                        is_percent_replaced = False
                        
                        if 'dest' in ad_replace_data_by_id:
                            # destination replace
                            for old, new in ad_replace_data_by_id['dest']:
                                if adwl_r['destination_id'] == old:
                                    ad_line_val['destination_id'] = new
                                    break
                                    
                        if 'cc' in ad_replace_data_by_id:
                            # cost center replace
                            for old, new in ad_replace_data_by_id['cc']:
                                if adwl_r['cost_center_id'] == old:
                                    ad_line_val['cost_center_id'] = new
                                    break
                                    
                        if 'fp' in ad_replace_data_by_id:
                            # funding pool replace
                            for old, new in ad_replace_data_by_id['fp']:
                                if adwl_r['analytic_id'] == old:
                                    ad_line_val['analytic_id'] = new
                                    break
                                              
                        if 'per' in ad_replace_data:
                            # percentage replace
                            for old, new in ad_replace_data['per']:
                                if percent == old:
                                    percent = new
                                    is_percent_replaced = True
                                    break
                                    
                        if ad_line_val or is_percent_replaced:
                            ad_line_val['percentage'] = percent  # line write workarround (always needed percentage in vals)
                            wizard_adfpl_obj.write([adwl_r['id']], ad_line_val)
                                              
                    # finance update amount from fp lines
                    # NOTE: for supply (state == 'cc') the amount is to be
                    # computed from amount of cc lines 
                    if wizard_ad_br.state != 'cc':
                        for adwl_r in wizard_adfpl_obj.read(line_ids,
                            ['amount']):
                            total_amount += adwl_r['amount']
            elif new_ad_breakdown_data:
                # replace full AD
                
                # delete previous AD
                del_vals = {}
                if wizard_ad_br.line_ids:
                    # get del vals
                    del_vals['line_ids'] = [ (2, l.id, ) \
                        for l in wizard_ad_br.line_ids ]
                if wizard_ad_br.fp_line_ids:
                    # get del vals
                    del_vals['fp_line_ids'] = [ (2, l.id, ) \
                        for l in wizard_ad_br.fp_line_ids ]
                if del_vals:
                    wizard_ad_obj.write([wizard_ad_id], del_vals)
                    
                # set the new AD
                ccy_id = self.get_company(db).currency_id.id
                ad_line_vals = []
                ad_fp_line_vals = []
                for percent, dest, cc, fp in new_ad_breakdown_data:
                    dest_id = self.get_account_from_code(db, dest,
                        is_analytic=True)
                    cc_id = self.get_account_from_code(db, cc,
                        is_analytic=True)
                    fp_id = self.get_account_from_code(db, fp,
                        is_analytic=True)
                        
                    total_amount += (ji_amount * percent) / 100.
                    
                    # set cc line
                    # 'destination_id' dest, # 'analytic_id' <=> CC
                    # not set amount here as will be auto computed from percent
                    ad_line_vals.append({
                        'wizard_id': wizard_ad_br.id,
                        'analytic_id': cc_id,
                        'percentage': percent,
                        'currency_id': ccy_id,
                        'destination_id': dest_id,
                    })
                    
                    # set fp line
                    # FP LINES: 'cost_center_id', 'destination_id',
                    # 'analytic_id' <=> FP
                    # not set amount here as will be auto computed from percent
                    ad_fp_line_vals.append({
                        'wizard_id': wizard_ad_br.id,
                        'analytic_id': fp_id,
                        'percentage': percent,
                        'currency_id': ccy_id,
                        'destination_id': dest_id,
                        'cost_center_id': cc_id,
                    })
                    
                if ad_line_vals and ad_fp_line_vals:
                    for new_vals in ad_line_vals:
                        wizard_adl_obj.create(new_vals)
                    for new_vals in ad_fp_line_vals:
                        wizard_adfpl_obj.create(new_vals)
                         
            # will validate cor wizard too
            if total_amount and \
                (ad_replace_data_by_id or new_ad_breakdown_data):
                # set wizard header vals to update
                ad_wiz_vals = {
                    'amount': total_amount,
                }
                if new_account_id:
                    # needed for AD wizard to process directly from it a G/L
                    # account change
                    ad_wiz_vals.update({
                        'old_account_id': old_account_id,
                        'account_id': new_account_id,
                    })
                wizard_ad_obj.write([wizard_ad_id], ad_wiz_vals)
                
                # confirm the wizard with adoc context values to process a
                # correction
                context = {
                    'from': 'wizard.journal.items.corrections',
                    'wiz_id': wizard_ad_id,
                }
                wizard_ad_obj.button_confirm([wizard_ad_id], context)
                return  # G/L account change already processed line above
 
        if new_account_id:
            # G/L correction without AD correction: confirm wizard
            # (with an AD correction, cor is confirmed by AD wizard)
            # action_confirm(ids, context=None, distrib_id=False)
            wizard_cor_obj.action_confirm([wiz_br.id], {'fake': 1}, False)
            
    def check_ji_correction(self, db, ji_id,
        account_code, new_account_code=False,
        expected_ad=False, expected_ad_rev=False, expected_ad_cor=False,
        expected_cor_rev_ajis_total_func_amount=False,
        cor_level=1, ji_origin_id=False):
        """
        ji_origin_id: 1st ji corrected for cor cascade
        cor_level: cor level for cor cascade
        """
        
        def get_rev_cor_amount_and_field(base_amount, is_rev):
            if is_rev:
                base_amount *= -1.
            amount_field = 'credit_currency' \
                    if base_amount > 0 else 'debit_currency'   
            return (base_amount, amount_field, )
            
        aml_obj = db.get('account.move.line')
        aal_obj = db.get('account.analytic.line')
        
        od_journal_ids = self.get_journal_ids(db, 'correction',
            is_of_instance=False, is_analytic=False)
        aod_journal_ids = self.get_journal_ids(db, 'correction',
            is_of_instance=False, is_analytic=True)
            
        account_id = self.get_account_from_code(db, account_code,
            is_analytic=False)
        new_account_id = False
        if new_account_code:
            new_account_id = self.get_account_from_code(db, new_account_code,
                is_analytic=False)
            self.assert_(
                new_account_id != False,
                "new account '%s' not found" % (new_account_id, )
            )
        
        ji_br = aml_obj.browse(ji_id)
        ji_origin = ji_origin_id and aml_obj.browse(ji_origin_id).name or \
            ji_br.name
        ji_amount = ji_br.debit_currency and ji_br.debit_currency * -1 or \
            ji_br.credit_currency
        
        if new_account_code and new_account_code != account_code:
            # CHECK JI REV COR
                
            # check JI REV
            cor_rev_amount, cor_rev_amount_field = get_rev_cor_amount_and_field(
                ji_amount, True)
            domain = [
                ('journal_id', 'in', od_journal_ids),
                ('reversal_line_id', '=', ji_id),
                ('account_id', '=', account_id),
                (cor_rev_amount_field, '=', abs(cor_rev_amount)),
            ]
            rev_ids = aml_obj.search(domain)
            self.assert_(
                rev_ids != False,
                "no JI REV found for %s %s %f:: %s" % (account_code,
                    ji_br.name, ji_amount, db.colored_name, )
            )
            
            # check JI COR
            cor_rev_amount, cor_rev_amount_field = get_rev_cor_amount_and_field(
                ji_amount, False)
            domain = [
                ('journal_id', 'in', od_journal_ids),
                ('corrected_line_id', '=', ji_id),
                ('account_id', '=', new_account_id),
                (cor_rev_amount_field, '=', abs(cor_rev_amount)),
            ]
            rev_ids = aml_obj.search(domain)
            self.assert_(
                rev_ids != False,
                "no JI COR found for %s %s %f:: %s" % (new_account_code,
                    ji_br.name, ji_amount, db.colored_name, )
            )
                
        # ids of AJIs not rev/cor (not in correction journal)
        base_aji_ids = aal_obj.search([
            ('move_id', '=', ji_id),
            ('journal_id', 'not in', aod_journal_ids),
            ('general_account_id', '=', account_id),
        ]) or []
        # FIXME way of truely getting AJIs when cor of cor
        
        if expected_ad and not cor_level > 1:  # FIXME remove and not cor_level > 1
            # check AJIs
            self.assert_(
                len(base_aji_ids) == len(expected_ad),
                "expected AJIs count do not match for JI %s %s %f:: %s" % (
                    new_account_code or account_code,
                    ji_br.name, ji_amount, db.colored_name, )
            )
            
            match_count = 0
            for aal_br in aal_obj.browse(base_aji_ids):
                for percent, dest, cc, fp in expected_ad:
                    if aal_br.general_account_id.id == account_id and \
                        aal_br.destination_id.code == dest and \
                        aal_br.cost_center_id.code == cc and \
                        aal_br.account_id.code == fp and \
                        aal_br.amount_currency == ((ji_amount * percent) / 100.):  # percent match ?
                        match_count += 1
                        break
                        
            self.assert_(
                len(base_aji_ids) == match_count,
                "expected AJIs do not match for JI %s %f:: %s" % (
                    ji_br.name, ji_amount, db.colored_name, )
            )
                
        if expected_ad_rev:
            # check REV AJIs
            domain = [
                ('journal_id', 'in', aod_journal_ids),
                ('general_account_id', '=', account_id),
            ]
            if cor_level == 1:
                domain.append(('reversal_origin', 'in', base_aji_ids))
            else:
                domain.append(('name', '=', "REV - %s" % (ji_br.name, )))
            ids = aal_obj.search(domain)
            self.assert_(
                len(ids) == len(expected_ad_rev),
                "expected REV AJIs count do not match for JI %s %s %f:: %s" % (
                    new_account_code or account_code,
                    ji_br.name, ji_amount, db.colored_name, )
            )
            
            match_count = 0
            total_func_amount = 0
            for aal_br in aal_obj.browse(ids):
                total_func_amount += aal_br.amount
                for percent, dest, cc, fp in expected_ad_rev:
                    if aal_br.general_account_id.id == account_id and \
                        aal_br.destination_id.code == dest and \
                        aal_br.cost_center_id.code == cc and \
                        aal_br.account_id.code == fp and \
                        aal_br.amount_currency == (((ji_amount * percent) / 100.) * -1):
                        match_count += 1
                        break
                        
            self.assert_(
                len(ids) == match_count,
                "expected REV AJIs do not match for JI %s %s %f:: %s" % (
                    new_account_code or account_code,
                    ji_br.name, ji_amount, db.colored_name, )
            )
            if expected_cor_rev_ajis_total_func_amount:
                self.assert_(
                    expected_cor_rev_ajis_total_func_amount == total_func_amount,
                    "expected REV AJIs total func amount %f not found:: %s" % (
                        expected_cor_rev_ajis_total_func_amount,
                        db.colored_name, )
                )
                
        if expected_ad_cor:
            # check COR AJIs
            ids = aal_obj.search([
                #('last_corrected_id', 'in', base_aji_ids),
                ('journal_id', 'in', aod_journal_ids),
                ('general_account_id', '=', new_account_id or account_id),
                ('name', '=', "COR%d - %s" % (cor_level, ji_origin, )),
            ])
            self.assert_(
                len(ids) == len(expected_ad_cor),
                "expected COR AJIs count do not match for JI %s %s %f:: %s" % (
                    new_account_code or account_code,
                    ji_br.name, ji_amount, db.colored_name, )
            )
            
            match_count = 0
            total_func_amount = 0
            for aal_br in aal_obj.browse(ids):
                total_func_amount += aal_br.amount
                for percent, dest, cc, fp in expected_ad_cor:
                    # COR with new account
                    gl_account_id = new_account_id or account_id
                    if aal_br.general_account_id.id == gl_account_id and \
                        aal_br.destination_id.code == dest and \
                        aal_br.cost_center_id.code == cc and \
                        aal_br.account_id.code == fp and \
                        aal_br.amount_currency == ((ji_amount * percent) / 100.):  # percent match ?
                        match_count += 1
                        break
                        
            self.assert_(
                len(ids) == match_count,
                "expected COR AJIs do not match for JI %s %s %f:: %s" % (
                    new_account_code or account_code,
                    ji_br.name, ji_amount, db.colored_name, )
            )
            if expected_cor_rev_ajis_total_func_amount:
                self.assert_(
                    expected_cor_rev_ajis_total_func_amount == total_func_amount,
                    "expected COR AJIs total func amount %f not found:: %s" % (
                        expected_cor_rev_ajis_total_func_amount,
                        db.colored_name, )
                )
        
    def journal_create_entry(self, database):
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
        self.assert_(
            move_id != False,
            "Move creation failed with these values: %s" % move_vals
        )
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
    
    def get_period_id(self, db, month, year=0):
        year = datetime.now().year if year == 0 else year
        period_obj = db.get('account.period')
        
        ids = period_obj.search([
            ('date_start', '=', "%04d-%02d-01" % (year, month, )),
        ])
        return ids and ids[0] or False
        
    def period_close(self, db, level, month, year=0):
        self._period_close_reopen(db, level, month, year=year, reopen=False)
        
    def period_reopen(self, db, level, month, year=0):
        self._period_close_reopen(db, level, month, year=year, reopen=True)
    
    def _period_close_reopen(self, db, level, month, year=0, reopen=False):
        """
        close/reopen period at given level
        :param level: 'f', 'm' or 'h' for 'field', 'mission' or 'hq'
        """
        self.assert_(
            level in ('f', 'm', 'h', ),
            "invalid level value 'f', 'm' or 'h' expected"
        )
        
        period_id = self.get_period_id(db, month, year=year)
        self.assert_(
            period_id != False,
            "period %02d/%04d not found" % (year, month, )
        )
            
        period_obj = db.get('account.period')
        
        if level =='f':
            if reopen:
                period_obj.action_reopen_field([period_id])
            else:
                period_obj.action_close_field([period_id])
        elif level == 'm':
            if reopen:
                period_obj.action_reopen_mission([period_id])
            else:
                period_obj.action_close_mission([period_id])
        elif level == 'h':
            if reopen:
                period_obj.action_open_period([period_id])
            else:
                period_obj.action_close_hq([period_id])
                
    def invoice_create_supplier_invoice(self, db, ccy_code=False, is_refund=False,
        date=False, partner_id=False, ad_header_breakdown_data=False, 
        lines_accounts=[], validate=False):
        """
        create a supplier invoice or
        :param ccy_code: ccy code (partner ccy if not set)
        :param is_refund: is a refund ? False for a regular invoice
        :param date: today if False
        :param partner_id: Local Market if False
        :param ad_header_breakdown_data: see analytic_distribution_create
        :param lines_accounts: list of account codes for each line to generate
        :return : id of invoice
        """
        res = {}
        
        ai_obj = db.get('account.invoice')
        
        # simulate menu context
        context = { 'type': 'in_invoice', 'journal_type': 'purchase', }
        
        # vals
        itype = 'in_refund' if is_refund else 'in_invoice'
        date = date or self.get_orm_date_now()
        vals = {
            'type': itype,
            
            'is_direct_invoice': False,
            'is_inkind_donation': False,
            'is_debit_note': False,
            'is_intermission': False,
            
            'date_invoice': date,  # posting date
            'document_date': date,
        }
        
        # company 
        # via on_change: will set journal
        # company_id = db.get('res.users').browse(cr, uid, [uid]).company_id.id
        company_id = db.user.company_id.id
        vals['company_id'] = company_id
        res = ai_obj.onchange_company_id(
            False,  # ids
            company_id,
            False,  # partner id
            itype,  # invoice type
            False,  # invoice line,
            False)  # ccy id
        if res and res['value']:
            vals.update(res['value'])
            
        # partner
        # via on_change: will set account_id, currency_id
        if not partner_id:
            domain = [
                ('supplier', '=', True),
                ('name', '=', 'Local Market'),
            ]
            partner_id = db.get('res.partner').search(domain)
            self.assert_(
                partner_id != False,
                "Partner %s not found" % (str(domain), )
            )
            partner_id = partner_id[0]
            vals['partner_id'] = partner_id
            
            res = ai_obj.onchange_partner_id(
                False,  # ids
                itype,  # invoice type
                partner_id,
                False,  # date_invoice
                False,  # payment_term
                False,  # partner_bank_id
                False,  # company_id
                False,  #  is_inkind_donation
                False,  # is_intermission
                False,  # is_debit_note
                False)  # is_direct_invoice
            if res and res['value']:
                vals.update(res['value'])
                
        if ccy_code:
            # specific ccy instead of partner one
            ccy_ids = db.get('res.currency').search([('name', '=', ccy_code)])
            self.assert_(
                ccy_ids != False,
                "'%s' currency not found" % (ccy_code, )
            )
            vals['currency_id'] = ccy_ids[0]
                    
        # header ad
        if ad_header_breakdown_data:
            ad_id = self.analytic_distribution_create(db,
                breakdown_data=ad_header_breakdown_data)
            vals['analytic_distribution_id'] = ad_id
            
        # save header
        id = ai_obj.create(vals, context)
        
        # save lines
        if lines_accounts:
            line_vals = [
                (0, 0, {
                    'account_id': self.get_account_from_code(db, a),
                    'name': FINANCE_TEST_MASK['invoice_line'] % (id, i + 1, a),
                    'price_unit': float(randrange(1, 10)),
                    'quantity': float(randrange(10, 100)),
                }) for i, a in list(enumerate(lines_accounts))
            ]
            ai_obj.write([id], {'invoice_line': line_vals}, context)
        
        return id
            
    def invoice_validate(self, db, ids):
        """
        validate the invoice and return its expense JIs ids list
        :return : {id: [ji_id, ...]} if ids is a list else return [ji_id, ...]
        """
        
        if isinstance(ids, (int, long, )):
            ids = [ids]
            is_single_ids = True
            res = []
        else:
            is_single_ids = False
            res = {}
            
        ai_model_name = 'account.invoice'
        ai_obj = db.get(ai_model_name)
        aml_obj = db.get('account.move.line')
        
        validated_ids = []
        
        for ai in ai_obj.browse(ids):
            if not is_single_ids:
                res[ai.id] = []
                
            if ai.state == 'draft':
                # - open it
                # - force doc date to posting date (as by default to cur date)
                vals = {
                    'document_date': self.date2orm(ai.date_invoice),
                }
                if not ai.check_total:
                    vals['check_total'] = ai.amount_total
                ai_obj.write([ai.id], vals)
                db.exec_workflow(ai_model_name, 'invoice_open', ai.id)
                validated_ids.append(ai.id)
                
        for ai in ai_obj.browse(validated_ids):
            # get invoice EXPENSE JIs from invoice reference 
            # (reference obtained once invoice is validated)
            ji_ids = aml_obj.search([
                ('reference', '=', ai.number),
                # only expense JIs
                ('account_id.is_analytic_addicted', '=', True),
            ])
            if is_single_ids:
                res = ji_ids or []
            else:
                res[ai.id] = ji_ids or []
                
        return res
        
    def analytic_account_activate_since(self, db, date):
        aaa_obj = db.get('account.analytic.account')
        aaa_ids = aaa_obj.search([('parent_id', '!=', False)])
        for aaa_br in aaa_obj.browse(aaa_ids):
            aaa_obj.write(aaa_br.id, {
                'parent_id': aaa_br.parent_id.id,
                'date_start': date,
            })        

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
