#!/usr/bin/env python
#-*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution    
#    Copyright (C) 2014 TeMPO Consulting. All Rights Reserved
#    TeMPO Consulting (<http://www.tempo-consulting.fr/>).
#    Author: Olivier DOSSMANN
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

#####
## IMPORTS
###
import sys
import oerplib
from base64 import decodestring

#####
## VARIABLES
###
p1_name='uf2377b_HQ1C1P1'
p1rw_name='uf2377b_HQ1C1P1_RW'
login = 'admin'
pwd = 'admin'
timeout = 3600

#####
## FUNCTIONS
###

def handleError(exception):
    """
    Handle exception error.
    Customize regarding your needs.
    """
    sys.stdout.write("Script ERROR: ")
    print(exception)
    sys.exit(1)

def error(message):
    if not isinstance(message, str):
        message = "Script error: cannot display message."
    print(message)
    sys.exit(1)

def connect(ip, dbname, protocol='xmlrpc', port='8069', timeout=3600):
    """
    Get an OERPLIB connection.
    Cf. http://pythonhosted.org/OERPLib/ for more information.
    """
    o = oerplib.OERP(ip, database=dbname, protocol=protocol, port=port, timeout=timeout)
    u = o.login(login, pwd, dbname)
    print('CONNECTED: %s' % (o.database or 'Unknown'))
    return o, u

def generate_file_from(db_connection):
    """
    Generate the file on given db.
    1/ create the wizard usb_synchronization
    2/ launch the process that permit to download a file
    """
    # Create the wizard
    usb_wizard = db_connection.get('usb_synchronisation')
    wiz_id = usb_wizard.create({})
    try:
      usb_wizard.push([wiz_id])
    except Exception, e:
      handleError(e)
    print("%s: File generated." % (db_connection.database or 'Unknown'))
    return True

def get_file_from(db_connection):
    """
    Get file from given db connection.
    Just search last file in ir.attachment that is linked to res.company object.
    """
    # Find the last changes on ir.attachment
    att_obj = db_connection.get('ir.attachment')
    last_attachment_ids = att_obj.search([('res_model', '=', 'res.company')], 0, 1, 'create_date DESC')
    if not last_attachment_ids:
        error("No attachment found!")
    # Get some details about attachment
    attachment = att_obj.read(last_attachment_ids[0], ['datas', 'name'])
    zipfile = attachment.get('datas', False)
    zipfilename = attachment.get('name', 'noname')
    print("%s: File retrieved (%s)." % (db_connection.database or 'Unknown', zipfilename))
    return zipfile, zipfilename

def put_file_into(db_connection, content, filename='noname'):
    """
    Put given content into given db by using USB Synchronisation wizard.
    1/ create the wizard usb_synchronisation with the given file (content variable)
    2/ launch the process that permit to upload a file into the database
    """
    # Use previous attachment for the RW database
    rw_usb_wizard = db_connection.get('usb_synchronisation')
    rw_wiz_id = rw_usb_wizard.create({'pull_data': decodestring(content)})
    try:
        rw_usb_wizard.pull([rw_wiz_id])
    except Exception, e:
        handleError(e)
    print("%s: File uploaded into (%s)." % (db_connection.database or 'Unknown', filename))
    return True

#####
## MAIN
###

def main():
    # Prepare the connection to the OpenERP server
    p1, p1_user = connect('localhost', p1_name, timeout=timeout)
    rw, rw_user = connect('localhost', p1rw_name, timeout=timeout)

    # First generate file from P1
    generate_file_from(p1)
    # Then get file (from P1)
    zipfile, filename = get_file_from(p1)
    # Finally put file into RW
    put_file_into(rw, zipfile, filename)

    return 0

#####
## BEGIN / END
###
if __name__ == '__main__':
    sys.exit(main())
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
