# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

from osv import fields, osv

class account_analytic_journal(osv.osv):
    _name = 'account.analytic.journal'
    _inherit = 'account.analytic.journal'
    
    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
    }
    
    _defaults = {
        'instance_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.instance_id.id,
    }

account_analytic_journal()

class account_analytic_line(osv.osv):
    _name = 'account.analytic.line'
    _inherit = 'account.analytic.line'
    
    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
    }
    
    _defaults = {
        'instance_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.instance_id.id,
    }

account_analytic_line()

class account_journal(osv.osv):
    _name = 'account.journal'
    _inherit = 'account.journal'
    
    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
    }
    
    _defaults = {
        'instance_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.instance_id.id,
    }

account_journal()

class account_move(osv.osv):
    _name = 'account.move'
    _inherit = 'account.move'
    
    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
    }
    
    _defaults = {
        'instance_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.instance_id.id,
    }

account_move()

class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'
    
    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
    }
    
    _defaults = {
        'instance_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.instance_id.id,
    }

account_move_line()

class account_bank_statement(osv.osv):
    _name = 'account.bank.statement'
    _inherit = 'account.bank.statement'
    
    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Proprietary Instance'),
    }
    
    _defaults = {
        'instance_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.instance_id.id,
    }

account_bank_statement()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
