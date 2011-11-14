#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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
from time import strftime
from tools.translate import _
import logging

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    _columns = {
        'from_yml_test': fields.boolean('Only used to pass addons unit test', readonly=True, help='Never set this field to true !'),
    }

    _defaults = {
        'from_yml_test': lambda *a: False,
    }

    def create(self, cr, uid, vals, context={}):
        """
        Filled in 'from_yml_test' to True if we come from tests
        """
        if not context:
            context = {}
        if context.get('update_mode') in ['init', 'update']:
            logging.getLogger('init').info('INV: set from yml test to True')
            vals['from_yml_test'] = True
        return super(account_invoice, self).create(cr, uid, vals, context)

    def action_open_invoice(self, cr, uid, ids, context={}, *args):
        """
        Give function to use when changing invoice to open state
        """
        if not context:
            context = {}
        if not self.action_date_assign(cr, uid, ids, context, args):
            return False
        if not self.action_move_create(cr, uid, ids, context, args):
            return False
        if not self.action_number(cr, uid, ids, context):
            return False
        return True

account_invoice()

class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    _columns = {
        'from_yml_test': fields.boolean('Only used to pass addons unit test', readonly=True, help='Never set this field to true !'),
    }

    _defaults = {
        'from_yml_test': lambda *a: False,
    }

    def create(self, cr, uid, vals, context={}):
        """
        Filled in 'from_yml_test' to True if we come from tests
        """
        if not context:
            context = {}
        if context.get('update_mode') in ['init', 'update']:
            logging.getLogger('init').info('INV: set from yml test to True')
            vals['from_yml_test'] = True
        return super(account_invoice_line, self).create(cr, uid, vals, context)

account_invoice_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
