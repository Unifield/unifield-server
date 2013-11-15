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
                raise osv.except_osv(_('Error'), _('Expected max amount: %s') % (expected_max_amount or 0.0,))
        return res

hq_entries_split_lines()

class hq_entries_split(osv.osv_memory):
    _name = 'hq.entries.split'
    _description = 'HQ entries split'

    _columns = {
        'original_id': fields.many2one('hq.entries', "Original HQ Entry", readonly=True),
        'original_amount': fields.float('Original Amount', readonly=True),
        'line_ids': fields.one2many('hq.entries.split.lines', 'wizard_id', "Split lines"),
    }

    def _get_original_id(self, cr, uid, context=None):
        """
        Get the only one original id given in context.
        If more than one, raise an error because we only split HQ Entries lines one by one.
        """
        if not context or not context.get('active_ids'):
            raise osv.except_osv(_('Error'), _('No line to split!'))
            return False
        if len(context.get('active_ids')) > 1:
            raise osv.except_osv(_('Warning'), _('You can only split HQ Entries one by one!'))
        return context.get('active_ids')[0]

    def _get_original_amount(self, cr, uid, context=None):
        """
        Get original amount of original HQ Entry
        """
        if not context:
            context = {}
        original_id = self._get_original_id(cr, uid, context=context)
        res = 0.0
        if original_id:
            res = self.pool.get('hq.entries').browse(cr, uid, original_id, context=context).amount
        return res

    _defaults = {
        'original_id': _get_original_id,
        'original_amount': _get_original_amount,
    }

    def button_validate(self, cr, uid, ids, context):
        """
        Validate wizard lines and create new split HQ lines.
        """
        # TODO:
        # - keep original line id (link)
        # - flag original line (is_original)
        # - flag new split hq lines (is_split)
        # create new hq lines
        return False

hq_entries_split()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
