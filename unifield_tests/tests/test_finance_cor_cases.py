#!/usr/bin/env python
# -*- coding: utf8 -*-

#
# FINANCE GL/AD CORRECTION UNIT TESTS
# Developer: Vincent GREINER
#

from __future__ import print_function
from unifield_test import UnifieldTestException
from unifield_test import UnifieldTest
from finance import FinanceTestException
from finance import FinanceTest

import time
from datetime import datetime

# play all flow:
# cd unifield/test-finance/unifield-wm/unifield_tests
# python -m unittest tests.test_finance_cor_cases

"""
TODO NOTES

- use cases to check at fonctional level:
    10: not expense account to expense one with an AD: 
        => AJIs are created in OD journal
            => check with Matthias
            => check case manually
            
- cases developed
    - single instance
        X 01
        X 02
        X 03
        X 04
        X 05
        X 06
        X 07
        X 08
        X 09
        X 10 
        X 11
        X 12
        X 13
        X 14
    - sync
          20
          21
          22
          23
          24
          25
          26
    
- options:
    - [IMP] check_ji_correction(): obtain expected AD with cor level > 1
    - [IMP] each case should delete some data
"""


#TEST_THE_TEST = True
TEST_THE_TEST = False


class FinanceTestCorCasesException(UnifieldTestException):
    pass


class FinanceTestCorCases(FinanceTest):
    class DataSetMeta(object):
        functional_ccy = 'EUR'
    
        rates = { # from Januar
            'EUR': [ 1., 1., ],
            'CHF': [ 0.95476, 0.965, ],
            'USD': [ 1.24, 1.28, ],
        }
        
        # new COST CENTERS (and related target instances)
        ccs = {
            # 'CC': [(Prop Instance, is_target), ]
            
            # C1 tree
            'HT120': [ ('HQ1C1', True), ],
            'HT112': [ ('HQ1C1', False), ('HQ1C1P1', True), ],
            'HT122': [ ('HQ1C1', False), ('HQ1C1P2', True), ],
            
            # C2 tree
            'HT220': [ ('HQ1C2', True), ],
        }
    
        # new FUNDING POOLS (and related cost centers)
        fp_ccs = {
            ('HQ1C1', 'FP1'): [ 'HT101', 'HT120', ],
            ('HQ1C1', 'FP2'): [ 'HT101', 'HT120', ],
        }
        
        # financing contracts
        financing_contracts_donor = 'DONOR',
        financing_contracts = {
            ('HQ1C1', 'FC1'): { 
                'ccs' : [ 'HT101', 'HT120', ],
                'fps': [ 'FP1', 'FP2', ],
            },
        }
        
        register_prefix = 'BNK'
        
    def _get_dataset_meta(self):
        if not hasattr(self, 'dataset_meta'):
            self.dataset_meta = self.DataSetMeta()
        return self.dataset_meta
    # end of dataset Meta
    
    # -------------------------------------------------------------------------
    # SETUP & TEARDOWN
    # -------------------------------------------------------------------------
    
    def setUp(self):
        def dataset_msg(msg):
            prefix = 'FinanceTestCorCases DATASET'
            prefix_pattern = '[' + self.colors.BGreen + prefix \
                + self.colors.Color_Off + '] '
            print(prefix_pattern + msg)
            
        keyword = 'finance_test_cor_cases_dataset'  # dataset flag at HQ level
            
        if not self.is_keyword_present(self.hq1, keyword):
            # dataset to generate
            dataset_msg('GENERATING')
            self._set_dataset()
            self.hq1.get(self.test_module_obj_name).create({
                'name': keyword,
                'active': True,
            })
            
    def tearDown(self):
        pass
        
    # -------------------------------------------------------------------------
    # DATASET
    # -------------------------------------------------------------------------
    
    def _set_dataset(self):
        def get_instance_id_from_code(db, code):
            instance_ids = db.get('msf.instance').search(
                [('code', '=', self.get_db_name_from_suffix(code))])
                
            if not instance_ids:
                # default dev instance (db/prop instances name from a RB)
                target_instance_code = "%s%s" % (
                    self._db_instance_prefix or self_db_prefix, code, )
                instance_ids = db.get('msf.instance').search(
                        [('code', '=', target_instance_code)])
                self.assert_(instance_ids != False, "instance not found")
            
            return instance_ids and instance_ids[0] or False
        
        def activate_currencies(db, codes):
            if isinstance(codes, (str, unicode, )):
                codes = [codes]
                
            ccy_obj = db.get('res.currency')
            ccy_ids = ccy_obj.search([
                ('name', 'in', codes),
                ('active', '=', False),
            ])
            if ccy_ids:  # to active
                ccy_obj.write(ccy_ids, {'active': True})
        
        def set_default_currency_rates(db):            
            for ccy_name in meta.rates:
                ccy_ids = db.get('res.currency').search([
                    ('name', '=', ccy_name),
                ])
                if ccy_ids:
                    index = 1
                    for r in meta.rates[ccy_name]:
                        # rates for ccy in month order from Januar
                        dt = "%04d-%02d-01" % (year, index, )
                        ccy_rate_ids = db.get('res.currency.rate').search([
                            ('currency_id', '=', ccy_ids[0]),
                            ('name', '=', dt),
                        ])
                        if ccy_rate_ids:
                            db.get('res.currency.rate').write(ccy_rate_ids,
                                {'name': dt, 'rate': r})
                        else:
                            db.get('res.currency.rate').create({
                                'currency_id': ccy_ids[0],
                                'name': dt,
                                'rate': r,
                            })
                        
                        index += 1

        def set_cost_centers():
            hq = self.hq1
            aaa_model = 'account.analytic.account'
            aaa_obj = hq.get(aaa_model)
            atcc_obj = hq.get('account.target.costcenter')
            
            company = self.get_company(hq)
            
            cc_id = False
            parent_cc_ids = {}
            for cc in meta.ccs:
                cc_ids = aaa_obj.search(
                    [('code', '=', cc), ('category', '=', 'OC')])
                    
                if not cc_ids:
                    # CC to create
                    
                    # get parent (parent code: 3 first caracters (HT1, HT2, ...))
                    parent_code = cc[:3]  
                    if not parent_code in parent_cc_ids:
                        parent_ids = aaa_obj.search([
                            ('type', '=', 'view'),
                            ('category', '=', 'OC'),
                            ('code', '=', parent_code),
                        ])
                        parent_id = parent_ids and parent_ids[0] or False
                        parent_cc_ids[parent_code] = parent_id
                    else:
                        parent_id = parent_cc_ids.get(parent_code, False)
                    self.assert_(
                        parent_id != False,
                        "parent cost center not found '%s'" % (parent_code, )
                    )
                        
                    vals = {
                        'code': cc,
                        'description': cc,
                        'currency_id': company.currency_id.id,
                        'name': cc,
                        'date_start': date_fy_start,
                        'parent_id': parent_id,
                        'state': 'open',
                        'type': 'normal', 
                        'category': 'OC',
                        'instance_id': company.instance_id.id,
                    }
                    cc_id = aaa_obj.create(vals)
                else:
                    cc_id = cc_ids[0]
                
                if cc_id:
                    # set target instance or/and is target
                    for instance_code, is_target in meta.ccs[cc]:
                        instance_id = get_instance_id_from_code(hq,
                            instance_code)
                        if instance_id:
                            target_ids = atcc_obj.search([
                                ('instance_id', '=', instance_id),
                                ('cost_center_id', '=', cc_id),
                            ])
                            
                            if not target_ids:
                                target_id = atcc_obj.create({
                                    'instance_id': instance_id,
                                    'cost_center_id': cc_id,
                                })
                            else:
                                target_id = target_ids[0]
                            
                            if is_target and target_id:
                                atcc_obj.write([target_id], {
                                    'is_target': True,
                                })
                        
        def set_funding_pools():
            c = self.c1
            aaa_model = 'account.analytic.account'
            
            for instance, fp in meta.fp_ccs:
                aaa_obj = c.get(aaa_model)
                company = c.get_company(db)
                
                parent_ids = aaa_obj.search([
                    ('code', '=', 'FUNDING'),
                    ('type', '=', 'view')
                ])
                self.assert_(
                    parent_ids != False,
                    'parent funding pool not found'
                )
        
                vals = {
                    'code': fp,
                    'description': fp,
                    'currency_id': company.currency_id.id,
                    'name': fp,
                    'date_start': date_fy_start,
                    'parent_id': parent_ids[0],
                    'state': 'open',
                    'type': 'normal', 
                    'category': 'FUNDING',
                    'instance_id': company.instance_id.id,
                }
                if not self.record_exists(c, aaa_model, 
                        self.dfv(vals, include=('code', 'instance_id', ))):
                    # get related CCs and set them
                    cc_ids = aaa_obj.search([
                        ('category', '=', 'OC'),
                        ('code', 'in', meta.fp_ccs[(instance, fp)]),
                    ])
                    if cc_ids:
                        vals['cost_center_ids'] = [(6, 0, cc_ids)]
                    aaa_obj.create(vals)
                
        def set_financing_contracts():
            model = 'financing.contract.contract'
            model_fcd = 'financing.contract.donor'
            model_fcfpl = 'financing.contract.funding.pool.line'
            model_aaa = 'account.analytic.account'
            
            for instance, fc in meta.financing_contracts:
                db = self.get_db_from_name(
                    self.get_db_name_from_suffix(instance))
                company = self.get_company(db)
                
                # set donor
                donor_code = "%s_%s" % (
                    instance, meta.financing_contracts_donor, )
                vals = {
                    'code': donor_code,
                    'name': donor_code.replace('_', ' '),
                    'reporting_currency': company.currency_id.id,
                }
                donor_ids = db.get(model_fcd).search(
                    self.dfv(vals, include=('code', )))
                if not donor_ids:
                    donor_ids = [db.get(model_fcd).create(vals), ]
                
                vals = {
                    'code': fc,
                    'name': fc,
                    'donor_id': donor_ids[0],
                    'instance_id': company.instance_id.id,
                    'eligibility_from_date': date_fy_start,
                    'eligibility_to_date': date_fy_stop,
                    'grant_amount': 0.,
                    'state': 'open',
                    'open_date': date_now,
                }
                if not self.record_exists(db, model,
                    self.dfv(vals, include=('code', ))):
                    # set cost centers
                    cc_codes = meta.financing_contracts[(instance, fc)].get(
                        'ccs', False)
                    if cc_codes:
                        cc_ids = db.get(model_aaa).search([
                            ('category', '=', 'OC'),
                            ('code', 'in', cc_codes),
                        ])
                        if cc_ids:
                            vals['cost_center_ids'] = [(6, 0, cc_ids)]
                    
                    contract_id = db.get(model).create(vals)
                    
                    # set funding pools
                    fp_codes = meta.financing_contracts[(instance, fc)].get(
                        'fps', False)
                    if fp_codes:
                        fp_ids = db.get(model_aaa).search([
                            ('category', '=', 'FUNDING'),
                            ('code', 'in', fp_codes),
                        ])
                        if fp_ids:
                            for fp_id in fp_ids:
                                vals = {
                                    'contract_id': contract_id,
                                    'funding_pool_id': fp_id,
                                    'funded': True,
                                    'total_project': True,
                                    'instance_id': company.instance_id.id,
                                }
                                db.get(model_fcfpl).create(vals, {'fake': 1})
                    
        # ---------------------------------------------------------------------
        meta = self._get_dataset_meta()
        
        now = datetime.now()
        year = now.year
        date_fy_start = self.get_orm_date_fy_start()
        date_fy_stop = self.get_orm_date_fy_stop()
        date_now = self.get_orm_date_now()
        
        # activate all analytic account (date start) from HQ
        # (will be synced later here)
        for i in self._instances_suffixes:
            # check instance dataset
            db = self.get_db_from_name(self.get_db_name_from_suffix(i))
            company = self.get_company(db)
            
            self.assert_(
                company.currency_id.name == meta.functional_ccy,
                 "wrong functionnal ccy: '%s' is expected" % (
                    meta.functional_ccy, )
            )
            
            # activate analytic accounts since FY start
            self.analytic_account_activate_since(self.hq1, date_fy_start)
            
            # open current month period
            period_id = self.get_period_id(db, now.month)
            if period_id:
                db.get('account.period').write([period_id], {
                    'state': 'draft',
                })
                    
            # activate currencies (if required)
            activate_currencies(db, [ccy_name for ccy_name in meta.rates])

        # set default rates: at HQ then sync down
        set_default_currency_rates(self.hq1)
        self._sync_down()
            
        # HQ level: set cost centers + target CC of instance + sync down
        set_cost_centers()
        self._sync_down()
            
        # C1 level: set funding pool + sync up/down (from c1)
        set_funding_pools()
        self._sync_c1()
        
        # C1 level: set financing contract + sync up/down (from c1)
        set_financing_contracts()
        self._sync_c1()
        
    # -------------------------------------------------------------------------
    # PRIVATE TOOLS FUNCTIONS
    # -------------------------------------------------------------------------
        
    def _sync_down(self):
        self.synchronize(self.hq1)
        self.synchronize(self.c1)  # pull from hq
        self.synchronize(self.c1)  # push to projects
        self.synchronize(self.p1)
        self.synchronize(self.p12)  # C1P2
        # TODO:C2 level and C2P1/P2 (C2 not use in scenario at this time)
        
    def _sync_c1(self):
        self.synchronize(self.c1)
        #self.synchronize(self.hq1)
        self.synchronize(self.p1)
        self.synchronize(self.p12)  # C1P2
           
    def _register_set(self, db, period_id=1, ccy_name=False):
        dataset_meta = self._get_dataset_meta()
        
        db = self.c1
        aj_obj = db.get('account.journal')
        abs_obj = db.get('account.bank.statement')
        
        if not ccy_name:
            ccy_name = dataset_meta.functional_ccy
        
        # set Januar bank journal/register and open it
        journal_code = dataset_meta.register_prefix + ' ' + ccy_name
        if not self.record_exists(db, 'account.journal',
            [('code', '=', journal_code)]):
            reg_id, journal_id = self.register_create(db, journal_code,
                journal_code, 'bank', '10200', ccy_name)
            # update period
            abs_obj.write([reg_id], {'period_id': period_id})
            abs_obj.button_open_bank([reg_id])
                
    def _register_get(self, db, ccy_name=False, browse=False):
        """
        :param browse: to return browsed object instead of id
        """
        dataset_meta = self._get_dataset_meta()
        
        abs_obj = db.get('account.bank.statement')
        if not ccy_name:
            ccy_name = dataset_meta.functional_ccy
        journal_code = dataset_meta.register_prefix + ' ' + ccy_name
        
        ids = abs_obj.search([('name', '=', journal_code)])
        self.assert_(
            ids != False,
            'register %s not found' % (journal_code, )
        )
        if browse:
            return abs_obj.browse([ids[0]])[0]
        else:
            return ids[0]
            
    # -------------------------------------------------------------------------
    # FLOW
    # -------------------------------------------------------------------------
           
    # play all flow:
    # cd unifield/test-finance/unifield-wm/unifield_tests
    # python -m unittest tests.test_finance_cor_cases
    
    def test_cor1_00(self):
        """
        fake unit test for dataset testing
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_00
        """
        pass
    
    # -------------------------------------------------------------------------
    # SINGLE CASES FLOW: from 01 to 14
    # -------------------------------------------------------------------------
        
    def test_cor1_01(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_01
        G/L ACCOUNT 60010=>60020
        """
        db = self.c1
        self._register_set(db)
        
        reg_id = self._register_get(db, browse=False)
        if reg_id:
            account = '60010'
            new_account = '60020'
            
            ad = [(100., 'OPS', 'HT101', 'PF'), ]
            
            regl_id, distrib_id, ji_id = self.register_create_line(
                db, reg_id,
                account, self.get_random_amount(True),
                ad_breakdown_data=ad,
                date=False, document_date=False,
                do_hard_post=True,
                tag="C1_01"
            )
            
            # 60010 -> 60020
            self.simulation_correction_wizard(db, ji_id,
                    new_account_code=new_account,
                    new_ad_breakdown_data=False,
                    ad_replace_data=False,
            )
            
            self.check_ji_correction(db, ji_id,
                account, new_account_code=new_account,
                expected_ad=ad,
                expected_ad_rev=ad,
                expected_ad_cor=ad,
            )
            
    def test_cor1_02(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_02
        DEST REPLACE OPS=>NAT NO REV/COR
        """
        db = self.c1
        self._register_set(db)
        
        reg_id = self._register_get(db, browse=False)
        if reg_id:
            account = '60010'
            dest = 'OPS'
            new_dest = 'NAT'
            
            regl_id, distrib_id, ji_id = self.register_create_line(
                db, reg_id,
                account, self.get_random_amount(True),
                ad_breakdown_data=[(100., dest, 'HT101', 'PF'), ],
                date=False, document_date=False,
                do_hard_post=True,
                tag="C1_02"
            )
            
            # correction dest from OPS to NAT
            self.simulation_correction_wizard(db, ji_id,
                new_account_code=False,
                new_ad_breakdown_data=False,
                ad_replace_data={ 100.: {'dest': new_dest, } },
            )
            
            self.check_ji_correction(db, ji_id,
                account, new_account_code=False,
                expected_ad=[(100., new_dest, 'HT101', 'PF'), ],
                expected_ad_rev=False,
                expected_ad_cor=False,
            )
            
    def test_cor1_03(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_03
        CC REPLACE HT101=>HT120 NO REV/COR
        """
        db = self.c1
        self._register_set(db)
        
        reg_id = self._register_get(db, browse=False)
        if reg_id:
            account = '60010'
            cc = 'HT101'
            new_cc = 'HT120'
            
            regl_id, distrib_id, ji_id = self.register_create_line(
                db, reg_id,
                account, self.get_random_amount(True),
                ad_breakdown_data=[(100., 'OPS', cc, 'PF'), ],
                date=False, document_date=False,
                do_hard_post=True,
                tag="C1_03"
            )
            
            # correction CC from HT101 to HT120
            self.simulation_correction_wizard(db, ji_id,
                    new_account_code=False,
                    new_ad_breakdown_data=False,
                    ad_replace_data={ 100.: {'cc': new_cc, } },
            )
            
            self.check_ji_correction(db, ji_id,
                account, new_account_code=False,
                expected_ad=[(100., 'OPS', new_cc, 'PF'), ],
                expected_ad_rev=False,
                expected_ad_cor=False,
            )
            
    def test_cor1_04(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_04
        FP REPLACE PF=>FP1 NO REV/COR
        """
        db = self.c1
        self._register_set(db)
        
        reg_id = self._register_get(db, browse=False)
        if reg_id:
            account = '60010'
            fp = 'PF'
            new_fp = 'FP1'
            
            regl_id, distrib_id, ji_id = self.register_create_line(
                db, reg_id,
                account, self.get_random_amount(True),
                ad_breakdown_data=[(100., 'OPS', 'HT101', fp), ],
                date=False, document_date=False,
                do_hard_post=True,
                tag="C1_04"
            )
            
            # correction FP from PF to FP1
            self.simulation_correction_wizard(db, ji_id,
                new_account_code=False,
                new_ad_breakdown_data=False,
                ad_replace_data={ 100.: {'fp': new_fp, } },
            )
            
            self.check_ji_correction(db, ji_id,
                account, new_account_code=False,
                expected_ad=[(100., 'OPS', 'HT101', new_fp), ],
                expected_ad_rev=False,
                expected_ad_cor=False,
            )
            
    def test_cor1_05(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_05
        G/L ACCOUNT 60010=>60000 and new AD 
        """
        db = self.c1
        self._register_set(db)
        
        reg_id = self._register_get(db, browse=False)
        if reg_id:
            account = '60010'
            new_account = '60000'
            
            ad = [(100., 'OPS', 'HT101', 'PF'), ]
            
            regl_id, distrib_id, ji_id = self.register_create_line(
                db, reg_id,
                account, -100.,  # 100 amount to easyly check AD brakdown
                ad_breakdown_data=ad,
                date=False, document_date=False,
                do_hard_post=True,
                tag="C1_05"
            )
            
            # 60010 -> 60000
            # AD 100% OPS, HT101, PF -> 55% OPS, HT101, PF
            #                        -> 45% NAT, HT101, PF
            new_ad=[
                (55., 'OPS', 'HT101', 'PF'),
                (45., 'NAT', 'HT101', 'PF'),
            ]
            self.simulation_correction_wizard(db, ji_id,
                    new_account_code=new_account,
                    new_ad_breakdown_data=new_ad,
                    ad_replace_data=False
            )
            
            self.check_ji_correction(db, ji_id,
                account, new_account_code=new_account,
                expected_ad=ad,
                expected_ad_rev=ad,
                expected_ad_cor=new_ad,
            )
            
    def test_cor1_06(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_06
        """
        db = self.c1
        self._register_set(db, ccy_name='USD')
        
        reg_id = self._register_get(db, browse=False, ccy_name='USD')
        if reg_id:
            account = '60010'
            
            ad = [
                (60., 'OPS', 'HT101', 'PF'),
                (40., 'OPS', 'HT120', 'PF'),
            ]
            
            regl_id, distrib_id, ji_id = self.register_create_line(
                db, reg_id,
                account, -100.,
                ad_breakdown_data=ad,
                date=False, document_date=False,
                do_hard_post=True,
                tag="C1_06"
            )
            
            # CLOSE PERIOD Januar (MISSION)
            self.period_close(db, 'f', 1)
            self.period_close(db, 'm', 1)
            
            new_ad=[
                (70., 'OPS', 'HT101', 'PF'),
                (30., 'OPS', 'HT120', 'PF'),
            ]
            self.simulation_correction_wizard(db, ji_id,
                    cor_date=self.get_orm_fy_date(2, 7),  # 7 Feb of this year
                    new_account_code=False,
                    new_ad_breakdown_data=False,
                    ad_replace_data={
                            60.: {'per': 70., },
                            40.: {'per': 30., 'cc': 'HT120', },
                        },
            )
            
            self.check_ji_correction(db, ji_id,
                account, new_account_code=False,
                expected_ad=ad,
                expected_ad_rev=ad,
                expected_ad_cor=new_ad,
                expected_cor_rev_ajis_total_func_amount=80.65,
            )
            
            # REOPEN period for over cases flows
            self.period_reopen(db, 'm', 1)
            self.period_reopen(db, 'f', 1)

            
    def test_cor1_07(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_07
        G/L ACCOUNT 60010=>60030
        """
        db = self.c1
        self._register_set(db, ccy_name='USD')
        
        reg_id = self._register_get(db, browse=False, ccy_name='USD')
        if reg_id:
            account = '60010'
            new_account = '60030'
            
            ad = [
                (60., 'OPS', 'HT101', 'PF'),
                (40., 'OPS', 'HT120', 'PF'),
            ]
            
            regl_id, distrib_id, ji_id = self.register_create_line(
                db, reg_id,
                account, -100.,
                ad_breakdown_data=ad,
                date=False, document_date=False,
                do_hard_post=True,
                tag="C1_07"
            )
            
            new_ad=[
                (70., 'OPS', 'HT101', 'PF'),
                (30., 'OPS', 'HT101', 'PF'),
            ]
            self.simulation_correction_wizard(db, ji_id,
                    cor_date=self.get_orm_fy_date(2, 7),  # 7 Feb of this year
                    new_account_code=new_account,
                    new_ad_breakdown_data=new_ad,
                    ad_replace_data=False
            )
            
            self.check_ji_correction(db, ji_id,
                account, new_account_code=new_account,
                expected_ad=ad,
                expected_ad_rev=ad,
                expected_ad_cor=new_ad,
                expected_cor_rev_ajis_total_func_amount=80.65,
            )
            
    def test_cor1_08(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_08
        """    
        db = self.c1
        self._register_set(db)
        
        reg_id = self._register_get(db, browse=False)
        if reg_id:
            account = '60010'
            new_account = '13310'
            
            ad = [
                (10., 'OPS', 'HT101', 'PF'),
                (90., 'OPS', 'HT101', 'FP1'),
            ]
            self.analytic_distribution_set_fp_account_dest(db, 'FP1', account,
                'OPS')
            
            regl_id, distrib_id, ji_id = self.register_create_line(
                db, reg_id,
                account, self.get_random_amount(True),
                ad_breakdown_data=ad,
                date=False, document_date=False,
                do_hard_post=True,
                tag="C1_08"
            )
 
            self.simulation_correction_wizard(db, ji_id,
                    cor_date=False,
                    new_account_code=new_account,
                    new_ad_breakdown_data=False,
                    ad_replace_data=False
            )
            
            self.check_ji_correction(db, ji_id,
                account, new_account_code=new_account,
                expected_ad=False,  # bc new account not an expense one
                expected_ad_rev=ad,
                expected_ad_cor=False,  # bc new account not an expense one
            )
            
    def test_cor1_09(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_09
        G/L ACCOUNT 13000=>13010
        """
        db = self.c1
        self._register_set(db)
        
        reg_id = self._register_get(db, browse=False)
        if reg_id:
            account = '13300'
            new_account = '13310'
            
            regl_id, distrib_id, ji_id = self.register_create_line(
                db, reg_id,
                account, self.get_random_amount(True),
                date=False, document_date=False,
                do_hard_post=True,
                tag="C1_09"
            )
            
            self.simulation_correction_wizard(db, ji_id,
                    cor_date=False,
                    new_account_code=new_account,
                    new_ad_breakdown_data=False,
                    ad_replace_data=False
            )
            
            self.check_ji_correction(db, ji_id,
                account, new_account_code=new_account,
                expected_ad=False,
                expected_ad_rev=False,
                expected_ad_cor=False,
            )
            
    def test_cor1_10(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_10
        """
        db = self.c1
        self._register_set(db)
        
        reg_id = self._register_get(db, browse=False)
        if reg_id:
            account = '13300'
            new_account = '61000'
            
            regl_id, distrib_id, ji_id = self.register_create_line(
                db, reg_id,
                account, self.get_random_amount(True),
                date=False, document_date=False,
                do_hard_post=True,
                tag="C1_10"
            )
 
            ad=[
                (30., 'OPS', 'HT101', 'PF'),
                (30., 'OPS', 'HT101', 'FP1'),
                (40., 'OPS', 'HT120', 'FP1'),
            ]
            self.analytic_distribution_set_fp_account_dest(db, 'FP1',
                new_account, 'OPS')
            
            self.simulation_correction_wizard(db, ji_id,
                    cor_date=False,
                    new_account_code=new_account,
                    new_ad_breakdown_data=ad,
                    ad_replace_data=False
            )
            
            self.check_ji_correction(db, ji_id,
                account, new_account_code=new_account,
                expected_ad=False,
                expected_ad_rev=False,
                expected_ad_cor=ad,
            )
            
    def test_cor1_11(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_11
        """
        db = self.c1
        
        aal_obj = db.get('account.analytic.line')
        
        ad=[
            (40., 'NAT', 'HT101', 'PF'),
            (60., 'NAT', 'HT120', 'FP1'),
        ]
        
        new_ad=[
            (40., 'NAT', 'HT101', 'PF'),
            (60., 'NAT', 'HT120', 'PF'),
        ]
        
        invoice_lines_accounts = [ '66002', '66003', '66004', ]
        for a in invoice_lines_accounts:
            self.analytic_distribution_set_fp_account_dest(db, 'FP1', a, 'NAT')
                
        ji_ids = self.invoice_validate(db,
            self.invoice_create_supplier_invoice(
                db, ccy_code=False, date=False, partner_id=False,
                ad_header_breakdown_data=ad,
                lines_accounts=invoice_lines_accounts,
                tag="C1_11"
            )
        )
            
        # close financing contract FC1: soft-close it
        fcc_obj = db.get('financing.contract.contract')
        fc_id = self.get_id_from_key(db, 'financing.contract.contract', 'FC1',
            assert_if_no_ids=True)
        fcc_obj.contract_soft_closed([fc_id])
        
        # select an AJI booked on FP1, correction wizard
        fp1_id = self.get_account_from_code(db, 'FP1', is_analytic=True)
        aji_ids = aal_obj.search([
            ('move_id', 'in', ji_ids),
            ('account_id', '=', fp1_id),
        ])
        aji_br = aal_obj.browse(aji_ids[0])
        ji_id = aji_br.move_id.id
        ji_account_code = aji_br.move_id.account_id.code
        
        # replace FP1 to PF => system deny as FC1 soft-closed:
        # RPCError: warning -- Error
        # Funding pool is on a soft/hard closed contract: FP1
        expected_except = 'Funding pool is on a soft/hard closed contract: FP1'
        e = False
        try:
            self.simulation_correction_wizard(db, ji_id,
                        cor_date=False,
                        new_account_code=False,
                        ad_replace_data={ 60.: {'fp': 'PF', } }
                )
        except Exception, e:
            if e and e.message and expected_except not in e.message:
                # reopen contract and let others exceptions occur
                fcc_obj.contract_open([fc_id])
                raise e
        self.assert_(
                # we want the given except to be raised
                e and e.message and expected_except in e.message,  
                "You should not correct FP1 to PF as FC1 contract soft closed" \
                    " :: %s" % (db.colored_name, )
            )
        
        # repoen FC1
        # select an AJI booked on FP1, correction wizard, change FP1 to PF,
        # AJI should be directly update (no cor rev) as AD replaced not deleted
        # AND should pass as financing contract reopened
        fcc_obj.contract_open([fc_id])
        self.simulation_correction_wizard(db, ji_id,
                    cor_date=False,
                    new_account_code=False,
                    ad_replace_data={ 60.: {'fp': 'PF', } }
            )
            
        self.check_ji_correction(db, ji_id,
                ji_account_code, new_account_code=False,
                expected_ad=new_ad,
                expected_ad_rev=False,
                expected_ad_cor=False,
            )
        
    def test_cor1_12(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_12
        """
        db = self.c1
        
        invoice_lines_accounts = [ '60010', '60020', '60030', ]
        
        ad = [
            (60., 'OPS', 'HT101', 'PF'),
            (40., 'OPS', 'HT120', 'PF'),
        ]
        
        ji_ids = self.invoice_validate(db,
            self.invoice_create_supplier_invoice(db,
                ccy_code='USD',
                date=self.get_orm_fy_date(1, 8),
                partner_id=False,
                ad_header_breakdown_data=ad,
                lines_accounts=invoice_lines_accounts,
                tag="C1_12"
            )
        )
        
        # CLOSE PERIOD Januar (MISSION)
        self.period_close(db, 'f', 1)
        self.period_close(db, 'm', 1)
        
        new_ad = [
            (70., 'OPS', 'HT101', 'PF'),
            (30., 'OPS', 'HT120', 'PF'),
        ]
        
        # simu of cor for each invoice JIs
        for ji_br in db.get('account.move.line').browse(ji_ids):
            self.simulation_correction_wizard(db, ji_br.id,
                cor_date=self.get_orm_fy_date(2, 7),
                new_account_code=False,
                new_ad_breakdown_data=new_ad,
                ad_replace_data=False
            )
                
            self.check_ji_correction(db, ji_br.id,
                ji_br.account_id.code, new_account_code=False,
                expected_ad=ad,
                expected_ad_rev=ad,
                expected_ad_cor=new_ad,
            )
            
        # 1st invoice line change account to 60000 for 10th Feb
        # should be deny as already analytically corrected
        ji_br = db.get('account.move.line').browse(ji_ids[0])
        self.assert_(
            ji_br.last_cor_was_only_analytic == True,
            "JI %s %s %f should not be g/l account corrected as already" \
                " analytically corrected " % (ji_br.account_id.code,
                ji_br.name, ji_br.debit_currency, )
        )
        
        # REOPEN period for over cases flows
        self.period_reopen(db, 'm', 1)
        self.period_reopen(db, 'f', 1)
        
    def test_cor1_13(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_13
        """
        db = self.c1
        
        invoice_lines_accounts = [ '60010', '60020', ]
        
        ad = [
            (55., 'OPS', 'HT101', 'PF'),
            (45., 'OPS', 'HT120', 'PF'),
        ]
        
        aml_obj = db.get('account.move.line')
        
        ji_ids = self.invoice_validate(db,
            self.invoice_create_supplier_invoice(db,
                ccy_code=False,
                date=False,
                partner_id=False,
                ad_header_breakdown_data=ad,
                lines_accounts=invoice_lines_accounts,
                tag="C1_13"
            )
        )
 
        # 13.4 account/ad correction of 1st invoice line
        new_account = '60000'
        new_ad = [ (100., 'OPS', 'HT120', 'PF'), ]
        ji_br = db.get('account.move.line').browse(ji_ids[0])
        
        self.simulation_correction_wizard(db, ji_ids[0],
            cor_date=False,
            new_account_code=new_account,
            new_ad_breakdown_data=new_ad,
            ad_replace_data=False
        )
                
        self.check_ji_correction(db, ji_ids[0],
            ji_br.account_id.code, new_account_code=new_account,
            expected_ad=ad,
            expected_ad_rev=ad,
            expected_ad_cor=new_ad,
        )
   
        # 13.6/7: correction of COR-1 => will generate COR-2
        cor1_ids = aml_obj.search([('corrected_line_id', '=', ji_ids[0])])
        self.assert_(cor1_ids != False, 'COR-1 JI not found!')
        
        new_account2 = '60030'
        new_ad2 = [ (100., 'OPS', 'HT120', 'FP1'), ]
        self.analytic_distribution_set_fp_account_dest(db, 'FP1', new_account2,
            'OPS')
        
        self.simulation_correction_wizard(db, cor1_ids[0],
            cor_date=False,
            new_account_code=new_account2,
            new_ad_breakdown_data=new_ad2,
            ad_replace_data=False
        )
        
        self.check_ji_correction(db, cor1_ids[0],
            new_account, new_account2,
            expected_ad=new_ad,  
            expected_ad_rev=new_ad,  
            expected_ad_cor=new_ad2,
            cor_level=2, ji_origin_id=ji_ids[0]
        )
            
        # 13.8/9:
        # correction of the correction of correction
        # correction of COR-2 => will generate COR-3
        cor2_ids = aml_obj.search([('corrected_line_id', '=', cor1_ids[0])])
        self.assert_(cor2_ids != False, 'COR-2 JI not found!')

        new_account3 = '60100'
        new_ad3 = [
            (70., 'OPS', 'HT120', 'FP2'),
            (30., 'OPS', 'HT101', 'FP2'),
        ]
        self.analytic_distribution_set_fp_account_dest(db, 'FP1', new_account3,
            'OPS')
        self.analytic_distribution_set_fp_account_dest(db, 'FP2', new_account3,
            'OPS')
 
        self.simulation_correction_wizard(db, cor2_ids[0],
            cor_date=False,
            new_account_code=new_account3,
            new_ad_breakdown_data=new_ad3,
            ad_replace_data=False
        )
            
        self.check_ji_correction(db, cor2_ids[0],
            new_account2, new_account_code=new_account3,
            expected_ad=new_ad2,
            expected_ad_rev=new_ad2,
            expected_ad_cor=new_ad3,
            cor_level=3, ji_origin_id=ji_ids[0]
        )
        
    def test_cor1_14(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_14
        """
        db = self.c1
        
        self._register_set(db)
        
        reg_id = self._register_get(db, browse=False)
        if reg_id:       
            regl_id, distrib_id, ji_id = self.register_create_line(
                db, reg_id,
                '60000', self.get_random_amount(),
                ad_breakdown_data=[ (100., 'OPS', 'HT101', 'PF'), ]  ,
                date=False, document_date=False,
                do_temp_post=True, do_hard_post=False,
                tag="C1_14"
            )
            
            # 14.4 correction wizard should not be available
            aml_obj = db.get('account.move.line')
            ji_br = aml_obj.browse(ji_id)
            self.assert_(
                ji_br.is_corrigible  == False,
                "Expense JI of the reg line should not be corrigible as ' \
                    'temp posted. %s %s %f:: %s" % (
                    ji_br.account_id.code, ji_br.name, ji_br.amount_currency,
                    db.colored_name, )
            )

            # hard post to allow future period closing for over test flows
            self.register_line_hard_post(db, regl_id)
            # => so now the cor wizard will be visible at this stage
            
   
    # -------------------------------------------------------------------------
    # SYNC CASES FLOW: from 20 to 26
    # -------------------------------------------------------------------------
 
    def test_cor1_20(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_21
        """
        
        """
account.analytic.line
SD ref : 	9dead17a-44cd-11e5-9243-00259054f102/account_analytic_line/9
Is deleted? : 		Force record recreation : 		Version : 	2
	
Synchronization
Fetched on : 	19/Aug/2015 16:12
Source Instance : 	test-finance2_HQ1C1
Sequence : 	33
Owner Instance : 	test-finance2_HQ1C1P1
Handle Priority : 		Run : 		Last execution : 	19/Aug/2015 16:12
Fields

['last_corrected_id/id', 'cost_center_id/id', 'reversal_origin/id', 'id']
	
Values

[False, u'sd.47883ce2-44cc-11e5-ab8b-00259054f102/account_analytic_account/37', False, u'sd.9dead17a-44cd-11e5-9243-00259054f102/account_analytic_line/9']
	
Fallback Values

Execution Messages

Cannot import in model account.analytic.line:
Data: {'cost_center_id/id': u'sd.47883ce2-44cc-11e5-ab8b-00259054f102/account_analytic_account/37', 'last_corrected_id/id': False, 'id': u'sd.9dead17a-44cd-11e5-9243-00259054f102/account_analytic_line/9', 'reversal_origin/id': False}
Reason: null value in column "name" violates not-null constraint
        """
        
        """
Model : 	account.analytic.line
SD ref : 	9dead17a-44cd-11e5-9243-00259054f102/account_analytic_line/9
Is deleted? : 		Force record recreation : 		Version : 	2
	
Synchronization
Fetched on : 	19/Aug/2015 16:12
Source Instance : 	test-finance2_HQ1C1
Sequence : 	33
Owner Instance : 	test-finance2_HQ1C1P1
Handle Priority : 		Run : 		Last execution : 	19/Aug/2015 16:12
Fields

['account_id/id', 'amount', 'amount_currency', 'correction_date', 'code', 'cost_center_id/id', 'currency_id/id', 'date', 'destination_id/id', 'distrib_line_id', 'distribution_id/id', 'document_date', 'general_account_id/id', 'instance_id/id', 'is_reallocated', 'is_reversal', 'journal_id/id', 'move_id/id', 'name', 'partner_txt', 'ref', 'reversal_origin/id', 'source_date', 'entry_sequence', 'id']
	
Values

[u'sd.analytic_distribution_analytic_account_msf_private_funds', u'75.0', u'75.0', False, False, u'sd.47883ce2-44cc-11e5-ab8b-00259054f102/account_analytic_account/37', u'sd.base_EUR', u'2015-08-19', u'sd.analytic_distribution_analytic_account_destination_operation', u"(u'sd', 'funding.pool.distribution.line', u'9dead17a-44cd-11e5-9243-00259054f102/funding_pool_distribution_line/8')", u'sd.9dead17a-44cd-11e5-9243-00259054f102/analytic_distribution/7', u'2015-08-19', u'sd.msf_sync_data_hq_account_63120', u'sd.47883ce2-44cc-11e5-ab8b-00259054f102/msf_instance/2', 'False', 'False', u'sd.9dead17a-44cd-11e5-9243-00259054f102/account_analytic_journal/19', u'sd.9dead17a-44cd-11e5-9243-00259054f102/account_move_line/3', u'[C1_20] 1/L003 63120', u'Local Market', u'false', False, u'2015-08-19', u'C11-PUF-150001', u'sd.9dead17a-44cd-11e5-9243-00259054f102/account_analytic_line/9']
	
Fallback Values

Execution Messages

Cannot import in model account.analytic.line:
Data: {'general_account_id/id': u'sd.msf_sync_data_hq_account_63120', 'code': False, 'cost_center_id/id': u'sd.47883ce2-44cc-11e5-ab8b-00259054f102/account_analytic_account/37', 'id': u'sd.9dead17a-44cd-11e5-9243-00259054f102/account_analytic_line/9', 'document_date': u'2015-08-19', 'partner_txt': u'Local Market', 'is_reallocated': 'False', 'is_reversal': 'False', 'instance_id/id': u'sd.47883ce2-44cc-11e5-ab8b-00259054f102/msf_instance/2', 'distribution_id/id': u'sd.9dead17a-44cd-11e5-9243-00259054f102/analytic_distribution/7', 'source_date': u'2015-08-19', 'distrib_line_id': u"(u'sd', 'funding.pool.distribution.line', u'9dead17a-44cd-11e5-9243-00259054f102/funding_pool_distribution_line/8')", 'ref': u'false', 'move_id/id': False, 'currency_id/id': u'sd.base_EUR', 'correction_date': False, 'date': u'2015-08-19', 'journal_id/id': u'sd.9dead17a-44cd-11e5-9243-00259054f102/account_analytic_journal/19', 'destination_id/id': u'sd.analytic_distribution_analytic_account_destination_operation', 'account_id/id': u'sd.analytic_distribution_analytic_account_msf_private_funds', 'name': u'[C1_20] 1/L003 63120', 'reversal_origin/id': False, 'amount': u'75.0', 'amount_currency': u'75.0', 'entry_sequence': u'C11-PUF-150001'}
Reason: 'unicode' object has no attribute 'year'
        """
        
        """
test-finance_HQ1C1=# select * from analytic_distribution where id=7;
id | create_uid |        create_date         | write_date | write_uid | amount | user_id |         name         | unit_amount |    date    | company_id | account_id | is_reallocated | destination_id | document_date | from_write_off | cost_center_id | is_reversal | distribution_id | reversal_origin | source_date |         distrib_line_id          | exported | code | general_account_id | currency_id | move_id | product_uom_id | journal_id | product_id | amount_currency |  ref  | imported_commitment | imported_entry_sequence | commitment_line_id | entry_sequence | imported_partner_txt | partner_txt  | instance_id | last_corrected_id | correction_date 
----+------------+----------------------------+------------+-----------+--------+---------+----------------------+-------------+------------+------------+------------+----------------+----------------+---------------+----------------+----------------+-------------+-----------------+-----------------+-------------+----------------------------------+----------+------+--------------------+-------------+---------+----------------+------------+------------+-----------------+-------+---------------------+-------------------------+--------------------+----------------+----------------------+--------------+-------------+-------------------+-----------------
  9 |          1 | 2015-08-19 16:28:49.031532 |            |           | 513.00 |       1 | [C1_20] 1/L003 63120 |             | 2015-08-19 |          1 |          6 | f              |              8 | 2015-08-19    | f              |             20 | f           |               7 |                 | 2015-08-19  | funding.pool.distribution.line,8 | f        |      |                197 |           1 |       3 |                |         19 |            |          513.00 | false | f                   |                         |                    | C11-PUF-150001 |                      | Local Market |           2 |                   | 
(1 row)

test-finance_HQ1C1=# select id, name, distribution_id, distrib_line_id from account_analytic_line where id=9;
id |         name         | distribution_id |         distrib_line_id          
----+----------------------+-----------------+----------------------------------
  9 | [C1_20] 1/L003 63120 |               7 | funding.pool.distribution.line,8
(1 row)

test-finance_HQ1C1=# select * from funding_pool_distribution_line where id=8;                     
id | create_uid |        create_date         | write_date | write_uid | currency_id |                  name                   | partner_type | cost_center_id | analytic_id | distribution_id | amount | source_date | destination_id |    date    | percentage 
----+------------+----------------------------+------------+-----------+-------------+-----------------------------------------+--------------+----------------+-------------+-----------------+--------+-------------+----------------+------------+------------
  8 |          1 | 2015-08-19 16:28:49.031532 |            |           |           1 | AD 0453b217-eec6-42c2-9a96-98773bc62e25 |              |             20 |           6 |               7 |   0.00 | 2015-08-19  |              8 | 2015-08-19 |      100.0
(1 row) 
        """
        
        invoice_lines_accounts = [ '63100', '63110', '63120', ]
        
        invoice_lines_breakdown_data = {
            1: [(100., 'OPS', 'HT101', 'FP1'), ],
            2: [(100., 'OPS', 'HT120', 'FP2'), ],
            3: [(100., 'OPS', 'HT112', 'PF'), ],
        }
        for db in (self.c1, self.p1, self.p12, ):
            self.analytic_distribution_set_fp_account_dest(db, 'FP1', '63100',
                'OPS')
            self.analytic_distribution_set_fp_account_dest(db, 'FP2', '63110',
                'OPS')
        
        # at C1
        db = self.c1
        aml_obj = db.get('account.move.line')
        ji_ids = self.invoice_validate(db,
            self.invoice_create_supplier_invoice(db,
                ccy_code=False,
                is_refund=True,
                date=False,
                partner_id=False,
                ad_header_breakdown_data=False,
                lines_accounts=invoice_lines_accounts,
                lines_breakdown_data=invoice_lines_breakdown_data,
                tag="C1_20"
            )
        )
        self.synchronize(db)
        
        # at C1P1
        db = self.p1
        self.synchronize(db)


def get_test_class():
    return FinanceTestCorCases
