# -*- coding: utf-8 -*-

from osv import osv, fields
from tools.translate import _
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time

class replenishment_location_config(osv.osv):
    _name = 'replenishment.location.config'
    _description = 'Location Configuration'
    _order = 'id desc'


    def _get_frequence_name(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns the name_get value of the frequence
        '''
        res = {}
        for proc in self.browse(cr, uid, ids):
            if proc.frequence_id:
                res[proc.id] = self.pool.get('stock.frequence').name_get(cr, uid, [proc.frequence_id.id], context=context)[0][1]
        return res


    _columns = {
        'name': fields.char('Reference', size=64, readonly=1, select=1),
        'description': fields.char('Desription', required=1, size=28, select=1),
        'synched': fields.boolean('Synched Locations'),
        'main_instance': fields.many2one('msf.instance', readonly=1, string="Main Instance"),
        'active': fields.boolean('Active'),
        'local_location_ids': fields.many2many('stock.location', 'local_location_configuration_rel', 'config_id', 'location_id', 'Local Locations', domain="[('usage', '=', 'internal'), ('location_category', 'in', ['stock', 'consumption_unit', 'eprep']), ('used_in_config', '=', False)]"),
        'remote_location_ids': fields.many2many('stock.location.instance', 'remote_location_configuration_rel', 'config_id', 'location_id', 'Project Locations', domain="[('usage', '!=', 'view'), ('used_in_config', '=', False)]"),

        # iventory review
        'review_active': fields.boolean('Review Active'),
        'projected_view': fields.integer('Standard Projected view (months)'),
        'rr_amc': fields.integer('RR-AMC period (months)'),
        'sleeping': fields.integer('Sleeping stock periodicity (months)'),
        'time_unit': fields.selection([('d', 'days'), ('w', 'weeks'), ('m', 'months')], string='Time units displayed (Inventory Review)'),
        'frequence_name': fields.function(_get_frequence_name, method=True, string='Frequency', type='char'),
        'frequence_id': fields.many2one('stock.frequence', string='Frequency'),
    }

    _defaults = {
        'active': True,
        'synched': True,
        'main_instance': lambda s, cr, uid, c: s.pool.get('res.company')._get_instance_id(cr, uid),
        'projected_view': 8,
        'sleeping': 12,
    }

    def write(self, cr, uid, ids, vals, context=None):
        if 'synched' in vals and not vals['synched']:
            vals['remote_location_ids'] = [(6, 0, [])]

        return super(replenishment_location_config, self).write(cr, uid, ids, vals, context=context)

    def create(self, cr, uid, vals, context=None):
        if 'name' not in vals:
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'replenishment.location.config')

        if 'synched' in vals and not vals['synched']:
            vals['remote_location_ids'] = [(6, 0, [])]

        return super(replenishment_location_config, self).create(cr, uid, vals, context)

    def check_no_duplicates(self, cr, uid, ids, context=None):
        instance_id = self.pool.get('res.company')._get_instance_id(cr, uid)
        error = []

        for location_table, location_name, rel_table in [('stock_location', 'name', 'local_location_configuration_rel'), ('stock_location_instance', 'full_name', 'remote_location_configuration_rel')]:
            cr.execute('''
                select config.description, config2.name, loc.''' + location_name + ''' from
                    replenishment_location_config config, ''' + rel_table + ''' rel, replenishment_location_config config2, ''' + rel_table + ''' rel2, ''' + location_table + ''' loc
                where
                    rel.config_id = config.id and
                    config.main_instance = %(instance)s and
                    config.id in %(ids)s and
                    rel2.config_id = config2.id and
                    config2.main_instance = %(instance)s and
                    config2.id != config.id and
                    rel.location_id = rel2.location_id and
                    config.active and
                    config2.active and
                    loc.id = rel.location_id
                group by config.description, config2.name, loc.id, loc.name
            ''', {'instance': instance_id, 'ids': tuple(ids)})   # not_a_user_entry
            nb_error = 0
            for x in cr.fetchall():
                if nb_error > 5:
                    error.append('...')
                    break
                error.append(_('%s : location %s already used in %s') % (x[0], x[2], x[1]))
                nb_error += 1
        if error:
            raise osv.except_osv(_('Warning'), "\n".join(error))
        return True

    _constraints = [(check_no_duplicates, 'Location already used on an active Configuration', [])]
    _sql_constraints = [
        ('unique_description_instance', 'unique(description, main_instance)', 'Desription must be unique'),
        ('review_active_with_freq', 'CHECK(review_active or frequence_id is not null)', "You can't activate a review w/o any frequency"),
    ]


    def choose_change_frequence(self, cr, uid, ids, context=None):
        '''
        Open a wizard to define a frequency for the automatic supply
        or open a wizard to modify the frequency if frequency already exists
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        proc = self.browse(cr, uid, ids[0], fields_to_fetch=['frequence_id'], context=context)
        if proc.frequence_id and proc.frequence_id.id:
            frequence_id = proc.frequence_id.id
        else:
            frequence_data = {
                'name': 'monthly',
                'monthly_choose_freq': 1,
                'monthly_choose_day': 'monday',
                'monthly_frequency': 1,
                'monthly_one_day': True,
                'no_end_date': True,
                'start_date': time.strftime('%Y-%m-%d'),
            }
            frequence_id = self.pool.get('stock.frequence').create(cr, uid, frequence_data, context=context)
            self.write(cr, uid, proc.id, {'frequence_id': frequence_id}, context=context)

        context.update({
            'active_id': proc.id,
            'active_model': 'replenishment.location.config',
            'res_ok': True,
        })

        return {
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'stock.frequence',
            'view_type': 'form',
            'view_model': 'form',
            'context': context,
            'res_id': frequence_id
        }

replenishment_location_config()


class replenishment_segment(osv.osv):
    _name = 'replenishment.segment'
    _description = 'Segment'

    def _get_date(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        for x in ids:
            ret[x] = {
                'previous_order_rrd': False,
                'date_preparing': False,
                'date_next_order_validated': False,
                'date_next_order_received': False,
            }
        return ret

    def _get_lt(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        for seg in self.read(cr, uid, ids, ['order_creation_lt', 'order_validation_lt', 'supplier_lt', 'handling_lt'], context=context):
            ret[seg['id']] = {
                'internal_lt': seg['order_creation_lt'] + seg['order_validation_lt'],
                'external_lt': seg['supplier_lt'] + seg['handling_lt'],
                'total_lt': seg['order_creation_lt'] + seg['order_validation_lt'] + seg['supplier_lt'] + seg['handling_lt'],
            }
        return ret

    _columns = {
        'name': fields.char('Reference', size=64, readonly=1, select=1),
        'description': fields.char('Desription', required=1, size=28, select=1),
        'location_config_id': fields.many2one('replenishment.location.config', 'Location Config', required=1),
        'rule': fields.selection([('cycle', 'Order Cycle'), ('minmax', 'Min/Max'), ('auto', 'Automatic Supply')], string='Replenishment Rule (Order quantity)', required=1),
        'ir_requesting_location': fields.many2one('stock.location', string='IR Requesting Location', domain="[('usage', '=', 'internal'), ('location_category', 'in', ['stock', 'consumption_unit', 'eprep'])"),
        'product_list_id': fields.many2one('product.list', 'Primary product list'),
        'status': fields.selection([('draft', 'Draft'), ('complete', 'Complete'), ('cancel', 'Cancelled'), ('archived', 'Archived')], 'Status', readonly=1),
        'order_creation_lt': fields.integer('Order Creation Lead Time (days)', required=1),
        'order_validation_lt': fields.integer('Order Validation Lead Time (days)', required=1),
        'internal_lt': fields.function(_get_lt, type='integer', method=1, string='Internal Lead Time', multi='get_lt'),
        'supplier_lt': fields.integer('Supplier Lead Time (days)', required=1),
        'handling_lt': fields.integer('Handling Lead Time (days)', required=1),
        'external_lt': fields.function(_get_lt, type='integer', method=1, string='External Lead Time', multi='get_lt'),
        'total_lt': fields.function(_get_lt, type='integer', method=1, string='Total Lead Time', multi='get_lt'),
        'order_coverage': fields.integer('Order Coverage (months)'),
        'safety_stock': fields.integer('Safety Stock (months)'),
        'previous_order_rrd': fields.function(_get_date, type='date', method=True, string='Previous order RDD Date', multi='get_date'),
        'date_preparing': fields.function(_get_date, type='date', method=True, string='Date to start preparing the order', multi='get_date'),
        'date_next_order_validated':  fields.function(_get_date, type='date', method=True, string='Date next order to be validated by', multi='get_date'),
        'date_next_order_received': fields.function(_get_date, type='date', method=True, string='Next order to be received by', multi='get_date'),
        'line_ids': fields.one2many('replenishment.segment.line', 'segment_id', 'Products', context={'default_code_only': 1}),
    }

    def create(self, cr, uid, vals, context=None):
        if 'name' not in vals:
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'replenishment.segment')

        return super(replenishment_segment, self).create(cr, uid, vals, context)

    def on_change_lt(self, cr, uid, ids, order_creation_lt, order_validation_lt, supplier_lt, handling_lt, context=None):
        ret = {}
        ret['internal_lt'] = (order_creation_lt or 0) + (order_validation_lt or 0)
        ret['external_lt'] = (supplier_lt or 0) + (handling_lt or 0)
        ret['total_lt'] = ret['internal_lt'] + ret['external_lt']
        return {'value': ret}

replenishment_segment()

class replenishment_segment_line(osv.osv):
    _name = 'replenishment.segment.line'
    _inherits = {'replenishment.segment': 'segment_id'}
    _description = 'Product'

    def _get_main_list(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        for x in ids:
            ret[x] = False

        return ret

    def _get_real_stock(self, cr, uid, ids, field_name, arg, context=None):
        prod_obj = self.pool.get('product.product')
        ret = {}
        segment = {}
        now = datetime.now()
        #now = datetime.strptime('2019-09-30', '%Y-%m-%d')
        for x in self.browse(cr, uid, ids, fields_to_fetch=['product_id', 'segment_id'], context=context):
            ret[x.id] = {
                'real_stock': 0,
                'real_stock_instance': 0,
                'rr_amc': 0,
            }
            if x.segment_id.id not in segment:
                segment[x.segment_id.id] = {
                    'context': {
                        'from_date': (now -  relativedelta(months=x.segment_id.location_config_id.rr_amc)).strftime('%Y-%m-%d'),
                        'to_date': now.strftime('%Y-%m-%d'),
                        'location_ids': [loc.id for loc in x.segment_id.location_config_id.local_location_ids],
                    },
                    'prod_seg_line': {}
                }
            segment[x.segment_id.id]['prod_seg_line'][x.product_id.id] = x.id

        for seg_id in segment:
            amc = prod_obj.compute_amc(cr, uid, segment[seg_id]['prod_seg_line'].keys(), segment[seg_id]['context'])
            for prod_id in amc:
                ret[segment[seg_id]['prod_seg_line'][prod_id]]['rr_amc'] = amc[prod_id]

            for prod in prod_obj.browse(cr, uid, segment[seg_id]['prod_seg_line'].keys(), fields_to_fetch=['qty_available'], context={'location_ids': segment[seg_id]['context']['location_ids']}):
                ret[segment[seg_id]['prod_seg_line'][prod.id]]['real_stock_instance'] = prod.qty_available
                ret[segment[seg_id]['prod_seg_line'][prod.id]]['real_stock'] = prod.qty_available

        return ret

    _columns = {
        'segment_id': fields.many2one('replenishment.segment', 'Segment', select=1, required=1),
        'product_id': fields.many2one('product.product', 'Product Code', select=1, required=1),
        'product_description': fields.related('product_id', 'name',  string='Desciption', type='char', size=64, readonly=True, select=True, write_relate=False),
        'uom_id': fields.related('product_id', 'uom_id',  string='UoM', type='many2one', relation='product.uom', readonly=True, select=True, write_relate=False),
        'in_main_list': fields.function(_get_main_list, type='boolean', method=True, string='In prod. list'),
        'status': fields.selection([('active', 'Active'), ('new', 'New')], string='Life cycle status'),
        'min_qty': fields.float('Min Qty', related_uom='uom_id'),
        'max_qty': fields.float('Max Qty', related_uom='uom_id'),
        'auto_qty': fields.float('Auto. Supply Qty', related_uom='uom_id'),
        'buffer_qty': fields.float('Buffer Qty', related_uom='uom_id'),
        'real_stock': fields.function(_get_real_stock, type='float', method=True, related_uom='uom_id', string='Real Stock', multi='get_stock_amc'),
        'real_stock_instance': fields.function(_get_real_stock, type='float', method=True, related_uom='uom_id', string='Real Stock', multi='get_stock_amc'),
        'rr_amc': fields.function(_get_real_stock, type='float', method=True, related_uom='uom_id', string='RR-AMC', multi='get_stock_amc'),
        'rr_fmc_1': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_1': fields.datetime('From'),
        'rr_fmc_to_1': fields.datetime('To'),
        'rr_fmc_2': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_2': fields.datetime('From'),
        'rr_fmc_to_2': fields.datetime('To'),
        'rr_fmc_3': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_3': fields.datetime('From'),
        'rr_fmc_to_3': fields.datetime('To'),
        'rr_fmc_4': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_4': fields.datetime('From'),
        'rr_fmc_to_4': fields.datetime('To'),
        'rr_fmc_5': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_5': fields.datetime('From'),
        'rr_fmc_to_5': fields.datetime('To'),
        'rr_fmc_6': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_6': fields.datetime('From'),
        'rr_fmc_to_6': fields.datetime('To'),
        'rr_fmc_7': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_7': fields.datetime('From'),
        'rr_fmc_to_7': fields.datetime('To'),
        'rr_fmc_8': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_8': fields.datetime('From'),
        'rr_fmc_to_8': fields.datetime('To'),
        'rr_fmc_9': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_9': fields.datetime('From'),
        'rr_fmc_to_9': fields.datetime('To'),
        'rr_fmc_10': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_10': fields.datetime('From'),
        'rr_fmc_to_10': fields.datetime('To'),
        'rr_fmc_11': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_11': fields.datetime('From'),
        'rr_fmc_to_11': fields.datetime('To'),
        'rr_fmc_12': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_12': fields.datetime('From'),
        'rr_fmc_to_12': fields.datetime('To'),
    }

    _sql_constraints = [
        ('uniq_segment_id_product_id', 'unique(segment_id, product_id)', 'Product already set in this segment')
    ]
replenishment_segment_line()
