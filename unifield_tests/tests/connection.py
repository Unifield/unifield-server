#!/usr/bin/env python
# -*- coding: utf8 -*-
'''
Created on Feb 28, 2014

@author: qt

Modified by 'od' on 2014 March, the 11th
'''

from ConfigParser import ConfigParser
from oerplib.oerp import OERP
import os

class UnifieldTestConfigParser(ConfigParser):
    '''
    Special ConfigParser for Unifield tests battery
    '''

    def read(self, filenames=[]):
        '''
        Override readfp() method to add the config file path
        '''
        conf_file = 'unifield.config'
        if not os.path.exists(conf_file):
            raise NameError('unifield.config file not found!')
        return ConfigParser.read(self, [conf_file])

class XMLRPCConnection(OERP):
    '''
    XML-RPC connection class to connect with OERP
    '''

    def __init__(self, db_suffix):
        '''
        Constructor
        '''
        # Read configuration file
        config = UnifieldTestConfigParser()
        config.read()
        # Prepare some values
        server_port = config.getint('Server', 'port')
        server_url = config.get('Server', 'url')
        uid = config.get('DB', 'username')
        pwd = config.get('DB', 'password')
        db_prefix = config.get('DB', 'db_prefix')
        # OpenERP connection
        super(XMLRPCConnection, self).__init__(
            server=server_url,
            protocol='xmlrpc',
            port=server_port,
            timeout=3600
        )
        # Login initialization
        db_name = '%s%s' % (db_prefix, db_suffix)
        self.login(uid, pwd, db_name)

if __name__ == '__main__':
    c = XMLRPCConnection('HQ1C1P1')
    if c:
        print "Connection succeeded"

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: