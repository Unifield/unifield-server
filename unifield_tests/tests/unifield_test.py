#!/usr/bin/env python
# -*- coding: utf8 -*-
'''
Created on Feb 28, 2014

@author: qt
Modified by 'od' on 2014 March, the 11th
'''
from __future__ import print_function
import unittest
from connection import XMLRPCConnection as XMLConn
from connection import UnifieldTestConfigParser

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

    # FIXME/TODO: Make unittest.TestCase inherit from oerplib.error class because of RPCError that could be raised by unittest.TestCase

    def _addConnection(self, db_suffix, name):
        '''
        Add new connection
        '''
        con = XMLConn(db_suffix)
        setattr(self, name, con)
        self.db[name] = con

    def __init__(self, *args, **kwargs):
        # Default behaviour
        super(UnifieldTest, self).__init__(*args, **kwargs)
        # Prepare some values
        c = UnifieldTestConfigParser()
        self.config = c.read()
        tempo_mkdb = c.getboolean('DB', 'tempo_mkdb')
        db_suffixes = ['SYNC_SERVER', 'HQ1', 'HQ1C1', 'HQ1C1P1']
        names = ['sync', 'hq1', 'c1', 'p1']
        if not tempo_mkdb:
            db_suffixes = ['SYNC_SERVER', 'HQ_01', 'COORDO_01', 'PROJECT_01']
        # Keep each database connection
        for db_tuple in zip(db_suffixes, names):
            self._addConnection(db_tuple[0], db_tuple[1])
        # For each database, check that unifield_tests module is loaded
        #+ If not, load it.
        #+ Except if the database is sync one
        for database_name in self.db:
            if database_name == 'sync':
                continue
            database = self.db.get(database_name)
            module_obj = database.get('ir.module.module')
            m_ids = module_obj.search([('name', '=', self.test_module_name)])
            for module in module_obj.read(m_ids, ['state']):
                state = module.get('state', '')
                if state == 'uninstalled':
                    print ('  * %s: MODULE %s UPDATE...' % (database_name, self.test_module_name))
                    module_obj.button_install([module.get('id')])
                    database.get('base.module.upgrade').upgrade_module([])
                elif state in ['to upgrade', 'to install']:
                    print ('  * %s: MODULE %s UPDATE...' % (database_name, self.test_module_name))
                    database.get('base.module.upgrade').upgrade_module([])
                elif state in ['installed']:
                    print ('  * %s: MODULE %s LOADED' % (database_name, self.test_module_name))
                    pass
                else:
                    raise EnvironmentError(' Wrong module state: %s' % (state or '',))

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

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
