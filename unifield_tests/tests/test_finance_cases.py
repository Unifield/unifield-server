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
    
        'functional_ccy': 'EUR',
    
        'rates': { # from Januar
            'USD': [ 1.24, 1.28, ],  
        },
    
        # FPs corresponding CCs
        'fp_ccs': {
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
        for i in self._data_set['instances']:
            db = self.get_db_from_name(self.get_db_name_from_suffix(i))
            print(db.db_name)
    

def get_test_class():
    return FinanceTestCases
