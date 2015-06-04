#!/usr/bin/env python
# -*- coding: utf8 -*-
from __future__ import print_function
from unifield_test import UnifieldTestException
from unifield_test import UnifieldTest
from finance import FinanceTestException
from finance import FinanceTest

import time
from datetime import datetime

# set it to True to simulate a sync P1 sync down failure for any test
#TEST_THE_TEST = True
TEST_THE_TEST = False


class FinanceTestCorCasesException(UnifieldTestException):
    pass


class FinanceTestCorCases(FinanceTest):
    _data_set = {
        'instances': [ 'HQ1', 'HQ1C1',  'HQ1C1P1', ],
        
        'ccs': [ 'HT112', 'HT120', 'HT122', 'HT220', ],
    
        # TODO EUR expected
        #'functional_ccy': 'EUR',
        'functional_ccy': 'CHF',
    
        'rates': { # from Januar
            'USD': [ 1.24, 1.28, ],  
        },
    
        # C1 FPs and relating CCs
        'C1_fp_ccs': {
            'FP1': [ 'HT101', 'HT120', ],
            'FP2': [ 'HT101', ],
        },
        
        'donor': 'DONOR',
    
        'financing_contrats': {
            'FC1': { 'ccs' : [ 'HT101', 'HT120', ], 'fps': [ 'FP1', 'FP2', ], },
        },
        
        'register': 'BNK',
    }  # end of dataset
    
    def setUp(self):
        pass

    def tearDown(self):
        pass
        
    def _setup(self):
        self._set_dataset()
        pass
        
    def _set_start_register(self, db, period_id=1, ccy_name=False):
        db = self.c1
        aj_obj = db.get('account.journal')
        abs_obj = db.get('account.bank.statement')
        
        if not ccy_name:
            ccy_name = self._data_set.get('functional_ccy', 'EUR')
        
        # set Januar bank journal/register and open it
        journal_code = self._data_set['register']
        if ccy:
            journal_code += ' ' + ccy_name
        if not self.record_exists(db, 'account.journal',
            [('code', '=', journal_code)]):
            reg_id, journal_id = self.create_register(db, journal_code,
                journal_code, 'bank', '10200', ccy_name)
            # update period
            abs_obj.write([reg_id], {'period_id': period_id})
            abs_obj.button_open_bank([reg_id])
                
    def _get_register(self, db, browse=False):
        """
        :param browse: to return browsed object instead of id
        """
        abs_obj = db.get('account.bank.statement')
        ids = abs_obj.search([('name', '=', self._data_set['register'])])
        if not ids:
            raise FinanceTestCorCasesException('register %s not found' % (
                 self._data_set['register'], ))
        if browse:
            return abs_obj.browse([ids[0]])[0]
        else:
            return ids[0]
    
    def _set_dataset(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCases.test_cor_dataset
        correction test cases dataset
        """
        def set_default_currency_rates(db):
            for ccy_name in self._data_set['rates']:
                ccy_ids = db.get('res.currency').search([
                    ('name', '=', ccy_name),
                    ('active', 'in', ('t', 'f')),
                ])
                if ccy_ids:
                    index = 1
                    for r in self._data_set['rates'][ccy_name]:
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
            propagate = False
            parent_cc_ids = {}
            
            for cc in self._data_set['ccs']:
                if self.record_exists(db, model, 
                    [('code', '=', cc), ('category', '=', 'OC')]):
                    continue
                
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
                    db.get(model).create(vals)
                    propagate = True
                else:
                    raise FinanceTestCorCasesException(
                        "parent cost center not found '%s'" % (parent_code,))
                        
            if propagate:
                # sync down to C1, C1P1, C1P2, C2 (C2P2 do not need any new CC)
                self.synchronize(self.hq1)
                self.synchronize(self.c1)
                self.synchronize(self.c1)
                self.synchronize(self.p1)
                #self.synchronize(self.p12)
                #self.synchronize(self.c2)
                        
        def set_funding_pool():
            db = self.hq1
            company = self.get_company(db)
            model = 'account.analytic.account'
            propagate = False
            
            parent_ids = db.get(model).search([
                ('code', '=', 'FUNDING'),
                ('type', '=', 'view')
            ])
            if not parent_ids:
                raise FinanceTestCorCasesException(
                    'parent funding pool not found')
            
            for fp in self._data_set['C1_fp_ccs']:
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
                if not self.record_exists(db, model, 
                        self.dfv(vals, include=('code', 'instance_id', ))):
                    # get related CCs and set them
                    cc_ids = db.get(model).search([
                        ('category', '=', 'OC'),
                        ('code', 'in', self._data_set['C1_fp_ccs'][fp]),
                    ])
                    if cc_ids:
                        vals['cost_center_ids'] = [(6, 0, cc_ids)]
                    db.get(model).create(vals)
                    propagate = True
                    
            if propagate:
                self.synchronize(self.hq1)
                self.synchronize(self.c1)
                self.synchronize(self.c1)
                self.synchronize(self.p1)
                
        def set_financing_contract():
            db = self.hq1
            company = self.get_company(db)
            model = 'financing.contract.contract'
            model_fcd = 'financing.contract.donor'
            model_fcfpl = 'financing.contract.funding.pool.line'
            model_aaa = 'account.analytic.account'
            propagate = False
            
            # set donor
            vals = {
                'code': self._data_set['donor'],
                'name': self._data_set['donor'],
                'reporting_currency': company.currency_id.id,
            }
            donor_ids = db.get(model_fcd).search(
                self.dfv(vals, include=('code', )))
            if not donor_ids:
                donor_ids = [db.get(model_fcd).create(vals), ]
            
            for fc in self._data_set['financing_contrats']:
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
                    # set CCS
                    cc_codes = self._data_set['financing_contrats'][fc].get(
                        'ccs', False)
                    if cc_codes:
                        cc_ids = db.get(model_aaa).search([
                            ('category', '=', 'OC'),
                            ('code', 'in', cc_codes),
                        ])
                        if cc_ids:
                            vals['cost_center_ids'] = [(6, 0, cc_ids)]
                    
                    contract_id = db.get(model).create(vals)
                    
                    # set FPs
                    # TODO
                    """
                    fp_codes = self._data_set['financing_contrats'][fc].get(
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
                                }
                                db.get(model_fcfpl).create(vals)
                    """
                    
                    propagate = True
                    
            if propagate:
                # sync down
                self.synchronize(self.hq1)
                self.synchronize(self.c1)
                self.synchronize(self.c1)
                self.synchronize(self.p1)
                #self.synchronize(self.p12)
                    
        # ---------------------------------------------------------------------
        year = datetime.now().year
        date_fy_start = self.get_orm_date_fy_start()
        date_fy_stop = self.get_orm_date_fy_stop()
        date_now = self.get_orm_date_now()
        
        for i in self._data_set['instances']:
            # check instance dataset
            db = self.get_db_from_name(self.get_db_name_from_suffix(i))
            
            company = self.get_company(db)
            
            # check functional currency
            self.assertEqual(
                company.currency_id.name, self._data_set['functional_ccy'],
                "Functional %s currency expected :: %s" % (
                    self._data_set['functional_ccy'], db.colored_name, )
            )
                
            # set default rates
            set_default_currency_rates(db)
            
        # HQ level: set financing contract + sync down
        set_cost_centers()
            
        # HQ level: set funding pool + sync up/down
        set_funding_pool()
        
        # HQ level: set financing contract + sync down
        set_financing_contract()
        
    def test_cor1_1(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_1
        """
        self._setup()
        
        db = self.c1
        self._set_start_register(db)
        
        reg_id = self._get_register(db, browse=False)
        if reg_id:
            regl_id, distrib_id, ji_id = self.create_register_line(
                db, reg_id,
                '60010', self.get_random_amount(True),
                ad_breakdown_data=[(100., 'OPS', 'HT101', 'PF'), ],
                date=False, document_date=False,
                do_hard_post=True
            )
            
            # 60010 -> 60020
            self.simulation_correction_wizard(db, ji_id,
                    new_account_code='60020',
                    new_ad_breakdown_data=False,
                    ad_replace_data=False,
            )
            
            ad = [(100., 'OPS', 'HT101', 'PF'), ]
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
        self._setup()
        
        db = self.c1
        self._set_start_register(db)
        
        reg_id = self._get_register(db, browse=False)
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
        self._setup()
        
        db = self.c1
        self._set_start_register(db)
        
        reg_id = self._get_register(db, browse=False)
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
        self._setup()
        
        db = self.c1
        self._set_start_register(db)
        
        reg_id = self._get_register(db, browse=False)
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
        self._setup()
        
        db = self.c1
        self._set_start_register(db)
        
        reg_id = self._get_register(db, browse=False)
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
                expected_ad=ad,
                expected_ad_rev=ad,
                expected_ad_cor=new_ad,
            )
            
    def test_cor1_6(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_6
        """
        self._setup()
        
        db = self.c1
        self._set_start_register(db, ccy_name='USD')
        
        reg_id = self._get_register(db, browse=False, ccy_name='USD')
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
            
            # CLOSE PERIOD Januar (MISSIONp
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
                expected_ad=ad,
                expected_ad_rev=new_ad,
                expected_ad_cor=new_ad,
            )
            
    def test_cor1_7(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_7
        """
        self._setup()
        
        db = self.c1
        self._set_start_register(db, ccy_name='USD')
        
        reg_id = self._get_register(db, browse=False, ccy_name='USD')
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
            self.period_close_reopen(db, 'm', 1, reopen=True)
            
            new_ad=[
                (70., 'OPS', 'HT101', 'PF'),
                (30., 'OPS', 'HT101', 'PF'),
            ]
            self.simulation_correction_wizard(db, ji_id,
                    cor_date=get_orm_fy_date(2, 7),  # 7 Feb of this year
                    new_account_code='60000',
                    new_ad_breakdown_data=new_ad,
                    ad_replace_data=False
            )
            
            self.check_ji_correction(db, ji_id,
                '60010', new_account_code='60000',
                expected_ad=ad,
                expected_ad_rev=new_ad,
                expected_ad_cor=new_ad,
            )
            
    def test_cor1_8(self):
        """
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor1_8
        """
        self._setup()
        
        db = self.c1
        self._set_start_register(db)
        
        reg_id = self._get_register(db, browse=False)
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
            
            # CLOSE PERIOD Januar (MISSION)
            self.period_close_reopen(db, 'm', 1, reopen=True)
 
            self.simulation_correction_wizard(db, ji_id,
                    new_account_code='13310',
                    new_ad_breakdown_data=new_ad,
                    ad_replace_data=False
            )
            
            self.check_ji_correction(db, ji_id,
                '60010', new_account_code='13310',
                expected_ad=ad,
                expected_ad_rev=ad,
                expected_ad_cor=ad,
            )

def get_test_class():
    return FinanceTestCorCases
