#!/usr/bin/env python
# -*- coding: utf8 -*-
from __future__ import print_function
from unifield_test import UnifieldTest

import time
from datetime import datetime

# set it to True to simulate a sync P1 sync down failure for any test
#TEST_THE_TEST = True
TEST_THE_TEST = False

PRODUCT_TEST_CODE = 'ADAPCART02-'


def dfv(vals, include=None, exclude=None):
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
    if exclude is None:
        exclude = []
    return [(x[0], '=', x[1]) for x in vals.iteritems() if x[0] not in exclude]

def are_same_db(db1, db2):
    return db1.db_name == db2.db_name or False

def date_now_field_val():
    return time.strftime("%Y-%m-%d")

def date_end_fy_val():
    return "%d-12-31" % (datetime.now().year, )


class MasterDataSyncTestException(Exception):
    pass


class MasterDataSyncTest(UnifieldTest):
    def setUp(self):
        # meta of generated test records
        self._ids_unlink_off = False
        self._ids = {}  # {'db_name': [(model, ids), ], }

    def tearDown(self):
        # delete auto generated test records
        self._record_unlink_all_generated_ids()

    # TOOLS

    def _get_db_from_name(self, db_name):
        if self.hq1.db_name == db_name:
            return self.hq1
        elif self.c1.db_name == db_name:
            return self.c1
        elif self.p1.db_name == db_name:
            return self.p1
        raise MasterDataSyncTestException("'%s' database not found" % (
            db_name, ))

    # AUTO GENERATED RECORD LOG

    def _record_set_ids(self, db, model_name, ids, _insert=True):
        """
        log an added data test records (to delete in tearDown)
        by db and by model name
        :type db: object
        :type model_name: str
        :type ids: int/long/list
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        # insert in log order to delete from the last (cascade dependancies)
        if _insert:
            self._ids.setdefault(db.db_name, []).insert(0, (model_name, ids))
        else:
            self._ids.setdefault(db.db_name, []).append((model_name, ids))

    def _record_unlink_db_generated_ids(self, db_name):
        """
        unlink all test data generated records in target db
        :type db_name: target db name
        """
        if self._ids_unlink_off:
            return
        db = self._get_db_from_name(db_name)
        for model_name, ids in self._ids.get(db_name, []):
            if ids:
                model = db.get(model_name)
                ids = model.search([('id', 'in', ids)])
                if ids and isinstance(ids, list) and len(ids) > 0:
                    model.unlink(ids)

    def _record_unlink_all_generated_ids(self):
        if self._ids_unlink_off:
            return
        # delete auto generated test records
        for db_name in self._ids:  # {'db_name': [(model, ids), ], }
            self._record_unlink_db_generated_ids(db_name)
        self._ids = {}

    def _record_create(self, db, model_name, vals, domain_include=None,
        domain_exclude=None, domain_extra=None, check_batch=None,
        teardown_log=True):
        """
        for a model create a record in hq using vals
        do never use in domain fields that are changed by sync (that are not
        const values sync speaking)
        :param db: db
        :type db: object
        :type model_name: str
        :param vals: vals
        :type vals: dict
        :param domain_include: see dfv() include param
        :param domain_exclude: ee dfv() exclude param
        :param domain_extra: an additional domain to add to the build domain
        :param domain_extra: list
        :param check_batch: [(model, domain), ] if provided auto check batch is
            generated here (see _sync_check_data_set_on_db())
        :type check_batch: list
        :param teardown_log: True to log 'generated record is to delete in
            tearDown()' (default True)
        :type teardown_log: bool
        :return: (id, domain)
        :rtype: tuple
        """
        def check_field_in_vals(field_name):
            if not field_name in vals:
                msg = "%s :: '%s' :: '%s' :: field '%s' not in vals :: %s" % (
                    db.colored_name, model_name, domain_type, field_name, vals, )
                raise MasterDataSyncTestException(msg)
        if domain_include:
            domain_type = 'domain_include'
            map(check_field_in_vals, domain_include)
        if domain_exclude is not None:
            domain_type = 'domain_exclude'
            map(check_field_in_vals, domain_exclude)

        model_obj = db.get(model_name)
        domain = dfv(vals, include=domain_include, exclude=domain_exclude)
        ids = model_obj.search(domain)
        if ids:
            id = ids[0]
        else:
            id = model_obj.create(vals)
        if teardown_log:
            self._record_set_ids(db, model_name, id)
        if check_batch is not None:
            # insert to keep record cascade dependencies when auto deleting
            # tests records
            if domain_extra is not None:
                domain += domain_extra
            check_batch.insert(0, (model_name, domain, ))
        return (id, domain, )

    def _record_copy(self, db, model_name, id, domain_include,
            defaults=None, check_batch=None, teardown_log=True):
        """
        copy a record in db
        :param db: db
        :type db: object
        :type model_name: str
        :param defaults: defaults
        :type defaults: dict
        :param domain_include: fields from defaults to include in domain for
            check battch (see dfv() include param)
        :param check_batch: [(model, domain), ] if provided auto check batch is
            generated here (see _sync_check_data_set_on_db())
        :type check_batch: list
        :param teardown_log: True to log 'generated record is to delete in
            tearDown()' (default True)
        :type teardown_log: bool
        :return: (id, domain)
        :rtype: tuple
        """
        new_id = db.get(model_name).copy(id, defaults)
        if teardown_log:
            self._record_set_ids(db, model_name, new_id)
        domain = dfv(defaults, include=domain_include)
        if check_batch is not None:
            # insert to keep record cascade dependencies when auto deleting
            # tests records
            check_batch.insert(0, (model_name, domain, ))
        return (new_id, domain, )
    # SYNC TOOLS

    def _sync_check_data_set_on_db(self, db, check_batch, inverse=False):
        """
        check in db that for model/domain entries there is one data set entry
        do never use in domain fields that are changed by sync (that are not
        const values sync speaking)
        :type db: object
        :param check_batch: [(model, domain), ]
        :param inverse: if True the record should not be sync down!
        :type inverse: bool
        """
        for model, domain in check_batch:
            ids = db.get(model).search(domain)
            count = len(ids) if ids else 0
            if ids:
                # log ids to remove in tearDown
                self._record_set_ids(db, model, ids, _insert=False)  # _insert=False check batch sorted by most child records
                if inverse:
                    # assert will be raised so delete test records
                    self._record_unlink_all_generated_ids()
            else:
                if not inverse:
                    # assert will be raised so delete previous test records
                    self._record_unlink_all_generated_ids()

            if not inverse:
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
            else:
                # record should not be sync down
                msg = "Should not be synced ::" \
                    " 'UF' '%s' entry found on %s :: %s"
                self.assertEquals(
                    count, 0,
                    msg % (model, db.colored_name, domain, )
                )

    def _sync_down_check(self, check_batch, db=None, last_db=None,
        inverse=False):
        """
        from hq sync down check batch to c1 then p1
        :param check_batch: see _sync_check_data_set_on_db() check_batch param
        :type check_batch: list
        :param db: db
        :type db: object
        :param last_db: optional last db to sync (c1 not to sync p1)
        :type last_db: object/None
        :param inverse: if True the record should not be sync down!
        :type inverse: bool
        """
        if db is None:
            db = self.hq1
        if are_same_db(self.p1, db):
            raise MasterDataSyncTestException('can not sync down from project')

        # sync down and check
        self.synchronize(db)

        if are_same_db(self.hq1, db):
            # c1 sync down and check
            global TEST_THE_TEST
            if not TEST_THE_TEST:  # volontary miss the sync to test the test
                self.synchronize(self.c1)
            # will volontary fail if above sync not done
            self._sync_check_data_set_on_db(self.c1, check_batch,
                inverse=inverse)
            if last_db is not None and are_same_db(last_db, self.c1):
                return

        # p1 sync down and check (from hq or c1 sync down)
        self.synchronize(self.p1)
        self._sync_check_data_set_on_db(self.p1, check_batch, inverse=inverse)

    def _sync_up_check(self, check_batch, db=None, last_db=None, inverse=False):
        """
        from hq sync down check batch to c1 then p1
        :param check_batch: see _sync_check_data_set_on_db() check_batch param
        :type check_batch: list
        :param db: db
        :type db: object
        :param last_db: optional last db to sync (c1 not to sync hq1)
        :type last_db: object/None
        :param inverse: if True the record should not be sync down!
        :type inverse: bool
        """
        if db is None:
            db = self.p1
        if are_same_db(self.hq1, db):
            raise MasterDataSyncTestException('can not sync up from hq')

        # sync down and check
        self.synchronize(db)

        if are_same_db(self.p1, db):
            # c1 sync up and check
            global TEST_THE_TEST
            if not TEST_THE_TEST:  # volontary miss the sync to test the test
                self.synchronize(self.c1)
            # will volontary fail if above sync not done
            self._sync_check_data_set_on_db(self.c1, check_batch,
                inverse=inverse)
            if last_db is not None and are_same_db(last_db, self.c1):
                return

        # hq1 sync up and check (from hq or c1 sync down)
        self.synchronize(self.hq1)
        self._sync_check_data_set_on_db(self.hq1, check_batch, inverse=inverse)

    # DATA TOOLS
    def _data_get_company_id(self, db):
        """
        :param db: db
        :return: company id
        :rtype: int
        """
        user = db.get('res.users').browse(1)
        return user.company_id.id if user else False

    def _data_get_id_from_name(self, db, model_name, res_name,
        name_field='name'):
        """
        get record id from model and record name
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

    def _data_create_product(self, db, code, name, vals=None,
        domain_extra=None, check_batch=None):
        """
        create a product
        :param db: db
        :param code: product code
        :param name: product name
        :param vals: optional additional vals to set
        :type vals: dict
        :type domain_extra: see _record_create
        :type check_batch: see _record_create
        :return: (id, domain)
        :rtype: tuple
        """
        def get_pnomenclature_id(nomen_name):
            """get product nomenclature id from name"""
            return self._data_get_id_from_name(db, 'product.nomenclature',
                nomen_name)

        product_vals = {
            'default_code': code,
            'name': name,
            'nomen_manda_0': get_pnomenclature_id('LOG'),
            'nomen_manda_1': get_pnomenclature_id('K - Log Kits'),
            'nomen_manda_2': get_pnomenclature_id('KCAM - Camps Kits'),
            'nomen_manda_3': get_pnomenclature_id('MISC - Miscellaneous'),
        }
        if vals is not None:
            product_vals.update(vals)
        return self._record_create(db, 'product.product', product_vals,
            domain_include=['default_code', ],
            domain_extra=domain_extra, check_batch=check_batch)

    # TEST FUNCTIONS

    def _test_standard_product_list(self, db, sync_up=False, inverse=False):
        """
        - create a standard product list in db
        - synchronize down/up and check
        """
        if sync_up:
            if are_same_db(db, self.hq1):
                raise MasterDataSyncTestException(
                    'can not test sync up product list from hq')
        else:
            if are_same_db(db, self.p1):
                raise MasterDataSyncTestException(
                    'can not test sync down product list from project')

        check_batch = []

        # product list
        vals = {
            'name': 'Unifield Product List Test',
            'ref': 'UF PLIST',
            'type': 'list',
            'standard_list_ok': True,  # do not miss it for sync test
        }
        plist_id = self._record_create(db,
            'product.list', vals, domain_exclude=['standard_list_ok', ],
            check_batch=check_batch)[0]

        # product list line
        # unique comment per list id/lineid/product code (for search)
        product_id = self._data_get_id_from_name(db, 'product.product',
            PRODUCT_TEST_CODE, name_field='default_code')
        comment = "%d/%d/%s UF Product List Line Test" % (plist_id,
            product_id, PRODUCT_TEST_CODE, )
        vals = {
            'name': product_id,
            'list_id': plist_id,
            'comment': comment,
        }
        self._record_create(db, 'product.list.line', vals,
            domain_include=['comment', ], check_batch=check_batch,
            teardown_log=False)  # will be deleted by product list (header)

        if sync_up:
            self._sync_up_check(check_batch, db=db, inverse=inverse)
        else:
            self._sync_down_check(check_batch, db=db, inverse=inverse)

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
        country_id = self._record_create(self.hq1,
            'res.country', vals, check_batch=check_batch)[0]

        # country state
        hq_state_obj = self.hq1.get('res.country.state')
        vals = {
            'code': 'UF',
            'name': 'Unifield Country State Test',
            'country_id': country_id,
        }
        self._record_create(self.hq1, 'res.country.state', vals,
            domain_exclude=['country_id', ], check_batch=check_batch)

        self._sync_down_check(check_batch)

    def test_s1_tec_22(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_22

        - create an uom category and an uom in hq
        - synchronize down from hq to coordo and project
        - check if the uom categ and the uom have been well sync down
        """
        db = self.hq1
        check_batch = []

        # uom category
        vals = {
            'name': 'Unifield Uom Category Test'
        }
        categ_id, domain = self._record_create(db, 'product.uom.categ', vals,
            check_batch=check_batch)

        # uom
        vals = {
            'name': 'UF Uom Test',
            'category_id': categ_id,
            'factor': 1.,
            'factor_inv': 1.,
            'rounding': 1.,
            'uom_type': 'reference',
        }
        self._record_create(db, 'product.uom', vals,
            domain_include=['name', 'uom_type', ], check_batch=check_batch)

        self._sync_down_check(check_batch)

    def test_s1_tec_23(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_23

        - create a product nomenclature in hq
        - synchronize down from hq to coordo and project and check
        """
        db = self.hq1
        check_batch = []

        vals = {
            'name': 'Unifield Nomenclature Test',
        }
        self._record_create(db, 'product.nomenclature', vals,
            check_batch=check_batch)

        self._sync_down_check(check_batch)

    def test_s1_tec_24(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_24

        - create a product category in hq
        - synchronize down from hq to coordo and project and check
        """
        db = self.hq1
        check_batch = []

        vals = {
            'name': 'Unifield Product Category Test',
            'type': 'normal',
        }
        self._record_create(db, 'product.category', vals,
            check_batch=check_batch)

        self._sync_down_check(check_batch)

    def test_s1_tec_25(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_25

        - create a product justification code in hq
        - create a product asset type in hq
        - synchronize down from hq to coordo and project and check
        """
        db = self.hq1
        check_batch = []

        # product justication code
        vals = {
            'code': 'UF',
            'description': 'Unifield Justification Code Test',
        }
        self._record_create(db, 'product.justification.code', vals,
            check_batch=check_batch)

        # product asset type
        vals = {
            'name': 'Unifield Asset Type Test',
        }
        self._record_create(db, 'product.asset.type', vals,
            check_batch=check_batch)

        self._sync_down_check(check_batch)

    def test_s1_tec_26(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_26

        - create a standard product list in hq
        - synchronize down from hq to coordo and project and check
        """
        self._test_standard_product_list(self.hq1)

    def test_s1_tec_27(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_27

        - create an OC product (OC Product (Creator = ITC, ESC or HQ))
        - so here we create it from HQ
        - synchronize down from hq to coordo and project and check
        """
        db = self.hq1
        check_batch = []

        # product
        self._data_create_product(db, 'UF_PRODUCT_TEST',
            'Unifield Product Test', check_batch=check_batch)

        self._sync_down_check(check_batch)

    def test_s1_tec_45(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_45

        - create a supplier catalogue and version in coord
        - check sync in proj (unless ESC)

        2 cases:
        1) 1 catalogue not ESC should sync in proj
        2) 1 catalogue ESC should NOT sync in proj
        """
        db = self.c1
        def create_catalogue_line(comment_prefix, line_check_batch):
            line_vals = {
                'catalogue_id': catalogue_id,
                'line_number': 1,
                'product_id': product_id,
                'line_uom_id': self._data_get_id_from_name(db, 'product.uom',
                    'PCE'),
                'min_qty': 10.,
                'unit_price': 1.,
                'comment': "%d/1 %s Unifield Supplier Catalogue Line TEST" % (
                    catalogue_id, comment_prefix, ),
            }
            return self._record_create(db, 'supplier.catalogue.line',
                line_vals, domain_include=['line_number', 'comment', ],
                check_batch=line_check_batch)[0]

        comp_ccy_id = db.browse('res.users', 1).company_id.currency_id.id

        product_id = self._data_get_id_from_name(db, 'product.product',
            PRODUCT_TEST_CODE, name_field='default_code')

        # 1) 1 catalogue not ESC should sync in proj (with 'Local Market')
        check_batch = []

        # create catalog
        partner_id = self._data_get_id_from_name(db, 'res.partner',
            'Local Market')
        vals = {
            'name': 'Unifield Supplier Catalogue TEST',
            'state': 'confirmed',
            'partner_id': partner_id,
            'period_from': date_now_field_val(),
            #'period_to': date_end_fy_val(),
            'currency_id': comp_ccy_id,
        }
        # NOTE: catalogue synced in P1 as inactive and draft
        catalogue_domain_include = ['name', 'period_from', ]
        catalogue_domain_extra = [
            ('state', '=', 'draft'),
            ('active', '!=', True),
        ]
        catalogue_id = self._record_create(db, 'supplier.catalogue', vals,
            domain_include=['name', 'period_from', ],
            domain_extra=catalogue_domain_extra,
            check_batch=check_batch)[0]

        # create catalog line
        # FIXME: RPCError: 'NoneType' object has no attribute 'copy'
        #create_catalogue_line('NO ESC', check_batch)

        self._sync_down_check(check_batch, db=db)

        # 2) 1 catalogue ESC should NOT sync in proj
        check_batch = []

        # create ESC partner (from 'Local Market' market copy)
        defaults = {
            'name': 'Unifield ESC Supplier Test',
            'ref': 'UF_ESC_SUPPLIER',
            'partner_type': 'esc',
            'zone': 'international',
        }
        esc_partner_id = self._record_copy(db, 'res.partner', partner_id,
            domain_include=defaults.keys(), defaults=defaults,
            check_batch=check_batch)[0]

        # create catalog
        vals = {
            'name': 'Unifield ESC Supplier Catalogue TEST',
            'state': 'confirmed',
            'partner_id': esc_partner_id,
            'period_from': date_now_field_val(),
            #'period_to': date_end_fy_val(),
            'currency_id': comp_ccy_id,
        }
        self._record_create(db, 'supplier.catalogue', vals,
            domain_include=catalogue_domain_include,
            domain_extra=catalogue_domain_extra,
            check_batch=check_batch)

        # create catalog line
        # FIXME: RPCError: 'NoneType' object has no attribute 'copy'
        #create_catalogue_line('ESC', check_batch)

        # inverse=True: should not be sync down check!
        self._sync_down_check(check_batch, db=db, inverse=True)

    def test_s1_tec_46(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_46

        - create a product with a country restriction from coord
        - check sync in proj
        """
        def test_s1_tec_46_test_case(intermediate_sync):
            check_batch = []

            suffix = '_2' if intermediate_sync else ''

            # product
            product_id = self._data_create_product(db,
                'UF_PRODUCT_TEST' + suffix,
                'Unifield Product Test' + suffix, check_batch=check_batch)[0]
            if intermediate_sync:
                self._sync_down_check([], db=db)

            # country restriction
            prestrict_id = self._record_create(db, 'res.country.restriction',
                { 'name': "Unifield Product Restriction Test" + suffix, },
                domain_include=['name', ], check_batch=check_batch)[0]
            vals = {
                'country_restriction': prestrict_id,
                'restricted_country': True,
            }
            db.get('product.product').write([product_id], vals)

            self._sync_down_check(check_batch, db=db)

        db = self.c1

        # case 1 create the product, do the country restriction then sync
        test_s1_tec_46_test_case(False)

        # case 2 create the product, sync, do the country restriction sync again
        test_s1_tec_46_test_case(True)

    def test_s1_tec_47(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_47

        - create a standard product list in coord
        - synchronize down in project and check
        """
        self._test_standard_product_list(self.c1)

    def test_s1_tec_48(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_48

        - create a product in coord (product in coord <=> mission product)
        - synchronize down in project and check
        """
        db = self.c1
        check_batch = []

        # product
        self._data_create_product(db, 'UF_PRODUCT_TEST',
            'Unifield Product Test', check_batch=check_batch)

        self._sync_down_check(check_batch)

    def test_s1_tec_76(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_76

        - create a product with a country restriction from project
        - check synced up in coord
        """
        def test_s1_tec_76_test_case(intermediate_sync):
            check_batch = []

            suffix = '_2' if intermediate_sync else ''

            # product
            product_id = self._data_create_product(db,
                'UF_PRODUCT_TEST' + suffix,
                'Unifield Product Test' + suffix, check_batch=check_batch)[0]
            if intermediate_sync:
                self._sync_up_check([], last_db=last_db)

            # country restriction
            prestrict_id = self._record_create(db, 'res.country.restriction',
                { 'name': "Unifield Product Restriction Test" + suffix, },
                domain_include=['name', ], check_batch=check_batch)[0]
            vals = {
                'country_restriction': prestrict_id,
                'restricted_country': True,
            }
            db.get('product.product').write([product_id], vals)

            self._sync_up_check(check_batch, last_db=last_db)

        db = self.p1
        last_db = self.c1

        # case 1 create the product, do the country restriction then sync
        test_s1_tec_76_test_case(False)

        # case 2 create the product, sync, do the country restriction sync again
        #test_s1_tec_76_test_case(True)

    def test_s1_tec_77(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_77

        - create a standard product list in prof
        - synchronize up in project, hq and check SHOULD NOT BE SYNCED in both
        """
        self._test_standard_product_list(self.p1, sync_up=True, inverse=True)

    def test_s1_tec_78(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_78

        - create mission product in coordo (mission <=> creator = 'local')
        - synchronize SHOULD NOT BE SYNCED
        """
        db = self.c1
        check_batch = []

        vals = {
            'international_status': self._data_get_id_from_name(db,
                'product.international.status', 'Local'),
        }
        self._data_create_product(db, 'UF_PRODUCT_TEST',
            'Unifield Product Test', vals=vals, check_batch=check_batch)

        self._sync_down_check(check_batch, db=db)  # should sync (mission = coord + projects)
        self._sync_up_check(check_batch, db=db, inverse=True)  # shoud not sync (hq not in mission sector)

    def test_s1_tec_79(self):
        """
        python -m unittest tests.test_sync_master_data.MasterDataSyncTest.test_s1_tec_79

        - create a tax code and an account tax in COORD
        - synchronize SHOULD NOT BE SYNCED
        """
        db = self.c1
        check_batch = []
        cpy_id = self._data_get_company_id(db)

        vals = {
            'name': 'Unifield Tax Code Test',
            'company_id': cpy_id,
            'sign': 1.,
        }
        tax_code_id = self._record_create(db, 'account.tax.code', vals,
            domain_include=['name', ], check_batch=check_batch)[0]

        vals = {
            'name': 'Unifield Tax Test',
            'company_id': cpy_id,
            'tax_code_id': tax_code_id,
            'amount': 0.2,
            'applicable_type': 'true',
            'sequence': 0,
            'type': 'percent',
            'type_tax_use': 'sale',
        }
        self._record_create(db, 'account.tax', vals,
            domain_exclude=['company_id', 'tax_code_id', ],
            check_batch=check_batch)

        # should not sync
        self._sync_down_check(check_batch, db=db, inverse=True)
        self._sync_up_check(check_batch, db=db, inverse=True)

def get_test_class():
    return MasterDataSyncTest

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
