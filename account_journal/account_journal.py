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
import logging
from os import path
import tools

class account_journal(osv.osv):
    _inherit = "account.journal"

    def init(self, cr):
        """
        Load demo.xml brefore addons
        """
        if hasattr(super(account_journal, self), 'init'):
            super(account_journal, self).init(cr)

        mod_obj = self.pool.get('ir.module.module')
        demo = False
        mod_id = mod_obj.search(cr, 1, [('name', '=', 'account_journal')])
        if mod_id:
            demo = mod_obj.read(cr, 1, mod_id, ['demo'])[0]['demo']

        if demo:
            logging.getLogger('init').info('HOOK: module account_journal: loading account_journal_demo.xml')
            pathname = path.join('account_journal', 'account_journal_demo.xml')
            file = tools.file_open(pathname)
            tools.convert_xml_import(cr, 'account_journal', file, {}, mode='init', noupdate=False)


    def get_journal_type(self, cursor, user_id, context=None):
        return [('bank', 'Bank'), \
                ('cash','Cash'), \
                ('purchase', 'Purchase'), \
                ('correction','Correction'), \
                ('cheque', 'Cheque'), \
                ('hq', 'HQ'), \
                ('hr', 'HR'), \
                ('accrual', 'Accrual'), \
                ('stock', 'Stock'), \
                ('depreciation', 'Depreciation'), \
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
    
    def onchange_type(self, cr, uid, ids, type, currency, context=None):
        value = super(account_journal, self).onchange_type(cr, uid, ids, type, currency, context)
        default_dom = [('type','<>','view'),('type','<>','consolidation')]
        value.setdefault('domain',{})
        if type in ('cash', 'bank', 'cheque'):
            default_dom += [('code', '=like', '5%' )]
        value['domain']['default_debit_account_id'] = default_dom
        value['domain']['default_crebit_account_id'] = default_dom
        return value


    def create(self, cr, uid, vals, context=None):
        
        # TODO: add default accounts
       
        if context is None:
            context = {}

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
            # UF-433: sequence is now only the number, no more prefix
            #'prefix': "%(year)s%(month)s-" + name + "-" + code + "-",
            'prefix': "",
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
            # 'from_journal_creation' in context permits to pass register creation that have a
            #  'prev_reg_id' mandatory field. This is because this register is the first register from this journal.
            context.update({'from_journal_creation': True})
            self.pool.get('account.bank.statement') \
                .create(cr, uid, {'journal_id': journal_obj,
                                  'name': "REG1" + vals['code'],
                                  'period_id': self.get_current_period(cr, uid, context),
                                  'currency': vals.get('currency')}, \
                                  context=context)
                
        return journal_obj
    

account_journal()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
