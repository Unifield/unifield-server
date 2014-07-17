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
## IMPORT
###
import sys
import oerplib
from datetime import datetime

#####
## VARIABLES
###
dbname='uf2377b_HQ1C1P1'
rwdbname='uf2377b_HQ1C1P1_RW'
login = 'admin'
pwd = 'admin'
timeout = 3600

#####
## BEGIN
###
# Prepare the connection to the OpenERP server
o = oerplib.OERP('localhost', protocol='xmlrpc', port=8069, timeout=timeout)
# Then user
u = o.login(login, pwd, dbname)

# Create the wizard
usb_wizard = o.get('usb_synchronisation')
wiz_id = usb_wizard.create({})
before = datetime.today()
#try:
#  usb_wizard.push([wiz_id])
#except Exception, e:
#  print e
#finally:
#  after = datetime.today()
#  print str(after - before)

# Find the last changes
att_obj = o.get('ir.attachment')
last_attachment_ids = att_obj.search([('res_model', '=', 'res.company')], 0, 1, 'create_date DESC')
if not last_attachment_ids:
  print("No attachment found!")
  sys.exit(1)
print att_obj.read(last_attachment_ids[0], ['create_date', 'description', 'res_name', 'type'])

#####
## END
###
sys.exit(0)
