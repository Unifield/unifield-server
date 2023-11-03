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

class hr_contract_msf(osv.osv):
    _name = 'hr.contract.msf'
    _rec_name = 'homere_codeterrain'
    _description = 'MSF Employee contract from Homère'

    _columns = {
        'homere_codeterrain': fields.char(string='Homere field: codeterrain', size=20, readonly=True, required=True, select=1),
        'homere_id_staff': fields.integer(string='Homere field: id_staff', size=10, readonly=True, required=True, select=1),
        'homere_id_unique': fields.char(string='Homere field: id_unique', size=42, readonly=True, required=True),
        'date_start': fields.date(string="Contract ' starting date", readonly=True, required=False),
        'date_end': fields.date(string="Contract's ending date", readonly=True, required=False),
        'current': fields.boolean(string="Current contract", readonly=True, required=True),
        'job_id': fields.many2one('hr.job', string="Job", readonly=True, required=False),
        'job_name': fields.char('Job', size=256),
    }

hr_contract_msf()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
