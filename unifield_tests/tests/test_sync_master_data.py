#!/usr/bin/env python
# -*- coding: utf8 -*-
from __future__ import print_function
from unifield_test import UnifieldTest

import time

# set it to True to simulate a sync P1 sync down failure for any test
#TEST_THE_TEST = True
TEST_THE_TEST = False


def dfv(vals, include=None, exclude=[]):
    """
    domain from vals (all vals with implicite &)

    create a domain from a data dictionary
    include is prior to exclude (exclude not used if include is set)
    :type d: dict
    :param include: field or list of field to include in domain
    :type include: str/list
    :param exclude: field or list of field not to include in domain
    :type exclude: str/list
    :return: A list of tuples like [('op1', 'operator', 'op2')]
    """
    if include and isinstance(include, (str, list, )):
        if isinstance(include, str):
            include = [include]
        return [(x[0], '=', x[1]) for x in vals.iteritems() if x[0] in include]
    if isinstance(exclude, str):
        exclude = [exclude]
    return [(x[0], '=', x[1]) for x in vals.iteritems() if x[0] not in exclude]

def are_same_db(db1, db2):
    return db1.db_name == db2.db_name or False

def get_id_from_name(db, model_name, res_name, name_field='name'):
    """
    :param db: db
    :param model_name: model name to search in
    :param res_name: name value to search in
    :param name_field: name field name (field for criteria)
    :return: id
    :rtype: int/long
    """
    ids = db.get(model_name).search([(name_field, '=', res_name)])
    if ids:
        return ids[0]
    msg = "'%s' not found in '%s' :: %s" % (res_name, model_name,
        db.colored_name, )
    raise MasterDataSyncTestException(msg)

class MasterDataSyncTestException(Exception):
    pass


class MasterDataSyncTest(UnifieldTest):
    def setUp(self):
        # meta of generated test records
        self._ids = {}  # {'db_name': {'model': ids, }, }

    def _get_db_from_name(self, db_name):
        if self.hq1.db_name == db_name:
            return self.hq1
        elif self.c1.db_name == db_name:
            return self.c1
        elif self.p1.db_name == db_name:
            return self.p1
        raise MasterDataSyncTestException("'%s' database not found" % (
            db_name, ))

    def _set_ids(self, db, model_name, ids):
        """
        log an added data test records (to delete in tearDown)
        by db and by model name
        :type db: object
        :type model_name: str
        :type ids: int/long/list
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        self._ids.setdefault(db.db_name, {})[model_name] = ids

    def _get_ids(self, db, model_name):
        """
        get logged added data test records (to delete in tearDown)
        :type db: object
        :type model_name: str
        """
        return self._ids.get(db.db_name, {}).get(model_name, False)

    def _unlink_db_generated_ids(self, db_name):
        """
        unlink all test data generated records in target db
        :type db_name: target db name
        """
        db = self._get_db_from_name(db_name)
        for model_name in self._ids.get(db_name, {}):
            ids = self._get_ids(db, model_name)
            if ids:
                db.get(model_name).unlink(ids)

    def _unlink_all_generated_ids(self):
        # delete auto generated test records
        for db_name in self._ids:  # {'db_name': {'model': ids, }, }
            self._unlink_db_generated_ids(db_name)
        self._ids = {}

    def _sync_check_data_set_on_db(self, db, check_batch):
        """
        check in db that for model/domain entries there is one data set entry
        :type db: object
        :param check_batch: [(model, domain), ]
        """
        for model, domain in check_batch:
            ids = db.get(model).search(domain)
            count = len(ids) if ids else 0
            if ids:
                self._set_ids(db, model, ids)  # log ids to remove in tearDown
            else:
                # assert will be raised so delete test records
                self._unlink_all_generated_ids()

            self.assertNotEquals(
                count, 0,
                "'UF' '%s' entry not found on %s :: %s" % (model,
                    db.colored_name, domain, )
            )
            self.assertEqual(
                count, 1,
                "There is more than 1 'UF' '%s' entry on %s :: %s :: %s" % (
                    model, db.colored_name, count, domain, )
            )

    def _create_data_record(self, db, model_name, vals, domain_include=None,
        domain_exclude=[], check_batch=None, teardown_log=True):
        """
        for a model create a record in hq using vals and create domain
        :param db: db
        :type db: object
        :type model_name: str
        :param vals: vals
        :type vals: dict
        :param domain_include: see dfv() include param
        :param domain_exclude: ee dfv() exclude param
        :param check_batch: [(model, domain), ] if provided auto check batch is
            generated here (see _sync_check_data_set_on_db())
        :type check_batch: list
        :param teardown_log: True to log 'generated record is to delete in
            tearDown()' (default True)
        :type teardown_log: bool
        :return: (id, domain)
        :rtype: tuple
        """
        """
        :param model_name:
        :param vals:
        :param domain_include:
        :param domain_exclude:
        :return:
        """
        # uom category
        hq_obj = db.get(model_name)
        domain = dfv(vals, include=domain_include, exclude=domain_exclude)
        if hq_obj.search(domain):
            id = hq_obj.search(domain)[0]
        else:
            id = hq_obj.create(vals)
        if teardown_log:
            self._set_ids(db, model_name, id)
        if check_batch is not None:
            check_batch.append((model_name, domain))
        return (id, domain, )

    def _sync_down_check(self, check_batch, db=None):
        """
        from hq sync down check batch to c1 then p1
        :param check_batch: see _sync_check_data_set_on_db() check_batch param
        :type check_batch: list
        :param db: db
        :type db: object
        """
        if db is None:
            db = self.hq1
        if are_same_db(self.p1, db):
            raise MasterDataSyncTestException('can not sync down from project')

        # sync down and check
        self.synchronize(db)

        if are_same_db(self.hq1, db):
            # c1 sync down and check check
            self.synchronize(self.c1)
            self._sync_check_data_set_on_db(self.c1, check_batch)

        # p1 sync down and check check (from hq or c1 sync down)
        global TEST_THE_TEST
        if not TEST_THE_TEST:  # volontary miss the sync to test the test
            self.synchronize(self.p1)
        # will volontary fail if above P1 sync not done
        self._sync_check_data_set_on_db(self.p1, check_batch)

    def tearDown(self):
        # delete auto generated test records
        self._unlink_all_generated_ids()

    def test_s1_tec_21(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_21

        - create a new country and country state in hq
        - synchronize down from hq to coordo and project
        - check if the country and the country state have been well sync down
        """
        check_batch = []

        # country
        vals = {
            'code': 'UF',
            'name': 'Unifield Country Test',
        }
        country_id, country_domain = self._create_data_record(self.hq1,
            'res.country', vals, check_batch=check_batch)

        # country state
        hq_state_obj = self.hq1.get('res.country.state')
        vals = {
            'code': 'UF',
            'name': 'Unifield Country State Test',
            'country_id': country_id,
        }
        id, state_domain = self._create_data_record(self.hq1,
            'res.country.state', vals, domain_exclude=['country_id', ],
            check_batch=check_batch)

        self._sync_down_check(check_batch)

    def test_s1_tec_22(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_22

        - create an uom category and an uom in hq
        - synchronize down from hq to coordo and project
        - check if the uom categ and the uom have been well sync down
        """
        check_batch = []

        # uom category
        vals = {
            'name': 'Unifield Uom Category Test'
        }
        categ_id, domain = self._create_data_record(self.hq1,
            'product.uom.categ', vals, check_batch=check_batch)

        # uom
        vals = {
            'name': 'UF Uom Test',
            'category_id': categ_id,
            'factor': 1.,
            'factor_inv': 1.,
            'rounding': 1.,
            'uom_type': 'reference',
        }
        self._create_data_record(self.hq1, 'product.uom', vals,
            domain_include=['name', 'uom_type', ], check_batch=check_batch)

        self._sync_down_check(check_batch)

    def test_s1_tec_23(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_23

        - create a product nomenclature in hq
        - synchronize down from hq to coordo and project and check
        """
        check_batch = []

        vals = {
            'name': 'Unifield Nomenclature Test',
        }
        self._create_data_record(self.hq1, 'product.nomenclature', vals,
            check_batch=check_batch)

        self._sync_down_check(check_batch)

    def test_s1_tec_24(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_24

        - create a product category in hq
        - synchronize down from hq to coordo and project and check
        """
        check_batch = []

        vals = {
            'name': 'Unifield Product Category Test',
            'type': 'normal',
        }
        self._create_data_record(self.hq1, 'product.category', vals,
            check_batch=check_batch)

        self._sync_down_check(check_batch)

    def test_s1_tec_25(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_25

        - create a product justification code in hq
        - create a product asset type in hq
        - synchronize down from hq to coordo and project and check
        """
        check_batch = []

        # product justication code
        vals = {
            'code': 'UF',
            'description': 'Unifield Justification Code Test',
        }
        self._create_data_record(self.hq1, 'product.justification.code', vals,
            check_batch=check_batch)

        # product asset type
        vals = {
            'name': 'Unifield Asset Type Test',
        }
        self._create_data_record(self.hq1, 'product.asset.type', vals,
            check_batch=check_batch)

        self._sync_down_check(check_batch)

    def test_s1_tec_26(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_26

        - create a standard product list in hq
        - synchronize down from hq to coordo and project and check
        """
        check_batch = []

        # product list
        vals = {
            'name': 'Unifield Product List Test',
            'ref': 'UF PLIST',
            'type': 'list',
            'standard_list_ok': True,  # do not miss it for sync test
        }
        plist_id, plist_domain = self._create_data_record(self.hq1,
            'product.list', vals, domain_exclude=['standard_list_ok', ],
            check_batch=check_batch)

        # product list line
        product_test_code = 'ADAPCART02-'
        domain = [('default_code', '=', product_test_code)]
        product_ids = self.hq1.get('product.product').search(domain)
        if not product_ids:
            msg = "can not found test product '%s' :: %s" % (product_test_code,
                self.hq1.colored_name, )
            raise MasterDataSyncTestException(msg)

        # unique comment per list id/lineid/product code (for search)
        comment = "%d/%d/%s UF Product List Line Test" % (plist_id,
            product_ids[0], product_test_code, )
        vals = {
            'name': product_ids[0],
            'list_id': plist_id,
            'comment': comment,
        }
        self._create_data_record(self.hq1, 'product.list.line', vals,
            domain_include=['comment', ], check_batch=check_batch,
            teardown_log=False)  # will be deleted by product list (header)

        self._sync_down_check(check_batch)

    def test_s1_tec_27(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_27

        - create an OC product (OC Product (Creator = ITC, ESC or HQ))
        - so here we create it from HQ
        - synchronize down from hq to coordo and project and check
        """
        def get_pnomenclature_id(nomen_name):
            """get product nomenclature id from name"""
            return get_id_from_name(self.hq1, 'product.nomenclature',
                nomen_name)

        check_batch = []

        # product list
        vals = {
            'default_code': 'UF_PRODUCT_TEST',
            'name': 'Unifield Product Test',
            'nomen_manda_0': get_pnomenclature_id('LOG'),
            'nomen_manda_1': get_pnomenclature_id('K - Log Kits'),
            'nomen_manda_2': get_pnomenclature_id('KCAM - Camps Kits'),
            'nomen_manda_3': get_pnomenclature_id('MISC - Miscellaneous'),
        }
        self._create_data_record(self.hq1, 'product.product', vals,
            domain_include=['default_code', 'name', ], check_batch=check_batch)

        self._sync_down_check(check_batch)

def get_test_class():
    return MasterDataSyncTest

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
