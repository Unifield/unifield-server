# -*- coding: utf-8 -*-

from osv import fields, osv
import time
from tools.translate import _
from datetime import datetime
from dateutil.relativedelta import relativedelta


#----------------------------------------------------------
# Assets
#----------------------------------------------------------
class product_asset_type(osv.osv):
    _name = "product.asset.type"
    _description = "Specify the type of asset at product level"
    _order = 'name, id'

    _columns = {
        'name': fields.char('Name', size=64, required=True),
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

    _columns = {
        'name': fields.char('Name', size=512, required=True),
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
            'has_lines': False,
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
        })
        return super(product_asset, self).copy_data(cr, uid, id, default, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        override write method to force readonly fields to be saved to db
        on data update
        '''
        if not ids:
            return True

        if context is None:
            context = {}

        if context.get('sync_update_execution'):
            for f in  ['asset_type_id', 'useful_life_id', 'asset_bs_depreciation_account_id', 'asset_pl_account_id', 'start_date', 'move_line_id']:
                if f in vals:
                    del(vals[f])

        # fetch the product
        if 'product_id' in vals:
            productId = vals['product_id']
            # add readonly fields to vals
            vals.update(self._getRelatedProductFields(cr, uid, productId, update_account=False))

        if 'move_line_id' in vals:
            vals.update(self._getRelatedMoveLineFields(cr, uid, vals['move_line_id'], context=context))

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

        # fetch the product
        if 'product_id' in vals:
            productId = vals['product_id']
            # add readonly fields to vals
            vals.update(self._getRelatedProductFields(cr, uid, productId, update_account=not from_sync))

        if not from_sync and 'move_line_id' in vals:
            vals.update(self._getRelatedMoveLineFields(cr, uid, vals['move_line_id'], context=context))

        # UF-1617: set the current instance into the new object if it has not been sent from the sync
        if 'instance_id' not in vals or not vals['instance_id']:
            vals['instance_id'] = self.pool.get('res.company')._get_instance_id(cr, uid)

        if not vals.get('name'):
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'product.asset')

        return super(product_asset, self).create(cr, uid, vals, context)

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

    def _getRelatedMoveLineFields(self, cr, uid, move_line_id, on_change=False, context=None):
        if not move_line_id:
            return {}
        ml = self.pool.get('account.move.line').browse(cr, uid, move_line_id, fields_to_fetch=['date', 'debit_currency', 'currency_id'], context=context)

        data = {
            'invo_date': ml.date,
            'invo_value': ml.debit_currency,
            'invo_currency': ml.currency_id.id
        }
        if on_change:
            data['start_date'] = ml.date
        return data


    def change_invo_date(self, cr, uid, ids, move_line_id, context=None):
        if move_line_id:
            return {'value': self._getRelatedMoveLineFields(cr, uid, move_line_id, on_change=True, context=context)}
        return {'value': {'start_date': False, 'invo_date': False, 'invo_value': False, 'invo_currency': False}}

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

    _columns = {
        # asset
        'name': fields.char('Asset Code', size=128, readonly=True),
        'asset_type_id': fields.many2one('product.asset.type', 'Asset Type'), # from product
        'description': fields.char('Asset Description', size=128),
        'product_id': fields.many2one('product.product', 'Product', required=True, ondelete='cascade'),
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
        'invo_date': fields.date('Invoice Date', required=True, readonly=1),
        'invo_value': fields.float('Value', required=True, readonly=1),
        'invoice_id': fields.many2one('account.invoice', 'Invoice'),
        'move_line_id': fields.many2one('account.move.line', 'Journal Item', domain="[('move_id.state', '=', 'posted'), ('account_id.type', '=', 'other'), ('account_id.user_type_code', '=', 'asset')]", required=1),
        'invoice_line_id': fields.many2one('account.invoice.line', 'Invoice Line'),
        #'invo_currency': fields.char('Currency', size=128, required=True),
        'invo_currency': fields.many2one('res.currency', 'Currency', required=True, readonly=1),
        #'invo_supplier': fields.char('Supplier', size=128),
        'invo_supplier_id': fields.many2one('res.partner', 'Supplier'),
        'invo_donator_code': fields.char('Donator Code', size=128),
        'invo_certif_depreciation': fields.char('Certificate of Depreciation', size=128),
        # event history
        'event_ids': fields.one2many('product.asset.event', 'asset_id', 'Events'),
        # UF-1617: field only used for sync purpose
        'instance_id': fields.many2one('msf.instance', string="Instance", readonly=True, required=False),
        'xmlid_name': fields.char('XML Code, hidden field', size=128),
        'from_invoice': fields.boolean('From Invoice', readonly=1),
        'from_sync': fields.boolean('From Sync', readonly=1),
        'state': fields.selection([('draft', 'Draft'), ('running', 'Running'), ('done', 'Done'), ('cancel', 'Cancel')], 'State', readonly=1),
        'asset_bs_depreciation_account_id': fields.many2one('account.account', 'Asset B/S Depreciation Account', domain=[('type', '=', 'other'), ('user_type_code', '=', 'asset')]),
        'asset_pl_account_id': fields.many2one('account.account', 'Asset P&L Depreciation Account', domain=[('user_type_code', 'in', ['expense', 'income'])]),
        'useful_life_id': fields.many2one('product.asset.useful.life', 'Useful Life', ondelete='restrict'),
        'start_date': fields.date('Start Date', required=1),
        'line_ids': fields.one2many('product.asset.line', 'asset_id', 'Depreciation Lines'),
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'depreciation_amount': fields.function(_get_book_value, string='Depreciation', type='float', method=True, help="Sum of all Asset journal item lines", multi='get_book', with_null=True),
        'disposal_amount': fields.function(_get_book_value, string='Remaining net value', type='float', method=True, multi='get_book', with_null=True),
        'journal_id': fields.many2one('account.journal', 'Journal', readonly=1),
        'has_lines': fields.boolean('Has Line', readonly='1'),
        'has_posted_lines': fields.function(_get_has_posted_lines, string='Has at least one posted line', type='boolean', method=True),
        'can_be_disposed': fields.function(_get_can_be_disposed, string='Can be diposed', type='boolean', method=True),
        'instance_level': fields.function(_get_instance_level, string='Instance Level', type='char', method=True),
        'prorata': fields.boolean('Prorata Temporis'),
        'depreciation_method': fields.selection([('straight', 'Straight Line')], 'Depreciation Method', required=True),
    }

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
        'instance_level': lambda self, cr, uid, context: self.pool.get('res.company')._get_instance_level(cr, uid)
    }
    # UF-2148: use this constraint with 3 attrs: name, prod and instance
    _sql_constraints = [('asset_name_uniq', 'unique(name)', 'Asset Code must be unique.')]
    _order = 'name desc'

    def button_cancel_asset(self, cr, uid, ids, context=None):
        draft_ids = self.search(cr, uid, [('id', 'in', ids), ('state', '=', 'draft')], context=context)
        if draft_ids:
            self.write(cr, uid, draft_ids, {'state': 'cancel'}, context=context)
        return True

    def button_from_cancel_to_draft(self, cr, uid, ids, context=None):
        cancel_ids = self.search(cr, uid, [('id', 'in', ids), ('state', '=', 'cancel')], context=context)
        if cancel_ids:
            self.write(cr, uid, cancel_ids, {'state': 'draft'}, context=context)
        return True

    def button_set_as_draft(self, cr, uid, ids, context=None):
        draft_ids = self.search(cr, uid, [('id', 'in', ids), ('state', '=', 'running')], context=context)
        if draft_ids:
            to_change = []
            for asset in self.browse(cr, uid, draft_ids, fields_to_fetch=['has_posted_lines'], context=context):
                if not asset.has_posted_lines:
                    to_change.append(asset.id)
            if to_change:
                self.write(cr, uid, draft_ids, {'state': 'draft'}, context=context)
        return True

    def button_project_depreciation(self, cr, uid, ids, context=None):
        draft_ids = self.search(cr, uid, [('id', 'in', ids), ('state', '=', 'draft')], context=context)
        if draft_ids:
            self.write(cr, uid, draft_ids, {'state': 'running'}, context=context)
        return True

    def button_start_depreciation(self, cr, uid, ids, context=None):
        draft_ids = self.search(cr, uid, [('id', 'in', ids), ('state', '=', 'draft')], context=context)
        if draft_ids:
            self.write(cr, uid, draft_ids, {'state': 'running'}, context=context)
        return True

    def button_delete_draft_entries(self, cr, uid, ids, context=None):
        draft_ids = self.search(cr, uid, [('id', 'in', ids), ('state', '=', 'draft')], context=context)
        line_ids = self.pool.get('product.asset.line').search(cr, uid, [('asset_id', 'in', draft_ids)], context=context)
        if line_ids:
            self.pool.get('product.asset.line').unlink(cr, uid, line_ids, context=context)
        if draft_ids:
            self.write(cr, uid, draft_ids, {'has_lines': False}, context=context)
        return True

    def button_generate_draft_entries(self, cr, uid, ids, context=None):
        line_obj = self.pool.get('product.asset.line')
        if not ids:
            return False

        default_j = False
        asset = self.browse(cr, uid, ids[0], context=context)
        if not asset.journal_id:
            default_j = self._get_default_journal(cr, uid, context=context)
            if not default_j:
                raise osv.except_osv(_('Error !'), _('Depreciation journal (code: DEP, type: depreciation) does not exist, please create a Depreciation G/L Journal'))

        for field in ['start_date', 'asset_bs_depreciation_account_id', 'asset_pl_account_id', 'useful_life_id']:
            if not asset[field]:
                raise osv.except_osv(_('Error !'), _('Please fill the mandatory field %s') % field) # TODO trans

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

        if asset.prorata:
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
        if asset.prorata and remaining > 1:
            last_entry_date = start_dt + relativedelta(months=nb_month+1, day=1, days=-1)
            to_create.append([last_entry_date, remaining, last_entry_date + relativedelta(day=1), last_entry_date + relativedelta(day=start_dt.day)])
        else:
            to_create[-1][1] = to_create[-1][1] + remaining

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
            to_write = {'has_lines': True}
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
        if isinstance(ids, (int, long)):
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
            # e = dict: {'asset_id': (68, u'AF/00045'), 'date': '2011-05-05', 'id': 75}
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

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'analytic_distribution_id': False,
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
                                                                                          line.asset_pl_account_id.id, amount=line.amount)
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
                    l1.id, sum(l2.amount), a.invo_value - sum(l2.amount)
                from
                    product_asset_line l1, product_asset a, product_asset_line l2
                where
                    l1.asset_id = a.id and
                    l2.asset_id = l1.asset_id and
                    l2.date <= l1.date and
                    l1.id in %s
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
        'move_state_fake': fields.related('move_id', 'state', type='selection', selection=[('posted', 'Posted'), ('draft', 'Unposted')], string="Internal Entry State", readonly=1),
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
        'depreciation_amount': fields.function(_get_dep, type='float', method=1, string="Cumulative Amount", multi='get_dep'),
        'remaining_amount': fields.function(_get_dep, type='float', method=1, string="Remaining Amount", multi='get_dep'),
    }

    _defaults = {
        'is_disposal': False,
    }


    def button_post_entries(self, cr, uid, ids, context=None):
        to_create = self.search(cr, uid, [('id', 'in', ids), ('move_id', '=', False), ('asset_id.state', '=', 'running')], context=context)
        if to_create:
            self.button_generate_unposted_entries(cr, uid, to_create, context=context)

        move_obj = self.pool.get('account.move')
        line_to_post = self.search(cr, uid, [('id', 'in', ids), ('move_id.state', '=', 'draft'), ('asset_id.state', '=', 'running')], context=context)
        to_post = []
        for line in self.browse(cr, uid, line_to_post, fields_to_fetch=['move_id'], context=context):
            to_post.append(line.move_id.id)
        if to_post:
            move_obj.button_validate(cr, uid, to_post, context=context)
        return True

    def button_generate_unposted_entries(self, cr, uid, ids, context=None):
        account_move_obj = self.pool.get('account.move')
        period_obj = self.pool.get('account.period')

        if context is None:
            context = {}

        period_cache = {}
        for line in self.browse(cr, uid, ids, context=context):
            if line.asset_id.state != 'running':
                continue
            update_data = {}
            context.update({'date': line.date})

            if line.date not in period_cache:
                period_domain = [('date_start', '<=', line.date), ('date_stop', '>=', line.date), ('special', '=', False), ('state', 'in', ['draft', 'field-closed'])]
                period_ids = period_obj.search(cr, uid, period_domain, context=context)

                if not period_ids:
                    raise osv.except_osv(_('No period found !'), _('Unable to find a valid period for %s!') % (line.date, ))
                period_cache[line.date] = period_ids[0]

            period_id = period_cache[line.date]

            #if not line.analytic_distribution_id and line.asset_id.analytic_distribution_id:
            #    analytic_line_id = self.pool.get('analytic.distribution').copy(cr, uid, line.asset_id.analytic_distribution_id.id, {}, context=context)
            #    update_data['analytic_distribution_id'] = analytic_line_id
            #else:
            #    analytic_line_id = line.analytic_distribution_id.id

            if line.is_disposal:
                entry_name = _('Disposal Asset %s') % line.asset_id.name
            else:
                entry_name =  _('Depreciation Asset %s') % line.asset_id.name

            entries = [
                {
                    'debit_currency': line.amount,
                    'credit_currency': 0,
                    'account_id': line.asset_pl_account_id.id,
                    'analytic_distribution_id': line.analytic_distribution_id.id or False,
                    'asset_line_id': line.id,
                }, {
                    'debit_currency': 0,
                    'credit_currency': line.amount,
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
                        'debit_currency': x['debit_currency'],
                        'credit_currency': x['credit_currency'],
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
    _columns = {
        'asset_id': fields.many2one('product.asset', 'Asset', required=1),
        'event_type_id': fields.many2one('product.asset.event.type', 'Event Type', required=1, domain=[('is_disposal', '=', True)], add_empty=True),
        'disposal_expense_account': fields.many2one('account.account', 'Disposal P&L account', required=1, domain=[('user_type_code', 'in', ['expense', 'income'])]), # TODO domain
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
            if ev.expense_account_id:
                return {'value': {'disposal_expense_account': ev.expense_account_id and ev.expense_account_id.id or False}}
        return {}

    def button_generate_disposal_entry(self, cr, uid, ids, context=None):
        asset_line_obj = self.pool.get('product.asset.line')
        wiz = self.browse(cr, uid, ids[0], context=context)

        if self.pool.get('product.asset').search_exists(cr, uid, [('id', '=', wiz.asset_id.id), ('start_date', '>=', wiz.disposal_date)], context=context):
            raise osv.except_osv(_('Error !'), _('Date of disposal %s is before the depreciation date %s!') % (wiz.disposal_date, wiz.asset_id.start_date))

        nb_posted = asset_line_obj.search(cr, uid, [('asset_id', '=', wiz.asset_id.id), ('date', '>=', wiz.disposal_date), ('move_id.state', '=', 'posted')], count=True, context=context)
        if nb_posted:
            raise osv.except_osv(_('Error !'), _('Date of disposal %s does not match: there are %d posted entries') % (wiz.disposal_date, nb_posted))

        nb_draft = asset_line_obj.search(cr, uid, [('asset_id', '=', wiz.asset_id.id), ('date', '>=', wiz.disposal_date), ('move_id.state', '=', 'draft')], count=True, context=context)
        if nb_draft > 1:
            raise osv.except_osv(_('Error !'), _('Date of disposal %s does not match: there are %d unposted entries') % (wiz.disposal_date, nb_draft))

        disposale_dt = datetime.strptime(wiz.disposal_date, '%Y-%m-%d')
        end_of_month = disposale_dt + relativedelta(months=1, day=1, days=-1)
        draft_lines = asset_line_obj.search(cr, uid, [('asset_id', '=', wiz.asset_id.id), ('date', '>', end_of_month)], context=context)
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

        line_to_update_id =  asset_line_obj.search(cr, uid, [('asset_id', '=', wiz.asset_id.id), ('date', '=', end_of_month)], context=context)
        if line_to_update_id:
            line_to_update = asset_line_obj.browse(cr, uid, line_to_update_id[0], context=context)
            if wiz.disposal_date < line_to_update.last_dep_day:
                start_entry_dt = datetime.strptime(line_to_update.first_dep_day, '%Y-%m-%d')
                last_entry_dt = datetime.strptime(line_to_update.last_dep_day, '%Y-%m-%d')
                new_value = round(line_to_update.amount / ((last_entry_dt - start_entry_dt).days + 1) * ((disposale_dt - start_entry_dt).days + 1), 2)
                asset_line_obj.write(cr, uid, line_to_update_id, {'amount': new_value, 'date': wiz.disposal_date}, context=context)
                for ji in line_to_update.move_id.line_id:
                    if ji.debit_currency:
                        self.pool.get('account.move.line').write(cr, uid, [ji.id], {'debit_currency': new_value, 'document_date': wiz.disposal_date, 'date': wiz.disposal_date}, context=context, check=False)
                    else:
                        self.pool.get('account.move.line').write(cr, uid, [ji.id], {'credit_currency': new_value, 'document_date': wiz.disposal_date, 'date': wiz.disposal_date}, context=context, check=False)
                self.pool.get('account.move').write(cr, uid, [line_to_update.move_id.id], {'document_date': wiz.disposal_date, 'date': wiz.disposal_date}, context=context)

        #asset = self.pool.get('product.asset').browse(cr, uid, [wiz.asset_id.id], fields_to_fetch=['disposal_amount'], context=context)
        #print asset[0].disposal_amount, wiz.asset_id.disposal_amount
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
        'date': fields.date('Date', required=1),
    }

    def button_generate_all(self, cr, uid, ids, context=None):
        asset_line_obj = self.pool.get('product.asset.line')
        wiz = self.browse(cr, uid, ids[0], context=context)
        end_date = (datetime.strptime(wiz.date, '%Y-%m-%d') + relativedelta(months=1, day=1, days=-1)).strftime('%Y-%m-%d')
        asset_line_ids = asset_line_obj.search(cr, uid, [('asset_id.state', '=', 'running'), ('move_id', '=', False), ('date', '<=', end_date)], context=context)
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
