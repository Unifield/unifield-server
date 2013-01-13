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

class account_account(osv.osv):
    _name = 'account.account'
    _inherit = 'account.account'

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        res = super(account_account, self).create(cr, uid, vals, context)
        
        ir_translation = {'lang': 'en_US',
                          'src': vals['name'],
                          'value': vals['name'],
                          'name': 'account.account,name',
                          'res_id': res,
                          'type': 'model'
                        }
        
        #UF-1662: for each new record created, an entry in the ir_translation must be added so that the field data could be later translated
        self.pool.get('ir.translation').create(cr, uid, ir_translation, context)
        return res

    _columns = {
        'name': fields.char('Name', size=128, required=True, select=True, translate=True),
    }
account_account()

class account_journal(osv.osv):
    _name = 'account.journal'
    _inherit = 'account.journal'

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        res = super(account_journal, self).create(cr, uid, vals, context)
        
        ir_translation = {'lang': 'en_US',
                          'src': vals['name'],
                          'value': vals['name'],
                          'name': 'account.journal,name',
                          'res_id': res,
                          'type': 'model'
                        }
        
        #UF-1662: for each new record created, an entry in the ir_translation must be added so that the field data could be later translated
        self.pool.get('ir.translation').create(cr, uid, ir_translation, context)
        return res

    _columns = {
        'name': fields.char('Journal Name', size=64, required=True, translate=True),
    }
account_journal()

class account_analytic_account(osv.osv):
    _name = 'account.analytic.account'
    _inherit = 'account.analytic.account'

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        res = super(account_analytic_account, self).create(cr, uid, vals, context)
        return res
        
        ir_translation = {'lang': 'en_US',
                          'src': vals['name'],
                          'value': vals['name'],
                          'name': 'account.analytic.account,name',
                          'res_id': res,
                          'type': 'model'
                        }
        
        #UF-1662: for each new record created, an entry in the ir_translation must be added so that the field data could be later translated
        self.pool.get('ir.translation').create(cr, uid, ir_translation, context)
        return res

    _columns = {
        'name': fields.char('Account Name', size=128, required=True, translate=True),
    }
    
account_analytic_account()

class account_analytic_journal(osv.osv):
    _name = 'account.analytic.journal'
    _inherit = 'account.analytic.journal'

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        res = super(account_analytic_journal, self).create(cr, uid, vals, context)
        
        ir_translation = {'lang': 'en_US',
                          'src': vals['name'],
                          'value': vals['name'],
                          'name': 'account.analytic.journal,name',
                          'res_id': res,
                          'type': 'model'
                        }
        
        #UF-1662: for each new record created, an entry in the ir_translation must be added so that the field data could be later translated
        self.pool.get('ir.translation').create(cr, uid, ir_translation, context)
        return res

    _columns = {
        'name': fields.char('Journal Name', size=64, required=True, translate=True),
    }
account_analytic_journal()

class account_period(osv.osv):
    _name = 'account.period'
    _inherit = 'account.period'

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        res = super(account_period, self).create(cr, uid, vals, context)
        
        ir_translation = {'lang': 'en_US',
                          'src': vals['name'],
                          'value': vals['name'],
                          'name': 'account.period,name',
                          'res_id': res,
                          'type': 'model'
                        }
        
        #UF-1662: for each new record created, an entry in the ir_translation must be added so that the field data could be later translated
        self.pool.get('ir.translation').create(cr, uid, ir_translation, context)
        return res

    _columns = {
        'name': fields.char('Period Name', size=64, required=True, translate=True),
    }
account_period()

class res_currency(osv.osv):
    _name = 'res.currency'
    _inherit = 'res.currency'

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        res = super(res_currency, self).create(cr, uid, vals, context)
        
        ir_translation = {'lang': 'en_US',
                          'src': vals['currency_name'],
                          'value': vals['currency_name'],
                          'name': 'res.currency,currency_name',
                          'res_id': res,
                          'type': 'model'
                        }
        
        #UF-1662: for each new record created, an entry in the ir_translation must be added so that the field data could be later translated
        self.pool.get('ir.translation').create(cr, uid, ir_translation, context)
        return res

    _columns = {
        'currency_name': fields.char('Currency Name', size=64, required=True, translate=True),
    }
res_currency()

class product_template(osv.osv):
    _name = 'product.template'
    _inherit = 'product.template'

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        res = super(product_template, self).create(cr, uid, vals, context)
        
        ir_translation = {'lang': 'en_US',
                          'src': vals['name'],
                          'value': vals['name'],
                          'name': 'product.template,name',
                          'res_id': res,
                          'type': 'model'
                        }
        
        #UF-1662: for each new record created, an entry in the ir_translation must be added so that the field data could be later translated
        self.pool.get('ir.translation').create(cr, uid, ir_translation, context)
        return res

product_template()

class product_nomenclature(osv.osv):
    _name = 'product.nomenclature'
    _inherit = 'product.nomenclature'

    _columns = {
        'name': fields.char('Name', size=64, required=True, select=True, translate=True),
    }

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        res = super(product_nomenclature, self).create(cr, uid, vals, context)
        
        ir_translation = {'lang': 'en_US',
                          'src': vals['name'],
                          'value': vals['name'],
                          'name': 'product.nomenclature,name',
                          'res_id': res,
                          'type': 'model'
                        }
        
        #UF-1662: for each new record created, an entry in the ir_translation must be added so that the field data could be later translated
        self.pool.get('ir.translation').create(cr, uid, ir_translation, context)
        return res

product_nomenclature()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
