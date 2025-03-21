# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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

from osv import fields
from osv import osv

class account_analytic_journal(osv.osv):
    _name = 'account.analytic.journal'
    _description = 'Analytic Journal'
    _columns = {
        'name': fields.char('Journal Name', size=64, required=True),
        'code': fields.char('Journal Code', size=8, required=True),
        # the Active tag should not be used anymore from US-7194
        'active': fields.boolean('Active', help="If the active field is set to False, it will allow you to hide the analytic journal without removing it."),
        'line_ids': fields.one2many('account.analytic.line', 'journal_id', 'Lines'),
        'company_id': fields.many2one('res.company', 'Company', required=True),
    }
    _defaults = {
        'active': True,
        'company_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.id,
    }

    def _check_corr_type(self, cr, uid, ids, context=None):
        """
        Check that only one "Correction" and one "Correction HQ" analytic journals exist per instance
        """
        if context is None:
            context = {}
        for analytic_journal in self.browse(cr, uid, ids, fields_to_fetch=['type', 'instance_id'], context=context):
            if analytic_journal.type in ('correction', 'correction_hq'):
                analytic_journal_dom = [('type', '=', analytic_journal.type),
                                        ('instance_id', '=', analytic_journal.instance_id.id),
                                        ('id', '!=', analytic_journal.id)]
                if self.search_exist(cr, uid, analytic_journal_dom, context=context):
                    return False
        return True

    def _check_hq_corr(self, cr, uid, ids, context=None):
        """
        Check that the prop. instance of the "Correction HQ" analytic journal is a coordo
        """
        if context is None:
            context = {}
        for analytic_journal in self.browse(cr, uid, ids, fields_to_fetch=['type', 'instance_id'], context=context):
            if analytic_journal.type == 'correction_hq' and analytic_journal.instance_id.level != 'coordo':
                return False
        return True

    _constraints = [
        (_check_corr_type, 'An analytic journal with this type already exists for this instance.', ['type', 'instance_id']),
        (_check_hq_corr, 'The prop. instance of the "Correction HQ" analytic journal must be a coordination.', ['type', 'instance_id']),
    ]

    def get_correction_analytic_journal(self, cr, uid, corr_type=False, context=None):
        """
        Returns the correction analytic journal of the current instance (or False if not found):
        - by default => standard Correction journal
        - corr_type 'hq' => Correction HQ journal
        - corr_type 'extra' => OD-Extra Accounting journal
        - corr_type 'manual' => Correction Manual journal
        """
        if context is None:
            context = {}
        if corr_type == 'hq':
            analytic_journal_type = 'correction_hq'
        elif corr_type == 'extra':
            analytic_journal_type = 'extra'
        elif corr_type == 'manual':
            analytic_journal_type = 'correction_manual'
        else:
            analytic_journal_type = 'correction'
        analytic_journal_ids = self.search(cr, uid, [('type', '=', analytic_journal_type), ('is_current_instance', '=', True)],
                                           order='id', limit=1, context=context)
        return analytic_journal_ids and analytic_journal_ids[0] or False


account_analytic_journal()


class account_journal(osv.osv):
    _inherit="account.journal"

    _columns = {
        'analytic_journal_id':fields.many2one('account.analytic.journal','Analytic Journal', help="Journal for analytic entries"),
    }

account_journal()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
