#!/usr/bin/env python
# -*- coding: utf8 -*-
from __future__ import print_function
from unifield_test import UnifieldTest

import time


def dfd(d):
    """
    Domain from dictionary

    Create a domain from a data dictionary
    :param d: Dictionary that contains data
    :return: A list of tuples like [('op1', 'operator', 'op2')]
    """
    return [(x[0], '=', x[1]) for x in d.iteritems()]


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

    def tearDown(self):
        self._unlink_model_ids('res.country.state')
        self._unlink_model_ids('res.country')

    def test_s1_tec_21(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_21

        Create a new country and country state on HQ database.
        Synchronize between the HQ, Coordination and project.
        Check if the country and the country state have been synchronized
        on Coordination and project database.
        """
        hq_country_obj = self.hq1.get('res.country')
        hq_state_obj = self.hq1.get('res.country.state')

        country_data = {
            'code': 'UF',
            'name': 'Unifield Country Test',
        }
        country_domain = dfd(country_data)

        if hq_country_obj.search(country_domain):
            country_id = hq_country_obj.search(country_domain)[0]
        else:
            country_id = hq_country_obj.create(country_data)
        self._set_ids(self.hq1, 'res.country', country_id)

        state_data = {
            'code': 'UF',
            'name': 'Unifield Country State Test',
            'country_id': country_id,
        }
        state_domain = dfd(state_data)
        state_data_sync = state_data.copy()
        del state_data_sync['country_id']
        state_domain_sync = dfd(state_data_sync)

        if hq_state_obj.search(state_domain):
            pass
        else:
            state_id = hq_state_obj.create(state_data)
            self._set_ids(self.hq1, 'res.country.state', state_id)

        # Launch synchronization on HQ1
        self.synchronize(self.hq1)

        def check_on_db(db):
            ids = db.get('res.country').search(country_domain)
            if ids:
                self._set_ids(db, 'res.country', ids)
                nb_countries = len(ids)
            else:
                nb_countries = 0
            self.assertNotEquals(
                nb_countries, 0,
                "'UF' country not found on %s" % db.colored_name,
            )
            self.assertEqual(
                nb_countries, 1,
                "There is more than 1 'UF' countries on %s :: %s" % (
                    db.colored_name,
                    nb_countries,
                )
            )

            ids = db.get('res.country.state').search(state_domain_sync)
            if ids:
                self._set_ids(db, 'res.country.state', ids)
                nb_states = len(ids)
            else:
                nb_states = 0
            self.assertNotEquals(
                nb_states, 0,
                "'UF' states not found on %s" % db.colored_name,
            )
            self.assertEqual(
                nb_states, 1,
                "There is more than 1 'UF' states on %s :: %s" % (
                    db.colored_name,
                    nb_states,
                )
            )

        # Checks on C1
        self.synchronize(self.c1)
        check_on_db(self.c1)

        # Checks on P1
        self.synchronize(self.p1)
        check_on_db(self.p1)

def get_test_class():
    return MasterDataSyncTest

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
