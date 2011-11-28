# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) MSF, TeMPO Consulting.
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
import decimal_precision as dp
from tools.misc import flatten
from time import strftime

class analytic_distribution(osv.osv):
    _name = "analytic.distribution"

    _columns = {
        'name': fields.char('Name', size=12),
        'global_distribution': fields.boolean('Is this distribution copied from the global distribution'),
        'analytic_lines': fields.one2many('account.analytic.line', 'distribution_id', 'Analytic Lines'),
        'invoice_ids': fields.one2many('account.invoice', 'analytic_distribution_id', string="Invoices"),
        'invoice_line_ids': fields.one2many('account.invoice.line', 'analytic_distribution_id', string="Invoice Lines"),
        'register_line_ids': fields.one2many('account.bank.statement.line', 'analytic_distribution_id', string="Register Lines"),
        'move_line_ids': fields.one2many('account.move.line', 'analytic_distribution_id', string="Move Lines"),
    }

    _defaults ={
        'name': lambda *a: 'Distribution',
        'global_distribution': lambda *a: False,
    }

    def copy(self, cr, uid, id, defaults={}, context={}):
        """
        Copy an analytic distribution without the one2many links
        """
        defaults.update({
            'analytic_lines': False,
            'invoice_ids': False,
            'invoice_line_ids': False,
            'register_line_ids': False,
            'move_line_ids': False,
        })
        return super(osv.osv, self).copy(cr, uid, id, defaults, context=context)

analytic_distribution()

class distribution_line(osv.osv):
    _name = "distribution.line"

    _columns = {
        'name': fields.char('Name', size=64),
        "distribution_id": fields.many2one('analytic.distribution', 'Associated Analytic Distribution', ondelete='cascade'),
        "analytic_id": fields.many2one('account.analytic.account', 'Analytical Account'),
        "amount": fields.float('Amount', digits_compute=dp.get_precision('Account')),
        "percentage": fields.float('Percentage', digits=(16,4)),
        "currency_id": fields.many2one('res.currency', 'Currency', required=True),
        "date": fields.date(string="Date"),
        "source_date": fields.date(string="Source Date", help="This date is for source_date for analytic lines"),
    }

    _defaults ={
        'name': 'Distribution Line',
        'date': lambda *a: strftime('%Y-%m-%d'),
        'source_date': lambda *a: strftime('%Y-%m-%d'),
    }

distribution_line()

class cost_center_distribution_line(osv.osv):
    _name = "cost.center.distribution.line"
    _inherit = "distribution.line"
    
cost_center_distribution_line()

class funding_pool_distribution_line(osv.osv):
    _name = "funding.pool.distribution.line"
    _inherit = "distribution.line"
    _columns = {
        "cost_center_id": fields.many2one('account.analytic.account', 'Cost Center Account'),
    }
    
funding_pool_distribution_line()

class free_1_distribution_line(osv.osv):
    _name = "free.1.distribution.line"
    _inherit = "distribution.line"

free_1_distribution_line()

class free_2_distribution_line(osv.osv):
    _name = "free.2.distribution.line"
    _inherit = "distribution.line"

free_2_distribution_line()

class analytic_distribution(osv.osv):
    _inherit = "analytic.distribution"

    def _get_lines_count(self, cr, uid, ids, name, args, context={}):
        """
        Get count of each analytic distribution lines type.
        Example: with an analytic distribution with 2 cost center, 3 funding pool and 1 Free 1:
        2 CC; 3 FP; 1 F1; 0 F2; 
        (Number of chars: 20 chars + 4 x some lines number)
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse given invoices
        for distrib in self.browse(cr, uid, ids, context=context):
            txt = ''
            txt += str(len(distrib.cost_center_lines) or '0') + ' CC; '
            txt += str(len(distrib.funding_pool_lines) or '0') + ' FP; '
            txt += str(len(distrib.free_1_lines) or '0') + ' F1; '
            txt += str(len(distrib.free_2_lines) or '0') + ' F2; '
            if not txt:
                txt = ''
            res[distrib.id] = txt
        return res

    _columns = {
        'cost_center_lines': fields.one2many('cost.center.distribution.line', 'distribution_id', 'Cost Center Distribution'),
        'funding_pool_lines': fields.one2many('funding.pool.distribution.line', 'distribution_id', 'Funding Pool Distribution'),
        'free_1_lines': fields.one2many('free.1.distribution.line', 'distribution_id', 'Free 1 Distribution'),
        'free_2_lines': fields.one2many('free.2.distribution.line', 'distribution_id', 'Free 2 Distribution'),
        'lines_count': fields.function(_get_lines_count, method=True, type='char', size=256,
            string="Analytic distribution count", readonly=True, store=False),
    }

    def update_distribution_line_amount(self, cr, uid, ids, amount=False, context={}):
        """
        Update amount on distribution lines for given distribution (ids)
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not amount:
            return False
        # Process distributions
        for distrib_id in ids:
            for dl_name in ['cost.center.distribution.line', 'funding.pool.distribution.line', 'free.1.distribution.line', 'free.2.distribution.line']:
                dl_obj = self.pool.get(dl_name)
                dl_ids = dl_obj.search(cr, uid, [('distribution_id', '=', distrib_id)], context=context)
                for dl in dl_obj.browse(cr, uid, dl_ids, context=context):
                    dl_vals = {
                        'amount': round(dl.percentage * amount) / 100.0,
                    }
                    dl_obj.write(cr, uid, [dl.id], dl_vals, context=context)
        return True

    def create_funding_pool_lines(self, cr, uid, ids, context={}):
        """
        Create funding pool lines regarding cost_center_lines from analytic distribution.
        If funding_pool_lines exists, then nothing appends.
        By default, add funding_pool_lines with MSF Private Fund element (written in an OpenERP demo file).
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse distributions
        for distrib in self.browse(cr, uid, ids, context=context):
            if distrib.funding_pool_lines:
                res[distrib.id] = False
                continue
            # Browse cost center lines
            for line in distrib.cost_center_lines:
                # Search MSF Private Fund
                pf_id = self.pool.get('account.analytic.account').search(cr, uid, [('code', '=', 'PF'), ('category', '=', 'FUNDING')], context=context, limit=1)
                if pf_id:
                    vals = {
                        'analytic_id': pf_id[0],
                        'amount': line.amount or 0.0,
                        'percentage': line.percentage or 0.0,
                        'currency_id': line.currency_id and line.currency_id.id or False,
                        'distribution_id': distrib.id or False,
                        'cost_center_id': line.analytic_id and line.analytic_id.id or False,
                    }
                    new_pf_line_id = self.pool.get('funding.pool.distribution.line').create(cr, uid, vals, context=context)
            res[distrib.id] = True
        return res

analytic_distribution()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
