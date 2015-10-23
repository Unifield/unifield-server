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


DEFAULT_DATE_PERIOD_ID = 1
DEFAULT_DATE_MONTH = 1


"""
TARGET CCs

CC          C1          C1P1        C1P2        C2      C2P1
HT101       X
HT120       X
HT111                   X
HT112                   X
HT121                               X
HT122                               X
HT201                                           X
HT220                                           X
HT211                                                   X
"""

"""
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
        X 20
        X 21
        X 22 (until 22.7 (22.8 > 22.10 are not real))
        X 23
        X 24
        X 25
        X 26

- TODO:
    - [IMP] check_ji_correction(): obtain expected AD with cor level > 1
"""


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

        # COST CENTERS BREAKDOWN related prop instances
        # SET HERE WHAT YOU EXCEPT FOR TREE
        # - only missing link will be created
        # - and is_target will be update for already existing link
        ccs = {
            # 'CC': [(Prop Instance, is_target), ]

            # C1 tree
            'HT101': [ ('HQ1C1', True), ],
            'HT120': [ ('HQ1C1', True), ],
            'HT111': [ ('HQ1C1', False), ('HQ1C1P1', True), ],
            'HT112': [ ('HQ1C1', False), ('HQ1C1P1', True), ],
            'HT121': [ ('HQ1C1', False), ('HQ1C1P2', True), ],
            'HT122': [ ('HQ1C1', False), ('HQ1C1P2', True), ],

            # C2 tree
            'HT201': [ ('HQ1C2', True), ],
            'HT220': [ ('HQ1C2', True), ],
            'HT211': [ ('HQ1C2', True), ('HQ1C2P1', True),],
        }

        # new FUNDING POOLS (and related cost centers)
        fp_ccs = {
            ('HQ1C1', 'FP1'): [ 'HT101', 'HT120', ],
            ('HQ1C1', 'FP2'): [ 'HT101', 'HT120', 'HT121', 'HT122', ],
         }

        # financing contracts
        financing_contracts_donor = 'DONOR'
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
                if not instance_ids:
                   # instance doesn't exist, create it
                   newcode = self.get_db_name_from_suffix(code)
                   return db.get('msf.instance').create({
                        'code': newcode,
                        'reconcile_prefix': newcode,
                        'move_prefix': newcode,
                        'name': newcode,
                        'level': 'coordo',
                        'instance': newcode,
                        'state': 'inactive',
                        'parent_id': self.get_company(db).instance_id.id,
                        'instance_identifier': newcode,
                   })
                #self.assert_(instance_ids != False, "instance not found")

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

                    # get parent (parent code: 3 first caracters (HT1, HT2,...))
                    parent_code = cc[:3]
                    if not parent_code in parent_cc_ids:
                        parent_ids = aaa_obj.search([
                            ('type', '=', 'view'),
                            ('category', '=', 'OC'),
                            ('code', '=', parent_code),
                        ])
                        parent_id = parent_ids and parent_ids[0] or False
                        if not parent_id:
                            parent_id = aaa_obj.create({
                                  'type': 'view',
                                  'category': 'OC',
                                  'code': parent_code,
                                  'currency_id': company.currency_id.id,
                                  'date_start': time.strftime('%Y-01-01'),
                                  'name': parent_code,
                                  'state': 'open',
                                  'parent_id': aaa_obj.search([('type', '=', 'view'), ('category', '=', 'OC'), ('parent_id', '=', False)])[0],
                            })
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
                                # create new link CC to prop instance
                                target_id = atcc_obj.create({
                                    'instance_id': instance_id,
                                    'cost_center_id': cc_id,
                                })
                            else:
                                target_id = target_ids[0]

                            if is_target and target_id:
                                # target expected update new or existing
                                # do not raise except regarding already a target
                                # to not block test dataset build and flow test
                                try:
                                    atcc_obj.write([target_id], {
                                        'is_target': True,
                                    })
                                except Exception:
                                    pass

        def set_funding_pools():
            c = self.c1
            aaa_model = 'account.analytic.account'

            for instance, fp in meta.fp_ccs:
                aaa_obj = c.get(aaa_model)
                company = self.get_company(c)

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

                if not self.record_exists(db, model, [('code', '=', fc)]):
                    # set vals
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

                    contract_id = db.get(model).create(vals, {'fake': 1})

                    # set funding pools
                    # NEED TO BE DONE AFTER CREATE (KO if done during create)
                    vals = {}
                    fp_codes = meta.financing_contracts[(instance, fc)].get(
                        'fps', False)
                    if fp_codes:
                        fp_ids = db.get(model_aaa).search([
                            ('category', '=', 'FUNDING'),
                            ('code', 'in', fp_codes),
                        ])
                        if fp_ids:
                            vals['funding_pool_ids'] = []
                            for fp_id in fp_ids:
                                vals['funding_pool_ids'].append((0, 0, {
                                        'funding_pool_id': fp_id,
                                        'funded': True,
                                        'total_project': True,
                                    'instance_id': company.instance_id.id,
                                    }))
                    if vals:
                        contract_id = db.get(model).write([contract_id], vals,
                            {'fake': 1})

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
        self._sync_from_c1()

        # C1 level: set financing contract + sync up/down (from c1)
        set_financing_contracts()
        self._sync_from_c1()

    # -------------------------------------------------------------------------
    # PRIVATE TOOLS FUNCTIONS
    # -------------------------------------------------------------------------

    def _sync_down(self, c2=False):
        self.synchronize(self.hq1)
        self.synchronize(self.c1)  # pull from hq
        self.synchronize(self.c1)  # push to projects
        self.synchronize(self.p1)
        self.synchronize(self.p12)  # C1P2

        # TODO:C2 level and C2P1/P2 (C2 not use in scenario at this time)
        """
        if c2:
            self.synchronize(self.c2) # pull from hq
            self.synchronize(self.c2)  # push to projects
            self.synchronize(self.p2)
            self.synchronize(self.p22)  # C2P2
        """

    def _sync_from_c1(self):
        self.synchronize(self.c1)
        #self.synchronize(self.hq1)
        self.synchronize(self.p1)
        self.synchronize(self.p12)  # C1P2

    def _get_default_date(self):
        return self.get_orm_fy_rand_month_date(DEFAULT_DATE_MONTH)

    def _register_set(self, db, period_id=None,
            ccy_name=False):
        dataset_meta = self._get_dataset_meta()

        db = self.c1
        aj_obj = db.get('account.journal')
        abs_obj = db.get('account.bank.statement')
        if period_id is None:
            period_id = db.get('account.period').search([('number', '=', DEFAULT_DATE_PERIOD_ID)], 0, 1, 'id')[0]
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

    '''def test_cor_00(self):
        """
        fake unit test for dataset testing
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_00
        """
        pass'''

    # -------------------------------------------------------------------------
    # SINGLE CASES FLOW: from 01 to 14
    # -------------------------------------------------------------------------

    def test_cor_01(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_01
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
                tag="CT_01"
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
                check_sequence_number=True
            )

    def test_cor_02(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_02
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
                tag="CT_02"
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

    def test_cor_03(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_03
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
                tag="CT_03"
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

    def test_cor_04(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_04
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
                tag="CT_04"
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

    def test_cor_05(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_05
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
                tag="CT_05"
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
                check_sequence_number=True
            )

    def test_cor_06(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_06
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
                tag="CT_06"
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
                check_sequence_number=True
            )

            # REOPEN period for over cases flow
            self.period_reopen(db, 'm', 1)
            self.period_reopen(db, 'f', 1)


    def test_cor_07(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_07
        G/L ACCOUNT 60010=>60030
        """
        db = self.c1

        # REOPEN period closed in case 06 (if it fails)
        self.period_reopen(db, 'm', 1)
        self.period_reopen(db, 'f', 1)

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
                tag="CT_07"
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
                check_sequence_number=True
            )

    def test_cor_08(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_08
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
                tag="CT_08"
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

    def test_cor_09(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_09
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
                tag="CT_09"
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

    def test_cor_10(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_10
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
                tag="CT_10"
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
                check_sequence_number=True
            )

    def test_cor_11(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_11
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
                db,
                ccy_code=False,
                date=self._get_default_date(),
                partner_id=False,
                ad_header_breakdown_data=ad,
                lines_accounts=invoice_lines_accounts,
                tag="CT_11"
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
                "You should not correct FP1 to PF as FC1 contract soft" \
                    " closed :: %s" % (db.colored_name, )
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
                expected_ad_cor=False
            )

    def test_cor_12(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_12
        """
        db = self.c1

        invoice_lines_accounts = [ '60010', '60020', '60030', ]

        ad = [
            (60., 'OPS', 'HT101', 'PF'),
            (40., 'OPS', 'HT120', 'PF'),
        ]

        ji_ids = self.invoice_validate(db,
            self.invoice_create_supplier_invoice(
                db,
                ccy_code='USD',
                date=self.get_orm_fy_date(1, 8),
                partner_id=False,
                ad_header_breakdown_data=ad,
                lines_accounts=invoice_lines_accounts,
                tag="CT_12"
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
                check_sequence_number=True
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

        # REOPEN period for over cases flow
        self.period_reopen(db, 'm', 1)
        self.period_reopen(db, 'f', 1)

    def test_cor_13(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_13
        """
        db = self.c1

        # REOPEN period closed in case 12 (if it fails)
        self.period_reopen(db, 'm', 1)
        self.period_reopen(db, 'f', 1)

        invoice_lines_accounts = [ '60010', '60020', ]

        ad = [
            (55., 'OPS', 'HT101', 'PF'),
            (45., 'OPS', 'HT120', 'PF'),
        ]

        aml_obj = db.get('account.move.line')

        ji_ids = self.invoice_validate(db,
            self.invoice_create_supplier_invoice(
                db,
                ccy_code=False,
                date=self._get_default_date(),
                partner_id=False,
                ad_header_breakdown_data=ad,
                lines_accounts=invoice_lines_accounts,
                tag="CT_13"
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
            check_sequence_number=True
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
            cor_level=2, ji_origin_id=ji_ids[0],
            check_sequence_number=True
        )

        # 13.8/9:
        # correction of the correction of correction
        # correction of COR-2 => will generate COR-3
        new_account3 = '60100'
        new_ad3 = [
            (70., 'OPS', 'HT120', 'FP2'),
            (30., 'OPS', 'HT101', 'FP2'),
        ]
        self.analytic_distribution_set_fp_account_dest(db, 'FP1', new_account3,
            'OPS')
        self.analytic_distribution_set_fp_account_dest(db, 'FP2', new_account3,
            'OPS')

        cor2_ids = aml_obj.search([('corrected_line_id', '=', cor1_ids[0])])
        self.assert_(cor2_ids != False, 'COR-2 JI not found!')

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

    def test_cor_14(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_14
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
                tag="CT_14"
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

    def test_cor_20(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_20
        """
        push_db = self.c1
        model_aal = 'account.analytic.line'

        invoice_lines_accounts = [ '63100', '63110', '63120', ]

        invoice_lines_breakdown_data = {
            1: [ (100., 'OPS', 'HT101', 'FP1'), ],
            2: [ (100., 'OPS', 'HT120', 'FP2'), ],
            3: [ (100., 'OPS', 'HT112', 'PF'), ],
        }
        self.analytic_distribution_set_fp_account_dest(push_db, 'FP1', '63100',
            'OPS')
        self.analytic_distribution_set_fp_account_dest(push_db, 'FP2', '63110',
            'OPS')
        self._sync_from_c1()  # sync down fp account/dest

        # 20.1, 20.2, 20.3
        ji_ids = self.invoice_validate(push_db,
            self.invoice_create_supplier_invoice(
                push_db,
                ccy_code=False,
                is_refund=True,
                date=self._get_default_date(),
                partner_id=False,
                ad_header_breakdown_data=False,
                lines_accounts=invoice_lines_accounts,
                lines_breakdown_data=invoice_lines_breakdown_data,
                tag="CT_20"
            )
        )
        jis_by_account = self.get_jis_by_account(push_db, ji_ids)
        ajis_by_account = self.get_ji_ajis_by_account(push_db, ji_ids)
        aji_HT112 = self.get_ji_ajis_by_account(push_db, ji_ids,
            account_code_filter='63120', cc_code_filter='HT112')[0]

        # 20.4
        self.synchronize(push_db)

        # 20.5
        pull_db = self.p1
        self.synchronize(pull_db)

        # pull 1 AJI: 63120 HT112
        push_expected=[
            aji_HT112[1],
        ]
        push_not_expected=[
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63100',
                cc_code_filter='HT101')[0][1],
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63110',
                cc_code_filter='HT120')[0][1],
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=push_db,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                pull_db=pull_db
            ))),
            "SYNC mismatch"
        )

        # 20.6
        pull_db = self.p12  # C1P2
        self.synchronize(pull_db)

        # NO AJIs
        push_expected=[]
        push_not_expected=[
            aji_HT112[1],
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63100',
                cc_code_filter='HT101')[0][1],
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63110',
                cc_code_filter='HT120')[0][1],
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=push_db,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                pull_db=pull_db
            ))),
            "SYNC mismatch"
        )

        # 20.7/8/9 (change 63120 refund line AD CC HT112 to HT121)
        new_CC = 'HT121'
        self.simulation_correction_wizard(push_db,
            jis_by_account['63120'][0][0],
            cor_date=False,
            new_account_code=False,
            new_ad_breakdown_data=False,
            ad_replace_data={ 100.: {'cc': new_CC, } }
        )

        self.check_ji_correction(push_db, jis_by_account['63120'][0][0],
            '63120', new_account_code=False,
            expected_ad=[ (100., 'OPS', new_CC, 'PF'), ],
            expected_ad_rev=False,
            expected_ad_cor=False
        )

        # 20.10
        self.synchronize(push_db)

        # 20.11
        pull_db = self.p1
        self.synchronize(pull_db)

        # 1 AJI deleted
        push_expected=[
        ]
        push_not_expected=[
        ]
        push_should_deleted=[
            # target instance changed CC HT112 to HT121
            aji_HT112[1],
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=push_db,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                push_should_deleted=push_should_deleted,
                pull_db=pull_db
            ))),
            "SYNC mismatch"
        )

        # 20.12
        pull_db = self.p12
        self.synchronize(pull_db)

        # pull 1 AJI: 63120 HT121
        push_expected=[
            # target instance changed CC HT112 to HT121: AJI moved to C1P2
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63120',
                cc_code_filter='HT121')[0][1],
        ]
        push_not_expected=[
        ]
        push_should_deleted=[
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=push_db,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                push_should_deleted=push_should_deleted,
                pull_db=pull_db
            ))),
            "SYNC mismatch"
        )

    def test_cor_21(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_21
        """
        push_db = self.c1
        model_aal = 'account.analytic.line'

        invoice_lines_accounts = [ '63100', '63110', '63120', ]

        invoice_lines_breakdown_data = {
            1: [ (100., 'OPS', 'HT101', 'FP1'), ],
            2: [ (100., 'OPS', 'HT120', 'FP2'), ],
            3: [ (100., 'OPS', 'HT112', 'PF'), ],
        }
        self.analytic_distribution_set_fp_account_dest(push_db, 'FP1', '63100',
            'OPS')
        self.analytic_distribution_set_fp_account_dest(push_db, 'FP2', '63110',
            'OPS')
        self._sync_from_c1()  # sync down fp account/dest

        # 21.1, 21.2, 21.3
        ji_ids = self.invoice_validate(push_db,
            self.invoice_create_supplier_invoice(
                push_db,
                ccy_code=False,
                is_refund=True,
                date=self._get_default_date(),
                partner_id=False,
                ad_header_breakdown_data=False,
                lines_accounts=invoice_lines_accounts,
                lines_breakdown_data=invoice_lines_breakdown_data,
                tag="CT_21"
            )
        )
        jis_by_account = self.get_jis_by_account(push_db, ji_ids)

        # 21.4
        self.synchronize(push_db)

        # 21.5
        pull_db = self.p1
        self.synchronize(pull_db)

        # pull 1 1JI: 63120 HT112
        push_expected=[
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63120',
                cc_code_filter='HT112')[0][1],
        ]
        push_not_expected=[
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63100',
                cc_code_filter='HT101')[0][1],
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63110',
                cc_code_filter='HT120')[0][1],
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=push_db,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                pull_db=pull_db
            ))),
            "SYNC mismatch"
        )

        # 21.6
        pull_db = self.p12  # C1P2
        self.synchronize(pull_db)

        # NO Ajis
        push_expected=[]
        push_not_expected = [
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63100',
                cc_code_filter='HT101')[0][1],
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63110',
                cc_code_filter='HT120')[0][1],
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63120',
                cc_code_filter='HT112')[0][1],
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=push_db,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                pull_db=pull_db
            ))),
            "SYNC mismatch"
        )

        # 21.7/21.8/21.9
        new_ad = [
            (50., 'OPS', 'HT112', 'PF'),
            (50., 'OPS', 'HT121', 'PF'),
        ]
        self.simulation_correction_wizard(push_db,
            jis_by_account['63120'][0][0],
            cor_date=False,
            new_account_code=False,
            new_ad_breakdown_data=new_ad,
            ad_replace_data=False
        )

        self.check_ji_correction(push_db,
            jis_by_account['63120'][0][0],
            '63120', new_account_code=False,
            expected_ad=new_ad,
            expected_ad_rev=False,
            expected_ad_cor=False
        )

        # 21.10
        self.synchronize(push_db)

        # 21.11
        pull_db = self.p1
        self.synchronize(pull_db)

        # pull update of AJI 63120 HT112 (amount changed)
        push_expected=[
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63120',
                cc_code_filter='HT112')[0][1],
        ]
        aji_ht121 = self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63120',
                cc_code_filter='HT121')[0]
        push_not_expected=[
            aji_ht121[1],  # not expected HT121 from AD split when C1 COR
        ]
        push_should_deleted=[
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=push_db,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                push_should_deleted=push_should_deleted,
                pull_db=pull_db
            ))),
            "SYNC mismatch"
        )

        # 21.12
        pull_db = self.p12
        self.synchronize(pull_db)

        # pull 1 AJI: 63120 HT121
        push_expected=[
            aji_ht121[1],
        ]
        push_not_expected=[
        ]
        push_should_deleted=[
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=push_db,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                push_should_deleted=push_should_deleted,
                pull_db=pull_db
            ))),
            "SYNC mismatch"
        )

    def test_cor_22(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_22
        """
        push_db = self.c1
        model_aal = 'account.analytic.line'
        model_aml = 'account.move.line'

        invoice_lines_accounts = [ '63100', '63110', '63120', ]

        invoice_lines_breakdown_data = {
            1: [ (100., 'OPS', 'HT101', 'FP1'), ],
            2: [ (100., 'OPS', 'HT120', 'FP2'), ],
            3: [ (50., 'OPS', 'HT111', 'PF'), (50., 'OPS', 'HT112', 'PF'), ],
        }
        self.analytic_distribution_set_fp_account_dest(push_db, 'FP1', '63100',
            'OPS')
        self.analytic_distribution_set_fp_account_dest(push_db, 'FP2', '63110',
            'OPS')
        self._sync_from_c1()  # sync down fp account/dest

        # 22.1, 22.2, 22.3
        ji_ids = self.invoice_validate(push_db,
            self.invoice_create_supplier_invoice(
                push_db,
                ccy_code=False,
                is_refund=False,
                date=self._get_default_date(),
                partner_id=False,
                ad_header_breakdown_data=False,
                lines_accounts=invoice_lines_accounts,
                lines_breakdown_data=invoice_lines_breakdown_data,
                tag="CT_22"
            )
        )
        jis_by_account = self.get_jis_by_account(push_db, ji_ids)

        # 22.4
        self.synchronize(push_db)

        # 22.5
        pull_db = self.p1
        self.synchronize(pull_db)

        # pull 2 AJIs: 63120 HT111, 63120 HT112
        push_expected = [
            # 2 AJIs HT111 & HT112
            self.get_ji_ajis_by_account(push_db, ji_ids,  # get sdref from c1
                cc_code_filter='HT111')['63120'][0][1],
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63120',
                cc_code_filter='HT112')[0][1],
        ]
        push_not_expected=[
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63100',
                cc_code_filter='HT101')[0][1],
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63110',
                cc_code_filter='HT120')[0][1],
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=push_db,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                pull_db=pull_db
            ))),
            "SYNC mismatch"
        )

    def test_cor_23(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_23
        """
        push_db = self.c1
        model_aal = 'account.analytic.line'

        invoice_lines_accounts = [ '63100', '63110', '63120', ]

        invoice_lines_breakdown_data = {
            1: [ (100., 'OPS', 'HT101', 'FP1'), ],
            2: [ (100., 'OPS', 'HT120', 'FP2'), ],
            3: [ (50., 'OPS', 'HT111', 'PF'), (50., 'OPS', 'HT112', 'PF'), ],
        }
        self.analytic_distribution_set_fp_account_dest(push_db, 'FP1', '63100',
            'OPS')
        self.analytic_distribution_set_fp_account_dest(push_db, 'FP2', '63110',
            'OPS')
        self._sync_from_c1()  # sync down fp account/dest

        # 23.1, 23.2, 23.3
        ji_ids = self.invoice_validate(push_db,
            self.invoice_create_supplier_invoice(
                push_db,
                ccy_code=False,
                is_refund=False,
                date=self._get_default_date(),
                partner_id=False,
                ad_header_breakdown_data=False,
                lines_accounts=invoice_lines_accounts,
                lines_breakdown_data=invoice_lines_breakdown_data,
                tag="CT_23"
            )
        )
        jis_by_account = self.get_jis_by_account(push_db, ji_ids)

        # 23.4
        self.synchronize(push_db)

        # 23.5
        pull_db = self.p1
        self.synchronize(pull_db)

        # pull 2 AJI: 63129 HT11/HT112
        push_expected = [
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63120',
                cc_code_filter='HT111')[0][1],
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63120',
                cc_code_filter='HT112')[0][1],
        ]
        push_not_expected=[
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63100',
                cc_code_filter='HT101')[0][1],
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63110',
                cc_code_filter='HT120')[0][1],
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=push_db,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                pull_db=pull_db
            ))),
            "SYNC mismatch"
        )

        # 23.6/7
        new_ad = [
            (20., 'OPS', 'HT111', 'PF'),
            (35., 'OPS', 'HT112', 'PF'),
            (45., 'OPS', 'HT112', 'FP1'),
        ]
        self.simulation_correction_wizard(push_db,
            jis_by_account['63120'][0][0],
            cor_date=False,
            new_account_code=False,
            new_ad_breakdown_data=new_ad,
            ad_replace_data=False
        )

        self.check_ji_correction(push_db, jis_by_account['63120'][0][0],
            '63120', new_account_code=False,
            expected_ad=new_ad,
            expected_ad_rev=False,
            expected_ad_cor=False
        )

        # 23.8
        self.synchronize(push_db)

        # 23.9
        self.synchronize(pull_db)

        ht112_ajis = self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63120',
                cc_code_filter='HT112')  # 2 items since C1 COR
        push_expected = [
            self.get_ji_ajis_by_account(push_db, ji_ids,
                cc_code_filter='HT111')['63120'][0][1],
            ht112_ajis[0][1],
            ht112_ajis[1][1],
        ]
        push_not_expected=[
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63100',
                cc_code_filter='HT101')[0][1],
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63110',
                cc_code_filter='HT120')[0][1],
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=push_db,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                pull_db=pull_db
            ))),
            "SYNC mismatch"
        )

    def test_cor_24(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_24
        """
        push_db = self.c1
        model_aal = 'account.analytic.line'

        invoice_lines_accounts = [ '63100', '63110', '63120', ]

        invoice_lines_breakdown_data = {
            1: [ (100., 'OPS', 'HT101', 'FP1'), ],
            2: [ (100., 'OPS', 'HT121', 'FP2'), ],
            3: [ (50., 'OPS', 'HT111', 'PF'), (50., 'OPS', 'HT121', 'PF'), ],
        }
        self.analytic_distribution_set_fp_account_dest(push_db, 'FP1', '63100',
            'OPS')
        self.analytic_distribution_set_fp_account_dest(push_db, 'FP2', '63110',
            'OPS')
        self._sync_from_c1()  # sync down fp account/dest

        # 24.1, 24.2, 24.3
        ji_ids = self.invoice_validate(push_db,
            self.invoice_create_supplier_invoice(
                push_db,
                ccy_code=False,
                is_refund=False,
                date=self._get_default_date(),
                partner_id=False,
                ad_header_breakdown_data=False,
                lines_accounts=invoice_lines_accounts,
                lines_breakdown_data=invoice_lines_breakdown_data,
                tag="CT_24"
            )
        )
        jis_by_account = self.get_jis_by_account(push_db, ji_ids)

        # get 63120 HT111 sdref: will be deleted later(C1P1) and need to assert
        aji_63120_HT111_sdref = self.get_ji_ajis_by_account(push_db, ji_ids,
            account_code_filter='63120',
            cc_code_filter='HT111')[0][1]
        # get 63120 HT121 sdref: will be deleted later(C1P2) and need to assert
        aji_63120_HT121_sdref = self.get_ji_ajis_by_account(push_db, ji_ids,
            account_code_filter='63120',
            cc_code_filter='HT121')[0][1]

        # 24.4
        self.synchronize(push_db)

        # 24.5
        pull_db = self.p1
        self.synchronize(pull_db)

        # pull 1 AJI: 63120 HT111
        push_expected = [
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63120',
                cc_code_filter='HT111')[0][1],
        ]
        push_not_expected=[
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63100',
                cc_code_filter='HT101')[0][1],
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63110',
                cc_code_filter='HT121')[0][1],
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63120',
                cc_code_filter='HT121')[0][1],
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=push_db,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                pull_db=pull_db
            ))),
            "SYNC mismatch"
        )

        # 24.6
        pull_db = self.p12
        self.synchronize(pull_db)

        # pull 2 AJIs: 63110 HT121, 63120 HT121
        push_expected = [
            self.get_ji_ajis_by_account(push_db, ji_ids,
                cc_code_filter='HT121')['63110'][0][1],
            self.get_ji_ajis_by_account(push_db, ji_ids,
                cc_code_filter='HT121')['63120'][0][1],
        ]
        push_not_expected=[
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63100',
                cc_code_filter='HT101')[0][1],
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63120',
                cc_code_filter='HT111')[0][1],
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=push_db,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                pull_db=pull_db
            ))),
            "SYNC mismatch"
        )

        # 24.7
        new_ad = [
            (100., 'OPS', 'HT120', 'PF'),
        ]
        self.simulation_correction_wizard(push_db,
            jis_by_account['63120'][0][0],
            cor_date=False,
            new_account_code=False,
            new_ad_breakdown_data=new_ad,
            ad_replace_data=False
        )
        self.check_ji_correction(push_db,
            jis_by_account['63120'][0][0],
            '63120', new_account_code=False,
            expected_ad=new_ad,
            expected_ad_rev=False,
            expected_ad_cor=False
        )

        # 24.8
        new_cc = 'HT122'
        new_ad = [
            (100., 'OPS', new_cc, 'FP2'),
        ]
        self.simulation_correction_wizard(push_db,
            jis_by_account['63110'][0][0],
            cor_date=False,
            new_account_code=False,
            new_ad_breakdown_data=False,
            ad_replace_data={ 100.: {'cc': new_cc, } },
        )
        self.check_ji_correction(push_db,
            jis_by_account['63110'][0][0],
            '63110', new_account_code=False,
            expected_ad=new_ad,
            expected_ad_rev=False,
            expected_ad_cor=False
        )

        # 24.9
        self.synchronize(push_db)
        self.synchronize(push_db)

        # 24.10
        pull_db = self.p1
        self.synchronize(pull_db)

        # delete 1 AJI: 63120 HT111
        push_expected = [
        ]
        push_not_expected = [
        ]
        push_should_deleted = [
            aji_63120_HT111_sdref,
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=push_db,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                push_should_deleted=push_should_deleted,
                pull_db=pull_db
            ))),
            "SYNC mismatch"
        )

        # 24.11
        pull_db = self.p12
        self.synchronize(pull_db)

        # - delete 1 AJI: 63120 HT121 -> HT120
        # - update 1 AJI: 63110 HT121 -> HT122
        push_expected = [
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63110',
                cc_code_filter='HT122')[0][1],
        ]
        push_not_expected = [
        ]
        push_should_deleted = [
            aji_63120_HT121_sdref
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=push_db,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                push_should_deleted=push_should_deleted,
                pull_db=pull_db
            ))),
            "SYNC mismatch"
        )

    def test_cor_25(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_25
        """
        push_db = self.c1
        model_aal = 'account.analytic.line'

        invoice_lines_accounts = [ '63100', '63110', '63120', ]

        invoice_lines_breakdown_data = {
            1: [ (100., 'OPS', 'HT101', 'FP1'), ],
            2: [ (100., 'OPS', 'HT121', 'FP2'), ],
            3: [ (50., 'OPS', 'HT111', 'PF'), (50., 'OPS', 'HT121', 'PF'), ],
        }
        self.analytic_distribution_set_fp_account_dest(push_db, 'FP1', '63100',
            'OPS')
        self.analytic_distribution_set_fp_account_dest(push_db, 'FP2', '63110',
            'OPS')
        self._sync_from_c1()  # sync down fp account/dest

        # 25.1, 25.2, 25.3
        ji_ids = self.invoice_validate(push_db,
            self.invoice_create_supplier_invoice(
                push_db,
                ccy_code=False,
                is_refund=False,
                date=self.get_orm_fy_date(1, 1),
                partner_id=False,
                ad_header_breakdown_data=False,
                lines_accounts=invoice_lines_accounts,
                lines_breakdown_data=invoice_lines_breakdown_data,
                tag="CT_25"
            )
        )
        jis_by_account = self.get_jis_by_account(push_db, ji_ids)

        # 25.4
        self.synchronize(push_db)

        # 25.5
        pull_db = self.p1
        self.synchronize(pull_db)

        # pull 1 AJI: 63120 HT111
        push_expected = [
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63120',
                cc_code_filter='HT111')[0][1],
        ]
        push_not_expected=[
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63100',
                cc_code_filter='HT101')[0][1],
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63110',
                cc_code_filter='HT121')[0][1],
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63120',
                cc_code_filter='HT121')[0][1],
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=push_db,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                pull_db=pull_db
            ))),
            "SYNC mismatch"
        )

        # 25.6
        pull_db = self.p12
        self.synchronize(pull_db)

        # pull 2 AJIs: 63110 HT121, 63120 HT121
        push_expected = [
            self.get_ji_ajis_by_account(push_db, ji_ids,
                cc_code_filter='HT121')['63110'][0][1],
            self.get_ji_ajis_by_account(push_db, ji_ids,
                cc_code_filter='HT121')['63120'][0][1],
        ]
        push_not_expected=[
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63100',
                cc_code_filter='HT101')[0][1],
            self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63120',
                cc_code_filter='HT111')[0][1],
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=push_db,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                pull_db=pull_db
            ))),
            "SYNC mismatch"
        )

        # 25.7
        self.period_close(push_db, 'f', 1, year=0)
        self.period_close(push_db, 'm', 1, year=0)

        # 25.8
        old_ad = [
            (50., 'OPS', 'HT111', 'PF'),
            (50., 'OPS', 'HT121', 'PF'),
        ]
        new_ad = [
            (100., 'OPS', 'HT120', 'PF'),
        ]
        self.simulation_correction_wizard(push_db,
            jis_by_account['63120'][0][0],
            cor_date=self.get_orm_fy_date(2, 7),
            new_account_code=False,
            new_ad_breakdown_data=new_ad,
            ad_replace_data=False
        )

        self.check_ji_correction(push_db,
            jis_by_account['63120'][0][0],
            '63120', new_account_code=False,
            expected_ad=old_ad,
            expected_ad_rev=old_ad,
            expected_ad_cor=new_ad
        )

        # 25.9
        old_ad = [ (100., 'OPS', 'HT121', 'FP2'), ]
        new_cc = 'HT122'
        new_ad = [
            (100., 'OPS', new_cc, 'FP2'),
        ]
        self.simulation_correction_wizard(push_db,
            jis_by_account['63110'][0][0],
            cor_date=self.get_orm_fy_date(2, 8),
            new_account_code=False,
            new_ad_breakdown_data=False,
            ad_replace_data={ 100.: {'cc': new_cc, } },
        )

        self.check_ji_correction(push_db,
            jis_by_account['63110'][0][0],
            '63110', new_account_code=False,
            expected_ad=old_ad,
            expected_ad_rev=old_ad,
            expected_ad_cor=new_ad
        )

        # 25.10
        self.synchronize(push_db)

        # 25.11
        pull_db = self.p1
        self.synchronize(pull_db)

        # pull 1 REV AJI 63120 HT111
        push_expected = [
            self.get_aji_revs(
                push_db,
                self.get_ji_ajis_by_account(push_db, ji_ids,
                    account_code_filter='63120',
                    cc_code_filter='HT111')[0][0]
            )[0][1],
        ]
        push_not_expected=[
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=push_db,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                pull_db=pull_db
            ))),
            "SYNC mismatch"
        )

        # 25.13
        pull_db = self.p12  # C1P2
        self.synchronize(pull_db)

        # pull 3 AJIs:
        # a) 1REV 63110 HT121 FP2, 1 COR 63110 HT112 FP2 due to 25.9
        # b) 1REV 63120 HT121 PF due to 25.8
        ht121_63110_id = self.get_ji_ajis_by_account(push_db, ji_ids,
            account_code_filter='63110',
            cc_code_filter='HT121')[0][0]
        push_expected = [
            # a) 63110
            self.get_aji_revs(push_db, ht121_63110_id)[0][1],
            self.get_aji_cors(push_db, ht121_63110_id,
                new_account=False)[0][1],

            # b) 63120
            self.get_aji_revs(
                push_db,
                self.get_ji_ajis_by_account(push_db, ji_ids,
                account_code_filter='63120',
                cc_code_filter='HT121')[0][0]
            )[0][1],
        ]
        push_not_expected=[
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=push_db,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                pull_db=pull_db
            ))),
            "SYNC mismatch"
        )

        # REOPEN period for over cases flow
        self.period_reopen(push_db, 'm', 1)
        self.period_reopen(push_db, 'f', 1)

    def test_cor_26(self):
        """
        cd unifield/test-finance/unifield-wm/unifield_tests
        python -m unittest tests.test_finance_cor_cases.FinanceTestCorCases.test_cor_26
        """
        # REOPEN period closed in case 25 (if it fails)
        self.period_reopen(self.c1, 'm', 1)
        self.period_reopen(self.c1, 'f', 1)
        self.period_reopen(self.p1, 'm', 1)
        self.period_reopen(self.p1, 'f', 1)

        model_aal = 'account.analytic.line'

        invoice_lines_accounts = [ '60000', '60010', ]
        header_ad = [
            (60., 'OPS', 'HT112', 'PF'),
            (40., 'NAT', 'HT122', 'PF'),
        ]

        # 26.1, 26.2, 26.3
        inv_out = {}
        ji_ids = self.invoice_validate(
            self.p1,
            self.invoice_create_supplier_invoice(
                self.p1,
                ccy_code=False,
                is_refund=False,
                date=self._get_default_date(),
                partner_id=False,
                ad_header_breakdown_data=header_ad,
                lines_accounts=invoice_lines_accounts,
                lines_breakdown_data=False,
                tag="CT_26"),
            out=inv_out
        )
        jis_by_account = self.get_jis_by_account(self.p1, ji_ids)

        # get sdref of entries that will be pull deleted after the following
        # correction on 26.7/8
        sdref_60000_ht112 = self.get_ji_ajis_by_account(self.p1, ji_ids,
            account_code_filter='60000',
                cc_code_filter='HT112')[0][1]
        sdref_60000_ht122 = self.get_ji_ajis_by_account(self.p1, ji_ids,
            account_code_filter='60000',
            cc_code_filter='HT122')[0][1]
        sdref_60010_ht112 = self.get_ji_ajis_by_account(self.p1, ji_ids,
            account_code_filter='60010',
                cc_code_filter='HT112')[0][1]
        sdref_60010_ht122 = self.get_ji_ajis_by_account(self.p1, ji_ids,
            account_code_filter='60010',
            cc_code_filter='HT122')[0][1]

        # 26.4
        self.synchronize(self.p1)

        # 26.5
        self.synchronize(self.c1)
        # check 3 JIs pulled

        push_expected = [
            jis_by_account['60000'][0][1],
            jis_by_account['60010'][0][1],
            inv_out['ji_counterpart_sdref'],  # invoice counterpart header
        ]
        push_not_expected=[
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_ji_record_sync_push_pulled(
                push_db=self.p1,
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                pull_db=self.c1
            ))),
            "SYNC mismatch"
        )

        # check 4 AJIs pulled
        push_expected = [
            sdref_60000_ht112,
            sdref_60000_ht122,
            sdref_60010_ht112,
            sdref_60010_ht122,
        ]
        push_not_expected=[
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=self.p1,  # from P1
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                pull_db=self.c1  # to C1
            ))),
            "SYNC mismatch"
        )

        # 26.6
        self.synchronize(self.p12)  # C1P1

        # check 2 AJIs pulled (60000/60010 HT122)

        push_expected = [
            sdref_60000_ht122,
            sdref_60010_ht122,
        ]
        push_not_expected=[
            sdref_60000_ht112,
            sdref_60010_ht112,
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=self.c1,  # from C1
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                pull_db=self.p12  # to C1P2
            ))),
            "SYNC mismatch"
        )

        # 26.7
        new_ad = [
            (100., 'OPS', 'HT120', 'PF'),
        ]
        # convert 60000 JI from P1 sdref to C1 id
        ji_60000_id = self.get_record_id_from_sdref(self.c1,
            jis_by_account['60000'][0][1])
        self.simulation_correction_wizard(self.c1,
            ji_60000_id,
            cor_date=False,
            new_account_code=False,
            new_ad_breakdown_data=new_ad,
            ad_replace_data=False
        )
        self.check_ji_correction(self.c1,
            ji_60000_id,
            '60000', new_account_code=False,
            expected_ad=new_ad,
            expected_ad_rev=False,
            expected_ad_cor=False
        )

        # 26.8
        new_cc = 'HT120'
        new_ad = [
            (60., 'OPS', 'HT112', 'PF'),
            (40., 'NAT', new_cc, 'PF'),
        ]
        # convert 60010 JI from P1 sdref to C1 id
        ji_60010_id = self.get_record_id_from_sdref(self.c1,
            jis_by_account['60010'][0][1])
        self.simulation_correction_wizard(self.c1,
            ji_60010_id,
            cor_date=False,
            new_account_code=False,
            new_ad_breakdown_data=False,
            ad_replace_data={ 40.: {'cc': new_cc, } }
        )
        self.check_ji_correction(self.c1,
            ji_60010_id,
            '60010', new_account_code=False,
            expected_ad=new_ad,
            expected_ad_rev=False,
            expected_ad_cor=False
        )

        # 26.9
        self.synchronize(self.c1)

        # 26.10
        self.synchronize(self.p12)  # C1P2

        # check 2 AJI deleted 60000/60010 HT122 (=>HT120)
        push_expected = [
        ]
        push_not_expected = [
        ]
        push_should_deleted = [
            sdref_60000_ht122,
            sdref_60010_ht122,
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=self.c1,  # from C1
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                push_should_deleted=push_should_deleted,
                pull_db=self.p12  # to C1P2
            ))),
            "SYNC mismatch"
        )

        # 26.11
        self.synchronize(self.p1)

        # check 1 AJI deleted 60000 HT112
        # (the 40% one from 60000) (left the 60% from 60010)
        push_expected = [
        ]
        push_not_expected = [
        ]
        push_should_deleted = [
            sdref_60000_ht112,
        ]
        self.assert_(
            all(self.flat_dict_vals(self.check_aji_record_sync_push_pulled(
                push_db=self.c1,  # from C1
                push_expected=push_expected,
                push_not_expected=push_not_expected,
                push_should_deleted=push_should_deleted,
                pull_db=self.p1  # to C1P1
            ))),
            "SYNC mismatch"
        )


def get_test_class():
    return FinanceTestCorCases
