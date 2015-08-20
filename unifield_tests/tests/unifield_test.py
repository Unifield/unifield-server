#!/usr/bin/env python
# -*- coding: utf8 -*-
'''
Created on Feb 28, 2014

@author: qt and vg
'''
from __future__ import print_function
import unittest
from connection import XMLRPCConnection as XMLConn
from connection import UnifieldTestConfigParser
from colors import TerminalColors
from datetime import datetime
from datetime import timedelta
import time
import random
from uuid import uuid4


class UnifieldTestException(Exception):
    pass

class UnifieldTest(unittest.TestCase):
    '''
    Main test class for Unifield tests using TestCase and Openerplib as main inheritance
    @var sync: contains Synchro Server oerplib connection
    @var hq1: same as sync for HQ1 DB
    @var c1: same as sync for HQ1C1 DB
    @var p1: same as sync for HQ1C1P1 DB
    @var db: contains the list of DB connections
    @var test_module_name: name of the module used to create extended table for tests
    @var test_module_obj_name: name of the OpenERP object to use to access to extended table
    '''
    # global variable
    db = {}
    test_module_name = 'unifield_tests'
    test_module_obj_name = 'unifield.test'
    already_loaded = False

    # FIXME/TODO: Make unittest.TestCase inherit from oerplib.error class because of RPCError that could be raised by unittest.TestCase

    def _addConnection(self, db_suffix, name):
        '''
        Add new connection
        '''
        con = XMLConn(db_suffix)
        setattr(self, name, con)
        self.db[name] = con
        # Set colors
        colors = self.colors
        database_display = colors.BRed + '[' + colors.Color_Off + name.center(6) + colors.BRed + ']' + colors.Color_Off
        self.db[name].colored_name = database_display

    def _hook_db_process(self, name, database):
        '''
        Some process to do for each database (except SYNC DB)
        '''
        return True

    def __init__(self, *args, **kwargs):
        # Default behaviour
        super(UnifieldTest, self).__init__(*args, **kwargs)
        # Prepare some values
        c = UnifieldTestConfigParser()
        self.config = c.read()
        self._db_prefix = c.get('DB', 'db_prefix')
        self._db_instance_prefix = c.get('DB', 'instance_prefix') or False
        tempo_mkdb = c.getboolean('DB', 'tempo_mkdb')
        db_suffixes = ['SYNC_SERVER', 'HQ1', 'HQ1C1', 'HQ1C1P1']
        names = ['sync', 'hq1', 'c1', 'p1']
        if not tempo_mkdb:
            db_suffixes = ['SYNC_SERVER', 'HQ_01', 'COORDO_01', 'PROJECT_01']
        # Check Remote warehouse and complete old params
        remote_warehouse = c.get('DB', 'RW') or False
        self.is_remote_warehouse = False
        if remote_warehouse:
            self.is_remote_warehouse = True
        self.is_remote_warehouse = False
        # TODO: Check coordo level (c2 for 'HQ1C2')
        # Check project level
        p_level = c.get('DB', 'project_level') or '1'
        p_level = int(p_level)
        if p_level > 1:
            levels = range(2, p_level + 1)
            db_suffixes += [ 'HQ1C1P%d' % (l, ) for l in levels ]
            names += [ 'p1%d' % (l, ) for l in levels ]
            # TODO: p21 for 'HQ1C2P1', p22 for 'HQ1C2P2'
        # instance suffixes except sync server
        self._instances_suffixes = list(db_suffixes)
        self._instances_suffixes.remove('SYNC_SERVER')
        # Other values
        colors = TerminalColors()
        self.colors = colors
        # Keep each database connection
        for db_tuple in zip(db_suffixes, names):
            self._addConnection(db_tuple[0], db_tuple[1])
        # Add remote warehouse
        if remote_warehouse:
            self._addConnection(remote_warehouse, 'rw')
        # For each database, check that unifield_tests module is loaded
        #+ If not, load it.
        #+ Except if the database is sync one
        if UnifieldTest.already_loaded:
            return
        for database_name in self.db:
            if database_name == 'sync':
                continue
            database = self.db.get(database_name)
            module_obj = database.get('ir.module.module')
            m_ids = module_obj.search([('name', '=', self.test_module_name)])
            database_display = database.colored_name
            for module in module_obj.read(m_ids, ['state']):
                state = module.get('state', '')
                if state == 'uninstalled':
                    print (database_display + ' [' + colors.BYellow + 'UP'.center(4) + colors.Color_Off + '] Module %s' % (self.test_module_name))
                    module_obj.button_install([module.get('id')])
                    database.get('base.module.upgrade').upgrade_module([])
                elif state in ['to upgrade', 'to install']:
                    print (database_display + ' [' + colors.BYellow + 'UP'.center(4) + colors.Color_Off + '] Module %s' % (self.test_module_name))
                    database.get('base.module.upgrade').upgrade_module([])
                elif state in ['installed']:
                    print (database_display + ' [' + colors.BGreen + 'OK'.center(4) + colors.Color_Off + '] Module %s' % (self.test_module_name))
                    pass
                else:
                    raise EnvironmentError(' Wrong module state: %s' % (state or '',))
            # Some processes after instanciation for this database
            self._hook_db_process(database_name, database)
        UnifieldTest.already_loaded = True

    def is_keyword_present(self, db, keyword):
        '''
        Check that the given keyword is present in given db connection and active.
        '''
        res = False
        if not db or not keyword:
            return res
        t_obj = db.get(self.test_module_obj_name)
        t_ids = t_obj.search([('name', '=', keyword), ('active', '=', True)])
        if not t_ids:
            return res
        return True

    def get_record(self, db, object_ref, module=None):
        '''
        Returns the object created by the test files.

        :param db: Connection to the database
        :param object_ref: XML ID of the object to find

        :return The ID of the object given in object_ref
        :rtype integer or False
        '''
        # Object
        data_obj = db.get('ir.model.data')

        if module is None:
            module = self.test_module_name

        obj = data_obj.get_object_reference(module, object_ref)

        if obj:
            return obj[1]

        return False

    def synchronize(self, db=None):
        '''
        Connect the 'db' database to the sync. server
        and run  synchronization.
        If no database givent in parameters, sync. all
        databases.
        :param db: DB connection to synchronize (can be None
                   or a list.
        :return: True
        '''
        if not db:
            for db_conn in self.db:
                self.synchronize(db=db_conn)

        if db and isinstance(db, list):
            for db_conn in db:
                self.synchronize(db=db_conn)

        conn_obj = db.get('sync.client.sync_server_connection')
        sync_obj = db.get('sync.client.sync_manager')

        conn_ids = conn_obj.search([])
        conn_obj.action_connect(conn_ids)
        sync_ids = sync_obj.search([])
        sync_obj.sync(sync_ids)

    def get_db_partner_name(self, db):
        '''
        Return the name of partner associated
        to the company of the database
        :param db: DB connection of which we
                   get the partner.
        :return: Name of the partner associated
                 to the company of the database
        '''
        company_obj = db.get('res.company')

        company_ids = company_obj.search([])
        return company_obj.browse(company_ids[0]).partner_id.name
        
    def get_company(self, db):
        """
        :param db: db
        :return: company
        """
        user = db.get('res.users').browse(1)
        return user.company_id if user else False
        
    def get_company_id(self, db):
        """
        :param db: db
        :return: company id
        :rtype: int
        """
        cpy = self.get_company(db)
        return cpy and cpy.id or False

    def get_instance(self, db):
        """
        :param db: db
        :return: instance
        """
        cpy = self.get_company(db)
        return cpy and company_id.instance_id or False
        
    def get_instance_id(self, db):
        """
        :param db: db
        :return: instance id
        :rtype: int
        """
        inst = self.get_instance(db)
        return inst and inst.id or False

    def get_id_from_key(self, db, model_name, search_val, key_field='name',
        assert_if_no_ids=False):
        """
        get record id from model and record name
        :param db: db
        :param model_name: model name to search in
        :param search_val: value to search in
        :param key_field: field for criteria name (default name)
        :type key_field: str
        :param assert_if_no_ids: raise a test error if not found (Failed Test)
        :type assert_if_no_ids: boolan
        :return: id
        :rtype: int/long
        """
        ids = db.get(model_name).search([(key_field, '=', search_val)])
        if ids:
            return ids[0]
        if assert_if_no_ids:
            assert(
                ids != False,
                "'%s' not found in '%s' :: %s" % (search_val, model_name,
                    db.colored_name, )
            )
        return False
        
    def get_db_name_from_suffix(self, suffix):
        return self._db_prefix + suffix
    
    def get_db_from_name(self, db_name):
        for attr_name in self.db:
            if self.db[attr_name].db_name == db_name:
                return self.db[attr_name]

        raise UnifieldTestException("'%s' database not found" % (db_name, ))
            
    def are_same_db(self, db1, db2):
        return db1.db_name == db2.db_name or False
        
    def dfv(self, vals, include=None, exclude=None):
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
        
    def record_exists(self, db, model, domain):
        """
        at least 1 record for the given domain
        :param db: db
        :type db: object
        :param model: model name
        :rtype: boolean
        """
        #return db.get(model).search(domain, 0, 1)  # domain, offset, limit
        return db.get(model).search(domain)  # domain, offset, limit
        
    def date2orm(self, dt):
        """
        convert date to orm format
        :type dt: DateTime
        :rtype: str YYYY-MM-DD
        """
        return dt.strftime('%Y-%m-%d')
        
    def get_orm_date_fy_start(self):
        return "%04d-01-01" % (datetime.now().year, )
        
    def get_orm_date_fy_stop(self):
        return "%04d-12-31" % (datetime.now().year, )
        
    def get_orm_date_now(self):
        return datetime.now().strftime('%Y-%m-%d')
        
    def get_orm_fy_date(self, month, day):
        return "%04d-%02d-%02d" % (datetime.now().year, month, day, )
        
    def get_uuid(self):
        """
        get UUID (universal unique id)
        :return uuid
        :rtype: str
        """
        return str(uuid4())
        
    def get_record_id_from_xmlid(self, db, module, xmlid):
        """
        get record id from xml id
        :type db: oerplib object
        :param module: module name
        :type module: str
        :param xmlid: xmlid
        :type xmlid: str
        :return: id
        """
        obj = db.get('ir.model.data').get_object_reference(module, xmlid)
        return obj[1] if obj else False
        
    def get_record_id_from_sdref(self, db, sdref):
        """
        :return id from sdref
        """
        if sdref.startswith('sd.'):
            sdref = sdref[3:]
            
        ids = obj = db.get('ir.model.data').search([
            ('module', '=', 'sd'),
            ('name', '=', sdref),
        ])
        
        if not ids:
            return False
        return db.get('ir.model.data').browse(ids[0]).res_id
        
    def get_record_sdref_from_id(self, model, db, id):
        """
        :param model: target model
        :param db: target db
        :param id: record id
        :return sdref (without sd.) from id
        """
        # [WORKAROUND]
        # oerlib proxy can not call sync client orm
        # class extended_orm_methods methods
        # return db.get(model).get_sd_ref([id], 'name')[id]
        
        model_data_obj = db.get('ir.model.data')
        sdref_ids = model_data_obj.search([
            ('model', '=', model),
            ('res_id', '=', id),
            ('module','=', 'sd'),
        ])
        
        if not sdref_ids:
            return False
        return model_data_obj.browse(sdref_ids[0]).name
        
    def get_record_sync_push_pulled(self, model, push_db, push_id, pull_db):
        """
        get(check) pulled record id of pushed record 'push_id' from model
        object 'push_obj' to 'pull_db' database
        :param model: target model name
        :param push_db: db to push record from
        :param push_id: record id to push
        :param pull_db: db to pull record from a get pulled record id
        :return pushed record id or False if not pulled
        """
        return self.get_record_id_from_sdref(pull_db,
            self.get_record_sdref_from_id(model, push_db, push_id))
            
    def compare_record_sync_push_pulled(self, model, push_db, push_id,
        pull_db, fields=False, fields_m2o=False, raise_report=True):
        """
        :param model: model name of target record
        :param push_db: db to push record from
        :param push_id: record id to push
        :param pull_db: db to pull record from
        :param fields: regular fields name
        :type fields: list/tuple/False
        :param fields_m2o: m2o list of tuples (comodel and field name)
        :type fields_m2o: [('comodel', 'field_name'), ]
        :raise_report: True to raise a report if fields mismatch
        :return records eguals ?
        :rtype: bool
        """
        push_obj = push_db.get(model)
        pull_obj = pull_db.get(model)
        diff_fields = []  # minimal result <=> pulled record found
        
        # push browsed record
        push_br = push_obj.browse(push_id)
        
        # pulled browsed record
        pull_id = self.get_record_sync_push_pulled(model, push_db, push_id,
            pull_db)
        if not pull_id:
            # record not pulled
            return False
        pull_br = pull_obj.browse(pull_id)
        
        # compare fields
        for f in fields:
            if f in push_br and push_br[f] != pull_br[f]:
                diff_fields.append(f)
        
        # compare m2o by sdref
        for comodel, f in fields_m2o:
            if f in push_br[f]:
                if not push_br[f] and not pull_br[f]:
                    continue

            push_sdref = self.get_record_sdref_from_id(comodel, push_db,
                push_br[f].id)
            pull_sdref = self.get_record_sdref_from_id(comodel, pull_db,
                pull_br[f].id)
            if push_sdref != pull_sdref:
                diff_fields.append(f)
        
        # report
        if diff_fields and raise_report:
            report = "pulled report %s fields mismatch: %s" % (
                self.get_record_sdref_from_id(model, push_db, push_id),
                ', '.join(diff_fields))
            raise UnifieldTestException(report)
            
        return not diff_fields or False
        
    def get_first(self, itr):
        """
        get first element of an iterator (to use with a not indexed iterator)
        """
        res = None
        if itr:
            for e in itr:
                res = e
                break
        return res
        
    def random_date(self, start, end):
        """
        :type start: datetime
        :type end: datetime
        :return: a random datetime between two datetime
        :rtype: datetime
        """
        # http://stackoverflow.com/questions/553303/generate-a-random-date-between-two-other-dates
        delta = end - start
        int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
        random_second = random.randrange(int_delta)
        return (start + timedelta(seconds=random_second))
        
    def get_iter_item(self, iterable, index):
        """
        get iterable item at given index
        used to get a specific item of an oerplib browsed list's item
        :param iter: iterable to get item from
        :param index: index of the wanted item
        :type index: int
        :return item or None
        """
        i = 0
        for item in iterable:
            if i == index:
                return item
            i += 1
        return None

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
