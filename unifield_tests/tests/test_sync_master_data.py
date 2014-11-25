#!/usr/bin/env python
# -*- coding: utf8 -*-
from __future__ import print_function
from unifield_test import UnifieldTest

import time


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

class MasterDataSyncTestException(Exception):
    pass


class MasterDataSyncTest(UnifieldTest):
    def setUp(self):
        self._ids = {}  # {'db_name': {'model': ids, }, }

    def _get_db_from_name(self, db_name):
        if self.hq1.db_name == db_name:
            return self.hq1
        elif self.c1.db_name == db_name:
            return self.c1
        elif self.p1.db_name == db_name:
            return self.p1
        raise MasterDataSyncTestException('database not found')

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

    def _unlink_model_ids(self, model_name):
        """
        unlink in h1/c1/p1 for model logged added data test records
        :type model_name: str
        """
        for db_name in self._ids:
            db = self._get_db_from_name(db_name)
            ids = self._get_ids(db, model_name)
            if ids:
                db.get(model_name).unlink(ids)

    def _check_data_set_on_db(self, db, check_batch):
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
                count = len(ids)
            else:
                count = 0

            self.assertNotEquals(
                count, 0,
                "'UF' '%s' entry not found on %s" % (model, db.colored_name, )
            )
            self.assertEqual(
                count, 1,
                "There is more than 1 'UF' '%s' entry on %s :: %s" % (model,
                    db.colored_name, count, )
            )

    def _create_data_record(self, db, model_name, vals, domain_include=None,
        domain_exclude=[]):
        """
        for a model create a record in hq using vals and create domain
        :param db: db
        :type db: object
        :type model_name: str
        :param vals: vals
        :type vals: dict
        :param domain_include: see dfv() include param
        :param domain_exclude: ee dfv() exclude param
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
        self._set_ids(self.hq1, model_name, id)
        return (id, domain, )

    def _sync_down_check(self, check_batch, db=None):
        """
        from hq sync down check batch to c1 then p1
        :param check_batch: see _check_data_set_on_db() check_batch param
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
            self._check_data_set_on_db(self.c1, check_batch)

        # p1 sync down and check check (from hq or c1 sync down)
        self.synchronize(self.p1)
        self._check_data_set_on_db(self.p1, check_batch)

    def tearDown(self):
        self._unlink_model_ids('res.country.state')
        self._unlink_model_ids('res.country')

    def test_s1_tec_21(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_21

        - create a new country and country state in hq
        - synchronize down from hq to coordo and project
        - check if the country and the country state have been well sync down
        """
        # country
        vals = {
            'code': 'UF',
            'name': 'Unifield Country Test',
        }
        country_id, country_domain = self._create_data_record(self.hq1,
            'res.country', vals)

        # country state
        hq_state_obj = self.hq1.get('res.country.state')
        vals = {
            'code': 'UF',
            'name': 'Unifield Country State Test',
            'country_id': country_id,
        }
        id, state_domain = self._create_data_record(self.hq1,
            'res.country.state', vals, domain_exclude=['country_id', ])

        check_batch = [
            ('res.country', country_domain),
            ('res.country.state', state_domain),
        ]
        self._sync_down_check(check_batch)

    def test_s1_tec_22(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_22

        - create an uom category and an uom in hq
        - synchronize down from hq to coordo and project
        - check if the uom categ and the uom have been well sync down
        """
        # uom category
        vals = {
            'name': 'Unifield Uom Category Test'
        }
        categ_id, uom_categ_domain = self._create_data_record(self.hq1,
            'product.uom.categ', vals)

        # uom
        vals = {
            'name': 'UF Uom Test',
            'category_id': categ_id,
            'factor': 1.,
            'factor_inv': 1.,
            'rounding': 1.,
            'uom_type': 'reference',
        }
        id, uom_domain = self._create_data_record(self.hq1, 'product.uom', vals,
            domain_include=['name', 'uom_type', ])

        check_batch = [
            ('product.uom.categ', uom_categ_domain),
            ('product.uom', uom_domain),
        ]
        self._sync_down_check(check_batch)

    def test_s1_tec_23(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_23

        - create a product nomenclature in hq
        - synchronize down from hq to coordo and project and check
        """
        vals = {
            'name': 'Unifield Nomenclature Test',
        }
        id, domain = self._create_data_record(self.hq1,
            'product.nomenclature', vals)

        check_batch = [
            ('product.nomenclature', domain),
        ]
        self._sync_down_check(check_batch)

    def test_s1_tec_24(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_24

        - create a product category in hq
        - synchronize down from hq to coordo and project and check
        """
        vals = {
            'name': 'Unifield Product Category Test',
            'type': 'normal',
        }
        id, domain = self._create_data_record(self.hq1,
            'product.category', vals)

        check_batch = [
            ('product.category', domain),
        ]
        self._sync_down_check(check_batch)

    def test_s1_tec_25(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_25

        - create a product justification code in hq
        - create a product asset type in hq
        - synchronize down from hq to coordo and project and check
        """
        # product justication code
        vals = {
            'code': 'UF',
            'description': 'Unifield Justification Code Test',
        }
        id, just_code_domain = self._create_data_record(self.hq1,
            'product.justification.code', vals)

        # product asset type
        vals = {
            'name': 'Unifield Asset Type Test',
        }
        id, asset_type_domain = self._create_data_record(self.hq1,
            'product.asset.type', vals)

        check_batch = [
            ('product.justification.code', just_code_domain),
            ('product.asset.type', asset_type_domain),
        ]
        self._sync_down_check(check_batch)

def get_test_class():
    return MasterDataSyncTest

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
