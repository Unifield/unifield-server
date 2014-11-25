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
            if ids:
                self._set_ids(db, model, ids)
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

    def tearDown(self):
        self._unlink_model_ids('res.country.state')
        self._unlink_model_ids('res.country')

    def test_s1_tec_21(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_21

        - create a new country and country state on HQ database
        - synchronize down from hq to coordo and project
        - check if the country and the country state have been well sync down
        """
        # country
        hq_country_obj = self.hq1.get('res.country')
        vals = {
            'code': 'UF',
            'name': 'Unifield Country Test',
        }
        country_domain = dfv(vals)
        if hq_country_obj.search(country_domain):
            country_id = hq_country_obj.search(country_domain)[0]
        else:
            country_id = hq_country_obj.create(vals)
        self._set_ids(self.hq1, 'res.country', country_id)

        # country state
        hq_state_obj = self.hq1.get('res.country.state')
        vals = {
            'code': 'UF',
            'name': 'Unifield Country State Test',
            'country_id': country_id,
        }
        state_domain = dfv(vals, exclude='country_id')
        if hq_state_obj.search(state_domain):
            pass
        else:
            state_id = hq_state_obj.create(vals)
            self._set_ids(self.hq1, 'res.country.state', state_id)

        # sync down and check
        self.synchronize(self.hq1)

        check_batch = [
            ('res.country', country_domain),
            ('res.country.state', state_domain),
        ]

        # c1 check
        self.synchronize(self.c1)
        self._check_data_set_on_db(self.c1, check_batch)

        # p1 check
        self.synchronize(self.p1)
        self._check_data_set_on_db(self.p1, check_batch)

    def test_s1_tec_22(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_22

        - create an uom category and an uom on hq
        - synchronize down from hq to coordo and project
        - check if the uom categ and the uom have been well sync down
        """
        # uom category
        hg_puomc_obj = self.hq1.get('product.uom.categ')
        vals = {
            'name': 'Unifield Uom Category Test'
        }
        uom_categ_domain = dfv(vals)
        if hg_puomc_obj.search(uom_categ_domain):
            categ_id = hg_puomc_obj.search(uom_categ_domain)[0]
        else:
            categ_id = hg_puomc_obj.create(vals)
        self._set_ids(self.hq1, 'product.uom.categ', categ_id)

        # uom
        hg_puom_obj = self.hq1.get('product.uom')
        vals = {
            'category_id': categ_id,
            'factor': 1.,
            'factor_inv': 1.,
            'name': 'UF Uom Test',
            'rounding': 1.,
            'uom_type': 'reference',
        }
        uom_domain = dfv(vals, include=['name', 'uom_type', ])
        if hg_puom_obj.search(uom_domain):
            uom_id = hg_puom_obj.search(uom_domain)[0]
        else:
            uom_id = hg_puom_obj.create(vals)
        self._set_ids(self.hq1, 'product.uom', uom_id)

        # sync down and check
        self.synchronize(self.hq1)

        check_batch = [
            ('product.uom.categ', uom_categ_domain),
            ('product.uom', uom_domain),
        ]

        # c1 check
        self.synchronize(self.c1)
        self._check_data_set_on_db(self.c1, check_batch)

        # p1 check
        self.synchronize(self.p1)
        self._check_data_set_on_db(self.p1, check_batch)

def get_test_class():
    return MasterDataSyncTest

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
