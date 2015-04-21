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
        raise_if_no_ids=False):
        """
        get record id from model and record name
        :param db: db
        :param model_name: model name to search in
        :param search_val: value to search in
        :param key_field: field for criteria name (default name)
        :type key_field: str
        :param raise_if_no_ids: raise a test error if not found (Failed Test)
        :type raise_if_no_ids: boolan
        :return: id
        :rtype: int/long
        """
        ids = db.get(model_name).search([(key_field, '=', search_val)])
        if ids:
            return ids[0]
        if raise_if_no_ids:
            msg = "'%s' not found in '%s' :: %s" % (search_val, model_name,
                db.colored_name, )
            raise UnifieldTestException(msg)
        return False
        
    def get_db_name_from_suffix(self, suffix):
        return self._db_prefix + suffix
    
    def get_db_from_name(self, db_name):
        if self.hq1.db_name == db_name:
            return self.hq1
        elif self.c1.db_name == db_name:
            return self.c1
        elif self.p1.db_name == db_name:
            return self.p1
        raise UnifieldTestException("'%s' database not found" % (
            db_name, ))
            
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
        return db.get(model).search(domain, 0, 1)  # domain, offset, limit
        
    def get_orm_date_fy_start(self):
        return "%04d-01-01" % (datetime.now().year, )
        
    def get_orm_date_fy_stop(self):
        return "%04d-12-31" % (datetime.now().year, )
        
    def get_orm_date_now(self):
        return datetime.now().strftime('%Y-%m-%d')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
