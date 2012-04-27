#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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

from osv import osv
from osv import fields
import os.path
from base64 import decodestring
from tempfile import NamedTemporaryFile
import csv
from tools.misc import ustr
from tools.translate import _
import time

class hq_entries_import_wizard(osv.osv_memory):
    _name = 'hq.entries.import'
    _description = 'HQ Entries Import Wizard'

    _columns = {
        'file': fields.binary(string="File", filters="*.csv", required=True),
    }

    def button_validate(self, cr, uid, ids, context=None):
        pass
        return True

hq_entries_import_wizard()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
