# -*- coding: utf-8 -*-

from osv import osv, fields
from tools.translate import _
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
import json

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


    def _get_sync_remote_location_txt(self, cr, uid, ids, field_name, args, context=None):
        ret = {}
        for conf in self.browse(cr, uid, ids, fields_to_fetch=['remote_location_ids'], context=context):
            ret[conf.id] = json.dumps([(x.instance_id.instance, x.instance_db_id) for x in conf.remote_location_ids])
        return ret

    def _set_sync_remote_location_txt(self, cr, uid, id, name=None, value=None, fnct_inv_arg=None, context=None):
        instance_obj = self.pool.get('res.company')._get_instance_record(cr, uid)
        if not instance_obj:
            return True
        instance = instance_obj.instance

        data =json.loads(value)
        cr.execute('delete from local_location_configuration_rel where config_id=%s', (id, ))
        for d in data:
            if d[0] == instance:
                cr.execute('insert into local_location_configuration_rel (config_id, location_id) values (%s, %s)', (id, d[1]))
        return True

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
        'sync_remote_location_txt': fields.function(_get_sync_remote_location_txt, method=True, type='text', fnct_inv=_set_sync_remote_location_txt, internal=1, string='Sync remote', help='Used to sync remote_location_ids'),
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
        ('review_active_with_freq', 'CHECK(not review_active or frequence_id is not null)', "You can't activate a review w/o any frequency"),
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
    _inherits = {'replenishment.location.config': 'location_config_id'}
    _rec_name = 'name_seg'
    _order = 'id desc'

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

    def _get_rule_alert(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        dict_d = {
            'cycle': _('PAS with FMC'),
            'minmax': _('Min'),
            'auto': _('None'),
        }
        for seg in self.read(cr, uid, ids, ['rule'], context=context):
            ret[seg['id']] = dict_d.get(seg['rule'],'')
        return ret

    _columns = {
        'name_seg': fields.char('Reference', size=64, readonly=1, select=1),
        'description_seg': fields.char('Desription', required=1, size=28, select=1),
        'location_config_id': fields.many2one('replenishment.location.config', 'Location Config', required=1),
        'rule': fields.selection([('cycle', 'Order Cycle'), ('minmax', 'Min/Max'), ('auto', 'Automatic Supply')], string='Replenishment Rule (Order quantity)', required=1),
        'rule_alert': fields.function(_get_rule_alert, method=1, string='Replenishment Rule (Alert Theshold', type='char'),
        'ir_requesting_location': fields.many2one('stock.location', string='IR Requesting Location', domain="[('usage', '=', 'internal'), ('location_category', 'in', ['stock', 'consumption_unit', 'eprep'])"),
        'product_list_id': fields.many2one('product.list', 'Primary product list'),
        'state': fields.selection([('draft', 'Draft'), ('complete', 'Complete'), ('cancel', 'Cancelled'), ('archived', 'Archived')], 'Status', readonly=1),
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

    _defaults = {
        'state': 'draft',
    }
    def create(self, cr, uid, vals, context=None):
        if 'name_seg' not in vals:
            vals['name_seg'] = self.pool.get('ir.sequence').get(cr, uid, 'replenishment.segment')

        return super(replenishment_segment, self).create(cr, uid, vals, context)

    def on_change_lt(self, cr, uid, ids, order_creation_lt, order_validation_lt, supplier_lt, handling_lt, context=None):
        ret = {}
        ret['internal_lt'] = (order_creation_lt or 0) + (order_validation_lt or 0)
        ret['external_lt'] = (supplier_lt or 0) + (handling_lt or 0)
        ret['total_lt'] = ret['internal_lt'] + ret['external_lt']
        return {'value': ret}

    def trigger_compute(self, cr, uid, ids, context):
        return self.pool.get('replenishment.segment.line.amc').generate_all_amc(cr, uid, context=context, seg_ids=ids)

    def generate_order_calc(self, cr, uid, ids, context):
        # TODO JFB RR: check state, date pulled from projects ...

        orcer_calc_line = self.pool.get('replenishment.order_calc.line')
        for seg in self.browse(cr, uid, ids, context):
            calc_id = self.pool.get('replenishment.order_calc').create(cr, uid, {
                    'segment_id': seg.id,
                    'description_seg': seg.description_seg,
                    'location_config_id': seg.location_config_id.id,
                    'rule': seg.rule
            }, context=context)

            loc_ids = [x.id for x in seg.local_location_ids]
            cr.execute('''
                select l.product_id, min(date_done) from stock_move m, stock_picking p, replenishment_segment_line l
                    where
                        m.picking_id = m.id and
                        m.state in ('available', 'confirm') and
                        m.location_dest_id in %s and
                        l.product_id = m.product_id and
                        l.segment_id = %s
                    group by l.product_id
                    ''', (tuple(loc_ids), seg.id)
            )
            prod_eta = {}
            for x in cr.fetchall():
                prod_eta[x[0]] = x[1]

            cr.execute('''
                select segment_line_id, sum(reserved_stock), sum(real_stock - reserved_stock - expired_before_rrd), sum(expired_before_rrd), sum(expired_between_rrd_oc)
                    from replenishment_segment_line_amc amc, replenishment_segment_line line
                    where
                        line.id = amc.segment_line_id
                    group by segment_line_id
            ''')
            sum_line = {}
            for x in cr.fetchall():
                sum_line[x[0]] = {
                    'reserved_stock_qty': x[1] or 0,
                    'pas_no_pipe_no_fmc': x[2] or 0,
                    'expired_before_rrd': x[3] or 0,
                    'expired_rdd_oc': x[4] or 0,
                }


            today = datetime.now()
            rdd = datetime.now() + relativedelta(days=int(seg.total_lt))
            oc = rdd + relativedelta(months=seg.order_coverage)
            for line in seg.line_ids:
                total_fmc = 0
                total_month = 0
                month_of_supply = 0

                total_fmc_oc = 0
                total_month_oc = 0

                laking = False
                for fmc_d in range(1, 13):
                    from_fmc = getattr(line, 'rr_fmc_from_%d'%fmc_d)
                    to_fmc = getattr(line, 'rr_fmc_to_%d'%fmc_d)
                    num_fmc = getattr(line, 'rr_fmc_%d'%fmc_d)
                    if from_fmc and to_fmc and num_fmc:
                        from_fmc = datetime.strptime(from_fmc, '%Y-%m-%d')
                        to_fmc = datetime.strptime(to_fmc, '%Y-%m-%d')
                        begin = max(today, from_fmc)
                        end = min(rdd, to_fmc)
                        if end >= begin:
                            month = (end-begin).days/30.44
                            total_month += month
                            total_fmc += month*num_fmc
                            if not laking:
                                if total_fmc < sum_line[line.id]['pas_no_pipe_no_fmc']:
                                    month_of_supply += month
                                else:
                                    month_of_supply += ( sum_line[line.id]['pas_no_pipe_no_fmc'] - total_fmc + month*num_fmc ) / num_fmc
                                    laking = True
                        else:
                            end_oc = min(oc, to_fmc)
                            if end_oc >= begin:
                                month = (end_oc-begin).days/30.44
                                total_month_oc += month
                                total_fmc_oc += month*num_fmc

                pas = max(0, sum_line.get(line.id, {}).get('pas_no_pipe_no_fmc', 0) + line.pipeline_before_rrd - total_fmc)
                ss_stock = 0
                if total_month_oc+total_month:
                    ss_stock = seg.safety_stock * ((total_fmc_oc+total_month)/(total_month_oc+total_month))
                line_data = {
                    'order_calc_id': calc_id,
                    'product_id': line.product_id.id,
                    'uom_id': line.uom_id.id,
                    'in_main_list': line.in_main_list,
                    'real_stock': line.real_stock,
                    'pipeline_qty': line.pipeline_before_rrd,
                    'eta_for_next_pipeline': prod_eta.get(line.product_id.id, False),
                    'reserved_stock_qty': sum_line.get(line.id, {}).get('reserved_stock_qty'),
                    'projected_stock_qty': pas,
                    'qty_lacking': max(0, sum_line.get(line.id, {}).get('pas_no_pipe_no_fmc', 0) - total_fmc),
                    'qty_lacking_needed_by': laking and (today + relativedelta(days=month_of_supply*30.44)).strftime('%Y-%m-%d'),
                    'expired_qty_before_cons': sum_line.get(line.id, {}).get('expired_before_rrd'),
                    'expired_qty_before_eta': False, #TODO JFB=  RR
                    'proposed_order_qty': max(0, total_fmc_oc + ss_stock + line.buffer_qty + sum_line.get(line.id, {}).get('expired_rdd_oc',0) - pas - line.pipeline_between_rrd_oc)   # TODO JFB NEW PROD
                }
                orcer_calc_line.create(cr, uid, line_data, context=context)



replenishment_segment()

class replenishment_segment_line(osv.osv):
    _name = 'replenishment.segment.line'
    _description = 'Product'
    _rec_name = 'product_id'

    def _get_main_list(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        for x in ids:
            ret[x] = False

        cr.execute('''select seg_line.id from
            replenishment_segment_line seg_line, replenishment_segment seg, product_list_line prod_line
            where
                seg.id = seg_line.segment_id and
                prod_line.list_id = seg.product_list_id and
                prod_line.name = seg_line.product_id and
                seg_line.id in %s''', (tuple(ids), )
        )
        for x in cr.fetchall():
            ret[x[0]] = True
        return ret

    def _get_real_stock(self, cr, uid, ids, field_name, arg, context=None):
        prod_obj = self.pool.get('product.product')
        ret = {}
        segment = {}
        for x in self.browse(cr, uid, ids, fields_to_fetch=['product_id', 'segment_id'], context=context):
            ret[x.id] = {
                'real_stock': 0,
                'real_stock_instance': 0,
                'rr_amc': 0,
            }
            if x.segment_id.id not in segment:
                to_date = datetime.now() + relativedelta(day=1, days=-1)
                segment[x.segment_id.id] = {
                    'context': {
                        'to_date': to_date.strftime('%Y-%m-%d'),
                        'from_date': (to_date -  relativedelta(months=x.segment_id.location_config_id.rr_amc)).strftime('%Y-%m-%d'),
                        'amc_location_ids': [loc.id for loc in x.segment_id.location_config_id.local_location_ids],
                    },
                    'prod_seg_line': {},
                    'remote_location_q': [],
                    'remote_instance_ids': [],
                }
                for remote_loc in x.segment_id.location_config_id.remote_location_ids:
                    if remote_loc.instance_id.id not in segment[x.segment_id.id]['remote_instance_ids']:
                        segment[x.segment_id.id]['remote_instance_ids'].append(remote_loc.instance_id.id)

                    segment[x.segment_id.id]['remote_location_q'].append('remote_instance_id=%s AND remote_location_id=%s' % (remote_loc.instance_id.id, remote_loc.instance_db_id))

            segment[x.segment_id.id]['prod_seg_line'][x.product_id.id] = x.id

        for seg_id in segment:
            if segment[seg_id]['remote_location_q']:
                # compute AMC for remote + local instances
                # TODO JFB RR : genereate_all_amc for local
                cr.execute("""
                    select segment_line_id, sum(amc)
                    from replenishment_segment_line_amc
                    where
                        segment_line_id in %s
                    group by segment_line_id
                """, (tuple(segment[seg_id]['prod_seg_line'].values()), ))
                for x in cr.fetchall():
                    ret[x[0]]['rr_amc'] = x[1]
            else:
                # AMC is fully local
                amc = prod_obj.compute_amc(cr, uid, segment[seg_id]['prod_seg_line'].keys(), segment[seg_id]['context'])
                for prod_id in amc:
                    ret[segment[seg_id]['prod_seg_line'][prod_id]]['rr_amc'] = amc[prod_id]

            for prod in prod_obj.browse(cr, uid, segment[seg_id]['prod_seg_line'].keys(), fields_to_fetch=['qty_available'], context={'location_ids': segment[seg_id]['context']['amc_location_ids']}):
                ret[segment[seg_id]['prod_seg_line'][prod.id]]['real_stock_instance'] = prod.qty_available
                ret[segment[seg_id]['prod_seg_line'][prod.id]]['real_stock'] = prod.qty_available

            if segment[seg_id]['remote_location_q']:
                remote_q = "select product_id, sum(quantity) from stock_mission_report_line_location where product_id in %s "
                remote_q += " AND ( %s ) " % ( ' OR '.join(segment[seg_id]['remote_location_q']))
                remote_q += 'group by product_id'
                cr.execute(remote_q, (tuple(segment[seg_id]['prod_seg_line'].keys()),))
                for x in cr.fetchall():
                    ret[segment[seg_id]['prod_seg_line'][x[0]]]['real_stock'] += x[1]


        return ret

    def _get_pipeline_before(self, cr, uid, ids, field_name, arg, context=None):
        segment = {}
        ret = {}
        for x in self.browse(cr, uid, ids, fields_to_fetch=['product_id', 'segment_id'], context=context):

            ret[x.id] = {
                'pipeline_before_rrd': 0,
                'pipeline_between_rrd_oc': 0
            }
            if x.segment_id.id not in segment:
                segment[x.segment_id.id] = {
                    'to_date_rrd': (datetime.now() + relativedelta(days=int(x.segment_id.total_lt))).strftime('%Y-%m-%d'),
                    'to_date_oc': (datetime.now() + relativedelta(days=int(x.segment_id.total_lt)) + relativedelta(months=x.segment_id.order_coverage)).strftime('%Y-%m-%d'),
                    'prod_seg_line': {},
                    'location_ids': [l.id for l in x.segment_id.location_config_id.local_location_ids],
                }
            segment[x.segment_id.id]['prod_seg_line'][x.product_id.id] = x.id

        prod_obj = self.pool.get('product.product')
        for seg_id in segment:
            # TODO JFB RR: compute_child ?
            for prod_id in prod_obj.browse(cr, uid, segment[seg_id]['prod_seg_line'].keys(), fields_to_fetch='incoming_qty', context={'to_date': segment[seg_id]['to_date_rrd'], 'location': segment[seg_id]['location_ids']}):
                ret[segment[seg_id]['prod_seg_line'][prod_id.id]]['pipeline_before_rrd'] =  prod_id['incoming_qty']
            for prod_id in prod_obj.browse(cr, uid, segment[seg_id]['prod_seg_line'].keys(), fields_to_fetch='incoming_qty', context={'from_strict_date': segment[seg_id]['to_date_rrd'], 'to_date': segment[seg_id]['to_date_oc'], 'location': segment[seg_id]['location_ids']}):
                ret[segment[seg_id]['prod_seg_line'][prod_id.id]]['pipeline_between_rrd_oc'] = prod_id['incoming_qty']

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
        'pipeline_before_rrd': fields.function(_get_pipeline_before, type='float', method=True, string='Pipeline Before RRD', multi='get_pipeline_before'),
        'pipeline_between_rrd_oc': fields.function(_get_pipeline_before, type='float', method=True, string='Pipeline between RDD and OC', multi='get_pipeline_before'),
        'rr_amc': fields.function(_get_real_stock, type='float', method=True, related_uom='uom_id', string='RR-AMC', multi='get_stock_amc'),
        'rr_fmc_1': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_1': fields.date('From'),
        'rr_fmc_to_1': fields.date('To'),
        'rr_fmc_2': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_2': fields.date('From'),
        'rr_fmc_to_2': fields.date('To'),
        'rr_fmc_3': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_3': fields.date('From'),
        'rr_fmc_to_3': fields.date('To'),
        'rr_fmc_4': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_4': fields.date('From'),
        'rr_fmc_to_4': fields.date('To'),
        'rr_fmc_5': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_5': fields.date('From'),
        'rr_fmc_to_5': fields.date('To'),
        'rr_fmc_6': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_6': fields.date('From'),
        'rr_fmc_to_6': fields.date('To'),
        'rr_fmc_7': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_7': fields.date('From'),
        'rr_fmc_to_7': fields.date('To'),
        'rr_fmc_8': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_8': fields.date('From'),
        'rr_fmc_to_8': fields.date('To'),
        'rr_fmc_9': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_9': fields.date('From'),
        'rr_fmc_to_9': fields.date('To'),
        'rr_fmc_10': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_10': fields.date('From'),
        'rr_fmc_to_10': fields.date('To'),
        'rr_fmc_11': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_11': fields.date('From'),
        'rr_fmc_to_11': fields.date('To'),
        'rr_fmc_12': fields.float('RR FMC', related_uom='uom_id'),
        'rr_fmc_from_12': fields.date('From'),
        'rr_fmc_to_12': fields.date('To'),
    }

    _sql_constraints = [
        ('uniq_segment_id_product_id', 'unique(segment_id, product_id)', 'Product already set in this segment')
    ]

    def _uniq_prod_location(self, cr, uid, ids, context=None):
        cr.execute('''select prod.default_code, array_agg(seg.name_seg)
            from replenishment_segment_line orig_seg_line, replenishment_segment_line seg_line, replenishment_segment seg, product_product prod
            where
                orig_seg_line.id in %s and
                orig_seg_line.product_id = seg_line.product_id and
                seg_line.segment_id = seg.id and
                seg.state in ('draft', 'complete') and
                prod.id = seg_line.product_id
            group by prod.default_code, seg.location_config_id
            having( count(*) > 1)''', (tuple(ids),)
        )
        error = []
        for x in cr.fetchall():
            error.append('%s : %s' % (x[0], " - ".join(x[1])))

        if error:
            raise osv.except_osv(_('Warning'), "The following product(s) are already defined in the same locations:\n%s" % "\n".join(error))
        return True

    _constraints = [
        (_uniq_prod_location, 'A product in a location may only belong to one segment.', []),
    ]

    _defaults = {
        'status': 'active',
    }
replenishment_segment_line()

class replenishment_segment_line_amc(osv.osv):
    _name = 'replenishment.segment.line.amc'
    _description = 'Segment Product AMC'
    _order = 'id desc'

    _columns = {
        'name': fields.datetime('Date of last Generation'),
        'segment_line_id': fields.many2one('replenishment.segment.line', 'Segment Line', select=1, ondelete='cascade'),
        'amc': fields.float('AMC'),
        'instance_id': fields.many2one('msf.instance', string='Instance', select=1),
        'reserved_stock': fields.float('Reserved Stock'),
        'real_stock': fields.float('Reserved Stock'),
        'expired_before_rrd': fields.float('Expired Qty before RRD'),
        'expired_between_rrd_oc': fields.float('Expired Qty between RRD and OC'),
        'expired_fmc_1': fields.float('Expired Qty FMC1'),
        'expired_fmc_2': fields.float('Expired Qty FMC2'),
        'expired_fmc_3': fields.float('Expired Qty FMC3'),
        'expired_fmc_4': fields.float('Expired Qty FMC4'),
        'expired_fmc_5': fields.float('Expired Qty FMC5'),
        'expired_fmc_6': fields.float('Expired Qty FMC6'),
        'expired_fmc_7': fields.float('Expired Qty FMC7'),
        'expired_fmc_8': fields.float('Expired Qty FMC8'),
        'expired_fmc_9': fields.float('Expired Qty FMC9'),
        'expired_fmc_10': fields.float('Expired Qty FMC10'),
        'expired_fmc_11': fields.float('Expired Qty FMC11'),
        'expired_fmc_12': fields.float('Expired Qty FMC12'),
    }

    def generate_all_amc(self, cr, uid, context=None, seg_ids=False):
        # TODO JFB RR
        # check last config mod date / conso mod date / current date and generates new AMC only if something has changed
        segment_obj = self.pool.get('replenishment.segment')
        prod_obj = self.pool.get('product.product')

        instance_id = self.pool.get('res.company')._get_instance_id(cr, uid)
        to_date = datetime.now() + relativedelta(day=1, days=-1)

        if not seg_ids:
            seg_ids = segment_obj.search(cr, uid, [('state', 'in', ['draft', 'complete'])], context=context)
        elif isinstance(seg_ids, (int, long)):
            seg_ids = [seg_ids]

        for segment in segment_obj.browse(cr, uid, seg_ids, context=context):
            seg_context = {
                'to_date': to_date.strftime('%Y-%m-%d'),
                'from_date': (to_date - relativedelta(months=segment.rr_amc)).strftime('%Y-%m-%d'),
                'amc_location_ids': [x.id for x in segment.local_location_ids],
            }
            lines = {}
            for line in segment.line_ids:
                lines[line.product_id.id] = line.id

            # update vs create line
            cache_line_amc = {}
            seg_line = {}
            line_amc_ids = self.search(cr, uid, [('instance_id', '=', instance_id), ('segment_line_id', 'in', lines.values())], context=context)
            for line_amc in self.browse(cr, uid, line_amc_ids, fields_to_fetch=['segment_line_id'], context=context):
                cache_line_amc[line_amc.segment_line_id.id] = line_amc.id
                seg_line[line_amc.id] = line_amc.segment_line_id
            # real stock - reserved stock
            stock_qties = {}
            for prod_alloc in prod_obj.browse(cr, uid, lines.keys(), fields_to_fetch=['qty_reserved', 'qty_available'], context={'location': seg_context['amc_location_ids']}):
                stock_qties[prod_alloc['id']] = {'qty_reserved': -1 * prod_alloc.qty_reserved, 'qty_available': prod_alloc.qty_available}

            # AMC
            amc = prod_obj.compute_amc(cr, uid, lines.keys(), context=seg_context)
            for prod_id in amc:
                data = {'amc': amc[prod_id], 'name': to_date, 'reserved_stock': stock_qties.get(prod_id, {}).get('qty_reserved'), 'real_stock': stock_qties.get(prod_id, {}).get('qty_available')}
                if lines[prod_id] in cache_line_amc:
                    self.write(cr, uid, cache_line_amc[lines[prod_id]], data, context=context)
                else:
                    data['segment_line_id'] = lines[prod_id]
                    data['instance_id'] = instance_id
                    cache_line_amc[lines[prod_id]] = self.create(cr, uid, data, context=context)

            # expired_before_rrd + expired_before_oc
            if segment.state == 'complete':
                expired_obj = self.pool.get('product.likely.expire.report')
                rrd_date = datetime.now() + relativedelta(days=int(segment.total_lt))
                oc_date = rrd_date + relativedelta(months=segment.order_coverage)
                expired_id = expired_obj.create(cr, uid, {'segment_id': segment.id, 'date_to': oc_date.strftime('%Y-%m-%d')})
                expired_obj._process_lines(cr, uid, expired_id, context=context, create_cr=False)

                # before rrd
                cr.execute("""
                    select line.product_id, sum(item.expired_qty)
                    from product_likely_expire_report_line line, product_likely_expire_report_item item
                    where
                        item.line_id = line.id and
                        report_id=%s and
                        item.period_start <= %s
                    group by line.product_id""", (expired_id, rrd_date.strftime('%Y-%m-%d')))
                for x in cr.fetchall():
                    self.write(cr, uid, cache_line_amc[lines[x[0]]], {'expired_before_rrd': x[1]}, context=context)

                # between rrd and oc
                cr.execute("""
                    select line.product_id, sum(item.expired_qty)
                    from product_likely_expire_report_line line, product_likely_expire_report_item item
                    where
                        item.line_id = line.id and
                        report_id=%s and
                        item.period_start > %s
                    group by line.product_id""", (expired_id, rrd_date.strftime('%Y-%m-%d')))
                for x in cr.fetchall():
                    self.write(cr, uid, cache_line_amc[lines[x[0]]], {'expired_between_rrd_oc': x[1]}, context=context)

                for amc_line_id in seg_line:
                    expired_before_fmc = {}
                    seg_line_record = seg_line[amc_line_id]
                    for x in range(1, 13):
                        expired_before_fmc['expired_fmc_%d'%x] = 0
                        if getattr(seg_line_record, 'rr_fmc_%d'%x) and getattr(seg_line_record, 'rr_fmc_from_%d'%x) and getattr(seg_line_record, 'rr_fmc_to_%d'%x):
                            cr.execute("""
                                select sum(item.expired_qty)
                                from product_likely_expire_report_line line, product_likely_expire_report_item item
                                where
                                    item.line_id = line.id and
                                    report_id=%s and
                                    item.period_start >= %s and
                                    item.period_start < %s and
                                    line.product_id = %s """, (expired_id, getattr(seg_line_record, 'rr_fmc_from_%d'%x), getattr(seg_line_record, 'rr_fmc_to_%d'%x), seg_line_record.product_id.id)
                            )
                            expired_before_fmc['expired_fmc_%d'%x] = cr.fetchone()[0] or False
                    self.write(cr, uid,  amc_line_id, expired_before_fmc, context=context)
        return True

    _sql_constraints = [
        ('uniq_segment_line_id_instance_id', 'unique(segment_line_id, instance_id)', 'Line is duplicated')
    ]

replenishment_segment_line_amc()


class replenishment_order_calc(osv.osv):
    _name = 'replenishment.order_calc'
    _description = 'Order Calculation'
    _order = 'id desc'

    def create(self, cr, uid, vals, context=None):
        if 'name' not in vals:
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'replenishment.order_calc')

        return super(replenishment_order_calc, self).create(cr, uid, vals, context)

    _columns = {
        'name': fields.char('Reference', size=64, readonly=1, select=1),
        'segment_id': fields.many2one('replenishment.segment', 'Segment', readonly=1),
        'description_seg': fields.char('Desription', required=1, size=28, readonly=1),
        'location_config_id': fields.many2one('replenishment.location.config', 'Location Config', required=1, readonly=1),
        'rule': fields.selection([('cycle', 'Order Cycle'), ('minmax', 'Min/Max'), ('auto', 'Automatic Supply')], string='Replenishment Rule (Order quantity)', readonly=1),
        'generation_date': fields.date('Order Calc generation date', readonly=1),
        'next_generation_date': fields.date('Date next order to be generated by', readonly=1),
        'state': fields.selection([('draft', 'Draft'), ('validated', 'Validated'), ('cancel', 'Cancel')], 'State', readonly=1),
        'order_calc_line_ids': fields.one2many('replenishment.order_calc.line', 'order_calc_id', 'Products'),
    }

    _defaults = {
        'generation_date': lambda *a: time.strftime('%Y-%m-%d'),
        'state': 'draft',
    }
replenishment_order_calc()

class replenishment_order_calc_line(osv.osv):
    _name ='replenishment.order_calc.line'
    _description = 'Order Calculation Lines'

    _columns = {
        'order_calc_id': fields.many2one('replenishment.order_calc', 'Order Calc', required=1, select=1),
        'product_id': fields.many2one('product.product', 'Product Code', select=1, required=1, readonly=1),
        'product_description': fields.related('product_id', 'name',  string='Desciption', type='char', size=64, readonly=True, select=True, write_relate=False),
        'uom_id': fields.related('product_id', 'uom_id',  string='UoM', type='many2one', relation='product.uom', readonly=True, select=True, write_relate=False),
        'in_main_list': fields.boolean('In prod. list', readonly=1),
        'valid_rr_fmc': fields.boolean('Valid FMC', readonly=1),
        'real_stock': fields.float('Real Stock', readonly=1, related_uom='uom_id'),
        'pipeline_qty': fields.float('Pipeline Qty', readonly=1, related_uom='uom_id'),
        'eta_for_next_pipeline': fields.date('ETA for Next Pipeline', readonly=1),
        'reserved_stock_qty': fields.float('Reserved Stock Qty', readonly=1, related_uom='uom_id'),
        'projected_stock_qty': fields.float('Projected Stock Level', readonly=1, related_uom='uom_id'),
        'qty_lacking': fields.float('Qty lacking before next ETA', readonly=1, related_uom='uom_id'),
        'qty_lacking_needed_by': fields.date('Qty lacking needed by', readonly=1),
        'open_loan': fields.boolean('Open Loan', readonly=1),
        'expired_qty_before_cons': fields.float('Expired Qty before cons.', readonly=1, related_uom='uom_id'),
        'expired_qty_before_eta': fields.float('Expired Qty before ETA', readonly=1, related_uom='uom_id'),
        'proposed_order_qty': fields.float('Proposed Order Qty', readonly=1, related_uom='uom_id'),
        'agreed_order_qty': fields.float('Agreed Order Qty', related_uom='uom_id'),
        'order_qty_comment': fields.char('Order Qty Comment', size=512),
        'warning': fields.char('Warning', size=512),
    }

replenishment_order_calc_line()
