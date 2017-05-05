# encoding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from osv import osv, fields
from lxml import etree
from tools.translate import _

class warning_import_currencies_lines(osv.osv_memory):
    _name = 'warning.import.currencies.lines'

    _columns = {
        'code': fields.char("Code", size='3', required=True),
        'rate': fields.float('Rate', digits=(12,6), required=True),
        'wizard_id': fields.many2one('warning.import.currencies', 'Wizard', required=True),
    }

warning_import_currencies_lines()

class warning_import_currencies(osv.osv_memory):
    _name = 'warning.import.currencies'
    
    _columns = {
        'currency_list': fields.text("Currency list"),
        'date': fields.date("Date", required=True),
    }

    def button_ok(self, cr, uid, ids, context=None):
        """
        Search attached lines and write new rates
        """
        for w_id in ids:
            line_ids = self.pool.get('warning.import.currencies.lines').search(cr, uid, [('wizard_id', '=', w_id)])
            for line in self.pool.get('warning.import.currencies.lines').browse(cr, uid, line_ids, context=context):
                c_ids = self.pool.get('res.currency').search(cr, uid, [('name', '=', line.code), ('active', 'in', ['t', 'f'])])
                if isinstance(c_ids, (int, long)):
                    c_ids = [c_ids]
                if not c_ids:
                    raise osv.except_osv(_('Warning'), _('Currency %s not found!') % line.code or '')
                c_rate_ids = self.pool.get('res.currency.rate').search(cr, uid, [('currency_id', 'in', c_ids), ('name', '=', line.wizard_id.date)], context=context)
                if isinstance(c_rate_ids, (int, long)):
                    c_rate_ids = [c_rate_ids]
                # Prepare some values
                rate_vals = {'name': line.wizard_id.date, 'rate': line.rate}
                if c_rate_ids:
                    self.pool.get('res.currency.rate').write(cr, uid, c_rate_ids, rate_vals, context=context)
                else:
                    rate_vals.update({'currency_id': c_ids[0]})
                    self.pool.get('res.currency.rate').create(cr, uid, rate_vals, context=context)
        return {'type' : 'ir.actions.act_window_close'}

warning_import_currencies()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
