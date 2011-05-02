# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

import datetime
from osv import osv, fields

class account_journal(osv.osv):
    _inherit = "account.journal"
    
    def get_journal_type(self, cursor, user_id, context=None):
        return [('bank', 'Bank Journal'), \
                ('cash','Cash Journal'), \
                ('purchase', 'Purchase Journal'), \
                ('correction','Correction Journal'), \
                ('cheque', 'Cheque Journal'), \
                ('hq', 'HQ Journal'), \
                ('hr', 'HR Journal'), \
                ('accrual', 'Accrual Journal'), \
                ('stock', 'Stock Journal'), \
                ('depreciation', 'Depreciation Journal'), \
                # Old journal types: not used, but kept to
                # not break OpenERP's demo/install data
                ('sale', 'Sale'), \
                ('sale_refund','Sale Refund'), \
                ('purchase_refund','Purchase Refund'), \
                ('general', 'General'), \
                ('situation', 'Opening/Closing Situation')]
    
    _columns = {
        'type': fields.selection(get_journal_type, 'Type', size=32, required=True),
        'instance_id': fields.char('Proprietary instance', size=32, required=True),
        'code': fields.char('Code', size=10, required=True, help="The code will be used to generate the numbers of the journal entries of this journal."),
    }

    _defaults = {
        'allow_date': False,
        'centralisation': False,
        'entry_posted': False,
        'update_posted': True,
        'group_invoice_lines': False,
        'instance_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.name,
    }
    
    def get_current_period(self, cr, uid, context=None):
        periods = self.pool.get('account.period').find(cr, uid, datetime.date.today())
        if periods:
            return periods[0]
        return False
    
    def name_get(self, cr, user, ids, context=None):
        result = self.browse(cr, user, ids, context=context)
        res = []
        for rs in result:
            code = rs.code
            res += [(rs.id, code)]
        return res
    
    def create(self, cr, uid, vals, context=None):
        
        # TODO: add default accounts
        
        # Create associated sequence
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')
        name = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.name
        code = vals['code'].lower()
        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)
        seq = {
            'name': name,
            'code': code,
            'active': True,
            'prefix': "%(year)s%(month)s-" + name + "-" + code + "-",
            'padding': 6,
            'number_increment': 1
        }
        vals['sequence_id'] = seq_pool.create(cr, uid, seq)
        
        # View is set by default, since every journal will display the same thing
        obj_data = self.pool.get('ir.model.data')
        data_id = obj_data.search(cr, uid, [('model','=','account.journal.view'), ('name','=','account_journal_view')])
        data = obj_data.browse(cr, uid, data_id[0], context=context)
        vals['view_id'] = data.res_id
        
        # create journal
        journal_obj = super(account_journal, self).create(cr, uid, vals, context)
        
        # if the journal can be linked to a register, the register is also created
        if vals['type'] in ('cash','bank','cheque'):
            self.pool.get('account.bank.statement') \
                .create(cr, uid, {'journal_id': journal_obj,
                                  'name': "REG1" + vals['code'],
                                  'period_id': self.get_current_period(cr, uid, context),
                                  'currency': vals.get('currency')}, \
                                  context=context)
                
        return journal_obj
    

account_journal()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
