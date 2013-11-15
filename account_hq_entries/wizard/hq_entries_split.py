#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013 TeMPO Consulting, MSF. All Rights Reserved
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
from tools.translate import _

class hq_entries_split_lines(osv.osv_memory):
    _name = 'hq.entries.split.lines'
    _description = 'HQ entries split lines'

    _columns = {
        'wizard_id': fields.many2one('hq.entries.split', "Wizard", required=True),
        'name': fields.char("Description", size=255, required=True),
        'ref': fields.char("Reference", size=255),
        'account_id': fields.many2one("account.account", "Account", domain=[('type', '!=', 'view')], required=True),
        'amount': fields.float('Amount', required=True),
        'destination_id': fields.many2one('account.analytic.account', "Destination", domain=[('category', '=', 'DEST'), ('type', '!=', 'view')], required=True),
        'cost_center_id': fields.many2one('account.analytic.account', "Cost Center", domain=[('category', '=', 'OC'), ('type', '!=', 'view')], required=True),
        'analytic_id': fields.many2one('account.analytic.account', "Funding Pool", domain=[('category', '=', 'FUNDING'), ('type', '!=', 'view')], required=True),
    }

    def _get_original_line(self, cr, uid, context=None):
        """
        Fetch original line from context. If not, return False.
        """
        res = False
        if not context:
            return res
        if context.get('parent_id', False):
            wiz = self.pool.get('hq.entries.split').browse(cr, uid, context.get('parent_id'))
            res = wiz and wiz.original_id or False
        return res

    def _get_field(self, cr, uid, field_name, field_type=False, context=None):
        """
        Get original line specific info given by "field_name" parameter
        """
        res = False
        if not context or not field_name:
            return res
        original_line = self._get_original_line(cr, uid, context=context)
        res = original_line and getattr(original_line, field_name, False) or False
        if res and field_type and field_type == 'm2o':
            res = getattr(res, 'id', False)
        return res

    def _get_amount(self, cr, uid, context=None):
        """
        Get original line amount substracted of all other lines amount
        """
        res = 0.0
        if not context:
            return res
        original_line = self._get_original_line(cr, uid, context=context)
        if original_line:
            res = original_line.amount
            line_ids = self.search(cr, uid, [('wizard_id', '=', context.get('parent_id', False))])
            for line in self.browse(cr, uid, line_ids) or []:
                res -= line.amount
        # Do not allow negative amounts
        if res < 0.0:
            res = 0.0
        return res

    _defaults = {
        'name': lambda obj, cr, uid, c: obj._get_field(cr, uid, 'name', context=c),
        'ref': lambda obj, cr, uid, c: obj._get_field(cr, uid, 'ref', context=c),
        'account_id': lambda obj, cr, uid, c: obj._get_field(cr, uid, 'account_id', field_type='m2o', context=c),
        'amount': _get_amount,
        'destination_id': lambda obj, cr, uid, c: obj._get_field(cr, uid, 'destination_id', field_type='m2o', context=c),
        'cost_center_id': lambda obj, cr, uid, c: obj._get_field(cr, uid, 'cost_center_id', field_type='m2o', context=c),
        'analytic_id': lambda obj, cr, uid, c: obj._get_field(cr, uid, 'analytic_id', field_type='m2o', context=c),
    }

    def create(self, cr, uid, vals, context=None):
        """
        Check that:
        - no negative value is given for amount
        - amount and all other line's amount is not superior to original line
        """
        if not context:
            context = {}
        if vals.get('amount', 0.0):
            # Check that amount is not negative
            if vals.get('amount') <= 0.0:
                raise osv.except_osv(_('Error'), _('Negative value is not allowed!'))
        res = super(hq_entries_split_lines, self).create(cr, uid, vals, context=context)
        # Check that amount is not superior to what expected
        if res:
            line = self.browse(cr, uid, res)
            expected_max_amount = line.wizard_id.original_amount
            for line in line.wizard_id.line_ids:
                expected_max_amount -= line.amount
            expected_max_amount += line.amount
            if line.amount > expected_max_amount:
                # WARNING: On osv.memory, no rollback. That's why we should unlink the previous line before raising this error
                self.unlink(cr, uid, [res], context=context)
                raise osv.except_osv(_('Error'), _('Expected max amount: %.2f') % (expected_max_amount or 0.0,))
        return res

hq_entries_split_lines()

class hq_entries_split(osv.osv_memory):
    _name = 'hq.entries.split'
    _description = 'HQ entry split'

    _columns = {
        'original_id': fields.many2one('hq.entries', "Original HQ Entry", readonly=True, required=True),
        'original_amount': fields.float('Original Amount', readonly=True, required=True),
        'line_ids': fields.one2many('hq.entries.split.lines', 'wizard_id', "Split lines"),
    }

    def button_validate(self, cr, uid, ids, context=None):
        """
        Validate wizard lines and create new split HQ lines.
        """
        # Some checks
        if not context:
            context = {}
        # Prepare some values
        hq_obj = self.pool.get('hq.entries')
        # Check total amount for this wizard
        for wiz in self.browse(cr, uid, ids, context=context):
            total = 0.00
            for line in wiz.line_ids:
                total += line.amount
            if total != wiz.original_amount:
                raise osv.except_osv(_('Error'), _('Wrong total: %.2f, instead of: %.2f') % (total or 0.00, wiz.original_amount or 0.00,))
            # If all is OK, do process of lines
            # Mark original line as it is: an original one :-)
            hq_obj.write(cr, uid, wiz.original_id.id, {'is_original': True,})
            # Create new lines
            for line in wiz.line_ids:
                line_vals = {
                    'original_id': wiz.original_id.id,
                    'is_split': True,
                    'account_id': line.account_id.id,
                    'destination_id': line.destination_id.id,
                    'cost_center_id': line.cost_center_id.id,
                    'analytic_id': line.analytic_id.id,
                    'date': wiz.original_id.date,
                    'partner_txt': wiz.original_id.partner_txt or '',
                    'period_id': wiz.original_id.period_id and wiz.original_id.period_id.id or False,
                    'name': line.name,
                    'ref': line.ref,
                    'document_date': wiz.original_id.document_date,
                    'currency_id': wiz.original_id.currency_id and wiz.original_id.currency_id.id or False,
                    'amount': line.amount,
                    'account_id_first_value': line.account_id.id,
                    'cost_center_id_first_value': line.cost_center_id.id, 
                    'analytic_id_first_value': line.analytic_id.id,
                    'destination_id_first_value': line.destination_id.id,
                }
                hq_line_id = hq_obj.create(cr, uid, line_vals, context=context)
                hq_line = hq_obj.browse(cr, uid, hq_line_id, context=context)
                if hq_line.analytic_state != 'valid':
                    raise osv.except_osv(_('Warning'), _('Analytic distribution is invalid for the line "%s" with %.2f amount.') % (line.name, line.amount))
        return {'type' : 'ir.actions.act_window_close',}

hq_entries_split()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
