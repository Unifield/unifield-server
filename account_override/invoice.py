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
        'sequence_id': fields.many2one('ir.sequence', 'Lines Sequence', required=True, ondelete='cascade',
            help="This field contains the information related to the numbering of the lines of this order."),
    }

    _defaults = {
        'from_yml_test': lambda *a: False,
    }

    def create_sequence(self, cr, uid, vals, context=None):
        """
        Create new entry sequence for every new invoice
        """
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        name = 'Invoice L' # For Invoice Lines
        code = 'account.invoice'

        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)

        seq = {
            'name': name,
            'code': code,
            'prefix': '',
            'padding': 0,
        }
        return seq_pool.create(cr, uid, seq)

    def create(self, cr, uid, vals, context=None):
        """
        Filled in 'from_yml_test' to True if we come from tests
        """
        if not context:
            context = {}
        if context.get('update_mode') in ['init', 'update']:
            logging.getLogger('init').info('INV: set from yml test to True')
            vals['from_yml_test'] = True
        # Create a sequence for this new invoice
        vals.update({'sequence_id': self.create_sequence(cr, uid, vals, context)})
        return super(account_invoice, self).create(cr, uid, vals, context)

    def action_open_invoice(self, cr, uid, ids, context=None, *args):
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

    def _hook_period_id(self, cr, uid, inv, context=None):
        """
        Give matches period that are not draft and not HQ-closed from given date
        """
        # Some verifications
        if not context:
            context = {}
        if not inv:
            return False
        # NB: there is some period state. So we define that we choose only open period (so not draft and not done)
        res = self.pool.get('account.period').search(cr, uid, [('date_start','<=',inv.date_invoice or strftime('%Y-%m-%d')),
            ('date_stop','>=',inv.date_invoice or strftime('%Y-%m-%d')), ('state', 'not in', ['created', 'done']), 
            ('company_id', '=', inv.company_id.id)], context=context, order="date_start ASC, name ASC")
        return res

account_invoice()

class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    _columns = {
        'from_yml_test': fields.boolean('Only used to pass addons unit test', readonly=True, help='Never set this field to true !'),
        'line_number': fields.integer(string='Line', required=True),
    }

    _defaults = {
        'from_yml_test': lambda *a: False,
    }

    _order = 'line_number'

    def create(self, cr, uid, vals, context=None):
        """
        Filled in 'from_yml_test' to True if we come from tests
        """
        if not context:
            context = {}
        if context.get('update_mode') in ['init', 'update']:
            logging.getLogger('init').info('INV: set from yml test to True')
            vals['from_yml_test'] = True
        # Create new number with invoice sequence
        invoice = self.pool.get('account.invoice').browse(cr, uid, vals['invoice_id'], context)
        sequence = invoice.sequence_id
        line = sequence.get_id(test='id', context=context)
        vals.update({'line_number': line})
        return super(account_invoice_line, self).create(cr, uid, vals, context)

account_invoice_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
