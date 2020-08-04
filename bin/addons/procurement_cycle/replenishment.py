# -*- coding: utf-8 -*-

from osv import osv, fields
from tools.translate import _
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
import json
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
import base64
from tools import misc, drop_view_if_exists
import threading
import logging
import pooler
import decimal_precision as dp
import math

life_cycle_status = [('active', _('Active')), ('new', _('New')), ('replaced', _('Replaced')), ('replacing', _('Replacing')), ('phasingout', _('Phasing Out')), ('activereplacing', _('Active-Replacing'))]
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

    def _get_instance(self, cr, uid, ids, field_name, args, context=None):
        instance = self.pool.get('res.company')._get_instance_record(cr, uid)

        is_project = not instance or instance.level != 'coordo'
        ret = {}
        for _id in ids:
            ret[_id] = {'is_current_instance': True, 'is_project': is_project}
        for _id in self.search(cr, uid, [('main_instance', '!=', instance.id), ('id', 'in', ids)], context=context):
            ret[_id]['is_current_instance'] = False

        return ret

    def _search_is_current_instance(self, cr, uid, obj, name, args, context):
        instance_id = self.pool.get('res.company')._get_instance_id(cr, uid)

        for arg in args:
            if arg[1] not in ('=', '!='):
                raise osv.except_osv(_('Error !'), _('Filter not implemented on %s') % name)

            cond = bool(arg[2])
            if arg[1] == '!=':
                cond = not cond

            return [('main_instance', cond and '=' or '!=', instance_id)]

        return []

    _columns = {
        'name': fields.char('Reference', size=64, readonly=1, select=1),
        'description': fields.char('Description', required=1, size=28, select=1),
        'synched': fields.boolean('Synched Locations'),
        'main_instance': fields.many2one('msf.instance', readonly=1, string="Main Instance"),
        'active': fields.boolean('Active'),
        'local_location_ids': fields.many2many('stock.location', 'local_location_configuration_rel', 'config_id', 'location_id', 'Local Locations', domain="[('usage', '=', 'internal'), ('location_category', 'in', ['stock', 'consumption_unit', 'eprep']), ('used_in_config', '=', False)]"),
        'remote_location_ids': fields.many2many('stock.location.instance', 'remote_location_configuration_rel', 'config_id', 'location_id', 'Project Locations', domain="[('usage', '!=', 'view'), ('used_in_config', '=', False)]"),

        # inventory review
        'review_active': fields.boolean('Scheduled Inventory Review active'),
        'include_product': fields.boolean('Include products not covered in Replenishment Segment'),
        'projected_view': fields.integer('Standard Projected view (months)'),
        'rr_amc': fields.integer('RR-AMC period (months)', required=1),
        'sleeping': fields.integer('Sleeping stock periodicity (months)'),
        'time_unit': fields.selection([('d', 'days'), ('w', 'weeks'), ('m', 'months')], string='Time units displayed (Inventory Review)'),
        'frequence_name': fields.function(_get_frequence_name, method=True, string='Frequency', type='char'),
        'frequence_id': fields.many2one('stock.frequence', string='Frequency'),
        'next_scheduler': fields.datetime('Next Scheduled Date', readonly=1),
        'sync_remote_location_txt': fields.function(_get_sync_remote_location_txt, method=True, type='text', fnct_inv=_set_sync_remote_location_txt, internal=1, string='Sync remote', help='Used to sync remote_location_ids'),
        'is_current_instance': fields.function(_get_instance,  method=True, type='boolean', fnct_search=_search_is_current_instance, string='Defined in the instance', multi='_get_instance'),
        'is_project': fields.function(_get_instance,  method=True, type='boolean', string='Is project instance', multi='_get_instance'),
        'last_review_error': fields.text('Review Error', readonly=1),
        'alert_threshold_deviation': fields.float_null('Alert threshold deviation AMC vs. FMC (%)'),
    }

    def _get_default_synced(self, cr, uid, context=None):
        return self.pool.get('res.company')._get_instance_level(cr, uid) == 'coordo'

    _defaults = {
        'active': True,
        'include_product': True,
        'synched': _get_default_synced,
        'main_instance': lambda s, cr, uid, c: s.pool.get('res.company')._get_instance_id(cr, uid),
        'projected_view': 8,
        'sleeping': 12,
        'rr_amc': 3,
        'time_unit': 'm',
        'last_review_error': False,
        'alert_threshold_deviation': 50,
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
        new_id = super(replenishment_location_config, self).create(cr, uid, vals, context)

        self.log(cr, uid, new_id, _('Inventory Review Config has now been created'), action_xmlid='procurement_cycle.replenishment_review_config_action')
        return new_id

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
        ('unique_description_instance', 'unique(description, main_instance)', 'Description must be unique'),
        ('review_active_with_freq', 'CHECK(not review_active or next_scheduler is not null)', "You can't activate a review w/o any frequency"),
        ('rr_amc_positive', 'CHECK(rr_amc>0)', 'RR_AMC must be not null and positive'),
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

    def inventory_review(self, cr, uid, ids, context=None):
        review_obj = self.pool.get('replenishment.inventory.review')
        rev_ids = review_obj.search(cr, uid, [('location_config_id', 'in', ids)], context=context)
        if not rev_ids:
            raise osv.except_osv(_('Info'), _('No review generated'))

        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'procurement_cycle.replenishment_inventory_review_action', ['form', 'tree'], context=context)
        res['res_id'] = rev_ids[0]
        return res


    def force_generate_inventory_review(self, cr, uid, ids, context=None):
        return self.generate_inventory_review(cr, uid, ids, context=context, forced=True)

    def generate_inventory_review(self, cr, uid, ids, context=None, forced=False):
        logger = logging.getLogger('RR Inv. Review')
        segment_obj = self.pool.get('replenishment.segment')
        review_obj = self.pool.get('replenishment.inventory.review')
        now = datetime.now()

        dwm_coeff = {
            'd': 30.44,
            'w': 4.35,
            'm': 1,
        }
        for config in self.browse(cr, uid, ids, context=context):
            logger.info('Try to gen inv. review on %s' % config.name)
            seg_dom = [('location_config_id', '=', config.id), ('state', '=', 'complete')]
            if not forced:
                seg_dom += ['|', ('last_review_date', '!=', config.next_scheduler), ('last_review_date', '=', False)]
            segment_ids = segment_obj.search(cr, uid, seg_dom, context=context)
            if not segment_ids:
                self.write(cr, uid, config.id, {'last_review_error': _('No Segment found')}, context=context)
                continue

            if config.include_product:
                if not segment_obj.search_exist(cr, uid, [('location_config_id', '=', config.id), ('hidden', '=', True)], context=context):
                    self.generate_hidden_segment(cr, uid, config.id, context)
                    segment_ids = segment_obj.search(cr, uid, seg_dom, context=context)

            segments = segment_obj.browse(cr, uid, segment_ids, fields_to_fetch=['name_seg'], context=context)

            review_id = False
            review_ids = review_obj.search(cr, uid, [('location_config_id', '=', config.id)], context=context)
            if review_ids:
                review = review_obj.browse(cr, uid, review_ids[0], context=context)
                if review.state == 'complete' or review.scheduler_date != config.next_scheduler or forced:
                    review_obj.unlink(cr, uid, review_ids, context=context)
                    review_id = False
                    segment_ids = segment_obj.search(cr, uid, [('location_config_id', '=', config.id), ('state', '=', 'complete')], context=context)
                else:
                    review_id = review_ids[0]

            if not review_id:
                review_id = review_obj.create(cr, uid, {
                    'location_config_id': config.id,
                    'amc_first_date': now + relativedelta(day=1) - relativedelta(months=config.rr_amc),
                    'amc_last_date': now + relativedelta(day=1, days=-1),
                    'projected_view': config.projected_view,
                    'final_date_projection': now + relativedelta(months=int(config.projected_view), day=1, days=-1),
                    'sleeping': config.sleeping,
                    'time_unit': config.time_unit,
                    'frequence_name': config.frequence_name,
                    'state': 'inprogress',
                    'scheduler_date': config.next_scheduler,
                }, context=context)

            cr.commit()
            error = []
            for segment in segments:
                try:
                    segment_obj.generate_order_cacl_inv_data(cr, uid, [segment.id], review_id=review_id, context=context, review_date=config.next_scheduler, coeff=dwm_coeff.get(config.time_unit,1))
                    logger.info('Inventory Review for config %s, segment %s ok' % (config.name, segment.name_seg))
                    cr.commit()
                except osv.except_osv, o:
                    error.append('%s %s' % (segment.name_seg, misc.ustr(o.value)))
                    cr.rollback()
                except Exception, e:
                    error.append('%s %s' % (segment.name_seg, misc.get_traceback(e)))
                    cr.rollback()
            if not error:
                logger.info('Inventory Review for config %s complete' % (config.name,))
                review_obj.write(cr, uid, review_id, {'state': 'complete'}, context=context)
                if config.frequence_id:
                    config.frequence_id.write({'last_run': now})
                    next_date = config.frequence_id.next_date
                    self.write(cr, uid, config.id, {'next_scheduler': next_date, 'last_review_error': False}, context=context)
                else:
                    self.write(cr, uid, config.id, {'last_review_error': False}, context=context)
            else:
                self.write(cr, uid, config.id, {'last_review_error': "\n".join(error)}, context=context)
        return True

    def generate_hidden_segment(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]
        loc_config_obj = self.pool.get('replenishment.location.config')
        segment_obj = self.pool.get('replenishment.segment')
        all_config_ids = loc_config_obj.search(cr, uid, [('include_product', '=', True), ('id', 'in', ids)], context=context)
        for loc_config in loc_config_obj.browse(cr, uid, all_config_ids, context=context):
            amc_location_ids = [x.id for x in loc_config.local_location_ids]
            if not amc_location_ids:
                continue
            hidden_seg_ids = segment_obj.search(cr, uid, [('location_config_id', '=', loc_config.id), ('hidden', '=', True)], context=context)
            if not hidden_seg_ids:
                hidden_seg = segment_obj.create(cr, uid, {
                    'location_config_id': loc_config.id,
                    'hidden': True,
                    'description_seg': 'HIDDEN',
                    'name_seg': 'Stock/Pipe products not segmented',
                    'order_creation_lt': 1,
                    'order_validation_lt': 1,
                    'supplier_lt': 1,
                    'handling_lt': 1,
                    'rule': 'auto',
                    'state': 'complete',
                }, context=context)
            else:
                hidden_seg = hidden_seg_ids[0]
            # get prod in stock on main level
            cr.execute('''
                select msl.product_id from
                    stock_mission_report_line_location msl
                where
                    msl.location_id in %s and
                    msl.quantity > 0 and
                    msl.product_id not in (
                        select
                            seg_line.product_id
                        from replenishment_segment_line seg_line, replenishment_segment seg
                        where
                            seg.state in ('draft', 'complete') and seg_line.segment_id = seg.id and seg.location_config_id = %s

                    )
                group by msl.product_id
            ''', (tuple(amc_location_ids), loc_config.id))

            for prod in cr.fetchall():
                self.pool.get('replenishment.segment.line').create(cr, uid, {'state': 'active', 'product_id': prod[0], 'segment_id': hidden_seg}, context=context)

            if loc_config.is_current_instance:
                # get prod in stock on lower level
                cr.execute('''
                    select msl.product_id from
                        stock_mission_report_line_location msl, stock_location_instance loc_instance, remote_location_configuration_rel rel
                    where
                        loc_instance.instance_id = msl.remote_instance_id and
                        loc_instance.instance_db_id = msl.remote_location_id and
                        rel.config_id = %s and
                        rel.location_id = loc_instance.id and
                        msl.quantity > 0 and
                        msl.product_id not in (
                            select
                                seg_line.product_id
                            from replenishment_segment_line seg_line, replenishment_segment seg
                            where
                                seg.state in ('draft', 'complete') and seg_line.segment_id = seg.id and seg.location_config_id = %s

                        )
                    group by msl.product_id
                ''', (loc_config.id, loc_config.id))

                for prod in cr.fetchall():
                    self.pool.get('replenishment.segment.line').create(cr, uid, {'state': 'active', 'product_id': prod[0], 'segment_id': hidden_seg}, context=context)

                # move in pipe at coo / only project
                cr.execute('''
                    select move.product_id from
                        stock_move move, stock_picking p
                    where
                        move.picking_id = p.id and
                        move.location_dest_id in %s and
                        move.product_qty > 0 and
                        move.state in ('confirmed','waiting','assigned') and
                        move.product_id not in (
                              select
                                seg_line.product_id
                            from replenishment_segment_line seg_line, replenishment_segment seg
                            where
                                seg.state in ('draft', 'complete') and seg_line.segment_id = seg.id and seg.location_config_id = %s

                        )
                    group by move.product_id
                ''', (tuple(amc_location_ids), loc_config.id))

                for prod in cr.fetchall():
                    self.pool.get('replenishment.segment.line').create(cr, uid, {'state': 'active', 'product_id': prod[0], 'segment_id': hidden_seg}, context=context)

                # PO lines
                cr.execute('''
                    select pol.product_id from
                        purchase_order_line pol
                    where
                        pol.location_dest_id in %s and
                        pol.state in ('validated', 'validated_n', 'sourced_sy', 'sourced_v', 'sourced_n') and
                        pol.product_id not in (
                              select
                                seg_line.product_id
                            from replenishment_segment_line seg_line, replenishment_segment seg
                            where
                                seg.state in ('draft', 'complete') and seg_line.segment_id = seg.id and seg.location_config_id = %s

                        )
                    group by pol.product_id
                ''', (tuple(amc_location_ids), loc_config.id))

                for prod in cr.fetchall():
                    self.pool.get('replenishment.segment.line').create(cr, uid, {'state': 'active', 'product_id': prod[0], 'segment_id': hidden_seg}, context=context)

        return True

replenishment_location_config()


class replenishment_segment(osv.osv):
    _name = 'replenishment.segment'
    _description = 'Replenishment Segment'
    _inherits = {'replenishment.location.config': 'location_config_id'}
    _rec_name = 'name_seg'
    _order = 'id desc'

    def _get_date(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        for seg in self.read(cr, uid, ids, ['previous_order_rdd', 'order_creation_lt', 'order_validation_lt', 'supplier_lt', 'handling_lt', 'order_coverage', 'date_next_order_received_modified', 'ir_requesting_location'], context=context):
            ret[seg['id']] = {
                'date_preparing': False,
                'date_next_order_validated': False,
                'date_next_order_received': False,
                'ir_requesting_location_rdo': seg['ir_requesting_location'] and seg['ir_requesting_location'][0],
            }
            ret[seg['id']].update(self.compute_next_order_received(cr, uid, ids,
                                                                   seg['order_creation_lt'], seg['order_validation_lt'], seg['supplier_lt'], seg['handling_lt'], seg['order_coverage'], seg['previous_order_rdd'], seg['date_next_order_received_modified'], context=context).get('value', {}))
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

    def _get_has_inprogress_cal(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        for _id in ids:
            ret[_id] = False
        cr.execute('''select segment_id from replenishment_order_calc where state not in ('cancel', 'closed') and segment_id in %s group by segment_id''', (tuple(ids),))
        for x in cr.fetchall():
            ret[x[0]] = True
        return ret

    def _get_amc_location_ids(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        for _id in ids:
            ret[_id] = False
        instance_name = self.pool.get('res.company')._get_instance_record(cr, uid).name
        for x in self.browse(cr, uid, ids, fields_to_fetch=['remote_location_ids', 'local_location_ids'], context=context):
            if x.remote_location_ids:
                ret[x['id']] = "\n".join([loc.full_name for loc in x.remote_location_ids])
            else:
                ret[x['id']] = "\n".join(['%s-%s' % (instance_name, loc.complete_name) for loc in x.local_location_ids])
        return ret

    def _get_safety_and_buffer_warn(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        for _id in ids:
            ret[_id] = False
        cr.execute('''select segment.id
            from
                replenishment_segment segment, replenishment_segment_line line
            where
                line.segment_id = segment.id and
                segment.safety_stock > 0 and
                line.buffer_qty > 0 and
                segment.id in %s
            group by segment.id
            ''', (tuple(ids), ))
        for x in cr.fetchall():
            ret[x[0]] = True
        return ret

    def _get_have_product(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        for _id in ids:
            ret[_id] = False

        if ids:
            cr.execute('''select segment.id
                from
                    replenishment_segment segment, replenishment_segment_line line
                where
                    line.segment_id = segment.id and
                    segment.id in %s
                group by segment.id
                having count(line.id) > 0
                ''', (tuple(ids), ))
            for x in cr.fetchall():
                ret[x[0]] = True
        return ret

    _columns = {
        'name_seg': fields.char('Reference', size=64, readonly=1, select=1),
        'description_seg': fields.char('Replenishment Segment Description', required=1, size=28, select=1),
        'location_config_id': fields.many2one('replenishment.location.config', 'Location Config', required=1, ondelete='cascade'),
        'amc_location_txt': fields.function(_get_amc_location_ids, type='text', method=1, string='AMC locations'),

        'rule': fields.selection([('cycle', 'Order Cycle'), ('minmax', 'Min/Max'), ('auto', 'Automatic Supply')], string='Replenishment Rule (Order quantity)', required=1, add_empty=True),
        'rule_alert': fields.function(_get_rule_alert, method=1, string='Replenishment Rule (Alert Theshold)', type='char'),
        'ir_requesting_location': fields.many2one('stock.location', string='IR Requesting Location', domain="[('usage', '=', 'internal'), ('location_category', 'in', ['stock', 'consumption_unit', 'eprep'])]", required=0),
        'ir_requesting_location_rdo': fields.function(_get_date, type='many2one', method=1, relation='stock.location', string='IR Requesting Location', multi='get_date'),
        'product_list_id': fields.many2one('product.list', 'Primary product list'),
        'state': fields.selection([('draft', 'Draft'), ('complete', 'Complete'), ('cancel', 'Cancelled'), ('archived', 'Archived')], 'State', readonly=1),
        'order_creation_lt': fields.integer_null('Order Creation Lead Time (days)', required=1),
        'order_validation_lt': fields.integer_null('Order Validation Lead Time (days)', required=1),
        'internal_lt': fields.function(_get_lt, type='integer', method=1, string='Internal Lead Time (days)', multi='get_lt'),
        'supplier_lt': fields.integer_null('Supplier Lead Time (days)', required=1),
        'handling_lt': fields.integer_null('Handling Lead Time (days)', required=1),
        'external_lt': fields.function(_get_lt, type='integer', method=1, string='External Lead Time (days)', multi='get_lt'),
        'total_lt': fields.function(_get_lt, type='integer', method=1, string='Total Lead Time (days)', multi='get_lt'),
        'order_coverage': fields.integer_null('Order Coverage (months)'),
        'safety_stock': fields.integer_null('Safety Stock (months)',),
        'previous_order_rdd': fields.date(string='Previous order RDD Date', readonly=1, help="Generated according to latest IR's RDD (from most recent Order calc which is now closed)."),
        'date_preparing': fields.function(_get_date, type='date', method=True, string='Date to start preparing the order', multi='get_date', help='This does not take account of any stockouts not related to order coverage. Calculation: "Next order RDD date" - Total Lead time.'),
        'date_next_order_validated':  fields.function(_get_date, type='date', method=True, string='Date next order to be validated by', multi='get_date', help='This does not take account of any stockouts not related to order coverage. Calculation: "Next order RDD date" - Total Lead time + Internal LT. This isupdated according to value in "Next order to be received by'),
        'date_next_order_received': fields.function(_get_date, type='date', method=True, string='Next order to be received by (calculated)', multi='get_date', help='Calculated according to last order RDDate + OC.'),
        'date_next_order_received_modified': fields.date(string='Next order to be received by (modified)'),
        'line_ids': fields.one2many('replenishment.segment.line', 'segment_id', 'Products', context={'default_code_only': 1}),
        'file_to_import': fields.binary(string='File to import'),
        'last_generation': fields.one2many('replenishment.segment.date.generation', 'segment_id', 'Generation Date', readonly=1),
        'has_inprogress_cal': fields.function(_get_has_inprogress_cal, type='boolean', method=1, internal=1, string='Has in-progess Order Calc.'),
        'safety_and_buffer_warn': fields.function(_get_safety_and_buffer_warn, type='boolean', method=1, internal=1, string='Lines has buffer and seg has safety'),
        'last_review_date': fields.datetime('Last review date', readonly=1),
        'have_product': fields.function(_get_have_product, type='boolean', method=1, internal=1, string='Products are set'),
        'hidden': fields.boolean('Hidden', help='Used to store not segemented products with stock/pipeline'),
    }

    _defaults = {
        'state': 'draft',
        'have_product': False,
        'hidden': False,
    }

    _sql_constraints = [
        ('oc_ss_positive', 'check(safety_stock>=0 and order_coverage>=0)', 'Safety Stock and Order Coverage must be positive or 0')
    ]

    def create(self, cr, uid, vals, context=None):
        if 'name_seg' not in vals:
            vals['name_seg'] = self.pool.get('ir.sequence').get(cr, uid, 'replenishment.segment')

        return super(replenishment_segment, self).create(cr, uid, vals, context)

    def compute_next_order_received(self, cr, uid, ids, order_creation_lt, order_validation_lt, supplier_lt, handling_lt, order_coverage, previous_order_rdd, date_next_order_received_modified, context=None):
        ret = {}
        if previous_order_rdd or date_next_order_received_modified:
            previous_rdd = False
            date_next_order_received = False
            if previous_order_rdd:
                previous_rdd = datetime.strptime(previous_order_rdd, '%Y-%m-%d')
                date_next_order_received = previous_rdd + relativedelta(months=order_coverage or 0)
            if date_next_order_received_modified:
                date_next_order_received_modified = datetime.strptime(date_next_order_received_modified, '%Y-%m-%d')
                previous_rdd = date_next_order_received_modified - relativedelta(months=order_coverage or 0)

            ret = {
                'date_preparing': (previous_rdd + relativedelta(months=order_coverage or 0) - relativedelta(days=(order_creation_lt or 0) + (order_validation_lt or 0) + (supplier_lt or 0) + (handling_lt or 0))).strftime('%Y-%m-%d'),
                'date_next_order_validated': (previous_rdd + relativedelta(months=order_coverage or 0) - relativedelta(days=(supplier_lt or 0) + (handling_lt or 0))).strftime('%Y-%m-%d'),
                'date_next_order_received': date_next_order_received and date_next_order_received.strftime('%Y-%m-%d'),
            }

        return {'value': ret}

    def on_change_lt(self, cr, uid, ids, order_creation_lt, order_validation_lt, supplier_lt, handling_lt, order_coverage, previous_order_rdd, date_next_order_received_modified, context=None):
        ret = {}
        ret['internal_lt'] = (order_creation_lt or 0) + (order_validation_lt or 0)
        ret['external_lt'] = (supplier_lt or 0) + (handling_lt or 0)
        ret['total_lt'] = ret['internal_lt'] + ret['external_lt']
        ret.update(self.compute_next_order_received(cr, uid, ids, order_creation_lt, order_validation_lt, supplier_lt, handling_lt, order_coverage, previous_order_rdd, date_next_order_received_modified, context).get('value', {}))
        return {'value': ret}

    def replenishment_compute_all_bg(self, cr, uid, ids=False, context=None):
        threaded_calculation = threading.Thread(target=self.replenishment_compute_thread, args=(cr.dbname, uid, ids, context))
        threaded_calculation.start()
        return {'type': 'ir.actions.act_window_close'}

    def replenishment_compute_thread(self, dbname, uid, ids=False, context=None):
        logger = logging.getLogger('RR')
        cr = pooler.get_db(dbname).cursor()
        logger.info("Start RR computation")
        try:
            self.pool.get('replenishment.segment.line.amc').generate_segment_data(cr, uid, context=context)
            logger.info("RR computation done")
            cr.commit()

            # compute inv. review
            config_obj = self.pool.get('replenishment.location.config')
            config_ids = config_obj.search(cr, uid, [('next_scheduler', '<', datetime.now().strftime('%Y-%m-%d %H:%M:%S')), ('is_current_instance', '=', True), ('review_active', '=', True)], context=context)
            if config_ids:
                config_obj.generate_inventory_review(cr, uid, config_ids, context=context)
            cr.commit()
        except Exception as e:
            cr.rollback()
            logger.error('Error RR: %s' % misc.get_traceback(e))
        finally:
            cr.close(True)

    def trigger_compute_segment_data(self, cr, uid, ids, context):
        cr.execute('''
            select hidden_seg.id from
                replenishment_segment hidden_seg, replenishment_segment this, replenishment_location_config config
                where
                    this.location_config_id = hidden_seg.location_config_id and
                    config.id = this.location_config_id and
                    hidden_seg.hidden = 't' and
                    config.include_product = 't' and
                    this.state = 'complete' and
                    this.id in %s
            ''', (tuple(ids),))
        other_ids = [x[0] for x in cr.fetchall()]
        seg_ids = ids + other_ids
        return self.pool.get('replenishment.segment.line.amc').generate_segment_data(cr, uid, context=context, seg_ids=seg_ids, force_review=True)

    def generate_order_calc(self, cr, uid, ids, context=None):
        return self.generate_order_cacl_inv_data(cr, uid, ids, context=context)

    def generate_order_cacl_inv_data(self, cr, uid, ids, review_id=False, context=None, review_date=False, coeff=1):

        if context is None:
            context = {}

        if review_id:
            context['inv_review'] = True
        order_calc_line = self.pool.get('replenishment.order_calc.line')
        review_line = self.pool.get('replenishment.inventory.review.line')

        calc_id = False
        for seg in self.browse(cr, uid, ids, context):
            if seg.hidden and (not seg.location_config_id.include_product or not seg.line_ids):
                continue
            instances_name_by_id = {seg.main_instance.id: seg.main_instance.code}
            all_instances = set([seg.main_instance.id])
            for remote_loc in seg.remote_location_ids:
                all_instances.add(remote_loc.instance_id.id)
                instances_name_by_id[remote_loc.instance_id.id] = remote_loc.instance_id.code

            for data_done in seg.last_generation:
                if review_id and data_done.review_date or not review_id and data_done.full_date:
                    try:
                        all_instances.remove(data_done.instance_id.id)
                    except KeyError:
                        pass

            if all_instances:
                raise osv.except_osv(_('Warning'), _('Data from instance(s) is missing, please wait for the next scheduled task or the next sync, or if relates to this instance, please use button "Compute Data". Instances missing data are:\n%s') % (', '.join([instances_name_by_id.get(x, '') for x in all_instances])))

            if not review_id and not seg.previous_order_rdd and not seg.date_next_order_received_modified:
                raise osv.except_osv(_('Warning'), _('Warning, to complete Segment, field "Next order to be received by (modified)" must have date filled'))

            if not review_id:
                new_order_reception_date = seg.date_next_order_received_modified or seg.date_next_order_received

                calc_id = self.pool.get('replenishment.order_calc').create(cr, uid, {
                    'segment_id': seg.id,
                    'description_seg': seg.description_seg,
                    'location_config_id': seg.location_config_id.id,
                    'location_config_description': seg.location_config_id.description,
                    'rule': seg.rule,
                    'rule_alert': seg.rule_alert,
                    'total_lt': seg.total_lt,
                    'local_location_ids': [(6, 0, [x.id for x in seg.local_location_ids])],
                    'remote_location_ids': [(6, 0, [x.id for x in seg.remote_location_ids])],
                    'instance_id': seg.main_instance.id,
                    'new_order_reception_date': new_order_reception_date,
                }, context=context)



            loc_ids = [x.id for x in seg.local_location_ids]
            cr.execute('''
              select prod_id, min(date) from (
                  select pol.product_id as prod_id, min(coalesce(pol.confirmed_delivery_date, pol.date_planned)) as date
                        from
                          purchase_order_line pol, replenishment_segment_line l
                        where
                          l.product_id = pol.product_id and
                          l.segment_id = %(seg_id)s and
                          pol.state in ('validated', 'validated_n', 'sourced_sy', 'sourced_v', 'sourced_n') and
                          location_dest_id in %(location_id)s
                        group by pol.product_id
                UNION
                    select l.product_id as prod_id, min(m.date) as date from stock_move m, stock_picking p, replenishment_segment_line l
                    where
                        m.picking_id = p.id and
                        m.state in ('assigned', 'confirmed') and
                        m.location_dest_id in %(location_id)s and
                        l.product_id = m.product_id and
                        l.segment_id = %(seg_id)s
                    group by l.product_id
                ) x
                group by prod_id
                    ''', {'location_id': tuple(loc_ids), 'seg_id': seg.id}
                       )
            prod_eta = {}
            for x in cr.fetchall():
                prod_eta[x[0]] = x[1]

            cr.execute('''
                select segment_line_id, sum(reserved_stock), sum(real_stock - reserved_stock - expired_before_rdd), sum(expired_before_rdd), sum(expired_between_rdd_oc), bool_or(open_loan), sum(total_expiry_nocons_qty), sum(real_stock), sum(expired_qty_before_eta), sum(sleeping_qty), bool_or(open_donation)
                    from replenishment_segment_line_amc amc, replenishment_segment_line line
                    where
                        line.id = amc.segment_line_id and
                        line.segment_id = %s
                    group by segment_line_id
            ''', (seg.id,))
            sum_line = {}
            for x in cr.fetchall():
                sum_line[x[0]] = {
                    'reserved_stock_qty': x[1] or 0,
                    'pas_no_pipe_no_fmc': x[2] or 0,
                    'expired_before_rdd': x[3] or 0,
                    'expired_rdd_oc': x[4] or 0,
                    'open_loan': x[5] or False,
                    'open_donation': x[10] or False,
                    'total_expiry_nocons_qty': x[6] or 0,
                    'real_stock': x[7] or 0,
                    'expired_qty_before_eta': x[8] or 0,
                    'sleeping_qty': x[9] or 0,
                }
                if review_id:
                    sum_line[x[0]]['pas_no_pipe_no_fmc'] -= sum_line[x[0]]['expired_rdd_oc']

            today = datetime.now() + relativedelta(hour=0, minute=0, second=0, microsecond=0)
            if seg.rule == 'cycle':
                self.save_past_fmc(cr, uid, [seg.id], context=context)

            if review_id:
                rdd = today + relativedelta(months=seg.projected_view, day=1, days=-1)
                exp_by_month = {}

                if seg.rule == 'cycle':
                    # sum expired by month
                    cr.execute('''
                        select line.product_id, exp.month, sum(exp.quantity)
                            from replenishment_segment_line line
                            inner join replenishment_segment_line_amc amc on amc.segment_line_id = line.id
                            left join replenishment_segment_line_amc_month_exp exp on exp.line_amc_id = amc.id
                            where
                                line.segment_id = %s and
                                exp.month >= %s and
                                exp.month <= %s
                            group by line.product_id, exp.month
                    ''', (seg.id, today.strftime('%Y-%m-%d'), rdd.strftime('%Y-%m-%d')))
                    for x in cr.fetchall():
                        end_day_month = (datetime.strptime(x[1], '%Y-%m-%d')+relativedelta(months=1, day=1, days=-1)).strftime('%Y-%m-%d')
                        exp_by_month.setdefault(x[0], {}).update({end_day_month: x[2]})


                past_fmc = {}
                if seg.rule == 'cycle':
                    cr.execute('''
                        select line.product_id, fmc.month, fmc
                        from replenishment_segment_line line
                        inner join replenishment_segment_line_amc_past_fmc fmc on fmc.segment_line_id = line.id
                        where
                            line.segment_id = %s
                    ''', (seg.id, ))
                    for x in cr.fetchall():
                        past_fmc.setdefault(x[0], {}).update({x[1]: x[2]})


                sum_hmc2 = {}
                hmc_month = {}
                total_fmc_hmc = {}
                cr.execute('''
                    select line.product_id, amc.month, sum(amc.amc)
                    from replenishment_segment_line line
                    inner join replenishment_segment_line_amc_detailed_amc amc on amc.segment_line_id = line.id
                    where
                        line.segment_id = %s
                    group by line.product_id, amc.month
                ''', (seg.id, ))

                for x in cr.fetchall():
                    sum_hmc2.setdefault(x[0], 0)
                    hmc_month.setdefault(x[0], {}).update({x[1]: x[2]})
                    total_fmc_hmc.setdefault(x[0], 0)
                    sum_hmc2[x[0]] += x[2]*x[2]
                    total_fmc_hmc[x[0]] += x[2]

            else:
                rdd = datetime.strptime(seg.date_next_order_received_modified or seg.date_next_order_received, '%Y-%m-%d')

            if seg.date_next_order_received_modified or seg.date_next_order_received:
                seg_rdd = datetime.strptime(seg.date_next_order_received_modified or seg.date_next_order_received, '%Y-%m-%d')
            else:
                seg_rdd = rdd
            oc = rdd + relativedelta(months=seg.order_coverage)
            line_ids_order = sorted(seg.line_ids, key=lambda x: bool(x.replaced_product_id))
            lacking_by_prod = {}
            for line in line_ids_order:
                total_fmc = 0
                total_month = 0
                month_of_supply = 0
                month_of_supply_oc = 0

                total_fmc_oc = 0
                total_month_oc = 0

                valid_rr_fmc = True
                valid_line = True
                before_today = False
                before_oc = False
                before_rdd = False

                lacking = False
                lacking_oc = False

                fmc_by_month = {}
                detailed_pas = []
                pas_full = False
                if seg.rule == 'cycle':

                    cr.execute('''
                    select date, sum(qty) from (
                        select coalesce(pol.confirmed_delivery_date, pol.date_planned) as date, sum(pol.product_qty) as qty
                        from
                          purchase_order_line pol
                        where
                          pol.product_id=%(product_id)s and
                          pol.state in ('validated', 'validated_n', 'sourced_sy', 'sourced_v', 'sourced_n') and
                          location_dest_id in %(location_id)s and
                          coalesce(pol.confirmed_delivery_date, pol.date_planned) <= %(date)s
                        group by coalesce(pol.confirmed_delivery_date, pol.date_planned)
                        UNION

                        select date(m.date) as date, sum(product_qty) as product_qty from stock_move m, stock_picking p
                            where
                                m.picking_id = p.id and
                                m.state in ('assigned', 'confirmed') and
                                m.location_dest_id in %(location_id)s and
                                m.product_id = %(product_id)s and
                                m.date <= %(date)s
                            group by date(m.date)
                        ) x
                    group by date
                            ''', {'location_id': tuple(loc_ids), 'product_id': line.product_id.id, 'date': oc}
                               )
                    pipe_data = {}
                    for x in cr.fetchall():
                        pipe_data[datetime.strptime('%s 23:59:59' % (x[0].split(' ')[0], ), '%Y-%m-%d %H:%M:%S')] = x[1]

                    pipe_date = sorted(pipe_data.keys())


                    if line.status== 'replacing':
                        compute_begin_date = lacking_by_prod.get(line.replaced_product_id.id) or datetime.strptime('3000-01-01', '%Y-%m-%d')
                    else:
                        compute_begin_date = today

                    pas_full = sum_line[line.id]['pas_no_pipe_no_fmc']
                    qty_lacking = 0
                    for x in pipe_date[:]:
                        if x <= compute_begin_date:
                            pas_full += pipe_data[x]
                            pipe_date.pop(0)
                        else:
                            break

                    for fmc_d in range(1, 13):
                        from_fmc = getattr(line, 'rr_fmc_from_%d'%fmc_d)
                        to_fmc = getattr(line, 'rr_fmc_to_%d'%fmc_d)
                        num_fmc = getattr(line, 'rr_fmc_%d'%fmc_d)
                        if from_fmc and to_fmc and num_fmc is not False:

                            from_fmc = datetime.strptime(from_fmc, '%Y-%m-%d')
                            to_fmc = datetime.strptime(to_fmc, '%Y-%m-%d')

                            if from_fmc <= today <= to_fmc:
                                before_today = True

                            if rdd <= to_fmc:
                                before_rdd = True

                            begin_init = max(compute_begin_date, from_fmc)
                            end_loop = min(rdd, to_fmc)
                            begin = begin_init
                            while begin < end_loop:
                                end = min(begin + relativedelta(months=1, day=1, days=-1), end_loop)
                                if begin < seg_rdd < end:
                                    split_dates = [(begin, seg_rdd), (seg_rdd+relativedelta(days=1), end)]
                                else:
                                    split_dates = [(begin, end)]

                                for begin, end in split_dates:
                                    date_before_rdd = seg_rdd >= end
                                    month = ((end-begin).days + 1)/30.44

                                    new_begin = begin
                                    period_conso = month*num_fmc
                                    if period_conso <= pas_full:
                                        pas_full -= period_conso
                                    else:
                                        # missing stock to cover the full period
                                        for x in pipe_date[:]:
                                            # add pipe before period
                                            if x <= begin:
                                                pas_full += pipe_data[x]
                                                pipe_date.pop(0)
                                            else:
                                                break
                                        if period_conso > pas_full:
                                            # still not enough stock
                                            for x in pipe_date[:]:
                                                if x <= end:
                                                    # compute missing just before the next pipe
                                                    ndays = (x - new_begin).days + 1
                                                    qty = num_fmc/30.44*ndays
                                                    pas_full -= qty
                                                    if pas_full < 0:
                                                        if date_before_rdd:
                                                            qty_lacking += pas_full
                                                        # new available qty is the qty in the pipe
                                                        pas_full = pipe_data[x]
                                                    else:
                                                        pas_full += pipe_data[x]
                                                    new_begin = pipe_date.pop(0)
                                                else:
                                                    break

                                        if end >= new_begin:
                                            # all qty in pipe is added
                                            # compute consumption from last received to the end
                                            qty = (num_fmc/30.44)*((end - new_begin).days+1)
                                            pas_full -= qty
                                            if pas_full < 0:
                                                if date_before_rdd:
                                                    qty_lacking += pas_full
                                                pas_full = 0

                                    total_month += month

                                    if not lacking:
                                        if total_fmc+month*num_fmc < sum_line[line.id]['pas_no_pipe_no_fmc']:
                                            month_of_supply += month
                                        elif num_fmc:
                                            month_of_supply += max(0, (sum_line[line.id]['pas_no_pipe_no_fmc'] - total_fmc) / num_fmc)
                                            lacking = True
                                    total_fmc += month*num_fmc

                                    if review_id:
                                        fmc_by_month[end.strftime('%Y-%m-%d')] = {'value': num_fmc, 'pas': pas_full}

                                begin += relativedelta(months=1, day=1)


                            if not review_id:
                                if oc <= to_fmc:
                                    before_oc = True
                                begin_oc = max(rdd, from_fmc, compute_begin_date)
                                end_oc = min(oc, to_fmc)
                                if end_oc >= begin_oc:
                                    month = ((end_oc-begin_oc).days +1)/30.44
                                    total_month_oc += month

                                    # used to compute SODate on replaced prod (period: RDD + OC)
                                    if not lacking and not lacking_oc:
                                        if total_fmc+total_fmc_oc+month*num_fmc < sum_line[line.id]['pas_no_pipe_no_fmc']:
                                            month_of_supply_oc += month
                                        elif num_fmc:
                                            month_of_supply_oc += max(0, (sum_line[line.id]['pas_no_pipe_no_fmc'] - total_fmc_oc - total_fmc) / num_fmc)
                                            lacking_oc = True

                                    total_fmc_oc += month*num_fmc
                    if not review_id:
                        month_of_supply_oc += month_of_supply
                        if lacking or lacking_oc:
                            lacking_by_prod[line.product_id.id] = today + relativedelta(days=month_of_supply_oc*30.44)
                        valid_rr_fmc = before_today and before_rdd and before_oc
                    else:
                        valid_rr_fmc = before_today and before_rdd

                    valid_line = valid_rr_fmc

                    if review_id and loc_ids and seg.rule == 'cycle':
                        total_expired_qty = sum_line[line.id].get('expired_rdd_oc', 0) + sum_line[line.id].get('expired_before_rdd', 0)
                        for nb_month in range(1, line.segment_id.projected_view+1):
                            end_date = today + relativedelta(months=nb_month, day=1, days=-1)
                            total_expired_qty -= exp_by_month.get(line.product_id.id, {}).get(end_date.strftime('%Y-%m-%d'), 0)
                            rr_fmc_month = fmc_by_month.get(end_date.strftime('%Y-%m-%d'), {}).get('value', False)
                            detailed_pas.append((0, 0, {
                                'date': end_date.strftime('%Y-%m-%d'),
                                'rr_fmc': rr_fmc_month,
                                'projected': rr_fmc_month and max(0, fmc_by_month.get(end_date.strftime('%Y-%m-%d'), {}).get('pas',0)) + total_expired_qty,
                            }))



                #pas = max(0, sum_line.get(line.id, {}).get('pas_no_pipe_no_fmc', 0) + line.pipeline_before_rdd - total_fmc)
                pas = pas_full
                ss_stock = 0
                warnings = []
                warnings_html = []
                qty_lacking_needed_by = False
                proposed_order_qty = 0
                if seg.rule == 'cycle':
                    if line.status == 'new':
                        if total_month_oc:
                            ss_stock = seg.safety_stock * total_fmc_oc / total_month_oc
                    else:
                        # sum fmc from today to ETC - qty in stock
                        #qty_lacking =  max(0, total_fmc - sum_line.get(line.id, {}).get('pas_no_pipe_no_fmc', 0))
                        if total_month_oc+total_month:
                            if line.status == 'replacing':
                                ss_stock = seg.safety_stock * ((total_fmc_oc+total_fmc)/(line.segment_id.order_coverage+int(line.segment_id.total_lt)/30.44))
                            else:
                                ss_stock = seg.safety_stock * ((total_fmc_oc+total_fmc)/(total_month_oc+total_month))

                        if line.status != 'phasingout':
                            if total_month and pas and pas <= line.buffer_qty + seg.safety_stock * (total_fmc / total_month):
                                wmsg = _('Projected use of safety stock/buffer')
                                warnings.append(wmsg)
                                warnings_html.append('<span title="%s">%s</span>' % (misc.escape_html(wmsg), misc.escape_html(_('SS used'))))
                            if qty_lacking:
                                wmsg = _('Stock-out before next RDD')
                                warnings.append(wmsg)
                                warnings_html.append('<span title="%s">%s</span>'  % (misc.escape_html(wmsg), misc.escape_html(_('Stock out'))))

                        if line.status == 'activereplacing':
                            replaced_lack = lacking_by_prod.get(line.replaced_product_id.id)
                            if replaced_lack:
                                wmsg = _('SODate of linked products is %s') % (self.pool.get('date.tools').get_date_formatted(cr, uid, datetime=replaced_lack.strftime('%Y-%m-%d'), context=context))
                                warnings.append(wmsg)
                                warnings_html.append('<span title="%s">%s</span>'  % (misc.escape_html(wmsg), misc.escape_html(_('Replaced SO'))))

                        if lacking:
                            qty_lacking_needed_by = today + relativedelta(days=month_of_supply*30.44)
                    if line.status != 'phasingout' and review_id and round(sum_line.get(line.id, {}).get('expired_before_rdd',0)):
                        wmsg = _('Forecasted expiries')
                        warnings.append(wmsg)
                        warnings_html.append('<span title="%s">%s</span>' % (misc.escape_html(wmsg), misc.escape_html(_('Expiries'))))

                    if line.status == 'replaced':
                        proposed_order_qty = 0
                        qty_lacking = 0
                    elif line.status == 'phasingout':
                        proposed_order_qty = 0
                        qty_lacking = False
                    else:
                        proposed_order_qty = max(0, total_fmc_oc + ss_stock + line.buffer_qty + sum_line.get(line.id, {}).get('expired_rdd_oc',0) - pas - line.pipeline_between_rdd_oc)

                elif seg.rule == 'minmax':
                    valid_line = bool(line.min_qty) and bool(line.max_qty)
                    if line.status in ('phasingout', 'replaced'):
                        proposed_order_qty = 0
                        qty_lacking = False
                    else:
                        proposed_order_qty = max(0, line.max_qty - sum_line.get(line.id, {}).get('real_stock') + sum_line.get(line.id, {}).get('reserved_stock_qty') + sum_line.get(line.id, {}).get('expired_qty_before_eta', 0) - line.pipeline_before_rdd)

                        qty_lacking = line.min_qty - sum_line.get(line.id, {}).get('real_stock') + sum_line.get(line.id, {}).get('reserved_stock_qty') - sum_line.get(line.id, {}).get('expired_qty_before_eta')
                        if line.status != 'new' and sum_line.get(line.id, {}).get('real_stock') - sum_line.get(line.id, {}).get('expired_qty_before_eta') <= line.min_qty:
                            if sum_line.get(line.id, {}).get('expired_qty_before_eta'):
                                wmsg = _('Alert: "inventory – batches expiring before ETA <= Min"')
                                warnings.append(wmsg)
                                warnings_html.append('<span title="%s">%s</span>' % (misc.escape_html(wmsg), misc.escape_html(_('Expiries'))))
                            else:
                                wmsg = _('Alert: "inventory <= Min"')
                                warnings.append(wmsg)
                                warnings_html.append('<span title="%s">%s</span>' % (misc.escape_html(wmsg), misc.escape_html(_('Insufficient'))))
                else:
                    valid_line = bool(line.auto_qty)
                    if line.status in ('phasingout', 'replaced'):
                        proposed_order_qty = 0
                    else:
                        proposed_order_qty = line.auto_qty

                if not valid_rr_fmc:
                    wmsg = _('Invalid FMC')
                    warnings.append(wmsg)
                    warnings_html.append('<span title="%s">%s</span>' % (misc.escape_html(wmsg), misc.escape_html(_('FMC'))))

                if line.status != 'phasingout':
                    if review_id and month_of_supply and month_of_supply*30.44 > (seg_rdd-today).days + line.segment_id.safety_stock*30.44:
                        wmsg = _('Excess Stock')
                        warnings.append(wmsg)
                        warnings_html.append('<span title="%s">%s</span>' % (misc.escape_html(wmsg), misc.escape_html(_('Excess'))))

                    if review_id and seg.hidden:
                        wmsg = _('Product is not in any related segment, only in stock / pipeline of location')
                        warnings.append(wmsg)
                        warnings_html.append('<span title="%s">%s</span>' % (misc.escape_html(wmsg), misc.escape_html(_('No Segment'))))

                    if prod_eta.get(line.product_id.id) and prod_eta.get(line.product_id.id) < time.strftime('%Y-%m-%d'):
                        wmsg = _('Pipeline in the past')
                        warnings.append(wmsg)
                        warnings_html.append('<span title="%s">%s</span>' % (misc.escape_html(wmsg), misc.escape_html(_('Delay'))))

                #lacking_by_prod[line.product_id.id] = qty_lacking_needed_by
                line_data = {
                    'product_id': line.product_id.id,
                    'uom_id': line.uom_id.id,
                    'real_stock': round(sum_line.get(line.id, {}).get('real_stock',0)),
                    'pipeline_qty': round(line.pipeline_before_rdd or 0),
                    'eta_for_next_pipeline': prod_eta.get(line.product_id.id, False),
                    'reserved_stock_qty': sum_line.get(line.id, {}).get('reserved_stock_qty'),
                    'qty_lacking': False if seg.rule not in ('cycle', 'minmax') else round(qty_lacking),
                    'qty_lacking_needed_by': qty_lacking_needed_by and qty_lacking_needed_by.strftime('%Y-%m-%d') or False,
                    'expired_qty_before_cons': False if seg.rule !='cycle' else round(sum_line.get(line.id, {}).get('expired_before_rdd',0)),
                    'expired_qty_before_eta': round(sum_line.get(line.id, {}).get('expired_qty_before_eta',0)),
                    'warning': False,
                    'warning_html': False,
                    'valid_rr_fmc': valid_line,
                    'status': line.status,
                    'open_loan': sum_line.get(line.id, {}).get('open_loan', False),
                    'open_donation': sum_line.get(line.id, {}).get('open_donation', False),
                    'auto_qty': line.auto_qty if seg.rule =='auto' else False,
                    'buffer_qty': line.buffer_qty if seg.rule =='cycle' else False,
                    'min_max': '',
                }
                if seg.rule == 'minmax':
                    line_data['min_max'] = '%d / %d' % (line.min_qty, line.max_qty)

                # order_cacl
                if not review_id:
                    if warnings_html:
                        line_data['warning_html'] = '<img src="/openerp/static/images/stock/gtk-dialog-warning.png" title="%s" class="warning"/> <div>%s</div> ' % (misc.escape_html("\n".join(warnings)), "<br>".join(warnings_html))
                        line_data['warning'] = "\n".join(warnings)
                    line_data.update({
                        'order_calc_id': calc_id,
                        'proposed_order_qty': round(proposed_order_qty),
                        'agreed_order_qty': round(proposed_order_qty) or False,
                        'in_main_list': line.in_main_list,
                        'projected_stock_qty': round(pas),
                        'cost_price': line.product_id.standard_price,
                    })

                    order_calc_line.create(cr, uid, line_data, context=context)

                else: # review
                    if seg.hidden:
                        line_data['valid_rr_fmc'] = False
                    line_data['paired_product_id'] = line.replacing_product_id and line.replacing_product_id.id or line.replaced_product_id and line.replaced_product_id.id
                    std_dev_hmc = False
                    amc = False
                    if total_fmc_hmc.get(line.product_id.id):
                        amc = total_fmc_hmc[line.product_id.id] / float(seg.rr_amc)
                        std_dev_hmc_tmp = sum_hmc2.get(line.product_id.id, 0) / float(seg.rr_amc) - (amc*amc)
                        if std_dev_hmc_tmp > 0:
                            std_dev_hmc = math.sqrt(std_dev_hmc_tmp)

                    #avg_error_hmc_fmc = False
                    std_dev_hmc_fmc = False
                    coef_var_hmc_fmc = False
                    if seg.rule == 'cycle':
                        diff_hmc_fmc = 0
                        diff_hmc_fmc2 = 0
                        sum_fmc = 0
                        nb_month = 0
                        for month in hmc_month.get(line.product_id.id, {}):
                            nb_month += 1
                            hmc = hmc_month[line.product_id.id][month]
                            fmc = past_fmc.get(line.product_id.id, {}).get(month, hmc)

                            sum_fmc += fmc
                            diff_hmc_fmc_tmp = hmc - fmc
                            diff_hmc_fmc += diff_hmc_fmc_tmp
                            diff_hmc_fmc2 += diff_hmc_fmc_tmp*diff_hmc_fmc_tmp

                        if nb_month and sum_fmc:
                            std_dev_hmc_fmc = math.sqrt(diff_hmc_fmc2/nb_month)
                            coef_var_hmc_fmc = 100 * nb_month/float(sum_fmc) * std_dev_hmc_fmc
                            #avg_error_hmc_fmc = 100 * diff_hmc_fmc / float(sum_fmc)

                    line_data.update({
                        'review_id': review_id,
                        'segment_ref_name': not seg.hidden and "%s / %s" % (seg.name_seg, seg.description_seg),
                        'rr_fmc_avg': False if seg.rule !='cycle' else total_month and total_fmc/total_month,
                        'rr_amc': line.rr_amc,
                        'total_expired_qty': sum_line.get(line.id, {}).get('total_expiry_nocons_qty', 0),
                        'unit_of_supply_amc': False if seg.rule !='cycle' and not seg.hidden else line.rr_amc and (round(sum_line.get(line.id, {}).get('real_stock',0)) - round(sum_line.get(line.id, {}).get('expired_before_rdd',0))) * coeff / line.rr_amc,
                        'unit_of_supply_fmc': False if seg.rule !='cycle' else month_of_supply * coeff,
                        'date_preparing': seg.date_preparing,
                        'date_next_order_validated': seg.date_next_order_validated,
                        'date_next_order_rdd': seg.date_next_order_received_modified or seg.date_next_order_received,
                        'internal_lt': seg.internal_lt,
                        'external_lt': seg.external_lt,
                        'total_lt': seg.total_lt,
                        'order_coverage': seg.order_coverage * coeff,
                        'primay_product_list': line.in_main_list and seg.product_list_id.name,
                        'rule': seg.rule,
                        'min_qty': line.min_qty,
                        'max_qty': line.max_qty,
                        'safety_stock': seg.safety_stock * coeff,
                        'pas_ids': detailed_pas,
                        'segment_line_id': line.id,
                        'sleeping_qty': round(sum_line.get(line.id, {}).get('sleeping_qty',0)),
                        'std_dev_hmc': std_dev_hmc,
                        'coef_var_hmc': amc and 100 * std_dev_hmc/amc or False,
                        #'avg_error_hmc_fmc': avg_error_hmc_fmc,
                        'std_dev_hmc_fmc': std_dev_hmc_fmc,
                        'coef_var_hmc_fmc': coef_var_hmc_fmc,
                    })
                    if review_id and line_data['coef_var_hmc_fmc'] and line_data['coef_var_hmc_fmc'] > line.segment_id.location_config_id.alert_threshold_deviation:
                        wmsg = _('Variation of HMC/FMC')
                        warnings.append(wmsg)
                        warnings_html.append('<span title="%s">%s</span>' % (misc.escape_html(wmsg), misc.escape_html(_('HMC/FMC Dev.'))))

                    if warnings_html:
                        line_data['warning_html'] = '<img src="/openerp/static/images/stock/gtk-dialog-warning.png" title="%s" class="warning"/> <div>%s</div> ' % (misc.escape_html("\n".join(warnings)), "<br>".join(warnings_html))
                        line_data['warning'] = "\n".join(warnings)

                    if seg.rule == 'cycle' or seg.hidden:
                        line_data.update({
                            'projected_stock_qty': False if seg.hidden else round(pas),
                            'projected_stock_qty_amc': max(0, sum_line.get(line.id, {}).get('pas_no_pipe_no_fmc', 0) + line.pipeline_before_rdd - line.rr_amc*seg.projected_view),
                        })
                    else:
                        line_data.update({
                            'projected_stock_qty': False,
                            'projected_stock_qty_amc': False,
                        })
                    review_line.create(cr, uid, line_data, context=context)

            if review_id:

                if seg.rule == 'cycle':
                    cr.execute('''insert into replenishment_inventory_review_line_stock (review_line_id, qty, instance_id)
                        select review_line.id, amc.real_stock, amc.instance_id from
                            replenishment_inventory_review_line review_line
                            left join replenishment_segment_line_amc amc on amc.segment_line_id = review_line.segment_line_id
                            left join replenishment_segment_line seg_line on seg_line.id = review_line.segment_line_id
                        where
                            seg_line.segment_id = %s and
                            review_line.review_id = %s
                    ''', (seg.id, review_id))
                    cr.execute('''insert into replenishment_inventory_review_line_exp (review_line_id, date, instance_id, exp_qty, expiry_line_id)
                        select review_line.id, exp.month, amc.instance_id, exp.quantity, exp.expiry_line_id from
                            replenishment_inventory_review_line review_line
                            left join replenishment_segment_line_amc amc on amc.segment_line_id = review_line.segment_line_id
                            left join replenishment_segment_line_amc_month_exp exp on exp.line_amc_id = amc.id
                            left join replenishment_segment_line seg_line on seg_line.id = review_line.segment_line_id
                        where
                            seg_line.segment_id = %s and
                            review_line.review_id = %s
                    ''', (seg.id, review_id))

                elif loc_ids:
                    # get details expiry before eta
                    cr.execute(''' insert into replenishment_inventory_review_line_exp_nocons (instance_id, review_line_id, batch_number, life_date, exp_qty)
                        select %s, line.id, lot.name, lot.life_date, sum(qty) from
                        stock_report_prodlots report, stock_production_lot lot, replenishment_inventory_review_line line
                        where
                            line.product_id = report.product_id and
                            lot.id = report.prodlot_id and
                            report.location_id in %s and
                            lot.life_date < %s and
                            line.review_id = %s
                        group by line.id, lot.name, lot.life_date
                        order by lot.life_date
                    ''', (seg.main_instance.id, tuple(loc_ids), rdd, review_id))

                    cr.execute('''insert into replenishment_inventory_review_line_exp_nocons (instance_id, review_line_id, stock_qty, exp_qty)
                        select amc.instance_id, review_line.id, amc.real_stock, expired_qty_before_eta from
                            replenishment_inventory_review_line review_line
                            left join replenishment_segment_line_amc amc on amc.segment_line_id = review_line.segment_line_id
                            left join replenishment_segment_line seg_line on seg_line.id = review_line.segment_line_id
                        where
                            seg_line.segment_id = %s and
                            review_line.review_id = %s
                        order by amc.instance_id
                    ''', (seg.id, review_id))



                self.write(cr, uid, seg.id, {'last_review_date': review_date}, context=context)

            if calc_id:
                res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'procurement_cycle.replenishment_order_calc_action', ['form', 'tree'], context=context)
                res['res_id'] = calc_id
                return res

        return True

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to open multiple lines
        '''
        context = context is None and {} or context
        ids = isinstance(ids, (int, long)) and [ids] or ids
        return self.pool.get('wizard.common.import.line').\
            open_wizard(cr, uid, ids[0], 'replenishment.segment', 'replenishment.segment.line', context=context)

    def delete_multiple_lines(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if not context.get('button_selected_ids'):
            raise osv.except_osv(_('Warning!'), _('Please select at least one line'))

        self.pool.get('replenishment.segment.line').unlink(cr, uid, context['button_selected_ids'], context=context)
        return True

    def import_lines(self, cr, uid, ids, context=None):
        ''' import replenishment.segment '''

        product_obj = self.pool.get('product.product')
        seg_line_obj = self.pool.get('replenishment.segment.line')
        wizard_obj = self.pool.get('physical.inventory.import.wizard')

        seg = self.browse(cr, uid, ids[0],  context=context)
        if not seg.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))

        try:
            file_data = SpreadsheetXML(xmlstring=base64.decodestring(seg.file_to_import))

            existing_line = {}
            for line in seg.line_ids:
                existing_line[line.product_id.default_code] = line.id

            idx = -1

            status = dict([(x[1], x[0]) for x in life_cycle_status])
            error = []
            code_created = {}
            created = 0
            updated = 0
            ignored = 0
            for row in file_data.getRows():
                idx += 1
                if idx < 8:
                    # header
                    continue

                if not len(row.cells):
                    # empty line
                    continue

                line_error = []
                prod_code = row.cells[0].data
                if not prod_code:
                    continue
                prod_code = prod_code.strip()

                cells_nb = len(row.cells)

                data_towrite = {
                    'status': cells_nb > 3 and status.get(row.cells[3].data and row.cells[3].data.strip()),
                    'replacing_product_id': False,
                    'replaced_product_id': False,
                    'buffer_qty': False,
                    'min_qty': 0,
                    'max_qty': 0,
                    'auto_qty': 0
                }
                for fmc in range(1, 13):
                    data_towrite.update({
                        'rr_fmc_%d' % fmc: False,
                        'rr_fmc_from_%d' % fmc: False,
                        'rr_fmc_to_%d' % fmc: False,
                    })


                col_replacing = 4
                col_replaced = 5
                col_buffer_min_qty = 8
                col_first_fmc = 9

                if cells_nb > col_replacing and row.cells[col_replacing].data and row.cells[col_replacing].data.strip():
                    if data_towrite['status'] not in  ('replaced', 'phasingout'):
                        line_error.append(_('Line %d: you can not set a Replacing product on this line, please change the satus or remove the replacing product') % (idx+1, ))
                    else:
                        replacing_id = product_obj.search(cr, uid, [('default_code', '=ilike', row.cells[col_replacing].data.strip())], context=context)
                        if not replacing_id:
                            line_error.append(_('Line %d: replacing product code %s not found') % (idx+1, row.cells[col_replacing].data))
                        else:
                            data_towrite['replacing_product_id'] = replacing_id[0]
                elif data_towrite['status'] == 'replaced' and not data_towrite['replacing_product_id']:
                    line_error.append(_('Line %d: replacing product must be set !') % (idx+1, ))

                if cells_nb > col_replaced and row.cells[col_replaced].data and row.cells[col_replaced].data.strip():
                    if data_towrite['status'] not in  ('replacing', 'activereplacing'):
                        line_error.append(_('Line %d: you can not set a Replaced product on this line, please change the satus or remove the replaced product') % (idx+1, ))
                    else:
                        replaced_id = product_obj.search(cr, uid, [('default_code', '=ilike', row.cells[col_replaced].data.strip())], context=context)
                        if not replaced_id:
                            line_error.append(_('Line %d: replaced product code %s not found') % (idx+1, row.cells[col_replaced].data))
                        else:
                            data_towrite['replaced_product_id'] = replaced_id[0]
                elif data_towrite['status'] in ('replacing', 'activereplacing') and not data_towrite['replaced_product_id']:
                    line_error.append(_('Line %d: replaced product must be set !') % (idx+1, ))


                if cells_nb > col_buffer_min_qty and seg.rule == 'cycle':
                    if row.cells[col_buffer_min_qty].data and not isinstance(row.cells[col_buffer_min_qty].data, (int, long, float)):
                        line_error.append(_('Line %d: Buffer Qty must be a number, found %s') % (idx+1, row.cells[col_buffer_min_qty].data))
                    else:
                        data_towrite['buffer_qty'] = row.cells[col_buffer_min_qty].data
                    for fmc in range(1, 13):
                        if cells_nb - 1 >=  col_first_fmc and row.cells[col_first_fmc].data:
                            from_data = False
                            fmc_data = row.cells[col_first_fmc].data
                            if fmc == 1:
                                if cells_nb - 1 < col_first_fmc+1:
                                    line_error.append(_('Line %d: FMC FROM %d, date expected') % (idx+1, fmc))
                                    continue
                                if not row.cells[col_first_fmc+1].type == 'datetime':
                                    line_error.append(_('Line %d: FMC FROM %d, date is not valid, found %s') % (idx+1, fmc, row.cells[col_first_fmc+1].data))
                                    continue
                                from_data = row.cells[col_first_fmc+1].data.strftime('%Y-%m-%d')
                                col_first_fmc += 1

                            if cells_nb - 1 < col_first_fmc+1:
                                line_error.append(_('Line %d: FMC TO %d, date expected') % (idx+1, fmc))
                                continue
                            if not row.cells[col_first_fmc+1].data or row.cells[col_first_fmc+1].type != 'datetime':
                                line_error.append(_('Line %d: FMC TO %d, date is not valid, found %s') % (idx+1, fmc, row.cells[col_first_fmc+1].data))
                                continue
                            if not isinstance(fmc_data, (int, long, float)):
                                line_error.append(_('Line %d: FMC %d, number expected, found %s') % (idx+1, fmc, fmc_data))
                                continue
                            data_towrite.update({
                                'rr_fmc_%d' % fmc: fmc_data,
                                'rr_fmc_from_%d' % fmc:from_data,
                                'rr_fmc_to_%d' % fmc: row.cells[col_first_fmc+1].data.strftime('%Y-%m-%d'),
                            })
                        col_first_fmc += 2
                elif cells_nb > col_buffer_min_qty and seg.rule == 'minmax':
                    if not row.cells[col_buffer_min_qty] or not isinstance(row.cells[col_buffer_min_qty].data, (int, long, float)):
                        line_error.append(_('Line %d: Min Qty, number expected, found %s') % (idx+1, row.cells[col_buffer_min_qty].data))
                    elif not row.cells[col_buffer_min_qty+1] or not isinstance(row.cells[col_buffer_min_qty+1].data, (int, long, float)):
                        line_error.append(_('Line %d: Max Qty, number expected, found %s') % (idx+1, row.cells[col_buffer_min_qty+1].data))
                    elif row.cells[col_buffer_min_qty+1].data < row.cells[col_buffer_min_qty].data:
                        line_error.append(_('Line %d: Max Qty (%s) must be larger than Min Qty (%s)') % (idx+1, row.cells[col_buffer_min_qty+1].data, row.cells[col_buffer_min_qty].data))
                    else:
                        data_towrite.update({
                            'min_qty': row.cells[col_buffer_min_qty].data,
                            'max_qty': row.cells[col_buffer_min_qty+1].data,
                        })
                elif cells_nb > col_buffer_min_qty:
                    if not row.cells[col_buffer_min_qty] or not isinstance(row.cells[col_buffer_min_qty].data, (int, long, float)):
                        line_error.append(_('Line %d: Auto Supply Qty, number expected, found %s') % (idx+1, row.cells[col_buffer_min_qty].data))
                    else:
                        data_towrite['auto_qty'] = row.cells[col_buffer_min_qty].data

                if prod_code not in existing_line:
                    prod_id = product_obj.search(cr, uid, [('default_code', '=ilike', prod_code)], context=context)
                    if not prod_id:
                        line_error.append(_('Line %d: product code %s not found') % (idx+1, prod_code))
                    else:
                        if prod_id[0] in code_created:
                            line_error.append(_('Line %d: product code %s already defined in the file') % (idx+1, prod_code))

                        code_created[prod_id[0]] = True
                        data_towrite['product_id'] = prod_id[0]
                        data_towrite['segment_id'] = seg.id
                else:
                    line_id = existing_line[prod_code]

                if line_error:
                    error += line_error
                    ignored += 1
                    continue
                if 'product_id' in data_towrite:
                    seg_line_obj.create(cr, uid, data_towrite, context=context)
                    created += 1
                else:
                    seg_line_obj.write(cr, uid, line_id, data_towrite, context=context)
                    updated += 1

        except Exception, e:
            cr.rollback()
            return wizard_obj.message_box_noclose(cr, uid, title=_('Importation errors'), message=_("Unexpected error during import:\n%s") % (misc.get_traceback(e), ))

        self.write(cr, uid, seg.id, {'file_to_import': False}, context=context)
        if error:
            error.insert(0, _('%d line(s) created, %d line(s) updated, %d line(s) in error') % (created, updated, ignored))
            return wizard_obj.message_box_noclose(cr, uid, title=_('Importation errors'), message='\n'.join(error))

        return wizard_obj.message_box_noclose(cr, uid, title=_('Importation Done'), message=_('%d line(s) created, %d line(s) updated') % (created, updated))

    def completed(self, cr, uid, ids, context=None):
        for x in self.read(cr, uid, ids, ['name_seg', 'date_next_order_received_modified', 'date_next_order_received', 'rule'], context=context):
            if not x['date_next_order_received_modified'] and not x['date_next_order_received']:
                raise osv.except_osv(_('Warning'), _('Warning, to complete Segment %s, field "Next order to be received by (modified)" must have date filled') % (x['name_seg'], ))

        if self.pool.get('replenishment.segment.line').search_exist(cr, uid, [('segment_id', 'in', ids), ('status', '=', False)], context=context):
            raise osv.except_osv(_('Warning'), _('Please complete Lifeycle status for products missing this, see red lines'))

        if self.pool.get('replenishment.segment.line').search_exist(cr, uid, [('segment_id', 'in', ids), ('status', '=', 'replaced'), ('replacing_product_id', '=', False)], context=context):
            raise osv.except_osv(_('Warning'), _('Please complete Replacing products with a paired product, see red lines'))

        if self.pool.get('replenishment.segment.line').search_exist(cr, uid, [('segment_id', 'in', ids), ('status', 'in', ['replacing', 'activereplacing']), ('replaced_product_id', '=', False)], context=context):
            raise osv.except_osv(_('Warning'), _('Please complete Replaced products with a paired product, see red lines'))

        cr.execute('''
            select prod.default_code, pair.default_code
                from replenishment_segment_line l1
                left join product_product prod on l1.product_id = prod.id
                left join replenishment_segment_line l2 on l2.product_id = l1.replacing_product_id and l2.segment_id = l1.segment_id
                left join product_product pair on pair.id = l1.replacing_product_id
            where
                l1.segment_id in %s and
                l1.replacing_product_id is not null and
                l2 is null
            ''', (tuple(ids),))
        warn_pair = []
        for x in cr.fetchall():
            if len(warn_pair) > 5:
                warn_pair.append('...')
                break
            warn_pair.append(_('Product %s: the paired product %s is not defined in the Segment, please create a segment line for the paired product') % (x[0], x[1]))

        cr.execute('''
            select prod.default_code, pair.default_code
                from replenishment_segment_line l1
                left join product_product prod on l1.product_id = prod.id
                left join replenishment_segment_line l2 on l2.product_id = l1.replaced_product_id and l2.segment_id = l1.segment_id
                left join product_product pair on pair.id = l1.replaced_product_id
            where
                l1.segment_id in %s and
                l1.replaced_product_id is not null and
                l2 is null
            ''', (tuple(ids),))
        for x in cr.fetchall():
            if len(warn_pair) > 5:
                warn_pair.append('...')
                break
            warn_pair.append(_('Product %s: the paired product %s is not defined in the Segment, please create a segment line for the paired product') % (x[0], x[1]))

        if warn_pair:
            raise osv.except_osv(_('Warning'),"\n".join(warn_pair))

        for seg in self.browse(cr, uid, ids, fields_to_fetch=['location_config_id'], context=context):
            if seg.location_config_id.include_product:
                self.pool.get('replenishment.location.config').generate_hidden_segment(cr, uid, seg.location_config_id.id, context=context)

        self.write(cr, uid, ids, {'state': 'complete'}, context=context)
        return True


    def check_inprogress_order_calc(self, cr, uid, ids, context=None):
        calc_obj = self.pool.get('replenishment.order_calc')
        calc_ids = calc_obj.search(cr, uid, [('segment_id', 'in', ids), ('state', 'not in', ['cancel', 'closed'])], context=context)
        if calc_ids:
            calc_name = calc_obj.read(cr, uid, calc_ids, ['name'], context=context)
            raise osv.except_osv(_('Warning'), _('Please cancel or close the following Order Calc:\n%s') % (', '.join([x['name'] for x in calc_name])))

    def set_as_archived(self, cr, uid, ids, context=None):
        self.check_inprogress_order_calc(cr, uid, ids, context=context)
        self.write(cr, uid, ids, {'state': 'archived'}, context=context)
        return True

    def set_as_draft(self, cr, uid, ids, context=None):
        self.check_inprogress_order_calc(cr, uid, ids, context=context)
        # reset last gen
        last_gen_obj = self.pool.get('replenishment.segment.date.generation')
        last_gen_ids = last_gen_obj.search(cr, uid, [('segment_id', 'in', ids)], context=context)
        if last_gen_ids:
            last_gen_obj.write(cr, uid, last_gen_ids, {'full_date': False, 'review_date': False}, context=context)
        self.write(cr, uid, ids, {'state': 'draft', 'last_review_date': False}, context=context)
        return True

    def set_as_cancel(self, cr, uid, ids, context=None):
        self.check_inprogress_order_calc(cr, uid, ids, context=context)
        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
        return True

    def set_as_cancel_and_cancel_order(self, cr, uid, ids, context=None):
        calc_obj = self.pool.get('replenishment.order_calc')
        calc_ids = calc_obj.search(cr, uid, [('segment_id', 'in', ids), ('state', 'not in', ['cancel', 'closed'])], context=context)
        if calc_ids:
            calc_obj.write(cr, uid, calc_ids, {'state': 'cancel'}, context=context)
        self.set_as_cancel(cr, uid, ids, context=context)
        return True

    def change_location_config_id(self, cr, uid, ids, loc_config_id, ir_loc_id, context=None):
        if not loc_config_id:
            return {}

        loc_config = self.pool.get('replenishment.location.config').browse(cr, uid, loc_config_id)
        data = {
            'local_location_ids': [x.id for x in loc_config.local_location_ids],
            'remote_location_ids': [x.id for x in loc_config.remote_location_ids],
            'description': loc_config.description,
            'rr_amc': loc_config.rr_amc,
        }
        if ir_loc_id not in data['local_location_ids']:
            if len(data['local_location_ids']) == 1:
                data['ir_requesting_location'] = data['local_location_ids'][0]
                data['ir_requesting_location_rdo'] = data['local_location_ids'][0]
            else:
                data['ir_requesting_location'] = False

        return {'value': data}


    def save_past_fmc(self, cr, uid, ids, context=None):
        first_day_of_month = (datetime.now() + relativedelta(day=1)).strftime('%Y-%m-%d')
        past_fmc_obj = self.pool.get('replenishment.segment.line.amc.past_fmc')
        for _id in ids:
            cr.execute('''
                select * from replenishment_segment_line line where segment_id = %s and rr_fmc_from_1 < %s
            ''', (_id, first_day_of_month))
            for x in cr.dictfetchall():
                to_update = {}
                for fmc_d in range(1, 13):
                    from_fmc = x['rr_fmc_from_%d'%fmc_d]
                    to_fmc = x['rr_fmc_to_%d'%fmc_d]
                    num_fmc = x['rr_fmc_%d'%fmc_d]

                    if from_fmc >= first_day_of_month or not from_fmc or not to_fmc or num_fmc is False:
                        break

                    upper = min(to_fmc, first_day_of_month)
                    key = datetime.strptime(from_fmc, '%Y-%m-%d')

                    while key.strftime('%Y-%m-%d') < upper:
                        to_update[key.strftime('%Y-%m-%d')] = num_fmc
                        key+=relativedelta(months=1)

                if to_update:
                    cr.execute('delete from replenishment_segment_line_amc_past_fmc where segment_line_id=%s and month in %s', (x['id'], tuple(to_update.keys())))
                    for month in to_update:
                        past_fmc_obj.create(cr, uid, {'segment_line_id': x['id'], 'month': month, 'fmc': to_update[month]}, context=context)

        return True

replenishment_segment()

class replenishment_segment_line(osv.osv):
    _name = 'replenishment.segment.line'
    _description = 'Product'
    _rec_name = 'product_id'
    _order = 'product_id, segment_id'

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


    def _get_status_tooltip(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        if not ids:
            return {}
        for x in ids:
            ret[x] = ''
        cr.execute('''select seg_line.id, prod.default_code
            from replenishment_segment_line seg_line, product_product prod
            where
                seg_line.id in %s and
                (seg_line.replacing_product_id = prod.id or seg_line.replaced_product_id = prod.id) ''', (tuple(ids), )
                   )
        for x in cr.fetchall():
            ret[x[0]] = x[1]
        return ret

    def _where_calc(self, cr, uid, domain, active_test=True, context=None):
        new_dom = []
        in_main = None
        for x in domain:
            if x[0] == 'in_main_list':
                in_main = bool(x[2])
            else:
                new_dom.append(x)

        ret = super(replenishment_segment_line, self)._where_calc(cr, uid, new_dom, active_test=active_test, context=context)

        if in_main is not None:
            ret.tables.append('"replenishment_segment"')
            ret.joins['"replenishment_segment_line"'] = [('"replenishment_segment"', 'segment_id', 'id', 'LEFT JOIN')]

            ret.tables.append('"product_list_line"')
            ret.joins['"replenishment_segment"'] = [('"product_list_line"', 'product_list_id', 'list_id\" AND "product_list_line"."name" = "replenishment_segment_line"."product_id', 'LEFT JOIN')]
            cond = in_main and "NOT" or ""
            ret.where_clause.append(' "product_list_line"."id" IS '+ cond +' NULL ')
        return ret

    def _get_real_stock(self, cr, uid, ids, field_name, arg, context=None):
        prod_obj = self.pool.get('product.product')
        ret = {}
        segment = {}
        for x in self.browse(cr, uid, ids, fields_to_fetch=['product_id', 'segment_id'], context=context):
            ret[x.id] = {
                'real_stock': 0,
                'rr_amc': 0,
            }
            if x.segment_id.id not in segment:
                to_date = datetime.now() + relativedelta(day=1, days=-1)
                segment[x.segment_id.id] = {
                    'context': {
                        'to_date': to_date.strftime('%Y-%m-%d'),
                        'from_date': (to_date -  relativedelta(months=x.segment_id.location_config_id.rr_amc, days=-1)).strftime('%Y-%m-%d'),
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
                cr.execute("""
                    select segment_line_id, sum(amc), sum(real_stock)
                    from replenishment_segment_line_amc
                    where
                        segment_line_id in %s
                    group by segment_line_id
                """, (tuple(segment[seg_id]['prod_seg_line'].values()), ))
                for x in cr.fetchall():
                    ret[x[0]]['rr_amc'] = x[1]
                    ret[x[0]]['real_stock'] = x[2]
            else:
                # AMC is fully local
                amc = prod_obj.compute_amc(cr, uid, segment[seg_id]['prod_seg_line'].keys(), segment[seg_id]['context'])
                for prod_id in amc:
                    ret[segment[seg_id]['prod_seg_line'][prod_id]]['rr_amc'] = amc[prod_id]

                for prod in prod_obj.browse(cr, uid, segment[seg_id]['prod_seg_line'].keys(), fields_to_fetch=['qty_available'], context={'location': segment[seg_id]['context']['amc_location_ids']}):
                    ret[segment[seg_id]['prod_seg_line'][prod.id]]['real_stock'] = prod.qty_available

        return ret

    def _get_pipeline_before(self, cr, uid, ids, field_name, arg, context=None):
        if context is None:
            context = {}

        segment = {}
        ret = {}
        inv_review = context.get('inv_review')
        now = datetime.now()

        for x in self.browse(cr, uid, ids, fields_to_fetch=['product_id', 'segment_id'], context=context):

            ret[x.id] = {
                'pipeline_before_rdd': 0,
                'pipeline_between_rdd_oc': 0
            }
            if x.segment_id.id not in segment:
                if inv_review:
                    rdd = now + relativedelta(months=int(x.segment_id.projected_view), day=1, days=-1)
                else:
                    rdd = datetime.strptime(x.segment_id.date_next_order_received_modified or x.segment_id.date_next_order_received, '%Y-%m-%d')
                segment[x.segment_id.id] = {
                    'to_date_rdd': rdd.strftime('%Y-%m-%d'),
                    'to_date_oc': (rdd  + relativedelta(months=x.segment_id.order_coverage)).strftime('%Y-%m-%d'),
                    'prod_seg_line': {},
                    'location_ids': [l.id for l in x.segment_id.location_config_id.local_location_ids],
                }
            segment[x.segment_id.id]['prod_seg_line'][x.product_id.id] = x.id

        prod_obj = self.pool.get('product.product')
        for seg_id in segment:
            # compute_child ?
            if 'pipeline_before_rdd' in field_name:
                for prod_id in prod_obj.browse(cr, uid, segment[seg_id]['prod_seg_line'].keys(), fields_to_fetch=['incoming_qty'], context={'to_date': segment[seg_id]['to_date_rdd'], 'location': segment[seg_id]['location_ids']}):
                    ret[segment[seg_id]['prod_seg_line'][prod_id.id]]['pipeline_before_rdd'] =  prod_id.incoming_qty

                for prod_id, qty in prod_obj.get_pipeline_from_po(cr, uid, segment[seg_id]['prod_seg_line'].keys(), to_date=segment[seg_id]['to_date_rdd'], location_ids=segment[seg_id]['location_ids']).iteritems():
                    ret[segment[seg_id]['prod_seg_line'][prod_id]]['pipeline_before_rdd'] += qty

            if not inv_review and 'pipeline_between_rdd_oc' in field_name:
                for prod_id in prod_obj.browse(cr, uid, segment[seg_id]['prod_seg_line'].keys(), fields_to_fetch=['incoming_qty'], context={'from_strict_date': segment[seg_id]['to_date_rdd'], 'to_date': segment[seg_id]['to_date_oc'], 'location': segment[seg_id]['location_ids']}):
                    ret[segment[seg_id]['prod_seg_line'][prod_id.id]]['pipeline_between_rdd_oc'] = prod_id.incoming_qty
                    for prod_id, qty in prod_obj.get_pipeline_from_po(cr, uid, segment[seg_id]['prod_seg_line'].keys(), from_date=segment[seg_id]['to_date_rdd'], to_date=segment[seg_id]['to_date_oc'], location_ids=segment[seg_id]['location_ids']).iteritems():
                        ret[segment[seg_id]['prod_seg_line'][prod_id]]['pipeline_between_rdd_oc'] += qty

        return ret

    def _get_list_fmc(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        for id in ids:
            ret[id] = ""
        for line in self.browse(cr, uid, ids, context=context):
            add = []
            for x in range(4, 13):
                rr_fmc = getattr(line, 'rr_fmc_%d'%x)
                rr_from = getattr(line, 'rr_fmc_from_%d'%x)
                rr_to = getattr(line, 'rr_fmc_to_%d'%x)
                if rr_fmc and rr_from and rr_to:
                    rr_from_dt = datetime.strptime(rr_from, '%Y-%m-%d')
                    rr_to_dt = datetime.strptime(rr_to, '%Y-%m-%d')
                    if rr_from_dt.year == rr_to_dt.year:
                        if rr_from_dt.month == rr_to_dt.month:
                            date_txt = '%s' % (misc.month_abbr[rr_from_dt.month])
                        else:
                            date_txt = '%s - %s' % (misc.month_abbr[rr_from_dt.month], misc.month_abbr[rr_to_dt.month])
                    else:
                        date_txt = '%s/%s - %s/%s' % (misc.month_abbr[rr_from_dt.month], rr_from_dt.year, misc.month_abbr[rr_to_dt.month], rr_to_dt.year)
                    add.append("%s: %s" % (date_txt, round(rr_fmc)))
                else:
                    break
            ret[line.id] = ' | '.join(add)
        return ret

    def _get_display_paired_icon(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        for _id in ids:
            ret[_id] = False
        for _id in self.search(cr, uid, [('id', 'in', ids), ('status', 'in', ['replaced', 'replacing', 'phasingout', 'activereplacing'])], context=context):
            ret[_id] = True
        return ret

    def _get_warning(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        for _id in ids:
            ret[_id] = {'warning': False, 'warning_html': ''}


        # has stock for new prod ?
        new_ids = self.search(cr, uid, [('id', 'in', ids), ('status', '=', 'new')], context=context)
        if new_ids:
            for line in self.browse(cr, uid, new_ids, fields_to_fetch=['real_stock'], context=context):
                if line.real_stock:
                    warn = _('Product has stock - check status!')
                    ret[line.id] = {
                        'warning': warn,
                        'warning_html': '<img src="/openerp/static/images/stock/gtk-dialog-warning.png" title="%s" class="warning"/> <div>%s</div> ' % (misc.escape_html(warn), _('New?'))
                    }


        # has pipe for replaced, phasingout statuses ?
        cr.execute('''
          select l_id, l_status from (
            select line.id as l_id, line.status as l_status from
                purchase_order_line pol, replenishment_segment_line line
            where
                pol.product_id = line.product_id and
                line.id in %(ids)s and
                pol.state in ('validated', 'validated_n', 'sourced_sy', 'sourced_v', 'sourced_n') and
                line.status in ('replaced', 'phasingout')
            UNION
            select line.id as l_id, line.status as l_status from
                stock_move m, stock_picking p, replenishment_segment_line line
            where
                m.picking_id = p.id and
                m.product_id = line.product_id and
                line.id in %(ids)s and
                (p.type = 'in' or p.type = 'internal' and p.subtype = 'sysint') and
                m.state in ('confirmed','waiting','assigned') and
                line.status in ('replaced', 'phasingout')
            group by line.id
            ) x group by l_id, l_status
        ''', {'ids': tuple(ids)})

        for line in cr.fetchall():
            warn = _('Product has pipeline - check status!')
            if line[1] == 'replaced':
                error = _('Replaced?')
            else:
                error = _('Phased out?')

            ret[line[0]] = {
                'warning': warn,
                'warning_html': '<img src="/openerp/static/images/stock/gtk-dialog-warning.png" title="%s" class="warning"/> <div>%s</div> ' % (misc.escape_html(warn), error)
            }
        return ret

    _columns = {
        'segment_id': fields.many2one('replenishment.segment', 'Replenishment Segment', select=1, required=1),
        'product_id': fields.many2one('product.product', 'Product Code', select=1, required=1),
        'product_description': fields.related('product_id', 'name',  string='Description', type='char', size=64, readonly=True, select=True, write_relate=False),
        'uom_id': fields.related('product_id', 'uom_id',  string='UoM', type='many2one', relation='product.uom', readonly=True, select=True, write_relate=False),
        'in_main_list': fields.function(_get_main_list, type='boolean', method=True, string='Prim. prod. list'),
        'status_tooltip': fields.function(_get_status_tooltip, type='char', method=True, string='Paired product'),
        'display_paired_icon': fields.function(_get_display_paired_icon, type='boolean', method=True, string='Display paired icon'),
        'status': fields.selection(life_cycle_status, string='RR Lifecycle'),
        'min_qty': fields.float('Min Qty', related_uom='uom_id'),
        'max_qty': fields.float('Max Qty', related_uom='uom_id'),
        'auto_qty': fields.float('Auto. Supply Qty', related_uom='uom_id'),
        'buffer_qty': fields.float_null('Buffer Qty', related_uom='uom_id'),
        'real_stock': fields.function(_get_real_stock, type='float', method=True, related_uom='uom_id', string='Real Stock', multi='get_stock_amc'),
        'pipeline_before_rdd': fields.function(_get_pipeline_before, type='float', method=True, string='Pipeline Before RDD', multi='get_pipeline_before'),
        'pipeline_between_rdd_oc': fields.function(_get_pipeline_before, type='float', method=True, string='Pipeline between RDD and OC', multi='get_pipeline_before'),
        'rr_amc': fields.function(_get_real_stock, type='float', method=True, string='RR-AMC', multi='get_stock_amc'),
        'list_fmc': fields.function(_get_list_fmc, method=1, type='char', string='more FMC'),
        'rr_fmc_1': fields.float_null('RR FMC 1', related_uom='uom_id'),
        'rr_fmc_from_1': fields.date('From 1'),
        'rr_fmc_to_1': fields.date('To 1'),
        'rr_fmc_2': fields.float_null('RR FMC 2', related_uom='uom_id'),
        'rr_fmc_from_2': fields.date('From 2'),
        'rr_fmc_to_2': fields.date('To 2'),
        'rr_fmc_3': fields.float_null('RR FMC 3', related_uom='uom_id'),
        'rr_fmc_from_3': fields.date('From 3'),
        'rr_fmc_to_3': fields.date('To 3'),
        'rr_fmc_4': fields.float_null('RR FMC 4', related_uom='uom_id'),
        'rr_fmc_from_4': fields.date('From 4'),
        'rr_fmc_to_4': fields.date('To 4'),
        'rr_fmc_5': fields.float_null('RR FMC 5', related_uom='uom_id'),
        'rr_fmc_from_5': fields.date('From 5'),
        'rr_fmc_to_5': fields.date('To 5'),
        'rr_fmc_6': fields.float_null('RR FMC 6', related_uom='uom_id'),
        'rr_fmc_from_6': fields.date('From 6'),
        'rr_fmc_to_6': fields.date('To 6'),
        'rr_fmc_7': fields.float_null('RR FMC 7', related_uom='uom_id'),
        'rr_fmc_from_7': fields.date('From 7'),
        'rr_fmc_to_7': fields.date('To 7'),
        'rr_fmc_8': fields.float_null('RR FMC 8', related_uom='uom_id'),
        'rr_fmc_from_8': fields.date('From 8'),
        'rr_fmc_to_8': fields.date('To 8'),
        'rr_fmc_9': fields.float_null('RR FMC 9', related_uom='uom_id'),
        'rr_fmc_from_9': fields.date('From 9'),
        'rr_fmc_to_9': fields.date('To 9'),
        'rr_fmc_10': fields.float_null('RR FMC 10', related_uom='uom_id'),
        'rr_fmc_from_10': fields.date('From 10'),
        'rr_fmc_to_10': fields.date('To 10'),
        'rr_fmc_11': fields.float_null('RR FMC 11', related_uom='uom_id'),
        'rr_fmc_from_11': fields.date('From 11'),
        'rr_fmc_to_11': fields.date('To 11'),
        'rr_fmc_12': fields.float_null('RR FMC 12', related_uom='uom_id'),
        'rr_fmc_from_12': fields.date('From 12'),
        'rr_fmc_to_12': fields.date('To 12'),
        'replacing_product_id': fields.many2one('product.product', 'Replacing product', select=1),
        'replaced_product_id': fields.many2one('product.product', 'Replaced product', select=1),
        'warning': fields.function(_get_warning, method=1, string='Warning', multi='get_warn', type='text'),
        'warning_html': fields.function(_get_warning, method=1, string='Warning', multi='get_warn', type='text'),
    }

    _sql_constraints = [
        ('uniq_segment_id_product_id', 'unique(segment_id, product_id)', 'Product already set in this segment')
    ]


    def _valid_fmc(self, cr, uid, ids, context=None):
        error = []
        line_ids = self.search(cr, uid, [('id', 'in', ids), ('segment_id.rule', '=', 'cycle')], context=context)
        if not line_ids:
            return True
        for line in self.browse(cr, uid, line_ids, context=context):
            prev_to = False
            for x in range(1, 13):
                rr_fmc = getattr(line, 'rr_fmc_%d'%x)
                rr_from = getattr(line, 'rr_fmc_from_%d'%x)
                rr_to = getattr(line, 'rr_fmc_to_%d'%x)
                if rr_from:
                    rr_from = datetime.strptime(rr_from, '%Y-%m-%d')
                    if rr_from.day != 1:
                        error.append(_('%s, FMC FROM %d must start the 1st day of the month') % (line.product_id.default_code, x))
                    if not rr_to:
                        if not rr_fmc:
                            continue
                        error.append(_("%s, FMC TO %d can't be empty if FMC from is set") % (line.product_id.default_code, x))
                    else:
                        rr_to = datetime.strptime(rr_to, '%Y-%m-%d')
                        if rr_to + relativedelta(months=1, day=1, days=-1) != rr_to:
                            error.append(_("%s, FMC TO %d must be the last day of the month") % (line.product_id.default_code, x))
                        if rr_from > rr_to:
                            error.append(_("%s, FMC TO %d must be later than FMC FROM") % (line.product_id.default_code, x))

                        if prev_to:
                            if prev_to + relativedelta(days=1) != rr_from:
                                error.append(_("%s, FMC FROM %d must be a day after FMC TO %d") % (line.product_id.default_code, x, x-1))
                            if prev_to > rr_from:
                                error.append(_("%s, FMC FROM %d must be later than FMC TO %d") % (line.product_id.default_code, x, x-1))
                    prev_to = rr_to
            if error:
                raise osv.except_osv(_('Error'), _('Please correct the following FMC values:\n%s') % ("\n".join(error)))

            return True

    def _uniq_prod_location(self, cr, uid, ids, context=None):
        # delete line in hidden seg
        cr.execute('''
           delete from replenishment_segment_line where id in (
            select line.id from replenishment_segment_line line
                inner join replenishment_segment seg on seg.id = line.segment_id
                where
                    seg.hidden = 't' and
                    (product_id, location_config_id) in
                    (select product_id, location_config_id from replenishment_segment_line l2, replenishment_segment seg2 where l2.id in %s and seg2.id = l2.segment_id and seg2.hidden = 'f')
            )
            ''', (tuple(ids), ))

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
        (_valid_fmc, 'FMC is invalid', []),
        (_uniq_prod_location, 'A product in a location may only belong to one segment.', []),
    ]

    _defaults = {
        'status': 'active',
    }

    def _clean_data(self, cr, uid, vals, context=None):
        if vals and 'status' in vals:
            if vals['status'] not in  ('replacing', 'activereplacing'):
                vals['replaced_product_id'] = False
            if vals['status'] not in  ('replaced', 'phasingout'):
                vals['replacing_product_id'] = False
        for x in range(1, 12):
            if vals.get('rr_fmc_to_%d'%x):
                try:
                    vals['rr_fmc_from_%d'%(x+1)] = (datetime.strptime(vals['rr_fmc_to_%d'%x], '%Y-%m-%d') + relativedelta(days=1)).strftime('%Y-%m-%d')
                except:
                    pass

    def create(self, cr, uid, vals, context=None):
        self._clean_data(cr, uid, vals, context=context)
        return super(replenishment_segment_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        self._clean_data(cr, uid, vals, context=context)
        return super(replenishment_segment_line, self).write(cr, uid, ids, vals, context=context)

    def create_multiple_lines(self, cr, uid, parent_id, product_ids, context=None):
        exist_ids = {}
        exist_code = []
        if product_ids:
            cr.execute('''select
                p.id, p.default_code
                from replenishment_segment_line seg_line, product_product p
                where
                    seg_line.product_id = p.id and
                    seg_line.segment_id = %s and
                    p.id in %s
            ''', (parent_id, tuple(product_ids)))
            for x in cr.fetchall():
                exist_ids[x[0]] = True
                exist_code.append(x[1])

        for prod_id in product_ids:
            if prod_id not in exist_ids:
                self.create(cr, uid, {'segment_id': parent_id, 'product_id': prod_id}, context=context)

        if exist_code:
            return {'msg': "Warning, duplicate products already in Segment have been ignored.\nProducts in duplicate:\n - %s" % '\n - '.join(exist_code)}
        return True

    def change_fmc(selc, cr, uid, ids, ch_type, nb, date_str, update_next, context=None):
        if not date_str:
            return {}

        msg = False
        value = {}
        try:
            fmc_date = datetime.strptime(date_str, '%Y-%m-%d')
        except:
            return {}
        if ch_type == 'from' and fmc_date.day != 1:
            msg =  _('FMC FROM %s must be the first day of the month') % (nb,)
        elif ch_type == 'to':
            if fmc_date + relativedelta(months=1, day=1, days=-1) != fmc_date:
                msg = _('FMC TO %s must be the last day of the month') % (nb, )
            if update_next:
                value = {'rr_fmc_from_%s'%(int(nb)+1): fmc_date and (fmc_date + relativedelta(days=1)).strftime('%Y-%m-%d') or False}

        if msg:
            return {'warning': {'message': msg}, 'value': value}

        return {'value': value}

    def set_paired_product(self, cr, uid, ids, context=None):

        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'procurement_cycle', 'replenishment_segment_line_paired_form')[1]
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'replenishment.segment.line',
            'res_id': ids[0],
            'view_id': [view_id],
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
            'height': '300px',
            'width': '720px',
        }

    def save_paired(self, cr, uid, ids, context=None):
        return {'type': 'ir.actions.act_window_close', 'o2m_refresh': 'line_ids'}

replenishment_segment_line()

class replenishment_segment_date_generation(osv.osv):
    _name = 'replenishment.segment.date.generation'
    _description = 'Last Generation'
    _rec_name = 'date'

    _columns = {
        'segment_id': fields.many2one('replenishment.segment', 'Replenishment Segment', select=1, required=1),
        'instance_id': fields.many2one('msf.instance', string='Instance', select=1, required=1),
        'amc_date': fields.datetime('Date AMC/Stock Data'),
        'full_date': fields.datetime('Date Full Data (exp.)'),
        'review_date': fields.datetime('Date Inv. Review'),
    }

replenishment_segment_date_generation()

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
        'expired_before_rdd': fields.float('Expired Qty before RDD'),
        'expired_qty_before_eta': fields.float('Qty expiring before RDD'),
        'expired_between_rdd_oc': fields.float('Expired Qty between RDD and OC'),
        'open_loan': fields.boolean('Open Loan'),
        'open_donation': fields.boolean('Donations pending'),
        'sleeping_qty': fields.float('Sleeping Qty'),
        'total_expiry_nocons_qty': fields.float('Qty expiring no cons.'),
    }

    _defaults = {
        'open_loan': False,
        'open_donation': False,
    }

    def generate_segment_data(self, cr, uid, context=None, seg_ids=False, force_review=False):

        segment_obj = self.pool.get('replenishment.segment')
        prod_obj = self.pool.get('product.product')
        last_gen_obj = self.pool.get('replenishment.segment.date.generation')
        month_exp_obj = self.pool.get('replenishment.segment.line.amc.month_exp')
        amc_details_obj = self.pool.get('replenishment.segment.line.amc.detailed.amc')

        datetime_now = datetime.now()
        instance_id = self.pool.get('res.company')._get_instance_id(cr, uid)
        to_date = datetime_now + relativedelta(day=1, days=-1)

        if not seg_ids:
            seg_ids = segment_obj.search(cr, uid, [('state', 'in', ['draft', 'complete'])], context=context)
        elif isinstance(seg_ids, (int, long)):
            seg_ids = [seg_ids]

        for segment in segment_obj.browse(cr, uid, seg_ids, context=context):
            last_gen_id = last_gen_obj.search(cr, uid, [('segment_id', '=', segment.id), ('instance_id', '=', instance_id)], context=context)
            last_gen_data = {
                'segment_id': segment.id,
                'instance_id': instance_id,
                'amc_date': datetime_now,
                'full_date': False,
            }

            review_date = False
            if last_gen_id:
                review_date = last_gen_obj.browse(cr, uid, last_gen_id[0], fields_to_fetch=['review_date'], context=context).review_date

            gen_inv_review = False
            full_data = False

            if segment.state == 'complete':
                gen_inv_review = force_review
                full_data = True
                if segment.next_scheduler < datetime_now.strftime('%Y-%m-%d %H:%M:%S') and (not review_date or review_date < datetime_now.strftime('%Y-%m-%d %H:%M:%S')):
                    gen_inv_review = True

            seg_context = {
                'to_date': to_date.strftime('%Y-%m-%d'),
                'from_date': (to_date - relativedelta(months=segment.rr_amc, days=-1)).strftime('%Y-%m-%d'),
                'amc_location_ids': [x.id for x in segment.local_location_ids],
            }
            lines = {}
            for line in segment.line_ids:
                lines[line.product_id.id] = line.id
            if not lines:
                continue
            # update vs create line
            cache_line_amc = {}
            seg_line = {}

            prod_with_stock = []

            line_amc_ids = self.search(cr, uid, [('instance_id', '=', instance_id), ('segment_line_id', 'in', lines.values())], context=context)
            for line_amc in self.browse(cr, uid, line_amc_ids, fields_to_fetch=['segment_line_id'], context=context):
                cache_line_amc[line_amc.segment_line_id.id] = line_amc.id
                seg_line[line_amc.id] = line_amc.segment_line_id
            # real stock - reserved stock
            stock_qties = {}
            qty_fields = ['qty_available']
            if full_data:
                qty_fields += ['qty_reserved']
            for prod_alloc in prod_obj.browse(cr, uid, lines.keys(), fields_to_fetch=qty_fields, context={'location': seg_context['amc_location_ids']}):
                stock_qties[prod_alloc['id']] = {'qty_available': prod_alloc.qty_available}
                if full_data:
                    stock_qties[prod_alloc['id']]['qty_reserved'] = -1 * prod_alloc.qty_reserved
                if gen_inv_review and prod_alloc.qty_available:
                    prod_with_stock.append(prod_alloc['id'])

            if full_data:
                open_loan = {}
                cr.execute('''
                    select product_id from purchase_order_line pol, purchase_order po
                    where
                        po.id = pol.order_id and
                        pol.product_id in %s and
                        pol.state not in ('done', 'cancel_r', 'cancel') and
                        po.partner_type != 'internal' and
                        po.order_type = 'loan'
                    group by product_id
                    ''', (tuple(lines.keys()), )
                )
                for loan in cr.fetchall():
                    open_loan[loan[0]] = True
                cr.execute('''
                    select product_id from sale_order_line sol, sale_order so
                    where
                        so.id = sol.order_id and
                        sol.product_id in %s and
                        sol.state not in ('done', 'cancel_r', 'cancel') and
                        so.partner_type != 'internal' and
                        so.order_type = 'loan'
                    group by product_id
                    ''', (tuple(lines.keys()), )
                )
                for loan in cr.fetchall():
                    open_loan[loan[0]] = True

                open_donation = {}
                if seg_context['amc_location_ids']:
                    cr.execute('''
                        select distinct(m.product_id) from stock_move m, stock_picking p, stock_reason_type rt
                            where
                                m.picking_id = p.id and
                                m.state in ('assigned', 'confirmed') and
                                p.type = 'out' and
                                m.location_id in %s and
                                m.product_id in %s and
                                m.reason_type_id = rt.id and
                                rt.name in ('Donation (standard)', 'Donation before expiry')
                            ''', (tuple(seg_context['amc_location_ids']), tuple(lines.keys())))
                    for don in cr.fetchall():
                        open_donation[don[0]] = True

            # AMC
            amc_by_month = {}
            if not segment.remote_location_ids:
                if gen_inv_review:
                    # trigger sync
                    cr.execute('''
                        update ir_model_data set last_modification=NOW() where model='replenishment.segment.line.amc.detailed.amc' and module='sd' and res_id in (
                            select id from replenishment_segment_line_amc_detailed_amc where segment_line_id in
                            (select seg_line.id from replenishment_segment_line seg_line where seg_line.segment_id = %s)
                        )
                    ''', (segment.id, ))
                    cr.execute('''
                        delete from replenishment_segment_line_amc_detailed_amc where segment_line_id in
                            (select seg_line.id from replenishment_segment_line seg_line where seg_line.segment_id = %s) ''', (segment.id, )
                               )
                    amc, amc_by_month = prod_obj.compute_amc(cr, uid, lines.keys(), context=seg_context, compute_amc_by_month=True)
                else:
                    amc = prod_obj.compute_amc(cr, uid, lines.keys(), context=seg_context)
            else:
                amc = {}
            for prod_id in lines.keys():
                data = {'amc': amc.get(prod_id, 0), 'name': to_date, 'real_stock': stock_qties.get(prod_id, {}).get('qty_available')}
                if segment.state == 'complete' or gen_inv_review:
                    data.update({
                        'expired_before_rdd': 0,
                        'expired_between_rdd_oc': 0,
                        'expired_qty_before_eta': 0,
                        'open_loan': open_loan.get(prod_id, False),
                        'open_donation': open_donation.get(prod_id, False),
                        'reserved_stock': stock_qties.get(prod_id, {}).get('qty_reserved'),

                    })
                    if gen_inv_review:
                        data.update({
                            'total_expiry_nocons_qty': 0,
                            'sleeping_qty': 0,
                        })
                        for month in amc_by_month.get(prod_id, {}):
                            amc_details_obj.create(cr, uid, {'segment_line_id': lines[prod_id], 'month': '%s-01' % (month,) , 'amc': amc_by_month[prod_id][month]}, context=context)

                if lines[prod_id] in cache_line_amc:
                    self.write(cr, uid, cache_line_amc[lines[prod_id]], data, context=context)
                else:
                    data['segment_line_id'] = lines[prod_id]
                    data['instance_id'] = instance_id
                    cache_line_amc[lines[prod_id]] = self.create(cr, uid, data, context=context)

            # expired_before_rdd + expired_before_oc
            if full_data:
                last_gen_data['full_date'] = datetime_now
                expired_obj = self.pool.get('product.likely.expire.report')


                amc_data_to_update = {}
                if gen_inv_review:
                    last_gen_data['review_date'] = datetime_now
                    # trigger sync
                    cr.execute(''' update ir_model_data set last_modification=NOW() where model='replenishment.segment.line.amc.month_exp' and module='sd' and res_id in (
                        select id from  replenishment_segment_line_amc_month_exp where line_amc_id in
                            (select amc.id from replenishment_segment_line_amc amc, replenishment_segment_line seg_line where seg_line.id = amc.segment_line_id and  seg_line.segment_id = %s) 
                    )''', (segment.id, ))
                    cr.execute('''
                        delete from replenishment_segment_line_amc_month_exp where line_amc_id in
                            (select amc.id from replenishment_segment_line_amc amc, replenishment_segment_line seg_line where seg_line.id = amc.segment_line_id and  seg_line.segment_id = %s) ''', (segment.id, )
                               )

                    projected_view = (datetime_now + relativedelta(months=segment.projected_view, day=1, days=-1)).strftime('%Y-%m-%d')

                    # sleeping qty
                    sleeping_context = {
                        'to_date': datetime_now.strftime('%Y-%m-%d'),
                        'from_date': (datetime_now - relativedelta(months=segment.sleeping)).strftime('%Y-%m-%d'),
                        'amc_location_ids': seg_context['amc_location_ids'],
                    }
                    if prod_with_stock:
                        sleeping_amc = prod_obj.compute_amc(cr, uid, prod_with_stock, context=sleeping_context)
                        for prod_id in sleeping_amc:
                            if not sleeping_amc[prod_id]:
                                amc_data_to_update.setdefault(cache_line_amc[lines[prod_id]],{}).update({'sleeping_qty': stock_qties.get(prod_id, {}).get('qty_available')})
                        for prod_expired in prod_obj.browse(cr, uid, prod_with_stock, fields_to_fetch=['qty_available'], context={'location': seg_context['amc_location_ids'], 'stock_expired_before_date': projected_view}):
                            amc_data_to_update.setdefault(cache_line_amc[lines[prod_expired.id]],{}).update({'total_expiry_nocons_qty': prod_expired.qty_available})


                if not segment.hidden:
                    rdd_date = datetime.strptime(segment.date_next_order_received_modified or segment.date_next_order_received, '%Y-%m-%d')
                    oc_date = rdd_date + relativedelta(months=segment.order_coverage)
                    if segment.rule == 'cycle':
                        max_expired_date = oc_date.strftime('%Y-%m-%d')
                        if gen_inv_review:
                            max_expired_date = max(oc_date.strftime('%Y-%m-%d'), projected_view)
                        expired_id = expired_obj.create(cr, uid, {'segment_id': segment.id, 'date_to': max_expired_date})
                        expired_obj._process_lines(cr, uid, expired_id, context=context, create_cr=False)
                        # before rdd
                        cr.execute("""
                            select line.product_id, sum(itemline.expired_qty)
                            from product_likely_expire_report_line line, product_likely_expire_report_item item, product_likely_expire_report_item_line itemline
                            where
                                item.line_id = line.id and
                                report_id=%s and
                                itemline.item_id = item.id and
                                itemline.expired_date <= %s
                            group by line.product_id
                            having sum(itemline.expired_qty) > 0 """, (expired_id, rdd_date.strftime('%Y-%m-%d')))
                        for x in cr.fetchall():
                            amc_data_to_update.setdefault(cache_line_amc[lines[x[0]]], {}).update({'expired_before_rdd': x[1]})

                        # between rdd and oc
                        cr.execute("""
                            select line.product_id, sum(itemline.expired_qty)
                            from product_likely_expire_report_line line, product_likely_expire_report_item item, product_likely_expire_report_item_line itemline
                            where
                                item.line_id = line.id and
                                report_id=%s and
                                itemline.item_id = item.id and
                                itemline.expired_date > %s
                            group by line.product_id
                            having sum(itemline.expired_qty) > 0""", (expired_id, rdd_date.strftime('%Y-%m-%d')))
                        for x in cr.fetchall():
                            amc_data_to_update.setdefault(cache_line_amc[lines[x[0]]], {}).update({'expired_between_rdd_oc': x[1]})
                    else:
                        for prod_expired in prod_obj.browse(cr, uid, prod_with_stock, fields_to_fetch=['qty_available'], context={'location': seg_context['amc_location_ids'], 'stock_expired_before_date': rdd_date.strftime('%Y-%m-%d')}):
                            amc_data_to_update.setdefault(cache_line_amc[lines[prod_expired.id]],{}).update({'expired_qty_before_eta': prod_expired.qty_available})

                    for to_update in amc_data_to_update:
                        self.write(cr, uid, to_update, amc_data_to_update[to_update], context=context)

                    if gen_inv_review:
                        if segment.rule == 'cycle':
                            cr.execute("""
                                select line.product_id, item.period_start, sum(item.expired_qty), line.id
                                from product_likely_expire_report_line line, product_likely_expire_report_item item
                                where
                                    item.line_id = line.id and
                                    report_id=%s and
                                    item.period_start <= %s
                                group by line.product_id, item.period_start, line.id
                                having sum(item.expired_qty) > 0 """, (expired_id, projected_view))
                            for x in cr.fetchall():
                                month_exp_obj.create(cr, uid, {'line_amc_id': cache_line_amc[lines[x[0]]], 'month': x[1], 'quantity': x[2], 'expiry_line_id': x[3]}, context=context)

            if last_gen_id:
                last_gen_obj.write(cr, uid, last_gen_id, last_gen_data, context=context)
            else:
                last_gen_obj.create(cr, uid, last_gen_data, context=context)


        return True

    _sql_constraints = [
        ('uniq_segment_line_id_instance_id', 'unique(segment_line_id, instance_id)', 'Line is duplicated')
    ]

replenishment_segment_line_amc()

class replenishment_segment_line_amc_month_exp(osv.osv):
    _name = 'replenishment.segment.line.amc.month_exp'
    _rec_name = 'line_amc_id'
    _columns = {
        'line_amc_id': fields.many2one('replenishment.segment.line.amc', 'Line AMC', required=1, select=1, ondelete='cascade'),
        'month': fields.date('Month', required=1, select=1),
        'quantity': fields.float('Qty'),
        'expiry_line_id': fields.many2one('product.likely.expire.report.line', 'Expiry Line'),
    }

replenishment_segment_line_amc_month_exp()

class replenishment_segment_line_amc_detailed_amc(osv.osv):
    _name = 'replenishment.segment.line.amc.detailed.amc'
    _rec_name = 'line_amc_id'
    _columns = {
        'segment_line_id': fields.many2one('replenishment.segment.line', 'Seg Line', required=1, select=1, ondelete='cascade'),
        'month': fields.date('Month', required=1, select=1),
        'amc': fields.float('AMC'),
    }
replenishment_segment_line_amc_detailed_amc()

class replenishment_segment_line_amc_past_fmc(osv.osv):
    _name = 'replenishment.segment.line.amc.past_fmc'
    _rec_name = 'line_amc_id'
    _columns = {
        'segment_line_id': fields.many2one('replenishment.segment.line', 'Seg Line', required=1, select=1, ondelete='cascade'),
        'month': fields.date('Month', required=1, select=1),
        'fmc': fields.float('FMC'),
    }
replenishment_segment_line_amc_past_fmc()

class replenishment_order_calc(osv.osv):
    _name = 'replenishment.order_calc'
    _description = 'Order Calculation'
    _order = 'id desc'

    def create(self, cr, uid, vals, context=None):
        if 'name' not in vals:
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'replenishment.order_calc')

        return super(replenishment_order_calc, self).create(cr, uid, vals, context)

    def _get_total_value(self, cr, uid, ids, field_name, arg, context=None):
        cr.execute('''
            select
                calc.id, sum(line.cost_price*line.agreed_order_qty)
            from replenishment_order_calc calc
            left join replenishment_order_calc_line line on line.order_calc_id = calc.id
            where
                calc.id in %s
            group by calc.id''', (tuple(ids), ))
        ret = {}
        for x in cr.fetchall():
            ret[x[0]] = x[1]

        return ret

    _columns = {
        'name': fields.char('Reference', size=64, readonly=1, select=1),
        'segment_id': fields.many2one('replenishment.segment', 'Replenishment Segment', readonly=1),
        'description_seg': fields.char('Description', required=1, size=28, readonly=1),
        'location_config_id': fields.many2one('replenishment.location.config', 'Location Config', required=1, readonly=1),
        'location_config_description': fields.char('Description', size=28, readonly=1),
        'rule': fields.selection([('cycle', 'Order Cycle'), ('minmax', 'Min/Max'), ('auto', 'Automatic Supply')], string='Replenishment Rule (Order quantity)', readonly=1),
        'rule_alert': fields.char('Replenishment Rule (Alert Theshold)', size=64, readonly=1),
        'total_lt': fields.integer('Total Lead Time (days)', readonly=1),
        'generation_date': fields.date('Order Calc generation date', readonly=1),
        'next_generation_date': fields.date('Date next order to be generated by', readonly=1),
        'new_order_reception_date': fields.date('Date new order reception date', readonly=1),
        'ir_generation_date': fields.date('Date of IR generation', readonly=1),
        'comments': fields.text('Comments'),
        'local_location_ids': fields.many2many('stock.location', 'local_location_order_calc_rel', 'order_calc_id', 'location_id', 'Local Locations', readonly=1),
        'remote_location_ids': fields.many2many('stock.location.instance', 'remote_location_order_calc_rel', 'order_calc_id', 'location_id', 'Project Locations', readonly=1),
        'state': fields.selection([('draft', 'Draft'), ('validated', 'Validated'), ('cancel', 'Cancelled'), ('closed', 'Closed')], 'State', readonly=1),
        'order_calc_line_ids': fields.one2many('replenishment.order_calc.line', 'order_calc_id', 'Products',  context={'default_code_only': 1}),
        'instance_id': fields.many2one('msf.instance', 'Instance', readonly=1),
        'file_to_import': fields.binary(string='File to import'),
        'ir_id': fields.many2one('sale.order', 'Generated IR', readonly=1),
        'total_value': fields.function(_get_total_value, method=True, type='float', with_null=True, string='Total Value', digits=(16, 2)),
    }

    _defaults = {
        'generation_date': lambda *a: time.strftime('%Y-%m-%d'),
        'state': 'draft',
    }

    def import_lines(self, cr, uid, ids, context=None):
        ''' import replenishment.order_calc '''

        calc_line_obj = self.pool.get('replenishment.order_calc.line')

        calc = self.browse(cr, uid, ids[0],  context=context)
        if not calc.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))
        file_data = SpreadsheetXML(xmlstring=base64.decodestring(calc.file_to_import))

        existing_line = {}
        for line in calc.order_calc_line_ids:
            existing_line[line.product_id.default_code] = line.id

        if calc.rule == 'cycle':
            qty_col = 16
            comment_col = 19
        elif calc.rule in ('auto', 'minmax'):
            qty_col = 14
            comment_col = 17
        idx = -1

        error = []
        updated = 0
        for row in file_data.getRows():
            idx += 1
            if idx < 8:
                # header
                continue

            if not len(row.cells):
                continue

            prod_code = row.cells[0].data
            if not prod_code:
                continue
            prod_code = prod_code.strip()

            if prod_code not in existing_line:
                error.append(_('Line %d: product %s not found.') % (idx+1, prod_code))
                continue

            if row.cells[qty_col].data and not isinstance(row.cells[qty_col].data, (int, long, float)):
                error.append(_('Line %d: Agreed Order Qty  must be a number, found %s') % (idx+1, row.cells[qty_col].data))

            calc_line_obj.write(cr, uid, existing_line[prod_code], {
                'agreed_order_qty': row.cells[qty_col].data,
                'order_qty_comment': row.cells[comment_col].data or '',
            }, context=context)
            updated += 1

        self.write(cr, uid, calc.id, {'file_to_import': False}, context=context)
        wizard_obj = self.pool.get('physical.inventory.import.wizard')
        if error:
            error.insert(0, _('%d line(s) updated, %d line(s) in error') % (updated, len(error)))
            return wizard_obj.message_box_noclose(cr, uid, title=_('Importation errors'), message='\n'.join(error))

        return wizard_obj.message_box_noclose(cr, uid, title=_('Importation Done'), message=_('%d line(s) updated') % (updated, ))


    def generate_ir(self, cr, uid, ids, context=None):
        sale_obj = self.pool.get('sale.order')
        sale_line_obj = self.pool.get('sale.order.line')
        for calc in self.browse(cr, uid, ids, context=context):
            ir_id = sale_obj.create(cr, uid, {
                'location_requestor_id': calc.segment_id.ir_requesting_location.id,
                'procurement_request': True,
                'delivery_requested_date': calc.new_order_reception_date,
                'categ': 'other',
                'origin': calc.name,
                'stock_take_date': calc.generation_date,
            })
            for line in calc.order_calc_line_ids:
                if line.agreed_order_qty:
                    sale_line_obj.create(cr, uid, {
                        'order_id': ir_id,
                        'procurement_request': True,
                        'product_id': line.product_id.id,
                        'product_uom': line.product_id.uom_id.id,
                        'product_uom_qty': line.agreed_order_qty,
                        'cost_price': line.product_id.standard_price,
                        'price_unit': line.product_id.list_price,
                        'type': 'make_to_order',
                        'stock_take_date': calc.generation_date,
                        'date_planned': calc.new_order_reception_date,
                        'notes': line.order_qty_comment,
                    }, context=context)

            self.write(cr, uid, calc.id, {'state': 'closed', 'ir_generation_date': time.strftime('%Y-%m-%d'), 'ir_id': ir_id}, context=context)
            self.pool.get('replenishment.segment').write(cr, uid, calc.segment_id.id, {'previous_order_rdd': calc.new_order_reception_date, 'date_next_order_received_modified': False}, context=context)
            ir_d = sale_obj.read(cr, uid, ir_id, ['name'], context=context)
            sale_obj.log(cr, uid, ir_id, _('%s created from %s') % (ir_d['name'], calc.name), action_xmlid='procurement_request.action_procurement_request')
        return True

    def validated(self, cr, uid, ids, context=None):
        line_obj = self.pool.get('replenishment.order_calc.line')
        line_ids = line_obj.search(cr, uid, [('order_calc_id', 'in', ids), ('agreed_order_qty', '=', False)], context=context)
        if line_ids:
            line_data = line_obj.browse(cr, uid, line_ids, fields_to_fetch=['product_id'], context=context)
            raise osv.except_osv(_('Warning'), _('Agreed Order Qty can\'t be blank, fix the following:\n%s') % ('\n'.join([x.product_id.default_code for x in line_data])))

        self.write(cr, uid, ids, {'state': 'validated'}, context=context)
        return True

    def cancel(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
        return True

    def set_as_draft(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'draft'}, context=context)
        return True

    def button_dummy(self, cr, uid, ids, context=None):
        return True

replenishment_order_calc()

class replenishment_order_calc_line(osv.osv):
    _name ='replenishment.order_calc.line'
    _description = 'Order Calculation Lines'
    _order = 'product_id, order_calc_id'

    def __init__(self, pool, cr):
        super(replenishment_order_calc_line, self).__init__(pool, cr)
        cr.execute('select cur.name from res_company comp, res_currency cur where cur.id=comp.currency_id limit 1')
        cur = cr.fetchone()
        if cur and cur[0]:
            self._columns['cost_price'].string = _('Cost Price %s') % cur[0]
            self._columns['line_value'].string = _('Line Value %s') % cur[0]
            pool.get('replenishment.order_calc')._columns['total_value'].string = _('Total Value %s') % cur[0]

    def _get_line_value(self, cr, uid, ids, field_name, arg, context=None):
        cr.execute(''' select id, cost_price*agreed_order_qty from replenishment_order_calc_line where id in %s ''', (tuple(ids), ))
        ret = {}
        for x in cr.fetchall():
            ret[x[0]] = x[1]

        return ret

    _columns = {
        'order_calc_id': fields.many2one('replenishment.order_calc', 'Order Calc', required=1, select=1),
        'product_id': fields.many2one('product.product', 'Product Code', select=1, required=1, readonly=1),
        'product_description': fields.related('product_id', 'name',  string='Description', type='char', size=64, readonly=True, select=True, write_relate=False),
        'status': fields.selection(life_cycle_status, string='Life cycle status', readony=1),
        'uom_id': fields.related('product_id', 'uom_id',  string='UoM', type='many2one', relation='product.uom', readonly=True, select=True, write_relate=False),
        'in_main_list': fields.boolean('Prim. prod. list', readonly=1),
        'valid_rr_fmc': fields.boolean('Valid', readonly=1),
        'real_stock': fields.float('Real Stock', readonly=1, related_uom='uom_id'),
        'pipeline_qty': fields.float('Pipeline Qty', readonly=1, related_uom='uom_id'),
        'eta_for_next_pipeline': fields.date('ETA for Next Pipeline', readonly=1),
        'reserved_stock_qty': fields.float('Reserved Stock Qty', readonly=1, related_uom='uom_id'),
        'projected_stock_qty': fields.float('Projected Stock Level', readonly=1, related_uom='uom_id'),
        'qty_lacking': fields.float_null('Qty lacking before next RDD', readonly=1, related_uom='uom_id', null_value='N/A'),
        'qty_lacking_needed_by': fields.date('Qty lacking needed by', readonly=1),
        'open_loan': fields.boolean('Open Loan', readonly=1),
        'open_donation': fields.boolean('Donations pending', readonly=1),
        'expired_qty_before_cons': fields.float('Expired Qty before cons.', readonly=1, related_uom='uom_id'),
        'expired_qty_before_eta': fields.float('Expired Qty before RDD', readonly=1, related_uom='uom_id'),
        'proposed_order_qty': fields.float('Proposed Order Qty', readonly=1, related_uom='uom_id'),
        'agreed_order_qty': fields.float_null('Agreed Order Qty', related_uom='uom_id'),
        'cost_price': fields.float('Cost Price', readonly=1, digits_compute=dp.get_precision('Account Computation')),
        'line_value': fields.function(_get_line_value, method=True, type='float', with_null=True, string='Line Value', digits=(16, 2)),
        'order_qty_comment': fields.char('Order Qty Comment', size=512),
        'warning': fields.text('Warning', readonly='1'),
        'warning_html': fields.text('Warning', readonly='1'),
        'buffer_qty': fields.float_null('Buffer Qty', related_uom='uom_id', readonly=1),
        'auto_qty': fields.float('Auto. Supply Qty', related_uom='uom_id', readonly=1),
        'min_max': fields.char('Min/Max', size=128, readonly=1),
    }

replenishment_order_calc_line()

class replenishment_inventory_review(osv.osv):
    _name = 'replenishment.inventory.review'
    _description = 'Inventory Review'
    _order = 'id desc'
    _rec_name = 'generation_date'
    _columns = {
        'location_config_id': fields.many2one('replenishment.location.config', 'Location Config', required=1, select=1, readonly=1),
        'generation_date': fields.datetime('Generated', readonly=1),
        'amc_first_date': fields.date('RR AMC first date', readonly=1),
        'amc_last_date': fields.date('RR AMC last date', readonly=1),
        'projected_view': fields.integer('Projected view (months from generation date)', readonly=1),
        'final_date_projection': fields.date('Final day of projection', readonly=1),
        'sleeping': fields.integer('Sleeping stock alert parameter (month)', readonly=1),
        'time_unit': fields.selection([('d', 'days'), ('w', 'weeks'), ('m', 'months')], string='Display variable durations in', readonly=1),
        'line_ids': fields.one2many('replenishment.inventory.review.line', 'review_id', 'Products', readonly=1, context={'default_code_only': 1}),
        'frequence_name': fields.char('Scheduled reviews periodicity', size=512, readonly=1),
        'scheduler_date': fields.datetime('Theoritical scheduler date', readonly=1, internal=1),
        'state': fields.selection([('complete', 'Complete'), ('inprogress', 'In Progress')], 'State', readonly=1),
    }

    _defaults = {
        'state': 'inprogress',
        'generation_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    def _selected_data(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if not context.get('button_selected_ids'):
            raise osv.except_osv(_('Warning!'), _('Please select at least one line'))

        inv_review = self.browse(cr, uid, ids[0], context=context)
        loc_ids = [x.id for x in inv_review.location_config_id.local_location_ids]

        inv_review_line = self.pool.get('replenishment.inventory.review.line').browse(cr, uid, context.get('button_selected_ids'), context=context)

        return {
            'location_ids': loc_ids,
            'products': [x.product_id for x in inv_review_line],
            'inv_review': inv_review,
        }

    def pipeline_po(self, cr, uid, ids, context=None):
        data = self._selected_data(cr, uid, ids, context=context)

        product_ids = [x.id for x in data['products']]
        product_code = [x.default_code for x in data['products']]


        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'purchase.purchase_line_pipeline_action', ['tree'], new_tab=True, context=context)
        res['domain'] = ['&', '&', ('location_dest_id', 'in', data['location_ids']), ('state', 'in', ['validated', 'validated_n', 'sourced_sy', 'sourced_v', 'sourced_n']), ('product_id', 'in', product_ids)]
        res['name'] = _('Pipeline %s: %s') % (data['inv_review'].location_config_id.name, ', '.join(product_code))
        res['nodestroy'] = True
        res['target'] = 'new'
        return res

    def pipeline(self, cr, uid, ids, context=None):
        data = self._selected_data(cr, uid, ids, context=context)

        product_ids = [x.id for x in data['products']]
        product_code = [x.default_code for x in data['products']]

        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'stock.action_move_form3', ['tree', 'form'], context=context)
        res['domain'] = ['&', '&', ('location_dest_id', 'in', data['location_ids']), ('state', 'in', ['confirmed', 'assigned']), ('product_id', 'in', product_ids)]
        res['name'] = _('Pipeline %s: %s') % (data['inv_review'].location_config_id.name, ', '.join(product_code))
        res['nodestroy'] = True
        res['target'] = 'new'
        return res

    def stock_by_location(self, cr, uid, ids, context=None):
        data = self._selected_data(cr, uid, ids, context=context)
        prod_id = data['products'][0].id
        context['active_id'] = prod_id
        return self.pool.get('product.product').open_stock_by_location(cr, uid, [prod_id], context=context)


replenishment_inventory_review()


class replenishment_inventory_review_line(osv.osv):
    _name = 'replenishment.inventory.review.line'
    _description = 'Inventory Review Line'
    _rec_name = 'product_id'
    _order = 'product_id, review_id'

    _columns = {
        'review_id': fields.many2one('replenishment.inventory.review', 'Review', required=1, select=1, ondelete='cascade'), # OC
        'product_id': fields.many2one('product.product', 'Product Code', select=1, required=1), # OC
        'product_description': fields.related('product_id', 'name',  string='Description', type='char', size=64, readonly=True, select=True, write_relate=False), # OC
        'uom_id': fields.related('product_id', 'uom_id',  string='UoM', type='many2one', relation='product.uom', readonly=True, select=True, write_relate=False), # OC
        'status': fields.selection(life_cycle_status, string='Life cycle status'), # OC
        'paired_product_id': fields.many2one('product.product', 'Replacing/Replaced product'),
        'primay_product_list': fields.char('Primary Product List', size=512), # OC
        'rule': fields.selection([('cycle', 'Order Cycle'), ('minmax', 'Min/Max'), ('auto', 'Automatic Supply')], string='Replenishment Rule (Order quantity)', required=1), #Seg
        'min_qty': fields.float_null('Min Qty', related_uom='uom_id'), # Seg line
        'max_qty': fields.float_null('Max Qty', related_uom='uom_id'), # Seg line
        'auto_qty': fields.float_null('Auto. Supply Qty', related_uom='uom_id'), # Seg line
        'buffer_qty': fields.float_null('Buffer Qty', related_uom='uom_id'), # Seg line
        'min_max': fields.char('Min / Max', size=128),
        'safety_stock': fields.integer('Safety Stock'), # Seg
        'segment_ref_name': fields.char('Segment Ref/Name', size=512), # Seg
        'rr_fmc_avg': fields.float_null('RR-FMC (average for period)', null_value='N/A'),
        'rr_amc': fields.float('RR-AMC'),
        'valid_rr_fmc': fields.boolean('Valid', readonly=1), # OC
        'real_stock': fields.float('Real Stock', readonly=1, related_uom='uom_id'), # OC
        'pipeline_qty': fields.float('Pipeline Qty', readonly=1, related_uom='uom_id'), # OC
        'reserved_stock_qty': fields.float('Reserved Stock Qty', readonly=1, related_uom='uom_id'),# OC
        'expired_qty_before_cons': fields.float_null('Expired Qty before cons.', readonly=1, related_uom='uom_id', null_value='N/A'), # OC
        'total_expired_qty': fields.float('Qty expiring within period', readonly=1, related_uom='uom_id'),
        'sleeping_qty': fields.float('Sleeping Qty'),
        'projected_stock_qty': fields.float_null('RR-FMC Projected Stock Level', readonly=1, related_uom='uom_id', null_value='N/A'), # OC
        'projected_stock_qty_amc': fields.float_null('RR-AMC Projected Stock Level', readonly=1, related_uom='uom_id', null_value='N/A'), # OC
        'unit_of_supply_amc': fields.float_null('Days/weeks/months of supply (RR-AMC)', null_value='N/A'),
        'unit_of_supply_fmc': fields.float_null('Days/weeks/months of supply (RR-FMC)', null_value='N/A'),
        'warning': fields.text('Warning', readonly='1'), # OC
        'warning_html': fields.text('Warning', readonly='1'), # OC
        'open_loan': fields.boolean('Open Loan', readonly=1), # OC
        'open_donation': fields.boolean('Donations pending', readonly=1), # OC
        'qty_lacking': fields.float_null('Qty lacking before next RDD', readonly=1, related_uom='uom_id', null_value='N/A'), # OC
        'qty_lacking_needed_by': fields.date('Qty lacking needed by', readonly=1), # OC
        'eta_for_next_pipeline': fields.date('ETA for Next Pipeline', readonly=1), # Seg

        'date_preparing': fields.date('Start preparing the next order'), # Seg
        'date_next_order_validated': fields.date('Next order to be validated by'), # Seg
        'date_next_order_rdd': fields.date('RDD for next order'), # Seg
        'internal_lt': fields.integer('Internal LT'),
        'external_lt': fields.integer('External LT'),
        'total_lt': fields.integer('Total LT'),
        'order_coverage': fields.integer('Order Coverage'),
        'pas_ids': fields.one2many('replenishment.inventory.review.line.pas', 'review_line_id', 'PAS by month'),
        'detail_ids': fields.one2many('replenishment.inventory.review.line.stock', 'review_line_id', 'Exp by month'),
        'detail_exp_nocons':  fields.one2many('replenishment.inventory.review.line.exp.nocons', 'review_line_id', 'Exp.'),
        'segment_line_id': fields.integer('Segment line id', 'Seg line id', internal=1, select=1),

        'std_dev_hmc': fields.float('Standard Deviation HMC'),
        'coef_var_hmc': fields.float('Coefficient of Variation of HMC (%)'),
        'std_dev_hmc_fmc': fields.float_null('Standard Deviation of HMC vs FMC'),
        'coef_var_hmc_fmc': fields.float_null('Coefficient of Variation of HMC and FMC (%)'),
    }

replenishment_inventory_review_line()

class replenishment_inventory_review_line_pas(osv.osv):
    _name = 'replenishment.inventory.review.line.pas'
    _description = 'Pas by month'
    _rec_name = 'date'
    _order = 'date'

    _columns = {
        'review_line_id': fields.many2one('replenishment.inventory.review.line', 'Review Line', required=1, select=1, ondelete='cascade'),
        'date': fields.date('Date'),
        'rr_fmc': fields.float_null('RR-FMC'),
        'projected': fields.float_null('Projected'),
    }

replenishment_inventory_review_line_pas()

class replenishment_inventory_review_line_exp_nocons(osv.osv):
    _name = 'replenishment.inventory.review.line.exp.nocons'
    _description = 'Exp by month / instance'
    _rec_name = 'instance_id'
    _order = 'id'

    _columns = {
        'review_line_id': fields.many2one('replenishment.inventory.review.line', 'Review Line', required=1, select=1, ondelete='cascade'),
        'instance_id': fields.many2one('msf.instance', 'Instance'),
        'exp_qty': fields.float_null('Exp'),
        'batch_number': fields.char('BN', size=256),
        'life_date': fields.date('ED'),
        'stock_qty': fields.float_null('Stock Qty'),
    }
replenishment_inventory_review_line_exp_nocons()

class replenishment_inventory_review_line_exp(osv.osv):
    _name = 'replenishment.inventory.review.line.exp'
    _description = 'Exp by month / instance'
    _rec_name = 'date'
    _order = 'date'

    _columns = {
        'review_line_id': fields.many2one('replenishment.inventory.review.line', 'Review Line', required=1, select=1, ondelete='cascade'),
        'date': fields.date('Date'),
        'instance_id': fields.many2one('msf.instance', 'Instance'),
        'exp_qty': fields.float('Exp'),
        'expiry_line_id': fields.many2one('product.likely.expire.report.line', 'Expiry Line'),
    }
replenishment_inventory_review_line_exp()

class replenishment_inventory_review_line_stock(osv.osv):
    _name = 'replenishment.inventory.review.line.stock'
    _description = 'Stock by instance'

    _columns = {
        'review_line_id': fields.many2one('replenishment.inventory.review.line', 'Review Line', required=1, select=1, ondelete='cascade'),
        'qty': fields.float('Stock Level'),
        'instance_id': fields.many2one('msf.instance', 'Instance'),
        'local_instance': fields.boolean('Local instance'),
        'total_exp': fields.float('Total Exp.'),
    }

    def fields_get(self, cr, uid, fields=None, context=None, with_uom_rounding=False):
        if context is None:
            context = {}

        fg = super(replenishment_inventory_review_line_stock, self).fields_get(cr, uid, fields=fields, context=context, with_uom_rounding=with_uom_rounding)
        if context.get('review_line_id'):
            cr.execute('''select distinct(date) from replenishment_inventory_review_line_exp where review_line_id=%s and date is not null''', (context.get('review_line_id'),))
            for date in cr.fetchall():
                if date and date[0]:
                    dd = date[0].split('-')
                    fg[date[0]] =  {'type': 'float', 'string': '%s/%s' % (dd[2], dd[1])}
        return fg

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}

        fvg = super(replenishment_inventory_review_line_stock, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        if view_type == 'tree' and context.get('review_line_id'):
            arch = '''<tree string="Exp by month">
                <field name="instance_id" />
                <field name="qty" sum="Total"/>
                <field name="local_instance" invisible="1" />
            '''

            cr.execute('''select distinct(date) from replenishment_inventory_review_line_exp where review_line_id=%s and date is not null''', (context.get('review_line_id'),))
            for date in cr.fetchall():
                arch += '''<field name="%s" sum="Total"/>''' % date[0]
                arch += '''<button name="go_to_item" type="object" string="%s" icon="gtk-info" context="{'item_date': '%s', 'review_line_id': %s}" attrs="{'invisible': [('local_instance', '=', False)]}"/>''' % (_('Go to item'), date[0], context.get('review_line_id'))
            arch += '''
            <field name="total_exp" sum="Total"/>
            </tree>'''

            fvg['arch'] = arch
        return fvg

    def read(self, cr, uid, ids, vals, context=None, load='_classic_read'):
        if context is None:
            context = {}

        if context.get('review_line_id'):
            instance_id = self.pool.get('res.company')._get_instance_id(cr, uid)
            res = {}
            cr.execute('''select stock.id, exp.date, exp.exp_qty, stock.review_line_id, stock.qty, stock.instance_id
                from replenishment_inventory_review_line_stock stock
                left join replenishment_inventory_review_line_exp exp on exp.review_line_id=stock.review_line_id and exp.date is not null
                where stock.id in %s''', (tuple(ids), ))
            for x in cr.fetchall():
                if x[0] not in res:
                    res[x[0]] = {
                        'id': x[0],
                        'review_line_id': x[3],
                        'qty': x[4],
                        'instance_id': x[5],
                        'local_instance': x[5] == instance_id,
                        'total_exp': 0
                    }
                if x[1]:
                    res[x[0]][x[1]] = x[2]
                    res[x[0]]['total_exp'] += x[2]
            return res.values()

        return super(replenishment_inventory_review_line_stock, self).read(cr, uid, ids, vals, context=context, load=load)

    def go_to_item(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if context.get('review_line_id') and context.get('item_date'):
            exp_obj = self.pool.get('replenishment.inventory.review.line.exp')
            exp_ids = exp_obj.search(cr, uid, [('review_line_id', '=', context.get('review_line_id')), ('date', '=', context.get('item_date'))], context=context)
            if exp_ids:
                exp = exp_obj.read(cr, uid, exp_ids, ['expiry_line_id'], context=context)[0]
                if exp and exp['expiry_line_id']:
                    item_ids = self.pool.get('product.likely.expire.report.item').search(cr, uid, [('period_start', '=', context.get('item_date')), ('line_id', '=', exp['expiry_line_id'][0])], context=context)
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'product.likely.expire.report.item',
                        'res_id': item_ids[0],
                        'view_type': 'form',
                        'view_mode': 'form',
                        'context': context,
                        'target': 'new'
                    }

        return False

replenishment_inventory_review_line_stock()

class replenishment_product_list(osv.osv):
    _name = 'replenishment.product.list'
    _description = 'RR Product List'
    _rec_name = 'product_id'
    _order = 'default_code'
    _auto = False

    def init(self, cr):
        drop_view_if_exists(cr, 'replenishment_product_list')

        cr.execute("""CREATE OR REPLACE VIEW replenishment_product_list AS (
            select CASE WHEN seg_line.id IS NULL THEN -1*prod.id ELSE seg_line.id END as id, prod.id as product_id, prod.default_code as default_code, segment.name_seg as name_seg, segment.description_seg as description_seg, segment.id as segment_id
            from
                product_product prod
                left join replenishment_segment_line seg_line on seg_line.product_id = prod.id
                left join replenishment_segment segment on segment.id = seg_line.segment_id and segment.hidden='f'
            where
                segment.state != 'cancel' or segment.state is null
        )""")

    def _search_list_sublist(self, cr, uid, obj, name, args, context=None):
        '''
        Filter the search according to the args parameter
        '''
        pl_obj = self.pool.get('product.list')

        if not context:
            context = {}

        ids = []

        for arg in args:
            if arg[0] == 'list_ids' and arg[1] == '=' and arg[2]:
                list = pl_obj.browse(cr, uid, int(arg[2]), context=context)
                for line in list.product_ids:
                    ids.append(line.name.id)
            elif arg[0] == 'list_ids' and arg[1] == 'in' and arg[2]:
                for list in pl_obj.browse(cr, uid, arg[2], context=context):
                    for line in list.product_ids:
                        ids.append(line.name.id)
            else:
                return []

        return [('product_id', 'in', ids)]

    _columns = {
        'product_id': fields.many2one('product.product', 'Product', select=1, required=1),
        'segment_id': fields.many2one('replenishment.segment', 'Replenishment Segment', select=1, required=1),
        'default_code': fields.char('Product Code', size=256, select=1, required=1),
        'product_description': fields.related('product_id', 'name',  string='Product Description', type='char', size=64, readonly=True, select=True, write_relate=False),
        'name_seg': fields.char('Replenishment Segment Reference', size=64, readonly=1, select=1, group_operator='count'),
        'description_seg': fields.char('Replenishment Segment Description', required=1, size=28, select=1),
        'list_ids': fields.function(misc.get_fake, fnct_search=_search_list_sublist, type='many2one', relation='product.list', method=True, string='Lists'),
    }

replenishment_product_list()

class wizard_export_replenishment_product_list(osv.osv_memory):
    _name ="wizard.export.replenishment.product.list"

    _columns = {
        'list_id': fields.many2one('product.list', 'Product List', required=1),
    }

    def create_report(self, cr, uid, ids, context=None):
        rec = self.browse(cr, uid, ids, context=context)
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'report_replenishment_product_list',
            'datas': {'context': context, 'list_id': rec[0].list_id.id}
        }

wizard_export_replenishment_product_list()

class product_stock_out(osv.osv):
    _name = 'product.stock_out'
    _description = 'Product Stock Outs'

    _columns = {
        'name': fields.char('Reference', size=64, readonly=1, select=1),
        'location_id': fields.many2one('stock.location', 'Location', domain="[('usage', '=', 'internal'), ('location_category', 'in', ['stock', 'consumption_unit', 'eprep'])]", required=1),
        'state': fields.selection([('draft', 'Draft'), ('validated', 'Validated'), ('closed', 'Closed'), ('cancelled', 'Cancelled')], 'State', readonly=1),
        'line_ids': fields.one2many('product.stock_out.line', 'stock_out_id', 'Stock Out Lines'),
        'sequence_id': fields.many2one('ir.sequence', 'Lines Sequence', required=True, ondelete='cascade'),
        'file_to_import': fields.binary(string='File to import'),
        'adjusted_amc': fields.boolean('RR-AMC adjusted', readonly=1),
        'warning': fields.boolean('Warning', readonly=1),
    }

    _defaults = {
        'state': 'draft',
        'adjusted_amc': False,
    }
    def create(self, cr, uid, vals, context=None):
        vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'product.stock_out')

        name = vals['name']
        code = 'stock_out.line'
        self.pool.get('ir.sequence.type').create(cr, uid, {'name': name, 'code': code})
        vals['sequence_id'] = self.pool.get('ir.sequence').create(cr, uid, {
            'name': name,
            'code': code,
            'prefix': '',
            'padding': 0,
        })

        return super(product_stock_out, self).create(cr, uid, vals, context=context)

    def import_lines(self, cr, uid, ids, context=None):
        line_obj = self.pool.get('product.stock_out.line')
        product_obj = self.pool.get('product.product')

        obj = self.browse(cr, uid, ids[0], context=context)
        if not obj.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))
        file_data = SpreadsheetXML(xmlstring=base64.decodestring(obj.file_to_import))

        existing_line = {}
        for line in obj.line_ids:
            existing_line[line.line_number] = line.id

        idx = 0
        error = []
        updated = 0
        ignored = 0
        created = 0
        for row in file_data.getRows():
            line_error = []
            idx += 1
            cells_nb = len(row.cells)
            if idx < 7 or cells_nb < 2:
                # header
                continue

            prod_line = row.cells[0].data
            prod_code = row.cells[1].data
            if not prod_code:
                continue
            prod_code = prod_code.strip()

            data_towrite = {
                'product_id': False,
                'from_date': False,
                'to_date': False,
                'qty_missed': False,
                'substitute_1_product_id': False,
                'substitute_1_qty': False,
                'substitute_2_product_id': False,
                'substitute_2_qty': False,
                'substitute_3_product_id': False,
                'substitute_3_qty': False,
            }

            if prod_line and prod_line not in existing_line:
                error.append(_('XLS Line %d: product line %s not found.') % (idx, prod_line))
                continue
            prod_id = product_obj.search(cr, uid, [('default_code', '=ilike', prod_code)], context=context)
            if not prod_id:
                line_error.append(_('XLS Line %d: product code %s not found') % (idx, prod_line))
            else:
                data_towrite['product_id'] = prod_id[0]


            if cells_nb < 5:
                line_error.append(_('XLS Line %d: dates from and to required') % (idx,))
                error += line_error
                ignored += 1
                continue

            if not row.cells[3].type == 'datetime':
                line_error.append(_('XLS Line %d: FROM DATE %d, date is not valid, found %s') % (idx, row.cells[3].data))
                error += line_error
                continue

            if not row.cells[4].type == 'datetime':
                line_error.append(_('XLS Line %d: TO DATE %d, date is not valid, found %s') % (idx, row.cells[4].data))
                error += line_error
                continue

            data_towrite['from_date'] = row.cells[3].data.strftime('%Y-%m-%d')
            data_towrite['to_date'] = row.cells[4].data.strftime('%Y-%m-%d')

            error_date = line_obj.change_date(cr, uid, [existing_line.get(prod_line, 0)], data_towrite['from_date'], data_towrite['to_date'], context=context)
            if error_date.get('warning', {}).get('message'):
                line_error.append(_('XLS Line %d: %s') % (idx, error_date['warning']['message']))


            if cells_nb > 6 and row.cells[6].data and not isinstance(row.cells[6].data, (int, long, float)):
                line_error.append(_('XLS Line %d: Missing Qty must be a number, found %s') % (idx, row.cells[6].data))
            else:
                data_towrite['qty_missed'] = row.cells[6].data

            replace_prod_col = 7
            for sub in [1, 2, 3]:
                if cells_nb > replace_prod_col and row.cells[replace_prod_col].data:
                    sub_prod_code = row.cells[replace_prod_col].data.strip()
                    sub_prod_ids = product_obj.search(cr, uid, [('default_code', '=ilike', sub_prod_code)], context=context)
                    if not sub_prod_ids:
                        line_error.append(_('XLS Line %d: product substitution %d code %s not found') % (idx, sub, prod_line))
                    else:
                        data_towrite['substitute_%d_product_id' % sub] = sub_prod_ids[0]

                    if cells_nb > replace_prod_col+2 and row.cells[replace_prod_col+2].data:
                        if not isinstance(row.cells[replace_prod_col+2].data, (int, long, float)):
                            line_error.append(_('XLS Line %d: Substitution Qty %d must be a number, found %s') % (idx, sub, row.cells[replace_prod_col+2].data))
                        else:
                            data_towrite['substitute_%d_qty' % sub] = row.cells[replace_prod_col+2].data

                replace_prod_col += 3

            if data_towrite['substitute_1_product_id'] and data_towrite['substitute_1_product_id'] in [data_towrite['substitute_2_product_id'], data_towrite['substitute_3_product_id']] \
                    or data_towrite['substitute_2_product_id'] and data_towrite['substitute_2_product_id'] == data_towrite['substitute_3_product_id']:
                line_error.append(_('XLS Line %d: substitute products must be different')% (idx, ))

            if data_towrite['product_id'] in [data_towrite['substitute_1_product_id'], data_towrite['substitute_2_product_id'], data_towrite['substitute_3_product_id']]:
                line_error.append(_('XLS Line %d: you can not substitute a product by itself')% (idx, ))

            if line_error:
                error += line_error
                ignored += 1
                continue
            if not prod_line:
                data_towrite['stock_out_id'] = obj.id
                line_obj.create(cr, uid, data_towrite, context=context)
                created += 1
            else:
                line_obj.write(cr, uid, existing_line[prod_line], data_towrite, context=context)
                updated += 1

        self.write(cr, uid, obj.id, {'file_to_import': False}, context=context)
        wizard_obj = self.pool.get('physical.inventory.import.wizard')
        if error:
            error.insert(0, _('%d line(s) created, %d line(s) updated, %d line(s) in error') % (created, updated, ignored))
            return wizard_obj.message_box_noclose(cr, uid, title=_('Importation errors'), message='\n'.join(error))

        return wizard_obj.message_box_noclose(cr, uid, title=_('Importation Done'), message=_('%d line(s) created, %d line(s) updated') % (created, updated))

    def set_as_draft(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'draft', 'adjusted_amc': False, 'warning': False}, context=context)
        return True

    def set_as_validated(self, cr, uid, ids, context=None):
        warn = []
        for sub in ['1', '2', '3']:
            if len(warn) > 10:
                warn.append('...')
                break
            cr.execute('''
                select
                    line_number from product_stock_out_line line
                where
                    line.stock_out_id in %s and
                    substitute_'''+sub+'''_product_id is not null and
                    substitute_'''+sub+'''_qty is null
                ''', (tuple(ids),)) # not_a_user_entry
            for x in cr.fetchall():
                if len(warn) > 10:
                    break
                warn.append(_('Line %d, "%s Qty used as substitute" must be set') % (x[0], sub))

        cr.execute('''
            select
                l1.line_number,l2.line_number
            from
                product_stock_out_line l1
            left join product_stock_out_line l2 on l2.product_id = l1.product_id and l2.stock_out_id = l1.stock_out_id and l1.id < l2.id
            where
                (l1.from_date, l1.to_date) OVERLAPS (l2.from_date, l2.to_date) and
                l1.stock_out_id in %s
            ''', (tuple(ids), ))
        for x in cr.fetchall():
            warn.append(_('L%s and L%s: dates overlap.') % (x[0], x[1]))

        if warn:
            raise osv.except_osv(_('Warning'), "\n".join(warn))

        self.write(cr, uid, ids, {'state': 'validated'}, context=context)
        return True

    def set_as_cancelled(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'cancelled'}, context=context)
        return True

    def apply_set_closed(self, cr, uid, ids, context=None):
        warning = False
        instance_id = self.pool.get('res.company')._get_instance_id(cr, uid)
        cr.execute('''
            select count(so.id) from product_stock_out so
                left join product_stock_out_line line on so.id = line.stock_out_id
                left join replenishment_segment_line seg_line on seg_line.product_id = line.product_id
                left join replenishment_segment seg on seg.id = seg_line.segment_id
                left join replenishment_location_config config on config.id = seg.location_config_id
                left join local_location_configuration_rel local_rel on local_rel.config_id = config.id
            where
                 so.id in %s and
                 config.main_instance = %s and
                 config.synched = 't' and
                 local_rel.location_id = so.location_id and 
                 seg.state = 'complete'
        ''', (tuple(ids), instance_id))
        nb = cr.fetchone()
        if nb and nb[0]:
            warning = True
        self.write(cr, uid, ids, {'state': 'closed', 'adjusted_amc': True, 'warning': warning}, context=context)
        return True

    def set_closed(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'closed'}, context=context)
        return True
product_stock_out()

class product_stock_out_line(osv.osv):
    _name = 'product.stock_out.line'
    _description = 'Stock Outs Lines'
    _rec_name = 'product_id'
    _order = 'line_number'

    def _get_nb_days(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for st_out in self.browse(cr, uid, ids, fields_to_fetch=['from_date', 'to_date']):
            if st_out.from_date and st_out.to_date:
                res[st_out.id] = (datetime.strptime(st_out.to_date, '%Y-%m-%d') - datetime.strptime(st_out.from_date, '%Y-%m-%d')).days
            else:
                res[st_out.id] = 0

        return res

    _columns = {
        'line_number': fields.integer('Line', readonly=1),
        'stock_out_id': fields.many2one('product.stock_out', 'Product Stock Out', required=1, select=1),
        'product_id': fields.many2one('product.product', 'Stock out product', required=1, select=1),
        'product_code': fields.related('product_id', 'default_code',  string='Stock out product', type='char', size=64, readonly=True, select=True, write_relate=False),
        'product_description': fields.related('product_id', 'name',  string='Description', type='char', size=64, readonly=True, select=True, write_relate=False),
        'uom_id': fields.related('product_id', 'uom_id',  string='UoM', type='many2one', relation='product.uom', readonly=True, select=True, write_relate=False),
        'from_date': fields.date('Stock out from', required=1),
        'to_date': fields.date('Stock out to', required=1),
        'nb_days': fields.function(_get_nb_days, method=1, type='integer', string='Days of stock out'),
        'qty_missed': fields.float_null('Qty missed', related_uom='uom_id'),
        'substitute_1_product_id': fields.many2one('product.product', '1. Substitute product', select=1),
        'substitute_1_product_code': fields.related('substitute_1_product_id', 'default_code',  string='1. Substitute product', type='char', size=64, readonly=True, select=True, write_relate=False),
        'substitute_1_product_description': fields.related('substitute_1_product_id', 'name',  string='1. Description', type='char', size=64, readonly=True, select=True, write_relate=False),
        'substitute_1_uom_id': fields.related('substitute_1_product_id', 'uom_id',  string='UoM', type='many2one', relation='product.uom', readonly=True, select=True, write_relate=False),
        'substitute_1_qty': fields.float_null('1. Qty used as substitute', related_uom='substitute_1_uom_id'),

        'substitute_2_product_id': fields.many2one('product.product', '2. Substitute product', select=1),
        'substitute_2_product_code': fields.related('substitute_2_product_id', 'default_code',  string='2. Substitute product', type='char', size=64, readonly=True, select=True, write_relate=False),
        'substitute_2_product_description': fields.related('substitute_2_product_id', 'name',  string='2. Description', type='char', size=64, readonly=True, select=True, write_relate=False),
        'substitute_2_uom_id': fields.related('substitute_2_product_id', 'uom_id',  string='UoM', type='many2one', relation='product.uom', readonly=True, select=True, write_relate=False),
        'substitute_2_qty': fields.float_null('2. Qty used as substitute', related_uom='substitute_2_uom_id'),

        'substitute_3_product_id': fields.many2one('product.product', '3. Substitute product', select=1),
        'substitute_3_product_code': fields.related('substitute_3_product_id', 'default_code',  string='3. Substitute product', type='char', size=64, readonly=True, select=True, write_relate=False),
        'substitute_3_product_description': fields.related('substitute_3_product_id', 'name',  string='3. Description', type='char', size=64, readonly=True, select=True, write_relate=False),
        'substitute_3_uom_id': fields.related('substitute_3_product_id', 'uom_id',  string='UoM', type='many2one', relation='product.uom', readonly=True, select=True, write_relate=False),
        'substitute_3_qty': fields.float_null('3. Qty used as substitute', related_uom='substitute_3_uom_id'),
    }

    def create(self, cr, uid, vals, context=None):
        if vals.get('stock_out_id'):
            stock_out = self.pool.get('product.stock_out').browse(cr, uid, vals['stock_out_id'], fields_to_fetch=['sequence_id'], context=context)
            vals['line_number'] = self.pool.get('ir.sequence').get_id(cr, uid, stock_out.sequence_id.id, code_or_id='id', context=context)

        return super(product_stock_out_line, self).create(cr, uid, vals, context)


    def change_date(self, cr, uid, ids, from_date, to_date, context=None):

        if len(ids) > 1:
            raise osv.except_osv(_('Error'), "ids must have 1 element in product_stock_out_line change_date %s" % (ids,))

        val = {'nb_days': 0}
        warn = []
        now_str = datetime.now().strftime('%Y-%m-%d')
        if from_date and from_date >= now_str:
            warn.append(_('The "Stock out from" date (%s) must be in the past.') % from_date)
        if to_date and to_date > now_str:
            warn.append(_('The "Stock out to" date (%s) cannot be in the future.') % to_date)

        if from_date and to_date:
            if from_date > to_date:
                warn.append(_('The "Stock out from" date (%s) must be before the "Stock out to" date (%s)') % (from_date, to_date))

            val['nb_days'] = (datetime.strptime(to_date, '%Y-%m-%d') - datetime.strptime(from_date, '%Y-%m-%d')).days
        ret = {
            'value': val,
        }
        if warn:
            ret['warning'] = {'message': '\n'.join(warn)}

        return ret

    def check_date(self, cr, uid, ids, context=None):
        for line in self.browse(cr, uid, ids, fields_to_fetch=['from_date', 'to_date', 'line_number'], context=context):
            get_msg = self.change_date(cr, uid, [line.id], line.from_date, line.to_date, context=context)
            if get_msg.get('warning', {}).get('message'):
                raise osv.except_osv(_('Warning'), "%s %s: %s" % (_('Line'), line.line_number, get_msg['warning']['message']))

        return True

    _constraints = [
        (check_date, 'Wrong date values', []),
    ]
product_stock_out_line()
