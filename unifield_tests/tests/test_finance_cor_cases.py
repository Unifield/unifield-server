#!/usr/bin/env python
# -*- coding: utf8 -*-
from __future__ import print_function
from unifield_test import UnifieldTestException
from unifield_test import UnifieldTest
from finance import FinanceTestException
from finance import FinanceTest

import time
from datetime import datetime

# TODO active again when dev/testing is finished
#DATASET = True
DATASET = False

#TEST_THE_TEST = True
TEST_THE_TEST = False

# when dbs are coming from a given RB, et the db prefix to retrieve
# prop instances correctly (not from local db names)
RBDB_PREFIX = 'cor-test'


class FinanceTestCorCasesException(UnifieldTestException):
    pass


class FinanceTestCorCases(FinanceTest):
    class DataSetMeta(object):
        instances = [ 'HQ1', 'HQ1C1',  'HQ1C1P1', ]
        #instances = [ 'HQ1', 'HQ1C1',  'HQ1C1P1', 'HQ1C1P2', 'HQ1C2',
        #   'HQ1C2P1',]
        
        functional_ccy = 'EUR'
    
        rates = { # from Januar
            'EUR': [ 1., 1., ],
            'CHF': [ 0.95476, 0.965, ],
            'USD': [ 1.24, 1.28, ],
        }
        
        # new COST CENTERS (and related target instances)
        ccs = {
            'HT112': [ 'HQ1C1P1', ],
            'HT120': [ 'HQ1C1', ],
            #'HT122': [ 'HQ1C1P2', ],  # TODO uncomment when instances activated
            #'HT220': [ 'HQ1C2', ],  # TODO uncomment when instances activated
        }
    
        # new FUNDING POOLS (and related cost centers)
        fp_ccs = {
            ('HQ1C1', 'FP1'): [ 'HT101', 'HT120', ],
            ('HQ1C1', 'FP2'): [ 'HT101', ],
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
        dataset_applied = DATASET and hasattr(self, 'dataset_applied') and \
            self.dataset_applied or False
        if not dataset_applied:
            self._set_dataset()

    def tearDown(self):
        pass
        
    # -------------------------------------------------------------------------
    # DATASET
    # -------------------------------------------------------------------------
    
    def _set_dataset(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCases.test_cor_dataset
        correction test cases dataset
        """
        def get_instance_ids_from_code(codes):
            if isinstance(codes, (str, unicode, )):
                codes = [codes]
                
            target_instance_codes = [
                self.get_db_name_from_suffix(c) for c in codes ]
            instance_ids = db.get('msf.instance').search(
                [('code', 'in', target_instance_codes)])
            if not instance_ids:
                # default dev instance (db/prop instances name from a RB)
                target_instance_codes = [
                    "%s_%s" % (RBDB_PREFIX, c, ) for c in codes ]
                instance_ids = db.get('msf.instance').search(
                        [('code', 'in', target_instance_codes)])
                if not instance_ids:
                    raise FinanceTestCorCasesException("instances not found")
            return instance_ids
        
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
            db = self.hq1
            company = self.get_company(db)
            model = 'account.analytic.account'
            parent_cc_ids = {}
            any_set = False
            
            for cc in meta.ccs:
                if self.record_exists(db, model, 
                    [('code', '=', cc), ('category', '=', 'OC')]):
                    continue
                any_set = True
                
                # get parent (parent code: 3 first caracters (HT1, HT2, ...))
                parent_code = cc[:3]  
                if not parent_code in parent_cc_ids:
                    parent_ids = db.get(model).search([
                        ('type', '=', 'view'),
                        ('category', '=', 'OC'),
                        ('code', '=', parent_code),
                    ])
                    parent_id = parent_ids and parent_ids[0] or False
                    parent_cc_ids[parent_code] = parent_id
                else:
                    parent_id = parent_cc_ids.get(parent_code, False)
                    
                if parent_id:
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
                    cc_id = db.get(model).create(vals)
                else:
                    raise FinanceTestCorCasesException(
                        "parent cost center not found '%s'" % (parent_code,))
                        
                # set target instance
                instance_ids = get_instance_ids_from_code(
                    [ti for ti in meta.ccs[cc]])
                atcc_obj = db.get('account.target.costcenter')
                for ins_id in instance_ids:
                    atcc_obj.create({
                        'instance_id': ins_id,
                        'cost_center_id': cc_id,
                        'is_target': True
                    })
 
            return any_set
                        
        def set_funding_pools():
            db = self.hq1
            aaa_model = 'account.analytic.account'
            aaa_obj = db.get(aaa_model)
            company = self.get_company(db)
            
            for instance, fp in meta.fp_ccs:
                db = self.get_db_from_name(
                    self.get_db_name_from_suffix(instance))
                aaa_model = 'account.analytic.account'
                aaa_obj = db.get(aaa_model)
                
                company = self.get_company(db)
                
                parent_ids = aaa_obj.search([
                    ('code', '=', 'FUNDING'),
                    ('type', '=', 'view')
                ])
                if not parent_ids:
                    raise FinanceTestCorCasesException(
                        'parent funding pool not found')
        
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
                if not self.record_exists(db, aaa_model, 
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
        
        year = datetime.now().year
        date_fy_start = self.get_orm_date_fy_start()
        date_fy_stop = self.get_orm_date_fy_stop()
        date_now = self.get_orm_date_now()
        
        for i in meta.instances:
            # check instance dataset
            db = self.get_db_from_name(self.get_db_name_from_suffix(i))
            company = self.get_company(db)
            
            if company.currency_id.name != meta.functional_ccy:
                raise FinanceTestCorCasesException(
                    "wrong functionnal ccy: '%s' expected" % (
                    meta.functional_ccy, ))
                    
            # activate currencies (if required)
            activate_currencies(db, [ccy_name for ccy_name in meta.rates])
                
        # set default rates: at HQ then sync down
        set_default_currency_rates(self.hq1)
        self._sync_down()
            
        # HQ level: set cost centers + sync down
        if set_cost_centers():
            self._sync_down()
            
        # set funding pool + sync up/down (from c1)
        set_funding_pools()
        self._sync_c1()
        
        # set financing contract + sync up/down (from c1)
        set_financing_contracts()
        self._sync_c1()
        
    # -------------------------------------------------------------------------
    # PRIVATE TOOLS FUNCTIONS (for flow)
    # -------------------------------------------------------------------------
        
    def _sync_down(self):
        self.synchronize(self.hq1)
        self.synchronize(self.c1)
        self.synchronize(self.c1)
        self.synchronize(self.p1)
        #self.synchronize(self.p12)
        
    def _sync_c1(self):
        self.synchronize(self.c1)
        self.synchronize(self.hq1)
        self.synchronize(self.p1)
        #self.synchronize(self.p12)
           
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
            reg_id, journal_id = self.create_register(db, journal_code,
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
        if not ids:
            raise FinanceTestCorCasesException('register %s not found' % (
                journal_code, ))
        if browse:
            return abs_obj.browse([ids[0]])[0]
        else:
            return ids[0]
            
    # -------------------------------------------------------------------------
    # FLOW
    # -------------------------------------------------------------------------
        
    def test_cor1_0(self):
        """
        for dataset testing
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_0
        """
        return
        
    def test_cor1_1(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_1
        """
        db = self.c1
        self._register_set(db)
        
        reg_id = self._register_get(db, browse=False)
        if reg_id:
            ad = [(100., 'OPS', 'HT101', 'PF'), ]
            
            regl_id, distrib_id, ji_id = self.create_register_line(
                db, reg_id,
                '60010', self.get_random_amount(True),
                ad_breakdown_data=ad,
                date=False, document_date=False,
                do_hard_post=True
            )
            
            # 60010 -> 60020
            self.simulation_correction_wizard(db, ji_id,
                    new_account_code='60020',
                    new_ad_breakdown_data=False,
                    ad_replace_data=False,
            )
            
            self.check_ji_correction(db, ji_id,
                '60010', new_account_code='60020',
                expected_ad=ad,
                expected_ad_rev=ad,
                expected_ad_cor=ad,
            )
            
    def test_cor1_2(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_2
        """
        db = self.c1
        self._register_set(db)
        
        reg_id = self._register_get(db, browse=False)
        if reg_id:
            regl_id, distrib_id, ji_id = self.create_register_line(
                db, reg_id,
                '60010', self.get_random_amount(True),
                ad_breakdown_data=[(100., 'OPS', 'HT101', 'PF'), ],
                date=False, document_date=False,
                do_hard_post=True
            )
            
            # correction dest from OPS to NAT
            self.simulation_correction_wizard(db, ji_id,
                    new_account_code=False,
                    new_ad_breakdown_data=False,
                    ad_replace_data={ 'dest': [('OPS', 'NAT')] },
            )
            
            self.check_ji_correction(db, ji_id,
                '60010', new_account_code=False,
                expected_ad=[(100., 'NAT', 'HT101', 'PF'), ],
                expected_ad_rev=False,
                expected_ad_cor=False,
            )
            
    def test_cor1_3(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_3
        """
        db = self.c1
        self._register_set(db)
        
        reg_id = self._register_get(db, browse=False)
        if reg_id:
            regl_id, distrib_id, ji_id = self.create_register_line(
                db, reg_id,
                '60010', self.get_random_amount(True),
                ad_breakdown_data=[(100., 'OPS', 'HT101', 'PF'), ],
                date=False, document_date=False,
                do_hard_post=True
            )
            
            # correction CC from HT101 to HT120
            self.simulation_correction_wizard(db, ji_id,
                    new_account_code=False,
                    new_ad_breakdown_data=False,
                    ad_replace_data={ 'cc': [('HT101', 'HT120')] },
            )
            
            ji_id = 1
            self.check_ji_correction(db, ji_id,
                '60010', new_account_code=False,
                expected_ad=[(100., 'OPS', 'HT120', 'PF'), ],
                expected_ad_rev=False,
                expected_ad_cor=False,
            )
            
    def test_cor1_4(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_4
        """
        db = self.c1
        self._register_set(db)
        
        reg_id = self._register_get(db, browse=False)
        if reg_id:
            regl_id, distrib_id, ji_id = self.create_register_line(
                db, reg_id,
                '60010', self.get_random_amount(True),
                ad_breakdown_data=[(100., 'OPS', 'HT101', 'PF'), ],
                date=False, document_date=False,
                do_hard_post=True
            )
            
            # correction FP from PF to FP1
            self.simulation_correction_wizard(db, ji_id,
                    new_account_code=False,
                    new_ad_breakdown_data=False,
                    ad_replace_data={ 'fp': [('PF', 'FP1')] },
            )
            
            ji_id = 1
            self.check_ji_correction(db, ji_id,
                '60010', new_account_code=False,
                expected_ad=[(100., 'OPS', 'HT101', 'FP1'), ],
                expected_ad_rev=False,
                expected_ad_cor=False,
            )
            
    def test_cor1_5(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_5
        """
        db = self.c1
        self._register_set(db)
        
        reg_id = self._register_get(db, browse=False)
        if reg_id:
            ad = [(100., 'OPS', 'HT101', 'PF'), ]
            
            regl_id, distrib_id, ji_id = self.create_register_line(
                db, reg_id,
                '60010', self.get_random_amount(True),
                ad_breakdown_data=ad,
                date=False, document_date=False,
                do_hard_post=True
            )
            
            # 60010 -> 60000
            # AD 100% OPS, HT101, PF -> 55% OPS, HT101, PF
            #                        -> 45% NAT, HT101, PF
            new_ad=[
                (55., 'OPS', 'HT101', 'PF'),
                (45., 'NAT', 'HT101', 'PF'),
            ]
            self.simulation_correction_wizard(db, ji_id,
                    new_account_code='60000',
                    new_ad_breakdown_data=new_ad,
                    ad_replace_data=False
            )
            
            self.check_ji_correction(db, ji_id,
                '60010', new_account_code='60000',
                expected_ad=new_ad,
                expected_ad_rev=ad,
                expected_ad_cor=new_ad,
            )
            
    def test_cor1_6(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_6
        """
        db = self.c1
        self._register_set(db, ccy_name='USD')
        
        reg_id = self._register_get(db, browse=False, ccy_name='USD')
        if reg_id:
            ad = [
                (60., 'OPS', 'HT101', 'PF'),
                (40., 'OPS', 'HT120', 'PF'),
            ]
            
            regl_id, distrib_id, ji_id = self.create_register_line(
                db, reg_id,
                '60010', 100,
                ad_breakdown_data=ad,
                date=False, document_date=False,
                do_hard_post=True
            )
            
            # CLOSE PERIOD Januar (MISSION)
            self.period_close_reopen(db, 'm', 1)
            
            new_ad=[
                (70., 'OPS', 'HT101', 'PF'),
                (30., 'OPS', 'HT101', 'PF'),
            ]
            self.simulation_correction_wizard(db, ji_id,
                    cor_date=get_orm_fy_date(2, 7),  # 7 Feb of this year
                    new_account_code=False,
                    new_ad_breakdown_data=False,
                    ad_replace_data={ 'per': [(60., 70.), (40., 30.), ] }
            )
            
            self.check_ji_correction(db, ji_id,
                '60010', new_account_code=False,
                expected_ad=new_ad,
                expected_ad_rev=ad,
                expected_ad_cor=ad,
            )
            
    def test_cor1_7(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_7
        """
        db = self.c1
        self._register_set(db, ccy_name='USD')
        
        reg_id = self._register_get(db, browse=False, ccy_name='USD')
        if reg_id:
            ad = [
                (60., 'OPS', 'HT101', 'PF'),
                (40., 'OPS', 'HT120', 'PF'),
            ]
            
            regl_id, distrib_id, ji_id = self.create_register_line(
                db, reg_id,
                '60010', 100,
                ad_breakdown_data=ad,
                date=False, document_date=False,
                do_hard_post=True
            )
            
            new_ad=[
                (70., 'OPS', 'HT101', 'PF'),
                (30., 'OPS', 'HT101', 'PF'),
            ]
            self.simulation_correction_wizard(db, ji_id,
                    cor_date=get_orm_fy_date(2, 7),  # 7 Feb of this year
                    new_account_code='60030',
                    new_ad_breakdown_data=new_ad,
                    ad_replace_data=False
            )
            
            self.check_ji_correction(db, ji_id,
                '60010', new_account_code='60030',
                expected_ad=new_ad,
                expected_ad_rev=ad,
                expected_ad_cor=ad,
            )
            
    def test_cor1_8(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_8
        """    
        db = self.c1
        self._register_set(db)
        
        reg_id = self._register_get(db, browse=False)
        if reg_id:
            ad = [
                (10., 'OPS', 'HT101', 'PF'),
                (90., 'OPS', 'HT101', 'FP1'),
            ]
            
            regl_id, distrib_id, ji_id = self.create_register_line(
                db, reg_id,
                '60010', self.get_random_amount(True),
                ad_breakdown_data=ad,
                date=False, document_date=False,
                do_hard_post=True
            )
 
            self.simulation_correction_wizard(db, ji_id,
                    cor_date=False,
                    new_account_code='13300',
                    new_ad_breakdown_data=False,
                    ad_replace_data=False
            )
            
            self.check_ji_correction(db, ji_id,
                '60010', new_account_code='13300',
                expected_ad=ad,
                expected_ad_rev=ad,
                expected_ad_cor=False,  # bc new account not an expense one
            )
            
    def test_cor1_9(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_9
        """
        db = self.c1
        self._register_set(db)
        
        reg_id = self._register_get(db, browse=False)
        if reg_id:
            regl_id, distrib_id, ji_id = self.create_register_line(
                db, reg_id,
                '13300', self.get_random_amount(True),
                date=False, document_date=False,
                do_hard_post=True
            )
            
            self.simulation_correction_wizard(db, ji_id,
                    cor_date=False,
                    new_account_code='13310',
                    new_ad_breakdown_data=False,
                    ad_replace_data=False
            )
            
            self.check_ji_correction(db, ji_id,
                '13300', new_account_code='13310',
                expected_ad=False,
                expected_ad_rev=False,
                expected_ad_cor=False,
            )
            
    def test_cor1_10(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_10
        """
        db = self.c1
        self._register_set(db)
        
        reg_id = self._register_get(db, browse=False)
        if reg_id:
            regl_id, distrib_id, ji_id = self.create_register_line(
                db, reg_id,
                '13300', self.get_random_amount(True),
                date=False, document_date=False,
                do_hard_post=True
            )
            
            # TODO
            # should deny unit test when no ad provided from not expense account
            # to expense one
            """self.simulation_correction_wizard(db, ji_id,
                    cor_date=False,
                    new_account_code='61000',
                    new_ad_breakdown_data=False
                    ad_replace_data=False
            )"""
 
            new_ad=[
                (30., 'OPS', 'HT101', 'PF'),
                (30., 'OPS', 'HT101', 'PF1'),
                (40., 'OPS', 'HT120', 'PF1'),
            ]
            self.simulation_correction_wizard(db, ji_id,
                    cor_date=False,
                    new_account_code='61000',
                    new_ad_breakdown_data=new_ad,
                    ad_replace_data=False
            )
            
            self.check_ji_correction(db, ji_id,
                '13300', new_account_code='61000',
                expected_ad=new_ad,
                expected_ad_rev=False,
                expected_ad_cor=False,
            )
            
    def test_cor1_11(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_11
        """
        # TODO: finish this use case
        db = self.c1
        
        self.validate_invoice(db, self.create_supplier_invoice(db,
            ccy_code=False, date=False, partner_id=False,
            ad_header_breakdown_data=[
                (50., 'NAT', 'HT101', 'PF'),
                (50., 'NAT', 'HT120', 'FP1'),
            ],
            lines_accounts=['60002', '60003', '60004', ],
        ))
            
        # TODO
        # close financing contract FC1 and soft-close it
        
        # select ALL boocked AJI of FP1, correction wizard: change FP1 to PF
        
        # repoen FC1
        
        # select ALL boocked AJI of FP1, correction wizard:
        # => change AD
        # - 50% NAT, HT101, PF
        # - 50% NAT, HT120, PF
        # => funding pool is modified by the AJI initially selected
        
    def test_cor1_12(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_12
        """
        db = self.c1
        
        ad = [
            (60., 'OPS', 'HT101', 'PF'),
            (40., 'OPS', 'HT120', 'PF'),
        ]
        
        ji_ids = self.validate_invoice(db, self.create_supplier_invoice(db,
            ccy_code='USD',
            date=self.get_orm_fy_date(1, 8),
            partner_id=False,
            ad_header_breakdown_data=ad,
            lines_accounts=['60010', '60020', '60030', ],
        ))
        
        # CLOSE PERIOD Januar (MISSION)
        self.period_close_reopen(db, 'm', 1)
        
        new_ad = [
            (70., 'OPS', 'HT101', 'PF'),
            (30., 'OPS', 'HT120', 'PF'),
        ],
        
        # simu of cor for each invoice JIs
        ji_records = db.get('account.move.line').read(ji_ids, ['account_id'])
        for ji_id in ji_ids:
            self.simulation_correction_wizard(db, ji_id,
                cor_date=self.get_orm_fy_date(2, 7),
                new_account_code=False,
                new_ad_breakdown_data=new_ad,
                    ad_replace_data=False
            )
                
            self.check_ji_correction(db, ji_id,
                ji_records[ji_id]['account_id'], new_account_code=False,
                expected_ad=new_ad,
                expected_ad_rev=ad,
                expected_ad_cor=new_ad,
            )
            
        # TODO
        # 1s invoice line correction date self.get_orm_fy_date(2, 10)
        # change account (to 60000) account field should be grayed 
        # (entry has been analytically already corrected)
        """
        self.simulation_correction_wizard(db, ji_records[0],
            cor_date=self.get_orm_fy_date(2, 10),
            new_account_code='60000',
            new_ad_breakdown_data=False,
            ad_replace_data=False
        )"""
        
    def test_cor1_13(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_13
        """
        db = self.c1
        aml_obj = db.get('account.move.line')
        
        ad = [
            (55., 'OPS', 'HT101', 'PF'),
            (45., 'OPS', 'HT120', 'PF'),
        ]
        
        ji_ids = self.validate_invoice(db, self.create_supplier_invoice(db,
            ccy_code=False,
            date=False,
            partner_id=False,
            ad_header_breakdown_data=ad,
            lines_accounts=['60010', '60020', ]
        ))
 
        # cor of the 1fst invoice line

        new_ad = [ (100., 'OPS', 'HT120', 'PF'), ]
        
        # simu of cor if 1st invoice line
        ji_ids = [ji_ids[0]]
        ji_records = db.get('account.move.line').read(ji_ids, ['account_id'])
        for ji_id in ji_ids:
            self.simulation_correction_wizard(db, ji_id,
                cor_date=False,
                new_account_code='60000',
                new_ad_breakdown_data=new_ad,
                ad_replace_data=False
            )
                
            self.check_ji_correction(db, ji_id,
                ji_records[ji_id]['account_id'], new_account_code='60000',
                expected_ad=new_ad,
                expected_ad_rev=ad,
                expected_ad_cor=new_ad,
            )
            
        # 13.7: cor the cor
        # get the COR JI of the corrected JI
        cor_ids = aml_obj.search([('corrected_line_id', '=', ji_ids[0])])
        if not cor_ids:
            raise FinanceTestCorCasesException('COR1 JI not found!')
        
        # simu cor of the cor and check
        new_ad2 = [ (100., 'OPS', 'HT120', 'FP1'), ]
        self.simulation_correction_wizard(db, cor_ids[0],
            cor_date=False,
            new_account_code='60030',
            new_ad_breakdown_data=new_ad2,
            ad_replace_data=False
        )
            
        self.check_ji_correction(db, cor_ids[0],
            '60000', new_account_code='60030',
            expected_ad=new_ad2,
            expected_ad_rev=new_ad,
            expected_ad_cor=new_ad2
        )
            
        # 13.8: cor the cor of cor
        # get the cor of cor
        cor_ids = aml_obj.search([('corrected_line_id', '=', cor_ids[0])])
        if not cor_ids:
            raise FinanceTestCorCasesException('COR2 JI not found!')
        
        # simu cor the cor of cor and check
        new_ad3 = [
            (70., 'OPS', 'HT120', 'FP2'),
            (30., 'OPS', 'HT101', 'FP2'),
        ]
        self.simulation_correction_wizard(db, cor_ids[0],
            cor_date=False,
            new_account_code='60050',
            new_ad_breakdown_data=new_ad3,
            ad_replace_data=False
        )
            
        self.check_ji_correction(db, cor_ids[0],
            '60030', new_account_code='60050',
            expected_ad=new_ad3,
            expected_ad_rev=new_ad2,
            expected_ad_cor=new_ad3
        )
        
    def test_cor1_14(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_13
        """
        db = self.c1
        
        self._register_set(db)
        
        reg_id = self._register_get(db, browse=False)
        if reg_id:       
            regl_id, distrib_id, ji_id = self.create_register_line(
                db, reg_id,
                '60000', self.get_random_amount(),
                ad_breakdown_data=[ (100., 'OPS', 'HT101', 'PF'), ]  ,
                date=False, document_date=False,
                do_hard_post=False
            )
            
            # temp post
            self.register_line_temp_post(db, [regl_id])
            
            # 14.4 correction wizard should not be available
            # TODO
        

def get_test_class():
    return FinanceTestCorCases
