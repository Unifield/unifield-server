# -*- coding: utf-8 -*-

from osv import fields, osv
import time
from tools.translate import _
from tools import misc
from datetime import datetime
from dateutil.relativedelta import relativedelta
import threading
import pooler
from tempfile import NamedTemporaryFile
from base64 import b64decode
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML


#----------------------------------------------------------
# Assets
#----------------------------------------------------------
class product_asset_type(osv.osv):
    _name = "product.asset.type"
    _description = "Specify the type of asset at product level"
    _order = 'name, id'
    _trace = True

    _columns = {
        'name': fields.char('Name', size=64, required=True, translate=1),
        'description': fields.char('Description', size=512),
        'active': fields.boolean('Active'),
        'useful_life_id': fields.one2many('product.asset.useful.life', 'asset_type_id', 'Useful Life (years)'),
    }

    _defaults = {
        'active': True,
    }

    _sql_constraints = [
        ('unique_name', 'unique(name)', 'Name already exists.'),
    ]
product_asset_type()

class product_asset_event_type(osv.osv):
    _name = 'product.asset.event.type'
    _description = 'Event Type'
    _order = 'name, id'
    _trace = True

    _columns = {
        'name': fields.char('Name', size=512, required=True, translate=1),
        'is_disposal': fields.boolean('Is Disposal'),
        'expense_account_id': fields.many2one('account.account', 'P&L account', domain=[('user_type_code', 'in', ['expense', 'income'])]), #TODO FIX DOMAIN ?
        'active': fields.boolean('Active')
    }
    _defaults = {
        'active': True,
    }

    _sql_constraints = [
        ('unique_name', 'unique(name)', 'Name already exists.'),
    ]
product_asset_event_type()

class product_asset_useful_life(osv.osv):
    _name = 'product.asset.useful.life'
    _description = 'Asset Useful Life'
    _rec_name = 'year'
    _order = 'year, id'
    _trace = True

    _columns = {
        'asset_type_id': fields.many2one('product.asset.type', 'Asset Type', required=1),
        'year': fields.integer('Years', required=1),
        'is_active': fields.boolean('Active'),
    }
    _defaults = {
        'is_active': True,
    }

    def name_get(self, cr, uid, ids, context=None):
        '''
        override because no name field is defined
        '''
        result = []
        for ul in self.read(cr, uid, ids, ['year'], context):
            if ul['year'] > 1:
                result.append((ul['id'], '%s %s' % (ul['year'], _('years'))))
            else:
                result.append((ul['id'], '%s %s' % (ul['year'], _('year'))))

        return result

    _sql_constraints = [
        ('unique_year', 'unique(year, asset_type_id)', 'Useful life already exists.'),
    ]
product_asset_useful_life()

class product_asset(osv.osv):
    _name = "product.asset"
    _description = "A specific asset of a product"
    _order='id desc'
    _trace = True

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        asset = self.browse(cr, uid, ids[0], context=context)

        vals = {
            'total_amount': asset.invo_value,
            'asset_id': asset.id,
            'currency_id': asset.invo_currency.id or False,
            'state': 'dispatch',
            'account_id': asset.asset_pl_account_id.id,
            'posting_date': time.strftime('%Y-%m-%d'),
            'document_date': time.strftime('%Y-%m-%d'),
        }
        if asset.analytic_distribution_id:
            vals.update({'distribution_id': asset.analytic_distribution_id.id})

        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)

        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        return {
            'name': _('Global analytic distribution'),
            'type': 'ir.actions.act_window',
            'res_model': 'analytic.distribution.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': [wiz_id],
            'context': context,
        }

    def button_reset_distribution(self, cr, uid, ids, context=None):
        line_obj = self.pool.get('product.asset.line')
        move_line_obj = self.pool.get('account.move.line')
        to_reset_asset_line_ids = line_obj.search(cr, uid, ['&', '&', ('asset_id', 'in', ids), '|', ('move_id', '=', False), ('move_id.state', '!=', 'posted'), ('analytic_distribution_id', '!=', False)])
        to_reset_move_line_ids = move_line_obj.search(cr, uid, [('move_id.state', '!=', 'posted'), ('analytic_distribution_id', '!=', False), ('asset_line_id', 'in', to_reset_asset_line_ids)])
        if to_reset_move_line_ids:
            move_line_obj.write(cr, uid, to_reset_move_line_ids, {'analytic_distribution_id': False})
        if to_reset_asset_line_ids:
            line_obj.write(cr, uid, to_reset_asset_line_ids, {'analytic_distribution_id': False})
        return True

    def _getRelatedProductFields(self, cr, uid, productId, update_account=True):
        '''
        get related fields from product
        '''
        # if no product, return empty dic
        if not productId:
            return {}

        # fetch the product
        product = self.pool.get('product.product').browse(cr, uid, productId, fields_to_fetch=['default_code', 'name', 'nomenclature_description', 'categ_id', 'property_account_expense'])

        result = {
            'prod_int_code': product.default_code,
            'prod_int_name': product.name,
            'nomenclature_description': product.nomenclature_description,
        }
        if update_account:
            result.update({
                'asset_bs_depreciation_account_id': product.categ_id.asset_bs_depreciation_account_id.id or False,
                'asset_pl_account_id': product.categ_id.asset_pl_account_id.id or product.property_account_expense.id or product.categ_id.property_account_expense_categ.id or False,
            })


        return result

    def copy(self, cr, uid, id, default=None, context=None):
        '''
        override copy to update the asset code which comes from a sequence
        '''
        if not default:
            default = {}
        default.update({
            'instance_id': False,
            'analytic_distribution_id': False,
            'line_ids': False,
            'lock_open': False,
            'journal_id': False,
        })
        # call to super
        return super(product_asset, self).copy(cr, uid, id, default, context=context)

    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        do not copy asset events
        '''
        if not default:
            default = {}
        default.update({
            'name': False,
            'from_invoice': False,
            'from_sync': False,
            'event_ids': [],
            'instance_id': False,
            'invoice_id': False,
            'move_line_id': False,
            'quantity_divisor': False,
            'invo_value': False,
            'invo_currency': False,
            'invo_date': False,
            'invo_supplier_id': False,
            'invo_donator_code': False,
            'invo_certif_depreciation': False,
            'serial_nb': False,
            'brand': False,
            'type': False,
            'model': False,
            'year': False,
            'project_po': False,
            'orig_mission_code': False,
            'international_po': False,
            'arrival_date': False,
            'receipt_place': False,
            'comment': False,
            'line_ids': [],
            'depreciation_amount': False,
            'disposal_amount': False,
            'start_date': False,
            'depreciation_method': False,
        })
        return super(product_asset, self).copy_data(cr, uid, id, default, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True

        if isinstance(ids,int):
            ids = [ids]

        if context is None:
            context = {}

        if context.get('sync_update_execution') and self.pool.get('res.company')._get_instance_level(cr, uid) != 'project':
            # prevent an update from project to overwrite data
            for f in  ['asset_type_id', 'useful_life_id', 'asset_bs_depreciation_account_id', 'asset_pl_account_id', 'start_date', 'move_line_id']:
                if f in vals:
                    del(vals[f])

        # fetch the product
        if 'product_id' in vals:
            productId = vals['product_id']
            # add readonly fields to vals
            vals.update(self._getRelatedProductFields(cr, uid, productId, update_account=False))

        if 'move_line_id' in vals:
            for current in self.browse(cr, uid, ids, context=context):
                new_data = vals.copy()
                if not current.from_invoice and not current.from_sync and (current.move_line_id.id != vals['move_line_id'] or 'quantity_divisor' in vals and current.quantity_divisor != vals['quantity_divisor']):
                    new_data.update(self._getRelatedMoveLineFields(cr, uid, vals['move_line_id'], divisor=vals.get('quantity_divisor', current.quantity_divisor), context=context))
                super(product_asset, self).write(cr, uid, current.id, new_data, context=context)

            return True

        return super(product_asset, self).write(cr, uid, ids, vals, context)

    def create(self, cr, uid, vals, context=None):
        '''
        override create method to force readonly fields to be saved to db
        on data creation
        '''

        if not context:
            context = {}

        from_sync = context.get('sync_update_execution')

        if from_sync:
            vals['from_sync'] = True
            vals['state'] = 'open'

        # fetch the product
        if 'product_id' in vals and not context.get('from_import'):
            productId = vals['product_id']
            # add readonly fields to vals
            vals.update(self._getRelatedProductFields(cr, uid, productId, update_account=not from_sync))

        if not from_sync and not vals.get('from_invoice') and not context.get('from_import') and 'move_line_id' in vals:
            vals.update(self._getRelatedMoveLineFields(cr, uid, vals['move_line_id'], divisor=vals.get('quantity_divisor'), context=context))

        # UF-1617: set the current instance into the new object if it has not been sent from the sync
        if 'instance_id' not in vals or not vals['instance_id']:
            vals['instance_id'] = self.pool.get('res.company')._get_instance_id(cr, uid)

        return super(product_asset, self).create(cr, uid, vals, context)

    def change_quantity_divisor(self, cr, uid, ids, quantity_divisor, move_line_id, context=None):
        if move_line_id and quantity_divisor:
            ml = self.pool.get('account.move.line').browse(cr, uid, move_line_id, fields_to_fetch=['debit_currency', 'quantity'], context=context)

            return {
                'value': {
                    'invo_value': round(float(ml.debit_currency) / quantity_divisor, 2),
                }
            }
        return {}

    def onChangeProductId(self, cr, uid, ids, productId):
        '''
        on change function when the product is changed
        '''
        result = {}

        # no product selected
        if not productId:
            return result

        result.update({'value': self._getRelatedProductFields(cr, uid, productId)
                       })

        return result

    def change_asset_type_id(self, cr, uid, _id, asset_type_id, useful_life_id, context=None):
        list = [()]
        if asset_type_id:
            list = self.pool.get('product.asset.useful.life')._name_search(cr, uid, '', [('asset_type_id', '=', asset_type_id), ('is_active', '=', True)] , limit=None, name_get_uid=1, context=context)
            if len(list) == 1:
                list = [(list[0][0], list[0][1], 'selected')]
        return {'value': {'useful_life_id': list}}

    def get_selection_useful_life_id(self, cr, uid, _id, fields, context=None):
        if not _id:
            return []
        if _id:
            asset_id = self.browse(cr, uid, _id, fields_to_fetch=['asset_type_id'], context=context).asset_type_id.id
            if asset_id:
                return self.pool.get('product.asset.useful.life')._name_search(cr, uid, '', [('asset_type_id', '=', asset_id)] , limit=None, name_get_uid=1, context=context)

        return []

    def onChangeYear(self, cr, uid, ids, year):
        '''
        year must be 4 digit long and comprised between 1900 and 2100
        '''
        value = {}
        warning = {}
        result = {'value': value, 'warning': warning}

        if not year:
            return result

        # check that the year specified is a number
        try:
            intValue = int(year)
        except:
            intValue = False

        if not intValue:
            warning.update({
                'title':'The format of year is invalid.',
                'message':
                        'The format of the year must be 4 digits, e.g. 1983.'
            })
        elif len(year) != 4:
            warning.update({
                'title':'The length of year is invalid.',
                'message':
                        'The length of year must be 4 digits long, e.g. 1983.'
            })
        elif (intValue < 1900) or (intValue > 2100):
            warning.update({
                'title':'The year is invalid.',
                'message':
                        'The year must be between 1900 and 2100.'
            })

        # if a warning has been generated, clear the field
        if 'title' in warning:
            value.update({'year': ''})

        return result

    def _getRelatedMoveLineFields(self, cr, uid, move_line_id, on_change=False, with_product=False, divisor=False, context=None):
        if not move_line_id:
            return {}
        ml = self.pool.get('account.move.line').browse(cr, uid, move_line_id, fields_to_fetch=['date', 'debit_currency', 'currency_id', 'product_id', 'quantity', 'partner_id'], context=context)

        data = {
            'invo_date': ml.date,
            'invo_value': ml.debit_currency,
            'invo_currency': ml.currency_id.id,
            'invo_supplier_id': ml.partner_id and ml.partner_id.id or False
        }

        if divisor:
            if divisor is True:
                divisor = ml.quantity and int(ml.quantity) or False

            if divisor:
                data['invo_value'] = round(float(ml.debit_currency) / divisor, 2)
                data['quantity_divisor'] = divisor

        if on_change:
            data['start_date'] = ml.date
        if with_product and ml.product_id:
            data['product_id'] = ml.product_id.id
            data.update(self._getRelatedProductFields(cr, uid, ml.product_id.id, True))

        return data


    def change_invo_date(self, cr, uid, ids, move_line_id, product_id, context=None):
        if move_line_id:
            return {'value': self._getRelatedMoveLineFields(cr, uid, move_line_id, on_change=True, with_product=not product_id, divisor=True, context=context)}
        return {'value': {'start_date': False, 'invo_date': False, 'invo_value': False, 'invo_currency': False, 'divisor': False, 'invo_supplier_id': False}}

    def _get_book_value(self, cr, uid, ids, field_name, args, context=None):
        if not ids:
            return {}
        ret = {}
        for _id in ids:
            ret[_id] = {'depreciation_amount': False,  'disposal_amount': False}
        cr.execute('''
            select
                a.id, sum(l.amount), a.invo_value
            from
                product_asset a, product_asset_line l
            where
                a.id = l.asset_id
                and a.id in %s
                and l.move_id is not null
                and coalesce(l.is_initial_line, 'f') = 'f'
            group by a.id
        ''', (tuple(ids), ))
        for x in cr.fetchall():
            ret[x[0]] = {'depreciation_amount': x[1]}
            if x[2]:
                ret[x[0]]['disposal_amount'] = x[2] - x[1]

        return ret

    def _get_has_posted_lines(self, cr, uid, ids, field_name, args, context=None):
        ret = {}
        if not ids:
            return {}
        for _id in ids:
            ret[_id] = False
        cr.execute("select asset_id from product_asset_line where move_id is not null and asset_id in %s group by asset_id", (tuple(ids), ))
        for x in cr.fetchall():
            ret[x[0]] = True
        return ret

    def _get_can_be_disposed(self, cr, uid, ids, field_name, args, context=None):
        ret = {}
        if not ids:
            return {}
        for _id in ids:
            ret[_id] = False

        cr.execute('''
            select
                a.id
            from
                product_asset a
                left join product_asset_line l on l.asset_id = a.id
                left join account_move m on m.asset_id = a.id and m.state = 'draft'
            where
                a.id in %s and
                a.state = 'running'
            group by a.id
            having  (
                count(l.is_disposal='t' or NULL) = 0
                and (count(m.id) > 0 or count(l.move_id is NULL or NULL) > 0)
            )
        ''', (tuple(ids), ))
        for x in cr.fetchall():
            ret[x[0]] = True
        return ret

    def _get_instance_level(self, cr, uid, ids, field_name, args, context=None):
        level = self.pool.get('res.company')._get_instance_level(cr, uid)
        res = {}
        for _id in ids:
            res[_id] = level
        return res

    def _search_period_id(self, cr, uid, obj, name, args, context=None):
        if context is None:
            context = {}
        if not args:
            return []
        for arg in args:
            if arg[0] == 'period_id' and (arg[1] != '=' or not arg[2]):
                raise osv.except_osv(_('Error !'), _('Filter not implemented on %s') % name)
            period = self.pool.get('account.period').browse(cr, uid, arg[2], fields_to_fetch=['date_start', 'date_stop'], context=context)
            return [('start_date', '>=', period.date_start), ('start_date', '<=', period.date_stop)]
        return []


    def _get_journal_domain(self, cr, uid, context=None):
        return ['|', ('type', 'in', ['purchase', 'intermission']), '&', ('instance_id.level', '=', 'coordo'), ('type', 'in', ['correction_hq', 'hq'])]

    _columns = {
        # asset
        'name': fields.char('Asset Code', size=128, readonly=True),
        'asset_type_id': fields.many2one('product.asset.type', 'Asset Type'), # from product
        'description': fields.char('Asset Description', size=128),
        'product_id': fields.many2one('product.product', 'Product', required=True, ondelete='cascade'),
        'external_asset_id': fields.char('External Asset ID', size=32),
        # msf codification
        'prod_int_code': fields.char('Product Code', size=128, readonly=True), # from product
        'prod_int_name': fields.char('Product Description', size=128, readonly=True), # from product
        'nomenclature_description': fields.char('Product Nomenclature', size=128, readonly=True), # from product when merged - to be added in _getRelatedProductFields and add dependency to module product_nomenclature
        'hq_ref': fields.char('HQ Reference', size=128),
        'local_ref': fields.char('Local Reference', size=128),
        # asset reference
        'serial_nb': fields.char('Serial Number', size=128), #required=True),
        'brand': fields.char('Brand', size=128), # required=True),
        'type': fields.char('Type', size=128), # required=True),
        'model': fields.char('Model', size=128), # required=True),
        'year': fields.char('Year', size=4),
        # remark
        'comment': fields.text('Comment'),
        # traceability
        'project_po': fields.char('Project PO', size=128),
        'orig_mission_code': fields.char('Original Mission Code', size=128), # required=True),
        'international_po': fields.char('International PO', size=128), # required=True),
        'arrival_date': fields.date('Arrival Date'), # required=True),
        'receipt_place': fields.char('Receipt Place', size=128), # required=True),
        # Invoice
        'invo_date': fields.date('Invoice Date', readonly=1),
        'invo_value': fields.float('Value', readonly=1),
        'invoice_id': fields.many2one('account.invoice', 'Invoice'),
        'move_line_id': fields.many2one('account.move.line', 'Journal Item', domain="['&', '&', '&', ('journal_id.type', 'in', ['purchase', 'correction_hq', 'hq', 'intermission']), ('debit', '>', 0), ('move_id.state', '=', 'posted'), ('account_id.user_type_code', 'in', ['asset', 'expense'])]", context="{'from_asset_journal_domain': True}"), # for domain see also _get_journal_domain used by G/L journal domain
        'quantity_divisor': fields.integer_null('Divisor Quantity', help='This quantity will divide the total invoice value.'),
        'invoice_line_id': fields.many2one('account.invoice.line', 'Invoice Line'),
        'invo_currency': fields.many2one('res.currency', 'Currency', readonly=1),
        'invo_supplier_id': fields.many2one('res.partner', 'Supplier', readonly=1),
        'invo_donator_code': fields.char('Donator Code', size=128),
        'invo_certif_depreciation': fields.char('Certificate of Depreciation', size=128),
        # event history
        'event_ids': fields.one2many('product.asset.event', 'asset_id', 'Events'),
        # UF-1617: field only used for sync purpose
        'instance_id': fields.many2one('msf.instance', string="Instance Creator", readonly=True, required=False),
        'xmlid_name': fields.char('XML Code, hidden field', size=128),
        'from_invoice': fields.boolean('From Invoice', readonly=1),
        'from_sync': fields.boolean('From Sync', readonly=1),
        'state': fields.selection([('draft', 'Draft'), ('open', 'Open'), ('running', 'Running'), ('done', 'Done'), ('cancel', 'Cancel')], 'State', readonly=1),
        'asset_bs_depreciation_account_id': fields.many2one('account.account', 'Asset B/S Depreciation Account', domain=[('type', '=', 'other'), ('user_type_code', '=', 'asset')]),
        'asset_pl_account_id': fields.many2one('account.account', 'Asset P&L Depreciation Account', domain=[('user_type_code', 'in', ['expense', 'income'])]),
        'useful_life_id': fields.many2one('product.asset.useful.life', 'Useful Life', ondelete='restrict'),
        'start_date': fields.date('Start Date'),
        'line_ids': fields.one2many('product.asset.line', 'asset_id', 'Depreciation Lines'),
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'depreciation_amount': fields.function(_get_book_value, string='Depreciation', type='float', method=True, help="Sum of all Asset journal item lines", multi='get_book', with_null=True),
        'disposal_amount': fields.function(_get_book_value, string='Remaining net value', type='float', method=True, multi='get_book', with_null=True),
        'journal_id': fields.many2one('account.journal', 'Journal', readonly=1),
        'lock_open': fields.boolean('Lock fields in openstate', readonly='1'),
        'has_posted_lines': fields.function(_get_has_posted_lines, string='Has at least one posted line', type='boolean', method=True),
        'can_be_disposed': fields.function(_get_can_be_disposed, string='Can be diposed', type='boolean', method=True),
        'instance_level': fields.function(_get_instance_level, string='Instance Level', type='char', method=True),
        'prorata': fields.boolean('Prorata Temporis'),
        'depreciation_method': fields.selection([('straight', 'Straight Line')], 'Depreciation Method'),
        'period_id': fields.function(misc.get_fake, fnct_search=_search_period_id, method=True, type='many2one', relation='account.period', string='Start Period', domain=[('special', '=', False)]),
    }

    def unlink(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
            ids = [ids]

        error = []
        if self.search_exists(cr, uid, [('id', 'in', ids), ('state', '!=', 'draft')], context=context):
            error.append(_('Only Draft asset can be deleted.'))

        if self.search_exists(cr, uid, [('id', 'in', ids), ('state', '=', 'draft'), ('from_invoice', '=', True)], context=context):
            error.append(_('Asset from invoice can not be deleted.'))

        if error:
            raise osv.except_osv(_('Error !'), '\n'.join(error))

        return super(product_asset, self).unlink(cr, uid, ids, context=context)

    def _get_default_journal(self, cr, uid, context=None):
        j_ids = self.pool.get('account.journal').search(cr, uid, [('code', '=', 'DEP'), ('type', '=', 'depreciation'), ('is_current_instance', '=', True)], context=context)
        if j_ids:
            return j_ids[0]
        return False

    _defaults = {
        'depreciation_method': 'straight',
        'prorata': False,
        'arrival_date': lambda *a: time.strftime('%Y-%m-%d'),
        'receipt_place': 'Country/Project/Activity',
        'state': 'draft',
        'journal_id': _get_default_journal,
        'instance_level': lambda self, cr, uid, context: self.pool.get('res.company')._get_instance_level(cr, uid),
        'quantity_divisor': False,
    }

    _sql_constraints = [('asset_name_uniq', 'unique(name)', 'Asset Code must be unique.')]

    def button_open_asset(self, cr, uid, ids, context=None):
        draft_ids = self.search(cr, uid, [('id', 'in', ids), ('state', '=', 'draft')], context=context)
        if draft_ids:
            self._check_mandatory_fields(cr, uid, draft_ids, context)
        for draft_id in draft_ids:
            vals = {
                'name': self.pool.get('ir.sequence').get(cr, uid, 'product.asset'),
                'state': 'open',
            }
            if self.pool.get('res.company')._get_instance_level(cr, uid) == 'project':
                vals['lock_open'] = True
            self.write(cr, uid, draft_id, vals, context=context)

        return True

    def button_cancel_asset(self, cr, uid, ids, context=None):
        cancel_ids = self.search(cr, uid, [('id', 'in', ids), ('state', 'in', ['draft', 'open'])], context=context)
        if cancel_ids:
            self.write(cr, uid, cancel_ids, {'state': 'cancel'}, context=context)
        return True


    def button_set_as_open(self, cr, uid, ids, context=None):
        if self.pool.get('res.company')._get_instance_level(cr, uid) == 'project':
            return True
        to_open_ids = self.search(cr, uid, [('id', 'in', ids), ('state', '=', 'running')], context=context)
        if to_open_ids:
            to_change = []
            for asset in self.browse(cr, uid, to_open_ids, fields_to_fetch=['has_posted_lines'], context=context):
                if not asset.has_posted_lines:
                    to_change.append(asset.id)
            if to_change:
                self.write(cr, uid, to_change, {'state': 'open'}, context=context)
        return True

    def _delete_asset_line(self, cr, uid, ids, context=None):
        line_obj = self.pool.get('product.asset.line')
        non_draft_ids = line_obj.search(cr, uid, [('asset_id', 'in', ids), ('move_id', '!=', False)], context=context)
        if non_draft_ids:
            raise osv.except_osv(_('Error !'), _('Can not delete posted depreciation lines'))
        line_ids = line_obj.search(cr, uid, [('asset_id', 'in', ids)], context=context)
        if line_ids:
            line_obj.unlink(cr, uid, line_ids, context=context)
        return True

    def button_delete_draft_entries(self, cr, uid, ids, context=None):
        draft_ids = self.search(cr, uid, [('id', 'in', ids), ('state', '=', 'open')], context=context)
        if draft_ids:
            self._delete_asset_line(cr, uid, draft_ids, context=None)
            self.write(cr, uid, draft_ids, {'lock_open': False}, context=context)
        return True

    def _check_mandatory_fields(self, cr, uid, ids, context=None):
        fields = ['start_date', 'asset_bs_depreciation_account_id', 'asset_pl_account_id', 'useful_life_id', 'analytic_distribution_id', 'move_line_id']
        all_fields = {}
        missing_fields = []
        for asset in self.browse(cr, uid,  ids, fields_to_fetch=fields, context=context):
            for field in fields:
                if not asset[field]:
                    if not all_fields:
                        all_fields = self.fields_get(cr, uid, fields=fields, context=context)
                    missing_fields.append(all_fields[field].get('string', field))
                elif field == 'analytic_distribution_id' and asset['analytic_distribution_id'] and asset['asset_pl_account_id']:
                    ad_state = (self.pool.get('analytic.distribution')
                                ._get_distribution_state(cr, uid, asset['analytic_distribution_id'].id, False,
                                                         asset['asset_pl_account_id'].id, context=context,
                                                         doc_date=time.strftime('%Y-%m-%d'),
                                                         posting_date=time.strftime('%Y-%m-%d'), manual=True))
                    if ad_state != 'valid':
                        raise osv.except_osv(_('Error !'), _('Please provide a valid analytic distribution.'))

        if missing_fields:
            raise osv.except_osv(_('Error !'), _('Please fill the mandatory field: %s') % ', '.join(missing_fields))
        return True

    def force_generate_draft_entries(self, cr, uid, ids, context=None):
        self.button_generate_draft_entries(cr, uid, ids, context=context, display_period_warning=False)
        return {'type': 'ir.actions.act_window_close'}

    def button_generate_draft_entries(self, cr, uid, ids, context=None, display_period_warning=True):
        line_obj = self.pool.get('product.asset.line')
        tools_obj = self.pool.get('date.tools')

        if not ids:
            return False

        default_j = False
        asset = self.browse(cr, uid, ids[0], context=context)
        if asset.start_date < asset.invo_date:
            raise osv.except_osv(_('Error !'), _('Asset %s: Start Date (%s) must be after Invoice Date (%s).') % (
                asset.name,
                tools_obj.get_date_formatted(cr, uid, datetime=asset.start_date, context=context),
                tools_obj.get_date_formatted(cr, uid, datetime=asset.invo_date, context=context),
            ))

        if display_period_warning and asset.start_date and asset.invo_date and asset.start_date[0:7] != asset.invo_date[0:7]:
            msg = self.pool.get('message.action').create(cr, uid, {
                'title':  _('Warning'),
                'message': '<h3>%s</h3>' % (_('The Depreciation Start Date (%s) is not in the same period as the Invoice Date (%s)') % (
                    tools_obj.get_date_formatted(cr, uid, datetime=asset.start_date, context=context),
                    tools_obj.get_date_formatted(cr, uid, datetime=asset.invo_date, context=context),
                )
                ),
                'yes_action': lambda cr, uid, context: self.force_generate_draft_entries(cr, uid, ids, context=context),
                'yes_label': _('Process Anyway'),
                'no_label': _('Close window'),
            }, context=context)
            return self.pool.get('message.action').pop_up(cr, uid, [msg], context=context)


        if not asset.journal_id:
            default_j = self._get_default_journal(cr, uid, context=context)
            if not default_j:
                raise osv.except_osv(_('Error !'), _('Depreciation journal (code: DEP, type: depreciation) does not exist, please create a Depreciation G/L Journal'))

        if not asset.analytic_distribution_id:
            raise osv.except_osv(_('Error !'), _('Please create an Analytical Distribution on header.'))

        self._check_mandatory_fields(cr, uid, ids, context)

        alreary_posted_ids = line_obj.search(cr, uid, [('asset_id', 'in', ids), ('move_id', '!=', False)], context=context)
        if alreary_posted_ids:
            raise osv.except_osv(_('Error !'), _('%d Entries already created on %s, cannot replace entries') % (len(alreary_posted_ids), asset.name))

        to_del = []
        for line in asset.line_ids:
            to_del.append(line.id)
        if to_del:
            line_obj.unlink(cr, uid, to_del, context=context)

        to_create = []
        nb_month = asset.useful_life_id.year * 12
        start_dt = datetime.strptime(asset.start_date, '%Y-%m-%d')
        dep_value = float(asset.invo_value)/nb_month
        sum_deprecated_value = 0
        accumulated_rounded = 0
        date_first_entry = start_dt + relativedelta(months=1, day=1, days=-1)

        if False and asset.prorata:
            first_entry_nb_days = (start_dt + relativedelta(months=1, day=1) - start_dt).days
            deprecated_value = dep_value / date_first_entry.day * first_entry_nb_days
        else:
            start_dt = start_dt + relativedelta(day=1)
            deprecated_value = dep_value


        rounded_dep = round(deprecated_value, 2)
        if rounded_dep >= 0.01:
            to_create.append([date_first_entry, rounded_dep, start_dt, date_first_entry])
            accumulated_rounded += deprecated_value - rounded_dep
            sum_deprecated_value += rounded_dep

        for mt in range(1, nb_month):
            date = start_dt + relativedelta(months=mt+1, day=1, days=-1)
            value = dep_value
            if abs(accumulated_rounded) >= 0.01:
                value = value + accumulated_rounded
                accumulated_rounded = 0

            rounded_dep = round(value, 2)
            if rounded_dep >= 0.01:
                to_create.append([date, rounded_dep, date + relativedelta(day=1), date])
                sum_deprecated_value +=  rounded_dep
                accumulated_rounded += value - rounded_dep
            else:
                accumulated_rounded += value

        remaining = round(asset.invo_value - sum_deprecated_value, 2)
        if False and asset.prorata and remaining > 1:
            last_entry_date = start_dt + relativedelta(months=nb_month+1, day=1, days=-1)
            to_create.append([last_entry_date, remaining, last_entry_date + relativedelta(day=1), last_entry_date + relativedelta(day=start_dt.day)])
        else:
            to_create[-1][1] = to_create[-1][1] + remaining

        if to_create and not asset.from_invoice:
            bs_prod_account_id = asset.product_id.categ_id and asset.product_id.categ_id.asset_bs_account_id and asset.product_id.categ_id.asset_bs_account_id.id or False
            if not bs_prod_account_id:
                raise osv.except_osv(_('Error'), _('Product Category %s has no Asset Balance Sheet Account') % (asset.product_id.categ_id and asset.product_id.categ_id.name or asset.product_id.default_code, ))

            new_ad_id = False
            if asset.move_line_id.analytic_distribution_id:
                new_ad_id = self.pool.get('analytic.distribution').copy(cr, uid, asset.move_line_id.analytic_distribution_id.id, {}, context=context)
            line_obj.create(cr, uid, {
                'asset_id': asset.id,
                'asset_bs_depreciation_account_id': bs_prod_account_id,
                'asset_pl_account_id': asset.move_line_id.account_id.id,
                'date': to_create[0][0],
                'amount': -1*asset.invo_value,
                'is_initial_line': True,
                'analytic_distribution_id': new_ad_id,
            }, context=context)

        for line in to_create:
            line_obj.create(cr, uid, {
                'asset_id': asset.id,
                'asset_bs_depreciation_account_id': asset.asset_bs_depreciation_account_id.id,
                'asset_pl_account_id': asset.asset_pl_account_id.id,
                'date': line[0],
                'amount': line[1],
                'first_dep_day': line[2],
                'last_dep_day': line[3],
            }, context=context)

        if to_create:
            to_write = {'lock_open': True}
            if default_j:
                to_write['journal_id'] = default_j
            self.write(cr, uid, ids[0], to_write, context=context)
        return True


    def button_dispose(self, cr, uid, ids, context=None):
        asset = self.browse(cr, uid, ids[0], fields_to_fetch=['move_line_id'], context=context)
        wiz_id = self.pool.get('product.asset.disposal').create(cr, uid, {'asset_id': ids[0], 'disposal_bs_account': asset.move_line_id and asset.move_line_id.account_id.id or False}, context=context)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.asset.disposal',
            'res_id': wiz_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
            'height': '400px',
            'width': '720px',
        }

    def open_asset_account_move_line(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        asset_ids = context.get('active_ids', [])
        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'account.action_account_moves_all_a', ['tree', 'form'],context=context)
        ji_with_ad_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_asset', 'view_account_move_line_asset_tree')
        views = []
        for x in res['views']:
            if x[1] == 'tree':
                views.append((ji_with_ad_view_id[1], 'tree'))
            else:
                views.append(x)
        res['name'] = _('Asset lines')
        res['views'] = views
        res['domain'] = [('move_id.asset_id', 'in', asset_ids)]
        res['target'] = 'current'
        return res

    def open_asset_account_move(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        asset_ids = context.get('active_ids', [])
        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'account.action_move_journal_line', ['tree', 'form'],context=context)
        res['domain'] = [('asset_id', 'in', asset_ids)]
        res['target'] = 'current'
        return res

    def change_line(self, cr , uid, ids, context=None):
        if ids:
            raw_display_strings_state = dict(self._columns['state'].selection)
            display_strings_state = dict([(k, _(v)) \
                                          for k, v in raw_display_strings_state.items()])

            display_strings = {}
            display_strings["state"] = display_strings_state

            d = self.read(cr, uid, ids[0], ['depreciation_amount', 'disposal_amount', 'state', 'has_posted_lines'], context=context)
            return {'value': {
                'depreciation_amount': d['depreciation_amount'],
                'disposal_amount': d['disposal_amount'],
                'state': d['state'],
                'has_posted_lines': d['has_posted_lines'],
            },
                'display_strings': display_strings
            }
        return {}

    def test_and_set_done(self, cr , uid, ids, context=None):
        if isinstance(ids, int):
            ids = [ids]
        cr.execute('''
            select
                a.id
            from
                product_asset a
                left join product_asset_line l on l.asset_id = a.id
                left join account_move_line ml on ml.asset_line_id = l.id
                left join account_move m on m.id = ml.move_id and m.state = 'posted'
            where
                a.id in %s and
                a.state = 'running'
            group by a.id
            having  (
                count(l.id) = count(m.id)
            )
        ''', (tuple(ids), ))
        to_close = [x[0] for x in cr.fetchall()]
        if to_close:
            self.write(cr, uid, to_close, {'state': 'done'}, context=context)
            return True
        return False

product_asset()


class product_asset_event(osv.osv):
    _name = "product.asset.event"
    _rec_name = 'asset_id'
    _description = "Event for asset follow up"
    _order = 'date desc, id desc'
    _trace = True

    eventTypeSelection = [('reception', 'Reception'),
                          ('startUse', 'Start Use'),
                          ('repairing', 'Repairing'),
                          ('endUse', 'End Use'),
                          ('obsolete', 'Obsolete'),
                          ('loaning', 'Loaning'),
                          ('transfer', 'Transfer (internal)'),
                          ('donation', 'Donation (external)'),
                          ('other', 'Other'),
                          ('damage', 'Damage'),
                          ('missing', 'Missing'),
                          ('sale', 'Sale'),
                          ]

    def name_get(self, cr, uid, ids, context=None):
        '''
        override because no name field is defined
        '''
        result = []
        for e in self.read(cr, uid, ids, ['asset_id', 'date'], context):
            # e = dict: {'asset_id': (68, 'AF/00045'), 'date': '2011-05-05', 'id': 75}
            result.append((e['id'], '%s - %s'%(e['asset_id'][1], e['date'])))

        return result

    def _getRelatedAssetFields(self, cr, uid, assetId):
        '''
        get related fields from product
        '''
        result = {}
        # if no asset, return empty dic
        if not assetId:
            return result

        # newly selected asset object
        asset = self.pool.get('product.asset').browse(cr, uid, assetId)

        result.update({
            'product_id': asset.product_id.id,
            'asset_type_id': asset.asset_type_id.id,
            'serial_nb': asset.serial_nb,
            'brand': asset.brand,
            'model': asset.model,
        })

        return result

    def write(self, cr, user, ids, vals, context=None):
        '''
        override write method to force readonly fields to be saved to db
        on data update
        '''
        if not ids:
            return True
        # fetch the asset
        if 'asset_id' in vals:
            assetId = vals['asset_id']
            # add readonly fields to vals
            vals.update(self._getRelatedAssetFields(cr, user, assetId))

        # save the data to db
        return super(product_asset_event, self).write(cr, user, ids, vals, context)

    def create(self, cr, user, vals, context=None):
        '''
        override create method to force readonly fields to be saved to db
        on data creation
        '''
        # fetch the asset
        if 'asset_id' in vals:
            assetId = vals['asset_id']
            # add readonly fields to vals
            vals.update(self._getRelatedAssetFields(cr, user, assetId))

        # save the data to db
        return super(product_asset_event, self).create(cr, user, vals, context)

    def onChangeAssetId(self, cr, uid, ids, assetId):

        result = {}

        # no asset selected
        if not assetId:
            return result

        result.update({'value': self._getRelatedAssetFields(cr, uid, assetId)})

        return result

    _columns = {
        # event information
        'date': fields.date('Date', required=True, select=1),
        'location': fields.char('Location', size=128, required=True),
        'proj_code': fields.char('Project Code', size=128),
        'event_type_id': fields.many2one('product.asset.event.type', 'Event Type', required=True, add_empty=True),
        # selection
        'asset_id': fields.many2one('product.asset', 'Asset Code', required=True, ondelete='cascade', domain=[('state', '=', 'running')]),
        'product_id': fields.many2one('product.product', 'Product', readonly=True, ondelete='cascade'),
        'serial_nb': fields.char('Serial Number', size=128, readonly=True),
        'brand': fields.char('Brand', size=128, readonly=True), # from asset
        'model': fields.char('Model', size=128, readonly=True), # from asset
        'comment': fields.text('Comment'),
        'asset_name': fields.related('asset_id', 'name', type='char', readonly=True, size=128, store=False, write_relate=False, string="Asset"),
        'asset_type_id': fields.many2one('product.asset.type', 'Asset Type', readonly=True), # from asset
        'asset_state': fields.related('asset_id', 'state', string='Asset State', type='selection', selection=[('draft', 'Draft'), ('running', 'Running'), ('done', 'Done'), ('cancel', 'Cancel')], readonly=1),
    }

    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d'),
    }

product_asset_event()

class product_asset_line(osv.osv):
    _name = 'product.asset.line'
    _rec_name = 'date'
    _order = 'date, id'
    _description = "Depreciation Lines"
    _trace = True

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'analytic_distribution_id': False,
            'initial_line': False,
        })
        return super(product_asset, self).copy(cr, uid, id, default, context=context)

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch analytic distribution wizard on an invoice line
        """
        line = self.browse(cr, uid, ids[0], context=context)
        # Prepare values for wizard
        vals = {
            'total_amount': line.amount,
            'asset_line_id': line.id,
            'currency_id': line.asset_id.invo_currency.id or False,
            'state': 'dispatch',
            'account_id': line.asset_pl_account_id.id,
            'posting_date': line.date,
            'document_date': line.date,
        }
        if line.analytic_distribution_id:
            vals.update({'distribution_id': line.analytic_distribution_id.id})
        wiz_id = self.pool.get('analytic.distribution.wizard').create(cr, uid, vals, context=context)
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        return {
            'name': _('Analytic distribution'),
            'type': 'ir.actions.act_window',
            'res_model': 'analytic.distribution.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': [wiz_id],
            'context': context,
        }

    def _get_distribution_state(self, cr, uid, ids, name, args, context=None):
        # Prepare some values
        res = {}
        # Browse all given lines
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = self.pool.get('analytic.distribution')._get_distribution_state(cr, uid, line.analytic_distribution_id.id,
                                                                                          line.asset_id.analytic_distribution_id.id,
                                                                                          line.asset_pl_account_id.id, amount=line.amount,
                                                                                          doc_date=line.date, posting_date=line.date, manual=True)
        return res

    def _have_analytic_distribution_from_header(self, cr, uid, ids, name, arg, context=None):
        """
        If model has an analytic distribution, return False, else return True
        """
        res = {}
        for _id in ids:
            res[_id] = True
        for _id in self.search(cr, uid, [('id', 'in', ids), ('analytic_distribution_id', '!=', False)], context=context):
            res[_id] = False
        return res

    def _get_is_allocatable(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for _id in ids:
            res[_id] = True
        for _id in self.search(cr, uid, [('id', 'in', ids), ('asset_pl_account_id.is_analytic_addicted', '=', False)], context=context):
            res[_id] = False
        return res

    def _get_distribution_state_recap(self, cr, uid, ids, name, arg, context=None):
        res = {}
        state_dict = dict(self.fields_get(cr, uid, ['analytic_distribution_state'], context=context).get('analytic_distribution_state', {}).get('selection', []))
        for line in self.browse(cr, uid, ids, fields_to_fetch=['is_allocatable', 'have_analytic_distribution_from_header', 'analytic_distribution_state']):
            res[line.id] = ''
            if not line.is_allocatable:
                continue
            from_header = ''
            if line.have_analytic_distribution_from_header:
                from_header = _(' (from header)')

            res[line.id] = "%s%s" % (state_dict.get(line.analytic_distribution_state, ''), from_header)

        return res

    def _get_dep(self, cr, uid, ids, name, arg, context=None):
        res = {}

        if ids:
            for _id in ids:
                res[_id] = {'depreciation_amount': False, 'remaining_amount': False}
            cr.execute("""
                select
                    l1.id,  sum(l2.amount), a.invo_value - sum(l2.amount)
                from
                    product_asset_line l1, product_asset a, product_asset_line l2
                where
                    l1.asset_id = a.id
                    and l2.asset_id = l1.asset_id
                    and (l2.date < l1.date or l2.date = l1.date and l2.id <= l1.id)
                    and l1.id in %s
                    and coalesce(l1.is_initial_line, 'f') = 'f'
                    and coalesce(l2.is_initial_line, 'f') = 'f'
                group by l1.id, a.invo_value
            """, (tuple(ids), ))
            for x in cr.fetchall():
                res[x[0]] = {'depreciation_amount': round(x[1], 2) , 'remaining_amount': max(round(x[2], 2), 0)}
        return res


    _columns = {
        'date': fields.date('Date', readonly=1, select=1),
        'amount': fields.float('Depreciation', readonly=1),
        'move_id': fields.many2one('account.move', 'Entry', readonly=1, join='LEFT', select=1),
        'move_state': fields.related('move_id', 'state', type='selection', selection=[('posted', 'Posted'), ('draft', 'Unposted')], string="Entry State", readonly=1),
        'asset_bs_depreciation_account_id': fields.many2one('account.account', 'Asset B/S Depreciation Account', domain=[('type', '=', 'other'), ('user_type_code', '=', 'asset')]),
        'asset_pl_account_id': fields.many2one('account.account', 'Asset P&L Depreciation Account', domain=[('user_type_code', 'in', ['expense', 'income'])]),
        'asset_id': fields.many2one('product.asset', 'Asset', required=1, select=1, join=True, ondelete='cascade'),
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'analytic_distribution_state': fields.function(_get_distribution_state, method=True, type='selection',
                                                       selection=[('none', 'None'), ('valid', 'Valid'),
                                                                  ('invalid', 'Invalid'), ('invalid_small_amount', 'Invalid')],
                                                       string="Distribution state", help="Informs from distribution state among 'none', 'valid', 'invalid."),
        'have_analytic_distribution_from_header': fields.function(_have_analytic_distribution_from_header, method=True, type='boolean',
                                                                  string='Header Distrib.?'),
        'is_allocatable': fields.function(_get_is_allocatable, method=True, type='boolean', string="Is allocatable?", readonly=True, store=False),
        'analytic_distribution_state_recap': fields.function(_get_distribution_state_recap, method=True, type='char', size=30,
                                                             string="Distribution",
                                                             help="Informs you about analaytic distribution state among 'none', 'valid', 'invalid', from header or not, or no analytic distribution"),
        'first_dep_day': fields.date('1st depreciation day', readonly=1),
        'last_dep_day': fields.date('Last depreciation day', readonly=1),
        'is_disposal': fields.boolean('Disposal'),
        'is_initial_line': fields.boolean('Initial Line'),
        'depreciation_amount': fields.function(_get_dep, type='float', with_null=True, method=1, string="Cumulative Amount", multi='get_dep'),
        'remaining_amount': fields.function(_get_dep, type='float', with_null=True, method=1, string="Remaining Amount", multi='get_dep'),
    }

    _defaults = {
        'is_disposal': False,
        'is_initial_line': False,
    }


    def button_generate_unposted_entries(self, cr, uid, ids, context=None):
        account_move_obj = self.pool.get('account.move')
        period_obj = self.pool.get('account.period')

        if context is None:
            context = {}

        period_cache = {}

        if ids:
            cr.execute('''
                select
                    asset.name, min(l1.date)
                from
                    product_asset_line l1, product_asset_line l2, product_asset asset
                where
                    l2.id in %s
                    and l1.id not in %s
                    and l1.asset_id = l2.asset_id
                    and ( l1.date < l2.date or l1.date = l2.date and l1.id < l2.id)
                    and l1.move_id is null
                    and asset.id = l2.asset_id
                    and asset.state = 'running'
                group by
                    asset.name
            ''', (tuple(ids), tuple(ids)))
            error = []
            for x in cr.fetchall():
                error.append('%s: %s' % (x[0], x[1]))
            if error:
                raise osv.except_osv(_('Error'), _('Please post entries in chronological order, following entries are draft:\n%s') % '\n'.join(error))

        for line in self.browse(cr, uid, ids, context=context):
            if line.asset_id.state != 'running':
                continue
            update_data = {}
            context.update({'date': line.date})

            if line.date not in period_cache:
                period_domain = [('date_start', '<=', line.date), ('date_stop', '>=', line.date), ('special', '=', False), ('state', 'in', ['draft', 'field-closed'])]
                period_ids = period_obj.search(cr, uid, period_domain, context=context)

                if not period_ids:
                    raise osv.except_osv(_('No period found !'), _('%s: unable to find a valid period for %s!') % (line.asset_id.name, line.date))
                period_cache[line.date] = period_ids[0]

            period_id = period_cache[line.date]

            #if not line.analytic_distribution_id and line.asset_id.analytic_distribution_id:
            #    analytic_line_id = self.pool.get('analytic.distribution').copy(cr, uid, line.asset_id.analytic_distribution_id.id, {}, context=context)
            #    update_data['analytic_distribution_id'] = analytic_line_id
            #else:
            #    analytic_line_id = line.analytic_distribution_id.id

            if line.is_disposal:
                entry_name = _('Disposal Asset %s') % line.asset_id.name
            elif line.is_initial_line:
                entry_name = _('Initial Asset %s') % line.asset_id.name
            else:
                entry_name =  _('Depreciation Asset %s') % line.asset_id.name

            entries = [
                {
                    #'debit_currency': line.amount,
                    #'credit_currency': 0,
                    'amount_currency': line.amount,
                    'account_id': line.asset_pl_account_id.id,
                    'analytic_distribution_id': line.analytic_distribution_id.id or False,
                    'asset_line_id': line.id,
                }, {
                    #'debit_currency': 0,
                    #'credit_currency': line.amount,
                    'amount_currency': -1*line.amount,
                    'account_id': line.asset_bs_depreciation_account_id.id,
                    'analytic_distribution_id': False,
                }
            ]

            update_data['move_id'] = account_move_obj.create(cr, uid, {
                'document_date': line.date,
                'date': line.date,
                'period_id': period_id,
                'journal_id': line.asset_id.journal_id.id,
                'currency_id': line.asset_id.invo_currency.id,
                'ref': line.asset_id.move_line_id.move_id.name,
                'analytic_distribution_id': line.asset_id.analytic_distribution_id.id or False,
                'asset_id': line.asset_id.id,
                'line_id':[
                    (0, 0, {
                        'name': entry_name,
                        'quantiy': 1,
                        'product_id': line.asset_id.product_id.id,
                        'reference': line.asset_id.move_line_id.move_id.name,
                        'amount_currency': x['amount_currency'],
                        #'credit_currency': x['credit_currency'],
                        'account_id': x['account_id'],
                        'analytic_distribution_id': x['analytic_distribution_id'],
                        'document_date': line.date,
                        'date': line.date,
                        'asset_line_id': x.get('asset_line_id', False),
                        'currency_id': line.asset_id.invo_currency.id,
                    }) for x in entries]
            }, context=context)

            self.write(cr, uid, line.id, update_data, context=context)
        return True
product_asset_line()

class product_asset_disposal(osv.osv_memory):
    _name = 'product.asset.disposal'
    _description = 'Asset Dispose'
    _rec_name = 'asset_id'
    _trace = True
    _columns = {
        'asset_id': fields.many2one('product.asset', 'Asset', required=1),
        'event_type_id': fields.many2one('product.asset.event.type', 'Event Type', required=1, domain=[('is_disposal', '=', True)], add_empty=True),
        'disposal_expense_account': fields.many2one('account.account', 'Disposal P&L account', required=1, domain=[('user_type_code', 'in', ['expense', 'income'])]),
        'disposal_bs_account': fields.many2one('account.account', 'Disposal B/S account', required=1, domain=[('user_type_code', '=', 'asset'), ('type', '=', 'other')]),
        'disposal_date': fields.date('Date', required=1),
        'register_event': fields.boolean('Register an Event'),
        'location': fields.char('Location', size=128),
        'proj_code': fields.char('Project Code', size=128),
        'comment': fields.text('Comment'),
    }

    def change_event_type_id(self, cr, uid, ids, event_type_id, context=None):
        if event_type_id:
            ev = self.pool.get('product.asset.event.type').browse(cr, uid, event_type_id, context=context)
            return {'value': {'disposal_expense_account': ev.expense_account_id and ev.expense_account_id.id or False}}
        return {}

    def button_generate_disposal_entry(self, cr, uid, ids, context=None):
        asset_line_obj = self.pool.get('product.asset.line')
        wiz = self.browse(cr, uid, ids[0], context=context)

        if self.pool.get('product.asset').search_exists(cr, uid, [('id', '=', wiz.asset_id.id), ('start_date', '>=', wiz.disposal_date)], context=context):
            raise osv.except_osv(_('Error !'), _('Date of disposal %s is before the depreciation date %s!') % (wiz.disposal_date, wiz.asset_id.start_date))

        disposale_dt = datetime.strptime(wiz.disposal_date, '%Y-%m-%d')
        last_disposal_entry =( disposale_dt + relativedelta(day=1, days=-1)).strftime('%Y-%m-%d')

        nb_posted = asset_line_obj.search(cr, uid, [('asset_id', '=', wiz.asset_id.id), ('date', '>', last_disposal_entry), ('move_id.state', '=', 'posted')], count=True, context=context)
        if nb_posted:
            raise osv.except_osv(_('Error !'), _('Date of disposal %s does not match: there are %d posted entries') % (wiz.disposal_date, nb_posted))

        nb_draft = asset_line_obj.search(cr, uid, [('asset_id', '=', wiz.asset_id.id), ('date', '>', last_disposal_entry), ('move_id.state', '=', 'draft')], count=True, context=context)
        if nb_draft:
            raise osv.except_osv(_('Error !'), _('Date of disposal %s does not match: there are %d unposted entries') % (wiz.disposal_date, nb_draft))

        if not asset_line_obj.search_exists(cr, uid, [('asset_id', '=', wiz.asset_id.id), ('last_dep_day', '>', wiz.disposal_date)], context=context):
            raise osv.except_osv(_('Error !'), _('Asset already fully deprecated at %s') % wiz.disposal_date)

        draft_lines = asset_line_obj.search(cr, uid, [('asset_id', '=', wiz.asset_id.id), ('date', '>', last_disposal_entry)], context=context)
        if draft_lines:
            asset_line_obj.unlink(cr, uid, draft_lines, context=context)


        if wiz.register_event:
            self.pool.get('product.asset.event').create(cr, uid, {
                'date': wiz.disposal_date,
                'asset_id': wiz.asset_id.id,
                'event_type_id': wiz.event_type_id.id,
                'location': wiz.location,
                'proj_code': wiz.proj_code,
                'comment': wiz.comment,
            }, context=context)

        to_draft_post = asset_line_obj.search(cr, uid, [('asset_id', '=', wiz.asset_id.id), ('move_id', '=', False)], context=context)
        if to_draft_post:
            asset_line_obj.button_generate_unposted_entries(cr, uid, to_draft_post, context=context)

        new_line_id = asset_line_obj.create(cr, uid, {
            'is_disposal': True,
            'date': wiz.disposal_date,
            'asset_pl_account_id': wiz.disposal_expense_account.id,
            'asset_bs_depreciation_account_id': wiz.disposal_bs_account.id,
            'amount': wiz.asset_id.disposal_amount,
            'asset_id': wiz.asset_id.id

        })
        asset_line_obj.button_generate_unposted_entries(cr, uid, [new_line_id], context=context)

        return {'type': 'ir.actions.act_window_close'}

product_asset_disposal()


class product_asset_generate_entries(osv.osv_memory):
    _name = 'product.asset.generate.entries'
    _description = 'Asset Generate Entries'
    _rec_name = 'date'
    _columns = {
        'period_id': fields.many2one('account.period', 'Period', required=1, domain=[('special', '=', False), ('state', 'in', ['field-closed', 'draft'])]),
    }

    def button_generate_all(self, cr, uid, ids, context=None):
        asset_line_obj = self.pool.get('product.asset.line')
        asset_obj = self.pool.get('product.asset')
        wiz = self.browse(cr, uid, ids[0], context=context)
        end_date = wiz.period_id.date_stop


        if self.pool.get('res.company')._get_instance_level(cr, uid) == 'project':
            asset_line_ids = []
        else:
            # at coo lock_open means Compute lines has been ran
            asset_ids = asset_obj.search(cr, uid, [('state', '=', 'open'), ('lock_open', '=', True), ('start_date', '<=', end_date)], context=context)
            if asset_ids:
                asset_obj.write(cr, uid, asset_ids, {'state': 'running'}, context=context)

            asset_line_ids = asset_line_obj.search(cr, uid, [('asset_id.state', 'in', ['open', 'running']), ('asset_id.lock_open', '=', True), ('move_id', '=', False), ('date', '<=', end_date)], context=context)
            if asset_line_ids:
                asset_line_obj.button_generate_unposted_entries(cr, uid, asset_line_ids, context=context)


        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'account.action_account_moves_all_a', ['tree', 'form'],context=context)
        ji_with_ad_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_asset', 'view_account_move_line_asset_tree')
        views = []
        for x in res['views']:
            if x[1] == 'tree':
                views.append((ji_with_ad_view_id[1], 'tree'))
            else:
                views.append(x)
        res['name'] = _('Asset lines')
        res['views'] = views
        res['domain'] = ['&', ('move_id.asset_id', '!=', False), ('date', '<=', end_date)]
        res['popup_message'] = _('%d asset journal entries created') % (len(asset_line_ids),)
        return res


        return




product_asset_generate_entries()


class product_asset_import_entries(osv.osv_memory):
    _name = 'product.asset.import.entries'
    _description = 'Import Asset Entries'
    _columns = {
        'file': fields.binary(string="File", filters='*.xml, *.xls', required=True),
        'filename': fields.char(string="Imported filename", size=256),
        'progression': fields.float(string="Progression", readonly=True),
        'message': fields.char(string="Message", size=256, readonly=True),
        'state': fields.selection(
            [('draft', 'Created'), ('inprogress', 'In Progress'), ('error', 'Error'), ('done', 'Done')], string="State",
            readonly=True, required=True),
        'error_ids': fields.one2many('product.asset.import.entries.errors', 'wizard_id', "Errors", readonly=True),
    }
    _defaults = {
        'progression': lambda *a: 0.0,
        'state': lambda *a: 'draft',
        'message': lambda *a: _('Initialization...'),
    }

    def _import(self, dbname, uid, ids, context=None):
        if context is None:
            context = {}
        cr = pooler.get_db(dbname).cursor()
        created = 0
        errors = []
        current_line_num = None
        acc_cache = {}
        prod_cache = {}
        asset_type_cache = {}
        use_life_cache = {}
        try:
            # Update wizard
            self.write(cr, uid, ids, {'message': _('Cleaning up old imports...'), 'progression': 1.00})
            # Clean up old temporary imported lines
            old_lines_ids = self.pool.get('product.asset.import.entries.lines').search(cr, uid, [])
            self.pool.get('product.asset.import.entries.lines').unlink(cr, uid, old_lines_ids)

            for wiz in self.browse(cr, uid, ids):
                # Check that a file was given
                if not wiz.file:
                    raise osv.except_osv(_('Error'), _('Nothing to import.'))
                # Update wizard
                self.write(cr, uid, [wiz.id], {'message': _('Copying file...'), 'progression': 2.00})
                fileobj = NamedTemporaryFile('w+b', delete=False)
                fileobj.write(b64decode(wiz.file))
                fileobj.close()
                content = SpreadsheetXML(xmlfile=fileobj.name, context=context)
                if not content:
                    raise osv.except_osv(_('Warning'), _('No content'))
                # Update wizard
                self.write(cr, uid, [wiz.id], {'message': _('Processing line...'), 'progression': 4.00})
                rows = content.getRows()
                nb_rows = len([x for x in content.getRows()])
                # Update wizard
                self.write(cr, uid, [wiz.id], {'message': _('Reading headers...'), 'progression': 5.00})
                # Use the first row to find which column to use
                cols = {}
                col_names = ['External Asset ID', 'Product Code', 'Asset Type', 'Useful Life', 'Serial Number', 'Brand',
                             'Type', 'Model', 'Year', 'Journal Item', 'Asset B/S Depreciation Account',
                             'Asset P&L Depreciation Account']
                for num, r in enumerate(rows):
                    header = [x and x.data for x in r.iter_cells()]
                    for el in col_names:
                        if el in header:
                            cols[el] = header.index(el)
                    break
                # Number of line to bypass in line's count
                base_num = 2
                for el in col_names:
                    if el not in cols:
                        raise osv.except_osv(_('Error'), _("'%s' column not found in file.") % (el or '',))
                # Update wizard
                self.write(cr, uid, [wiz.id], {'message': _('Reading lines...'), 'progression': 6.00})
                # Check file's content
                for num, r in enumerate(rows):
                    # Update wizard
                    progression = ((float(num + 1) * 94) / float(nb_rows)) + 6
                    self.write(cr, uid, [wiz.id], {'message': _('Checking file...'), 'progression': progression})
                    # Prepare some values
                    r_prod = False
                    r_asset_type = False
                    r_use_life = False
                    r_ji = False
                    r_bs_acc = False
                    r_pl_acc = False

                    current_line_num = num + base_num
                    # Fetch all XML row values
                    line = self.pool.get('import.cell.data').get_line_values(cr, uid, ids, r, context=context)

                    # ignore empty lines
                    if not self.pool.get('msf.doc.import.accounting')._check_has_data(line):
                        continue

                    # Check line length and fill the cropped empty/missing cells at end of line with False
                    if len(line) < len(col_names):
                        line.extend([False] * (len(col_names) - len(line)))

                    line = self.pool.get('msf.doc.import.accounting')._format_special_char(line)

                    # Check Product Code
                    if not line[cols['Product Code']]:
                        errors.append(
                            _('Line %s: No Product Code specified! (External Asset ID: %s, Serial Number: %s)') %
                             (current_line_num, line[cols['External Asset ID']] or '_', line[cols['Serial Number']] or '_'))
                    else:
                        if not prod_cache.get(line[cols['Product Code']], False):
                            product_ids = self.pool.get('product.product').search(cr, uid, [('default_code', '=', line[cols['Product Code']])])
                            if product_ids:
                                prod_cache[line[cols['Product Code']]] = product_ids[0]
                            else:
                                errors.append(_('Line %s: Product Code "%s" not found!') % (current_line_num, line[cols['Product Code']],))
                        r_prod = prod_cache.get(line[cols['Product Code']], False)

                    # Check Asset Type
                    if not line[cols['Asset Type']]:
                        errors.append(
                            _('Line %s: No Asset Type specified! (External Asset ID: %s, Serial Number: %s)') %
                            (current_line_num, line[cols['External Asset ID']] or '_', line[cols['Serial Number']] or '_'))
                    else:
                        if not asset_type_cache.get(line[cols['Asset Type']], False):
                            cr.execute("SELECT src FROM ir_translation WHERE value = '%s' AND name = 'product.asset.type,name'" % line[cols['Asset Type']])
                            query_res = cr.dictfetchone()
                            asset_type_name = query_res and query_res['src'] or False
                            asset_type_ids = self.pool.get('product.asset.type').search(cr, uid, [('name', '=', asset_type_name or line[cols['Asset Type']])], context=context)
                            if asset_type_ids:
                                asset_type_cache[line[cols['Asset Type']]] = asset_type_ids[0]
                            else:
                                errors.append(_('Line %s: Asset Type "%s" not found!') % (current_line_num, line[cols['Asset Type']],))
                        r_asset_type = asset_type_cache.get(line[cols['Asset Type']], False)

                    # Check Useful Life
                    if not line[cols['Useful Life']]:
                        errors.append(
                            _('Line %s: No Useful Life specified! (External Asset ID: %s, Serial Number: %s)') %
                            (current_line_num, line[cols['External Asset ID']] or '_', line[cols['Serial Number']] or '_'))
                    elif line[cols['Useful Life']] and r_asset_type:
                        if not use_life_cache.get((line[cols['Useful Life']], r_asset_type), False):
                            use_life_ids = self.pool.get('product.asset.useful.life').search(cr, uid, [('asset_type_id', '=', r_asset_type), ('year', '=', line[cols['Useful Life']])])
                            if use_life_ids:
                                use_life_cache[(line[cols['Useful Life']], r_asset_type)] = use_life_ids[0]
                            else:
                                errors.append(
                                    _('Line %s: The "%s" year(s) Useful Life of Asset Type "%s" not found!') %
                                    (current_line_num, line[cols['Useful Life']], line[cols['Asset Type']],))
                        r_use_life = use_life_cache.get((line[cols['Useful Life']], r_asset_type), False)

                    # Check Journal Item
                    move_ids = False
                    aml_ids = False
                    if line[cols['Journal Item']]:
                        move_ids = self.pool.get('account.move').search(cr, uid, [('name', '=', line[cols['Journal Item']])])
                        if move_ids and move_ids[0]:
                            if r_prod:
                                product = self.pool.get('product.product').browse(cr, uid, r_prod, context=context)
                                aml_ids = self.pool.get('account.move.line').search(cr, uid, [('move_id', '=', move_ids[0]), ('product_id', '=', product.id)])
                        if not move_ids or not aml_ids:
                            errors.append(_('Line %s: Journal Item "%s" not found!\nPlease check if that JI exists or has the product specified') % (current_line_num, line[cols['Journal Item']],))
                        elif aml_ids:
                            ji_error = False
                            # Apply the same restrictions as in the asset form view
                            aml = self.pool.get('account.move.line').browse(cr, uid, aml_ids[0], context=context)
                            if aml.journal_id.type not in ['purchase', 'correction_hq', 'hq', 'intermission']:
                                errors.append(_('Line %s: The journal of Journal Item "%s" has to be of type Purchase, Correction HQ, HQ or Intermission!') % (current_line_num, line[cols['Journal Item']],))
                                ji_error = True
                            if not (aml.debit > 0):
                                errors.append(_('Line %s: The debit of Journal Item "%s" has to be greater than 0.') % (current_line_num, line[cols['Journal Item']],))
                                ji_error = True
                            if aml.move_id.state != 'posted':
                                errors.append(_('Line %s: The Journal Entry "%s" has to be in "posted" state.') % (current_line_num, line[cols['Journal Item']],))
                                ji_error = True
                            if aml.account_id.user_type_code not in ['asset', 'expense']:
                                errors.append(_('Line %s: The account type of Journal Item "%s" has to be either Asset or Expense.') % (current_line_num, line[cols['Journal Item']],))
                                ji_error = True
                            if not ji_error:
                                r_ji = aml_ids[0]

                    # Check Asset B/S Depreciation Account
                    bs_ids = False
                    if line[cols['Asset B/S Depreciation Account']]:
                        if not acc_cache.get((line[cols['Asset B/S Depreciation Account']], 'bs'), False):
                            bs_ids = self.pool.get('account.account').search(cr, uid, [('code', '=', line[cols['Asset B/S Depreciation Account']])])
                            if not bs_ids:
                                errors.append(_('Line %s: Asset B/S Depreciation Account "%s" not found!') % (current_line_num, line[cols['Asset B/S Depreciation Account']],))
                            else:
                                bs_account = self.pool.get('account.account').browse(cr, uid, bs_ids[0], context=context)
                                if bs_account.type != 'other' or bs_account.user_type_code != 'asset':
                                    errors.append(_('Line %s: Asset B/S Depreciation Account "%s" must have "Regular" as Internal Type and "Asset" as Account Type') %
                                                  (current_line_num, line[cols['Asset B/S Depreciation Account']],))
                                else:
                                    acc_cache[(line[cols['Asset B/S Depreciation Account']], 'bs')] = bs_ids[0]
                        else:
                            r_bs_acc = acc_cache.get((line[cols['Asset B/S Depreciation Account']], 'bs'), False)

                    # Check Asset P&L Depreciation Account
                    pl_ids = False
                    if line[cols['Asset P&L Depreciation Account']]:
                        if not acc_cache.get((line[cols['Asset P&L Depreciation Account']], 'pl'), False):
                            pl_ids = self.pool.get('account.account').search(cr, uid, [('code', '=', line[cols['Asset P&L Depreciation Account']])])
                            if not pl_ids:
                                errors.append(_('Line %s: Asset P&L Depreciation Account "%s" not found!') %
                                              (current_line_num, line[cols['Asset P&L Depreciation Account']],))
                            else:
                                pl_account = self.pool.get('account.account').browse(cr, uid, pl_ids[0], context=context)
                                if pl_account.user_type_code not in ['expense', 'income']:
                                    errors.append(
                                        _('Line %s: Asset P&L Depreciation Account "%s" must have "Expense" or "Income" as Account Type') %
                                        (current_line_num, line[cols['Asset P&L Depreciation Account']],))
                                else:
                                    acc_cache[(line[cols['Asset P&L Depreciation Account']], 'pl')] = pl_ids[0]
                        else:
                            r_pl_acc = acc_cache.get((line[cols['Asset P&L Depreciation Account']], 'pl'), False)

                    vals = {
                        'external_asset_id': line[cols['External Asset ID']] or '',
                        'prod_int_code': line[cols['Product Code']],
                        'product_id': r_prod,
                        'asset_type_id': r_asset_type,
                        'useful_life_id': r_use_life,
                        'serial_nb': line[cols['Serial Number']] or '',
                        'brand': line[cols['Brand']],
                        'type': line[cols['Type']] or '',
                        'model': line[cols['Model']] or '',
                        'year': line[cols['Year']] or '',
                        'move_line_id': r_ji,
                        'asset_bs_depreciation_account_id': r_bs_acc,
                        'asset_pl_account_id': r_pl_acc,
                        'wizard_id': wiz.id,
                    }

                    if not errors:
                        line_res = self.pool.get('product.asset.import.entries.lines').create(cr, uid, vals, context=context)
                        if not line_res:
                            errors.append(_('Line %s: A problem occurred for line registration. Please contact an Administrator.') % (current_line_num,))
                            continue
                        created += 1

            # Update wizard
            self.write(cr, uid, ids,
                       {'message': _('Check complete. Reading potential errors or write needed changes.'),
                        'progression': 100.0})

            wiz_state = 'done'
            # If errors, cancel probable modifications
            if errors:
                cr.rollback()
                created = 0
                message = _('Import FAILED.')
                # Delete old errors
                error_ids = self.pool.get('product.asset.import.entries.errors').search(cr, uid, [], context)
                if error_ids:
                    self.pool.get('product.asset.import.entries.errors').unlink(cr, uid, error_ids, context)
                # create errors lines
                for e in errors:
                    self.pool.get('product.asset.import.entries.errors').create(cr, uid,
                                                                                {'wizard_id': wiz.id, 'name': e},
                                                                                context)
                wiz_state = 'error'
            else:
                # Update wizard
                self.write(cr, uid, ids, {'message': _('Writing changes...'), 'progression': 0.0})
                # Create all asset entries
                import_lines_ids = self.pool.get('product.asset.import.entries.lines').search(cr, uid, [('wizard_id', '=', wiz.id)], context=context)
                import_lines = self.pool.get('product.asset.import.entries.lines').browse(cr, uid, import_lines_ids, context=context)
                context.update({'from_import': True})
                try:
                    for asset in import_lines:
                        asset_vals = {
                            'external_asset_id': asset.external_asset_id,
                            'prod_int_code': asset.prod_int_code,
                            'product_id': asset.product_id.id,
                            'asset_type_id': asset.asset_type_id.id,
                            'useful_life_id': asset.useful_life_id.id,
                            'serial_nb': asset.serial_nb,
                            'brand': asset.brand,
                            'type': asset.type,
                            'model': asset.model,
                            'year': asset.year,
                            'move_line_id': asset.move_line_id.id,
                            'asset_bs_depreciation_account_id': asset.asset_bs_depreciation_account_id.id,
                            'asset_pl_account_id': asset.asset_pl_account_id.id,
                        }
                        self.pool.get('product.asset').create(cr, uid, asset_vals, context=context)
                    message = _('Import successful.')
                except osv.except_osv as osv_error:
                    cr.rollback()
                    self.write(cr, uid, ids,
                               {'message': _("An error occurred. %s: %s") % (osv_error.name, osv_error.value,),
                                'state': 'done', 'progression': 100.0})
                    cr.close(True)

            # Update wizard
            self.write(cr, uid, ids, {'message': message, 'state': wiz_state, 'progression': 100.0})

            # Close cursor
            cr.commit()
            cr.close(True)

        except osv.except_osv as osv_error:
            cr.rollback()
            self.write(cr, uid, ids, {'message': _("An error occurred. %s: %s") % (osv_error.name, osv_error.value,), 'state': 'done', 'progression': 100.0})
            cr.close(True)
        except Exception as e:
            cr.rollback()
            if current_line_num is not None:
                message = _("An error occurred on line %s: %s") % (current_line_num, e.args and e.args[0] or '')
            else:
                message = _("An error occurred: %s") % (e.args and e.args[0] or '',)
            self.write(cr, uid, ids, {'message': message, 'state': 'done', 'progression': 100.0})
            cr.close(True)
        return True

    def button_validate(self, cr, uid, ids, context=None):
        """
        Launch process in a thread and return a wizard
        """
        if not context:
            context = {}
        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
        thread.start()
        return self.write(cr, uid, ids, {'state': 'inprogress'}, context=context)

    def button_update(self, cr, uid, ids, context=None):
        """
        Update view
        """
        return False


product_asset_import_entries()


class product_asset_import_entries_lines(osv.osv):
    _name = 'product.asset.import.entries.lines'

    _columns = {
        'external_asset_id': fields.char('External Asset ID', size=32, readonly=True),
        'prod_int_code': fields.char('Product Code', size=128, readonly=True, required=True),
        'product_id': fields.many2one('product.product', 'Product', required=True),
        'asset_type_id': fields.many2one('product.asset.type', 'Asset Type', readonly=True, required=True),
        'useful_life_id': fields.many2one('product.asset.useful.life', 'Useful Life', ondelete='restrict', readonly=True, required=True),
        'serial_nb': fields.char('Serial Number', size=128, readonly=True),
        'brand': fields.char('Brand', size=128, readonly=True),
        'type': fields.char('Type', size=128, readonly=True),
        'model': fields.char('Model', size=128, readonly=True),
        'year': fields.char('Year', size=4, readonly=True),
        'move_line_id': fields.many2one('account.move.line', 'Journal Item', readonly=True),
        'asset_bs_depreciation_account_id': fields.many2one('account.account', 'Asset B/S Depreciation Account', readonly=True),
        'asset_pl_account_id': fields.many2one('account.account', 'Asset P&L Depreciation Account', readonly=True),
        'wizard_id': fields.integer("Wizard", required=True, readonly=True),
    }


product_asset_import_entries_lines()


class product_asset_import_entries_errors(osv.osv_memory):
    _name = 'product.asset.import.entries.errors'
    _description = 'Asset Entries Import - Error List'

    _columns = {
        'name': fields.text("Description", readonly=True, required=True),
        'wizard_id': fields.many2one('product.asset.import.entries', "Wizard", required=True, readonly=True),
    }


product_asset_import_entries_errors()


#----------------------------------------------------------
# Products
#----------------------------------------------------------
class product_template(osv.osv):

    _inherit = "product.template"
    _description = "Product Template"

    PRODUCT_SUBTYPE = [('single','Single Item'),('kit', 'Kit/Module'),('asset','Asset')]

    _columns = {
        'subtype': fields.selection(PRODUCT_SUBTYPE, 'Product SubType', required=True, help="Will change the way procurements are processed."),
        'asset_type_id': fields.many2one('product.asset.type', 'Asset Type'),
    }

    _defaults = {
        'subtype': lambda *a: 'single',
    }

product_template()

class product_product(osv.osv):

    _inherit = "product.product"
    _description = "Product"

    def write(self, cr, uid, ids, vals, context=None):
        '''
        if a product is not of type product, it is set to single subtype
        '''
        if not ids:
            return True
        if context is None:
            context={}
        # fetch the product
        if 'type' in vals and vals['type'] != 'product':
            vals.update(subtype='single')

        #UF-2170: remove the standard price value from the list if the value comes from the sync
        #US-803: If the price comes from rw_sync, then take it
        # US-3254: update standard_pricde during initial sync (i.e if msf.instance is not set)
        if 'standard_price' in vals and context.get('sync_update_execution', False) and not context.get('rw_sync', False) and not context.get('keep_standard_price'):
            msf_instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
            if msf_instance:
                del vals['standard_price']
            elif not vals['standard_price']:
                vals['standard_price'] = 1

        return super(product_product, self).write(cr, uid, ids, vals, context=context)

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}

        if context.get('sync_update_execution', False) and 'standard_price' in vals and not vals['standard_price']:
            vals['standard_price'] = 1

        return super(product_product, self).create(cr, uid, vals, context)


    def _constaints_product_consu(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        for obj in self.read(cr, uid, ids, ['type', 'procure_method'], context=context):
            if obj['type'] == 'consu' and obj['procure_method'] != 'make_to_order':
                return False
        return True


    _columns = {
        'asset_ids': fields.one2many('product.asset', 'product_id', 'Assets')
    }

    _constraints = [
        (_constaints_product_consu, 'If you select "Non-stockable" as product type then you have to select "Make to order" as procurement method', []),
    ]

product_product()

#----------------------------------------------------------
# Stock moves
#----------------------------------------------------------
class stock_move(osv.osv):

    _inherit = "stock.move"
    _description = "Stock Move"

    def _do_partial_hook(self, cr, uid, ids, context, *args, **kwargs):
        '''
        hook to update defaults data
        '''
        # variable parameters
        move = kwargs.get('move')
        assert move, 'missing move'
        partial_datas = kwargs.get('partial_datas')
        assert partial_datas, 'missing partial_datas'

        # calling super method
        defaults = super(stock_move, self)._do_partial_hook(cr, uid, ids, context, *args, **kwargs)
        assert defaults is not None

        assetId = partial_datas.get('move%s'%(move.id), False).get('asset_id')
        if assetId:
            defaults.update({'asset_id': assetId})

        return defaults

stock_move()


class stock_picking(osv.osv):
    '''

    '''
    _inherit = 'stock.picking'
    _description = 'Stock Picking with hook'

    def _do_partial_hook(self, cr, uid, ids, context, *args, **kwargs):
        '''
        hook to update defaults data
        '''
        # variable parameters
        move = kwargs.get('move')
        assert move, 'missing move'
        partial_datas = kwargs.get('partial_datas')
        assert partial_datas, 'missing partial_datas'

        # calling super method
        defaults = super(stock_picking, self)._do_partial_hook(cr, uid, ids, context, *args, **kwargs)
        assetId = partial_datas.get('move%s'%(move.id), {}).get('asset_id')
        if assetId:
            defaults.update({'asset_id': assetId})

        return defaults

stock_picking()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
