#!/usr/bin/env python
# -*- coding: utf8 -*-
from __future__ import print_function
from unifield_test import UnifieldTestException
from unifield_test import UnifieldTest

import time
from datetime import datetime

# set it to True to simulate a sync P1 sync down failure for any test
#TEST_THE_TEST = True
TEST_THE_TEST = False


class FinanceTestCasesException(UnifieldTestException):
    pass


class FinanceTestCases(UnifieldTest):
    _data_set = {
        'instances': [ 'HQ1', 'HQ1C1',  'HQ1C1P1', ],
    
        # instances CCs and associated FPs
        'instance_ccs_fps_matrix': [
            [ 'HQ1', [], [ 'FP1', 'FP2', ], ],
            [ 'C1', [ 'HT101', 'HT120', ], [ 'FP1', 'FP2', ], ],
            [ 'C1P1', [ 'HT111', 'HT112', ], [ 'FP1', 'FP2', ], ],
            #[ 'C1P2', [ 'HT121', 'HT122', ], [ 'FP1', 'FP2', ], ],
            [ 'C2', [ 'HT201', 'HT220',], [], ],
            #[ 'C2P1', [ 'HT211', ], [], ],
        ],
    
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
    
        'financing_contrats': {
            'FC1': [ 'HT101', 'HT120', ],
        },
    }  # end of dataset
    
    def setUp(self):
        pass

    def tearDown(self):
        pass
    
    def test_dataset(self):
        """
        python -m unittest tests.test_finance_cases.FinanceTestCases.test_dataset
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
                        
        def set_funding_pool():
            # propagation from C1
            
            # create on C1
            db = self.c1
            company = self.get_company(db)
            model = 'account.analytic.account'
            
            parent_ids = db.get(model).search([
                ('code', '=', 'FUNDING'),
                ('type', '=', 'view')
            ])
            if not parent_ids:
                raise FinanceTestCasesException(
                    'parent funding pool not found')
            
            for fp in self._data_set['C1_fp_ccs']:
                vals = {
                    'code': fp,
                    'description': fp,
                    'currency_id': company.currency_id.id,
                    'name': fp,
                    'date_start': fy_start_date,
                    'parent_id': parent_ids[0],
                    'state': 'open',
                    'type': 'normal', 
                    'category': 'FUNDING',
                    'instance_id': company.instance_id.id,
                }
                if not self.record_exists(db, model, 
                        self.dfv(vals, include=('code', 'instance_id', ))):
                    db.get(model).create(vals)
                    
            # sync up
            self.synchronize(db)
            self.synchronize(self.h1)
            
            # sync down
            self.synchronize(self.p1)
            # TODO
            #self.synchronize(self.p12)
        
        year = datetime.now().year
        fy_start_date = "%04d-01-01" % (year, )
        
        for i in self._data_set['instances']:
            # check instance dataset
            db = self.get_db_from_name(self.get_db_name_from_suffix(i))
            print(db.db_name)
            
            company = self.get_company(db)
            
            # check functional currency
            self.assertEqual(
                company.currency_id.name, self._data_set['functional_ccy'],
                "Functional %s currency expected :: %s" % (
                    self._data_set['functional_ccy'], db.colored_name, )
            )
                
            # set default rates
            set_default_currency_rates(db)
            
        # C1 funding pool + sync up/down
        set_funding_pool()
        
        
        
    

def get_test_class():
    return FinanceTestCases
