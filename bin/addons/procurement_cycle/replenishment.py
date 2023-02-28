#  -*- coding: utf-8 -*-

from osv import osv, fields
from tools.translate import _
from datetime import datetime, date
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
import re
import hashlib
from . import normalize_td
from lxml import etree


life_cycle_status = [('active', _('Active')), ('new', _('New')), ('replaced', _('Replaced')), ('replacing', _('Replacing')), ('phasingout', _('Phasing Out')), ('activereplacing', _('Active-Replacing'))]
class replenishment_location_config(osv.osv):
    _name = 'replenishment.location.config'
    _description = 'Location Configuration'
    _order = 'id desc'

    def need_to_push(self, cr, uid, ids, touched_fields=None, field='sync_date', empty_ids=False, context=None):
        """
            trigger sync if remote_location_ids is touched
        """
        if touched_fields:
            touched_fields.append('remote_location_ids')
        return super(replenishment_location_config, self).need_to_push(cr, uid, ids, touched_fields=touched_fields, field=field, empty_ids=empty_ids, context=context)

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
        if isinstance(ids, int):
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

        instance_id = self.pool.get('res.company')._get_instance_id(cr, uid)

        for config in self.browse(cr, uid, ids, context=context):
            all_instance = {0: True}
            if config.local_location_ids:
                all_instance[instance_id] = True
            for x in config.remote_location_ids:
                all_instance[x.instance_id.id] = True

            logger.info('Try to gen inv. review on %s' % config.name)
            seg_dom = [('location_config_id', '=', config.id), ('state', '=', 'complete')]
            if not forced:
                seg_dom += ['|', ('last_review_date', '!=', config.next_scheduler), ('last_review_date', '=', False)]
            segment_ids = segment_obj.search(cr, uid, seg_dom, context=context)
            if not segment_ids:
                self.write(cr, uid, config.id, {'last_review_error': _('No Segment found')}, context=context)
                continue

            # locations removed: delete data
            cr.execute('delete from replenishment_segment_date_generation where segment_id in %s and instance_id not in %s', (tuple(segment_ids), tuple(all_instance.keys())))

            cr.execute('''
                delete from replenishment_segment_line_amc where
                instance_id not in %s and
                segment_line_id in (select seg_line.id from replenishment_segment_line seg_line where seg_line.segment_id in %s) ''', (tuple(all_instance.keys()), tuple(segment_ids))
                       )

            if not config.local_location_ids:
                self.write(cr, uid, config.id, {'last_review_error': 'Local location is empty, please complete location config %s.' % config.name}, context=context)
                return True


            if config.include_product:
                self.generate_hidden_segment(cr, uid, config.id, context)
                segment_ids = segment_obj.search(cr, uid, seg_dom, context=context)

            segments = segment_obj.browse(cr, uid, segment_ids, fields_to_fetch=['name_seg', 'state', 'missing_inv_review'], context=context)

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

            seg_to_gen = []
            missing_error = []
            for segment in segments:
                if segment.state == 'complete':
                    if segment.missing_inv_review:
                        missing_error.append(_('%s Data from instance(s) is missing, please wait for the next scheduled task or the next sync, or if relates to this instance, please use button "Compute Data". Instances missing data are:\n%s') % (segment.name_seg, segment.missing_inv_review))
                    else:
                        seg_to_gen.append(segment)

            if missing_error:
                self.write(cr, uid, config.id, {'last_review_error': "\n".join(missing_error)}, context=context)
                return True

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

            error = []
            for segment in seg_to_gen:
                try:
                    segment_obj.generate_order_cacl_inv_data(cr, uid, [segment.id], review_id=review_id, context=context, review_date=config.next_scheduler, inv_unit=config.time_unit)
                    logger.info('Inventory Review for config %s, segment %s ok' % (config.name, segment.name_seg))
                except osv.except_osv as o:
                    error.append('%s %s' % (segment.name_seg, misc.ustr(o.value)))
                    cr.rollback()
                except Exception as e:
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
                cr.rollback()
                self.write(cr, uid, config.id, {'last_review_error': "\n".join(error)}, context=context)
        return True

    def generate_hidden_segment(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]
        loc_config_obj = self.pool.get('replenishment.location.config')
        segment_obj = self.pool.get('replenishment.segment')
        all_config_ids = loc_config_obj.search(cr, uid, [('include_product', '=', True), ('id', 'in', ids)], context=context)
        for loc_config in loc_config_obj.browse(cr, uid, all_config_ids, context=context):
            amc_location_ids = [x.id for x in loc_config.local_location_ids]
            hidden_seg_ids = segment_obj.search(cr, uid, [('location_config_id', '=', loc_config.id), ('hidden', '=', True)], context=context)
            if not hidden_seg_ids:
                parent_id = self.pool.get('replenishment.parent.segment').create(cr, uid, {
                    'location_config_id': loc_config.id,
                    'description_parent_seg': 'HIDDEN',
                    'hidden': True,
                    'order_preparation_lt': 1,
                    'order_creation_lt': 1,
                    'order_validation_lt': 1,
                    'supplier_lt': 1,
                    'handling_lt': 1,
                }, context=context)
                hidden_seg = segment_obj.create(cr, uid, {
                    'parent_id': parent_id,
                    'description_seg': 'HIDDEN',
                    'name_seg': 'Stock/Pipe products not segmented',
                    'rule': 'auto',
                    'state': 'complete',
                }, context=context)
            else:
                hidden_seg = hidden_seg_ids[0]

            if not amc_location_ids:
                cr.execute('delete from replenishment_segment_line where segment_id = %s', (hidden_seg, ))
                continue

            cr.execute("select product_id, id from replenishment_segment_line where segment_id = %s", (hidden_seg, ))
            existing_prod = dict((x[0], x[1]) for x in cr.fetchall())
            found_prod = set()

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
                        from replenishment_segment_line seg_line, replenishment_segment seg, replenishment_parent_segment parent_seg
                        where
                            parent_seg.id = seg.parent_id and seg.state in ('draft', 'complete') and seg_line.segment_id = seg.id and parent_seg.location_config_id = %s and parent_seg.hidden='f'

                    )
                group by msl.product_id
            ''', (tuple(amc_location_ids), loc_config.id))

            for prod in cr.fetchall():
                found_prod.add(prod[0])
                if prod[0] not in existing_prod:
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
                            from replenishment_segment_line seg_line, replenishment_segment seg, replenishment_parent_segment parent_seg
                            where
                                parent_seg.id = seg.parent_id and seg.state in ('draft', 'complete') and seg_line.segment_id = seg.id and parent_seg.location_config_id = %s and parent_seg.hidden='f'

                        )
                    group by msl.product_id
                ''', (loc_config.id, loc_config.id))

                for prod in cr.fetchall():
                    if prod[0] in found_prod:
                        continue
                    found_prod.add(prod[0])
                    if prod[0] not in existing_prod:
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
                            from replenishment_segment_line seg_line, replenishment_segment seg, replenishment_parent_segment parent_seg
                            where
                                parent_seg.id = seg.parent_id and seg.state in ('draft', 'complete') and seg_line.segment_id = seg.id and parent_seg.location_config_id = %s and parent_seg.hidden='f'

                        )
                    group by move.product_id
                ''', (tuple(amc_location_ids), loc_config.id))

                for prod in cr.fetchall():
                    if prod[0] in found_prod:
                        continue
                    found_prod.add(prod[0])
                    if prod[0] not in existing_prod:
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
                            from replenishment_segment_line seg_line, replenishment_segment seg, replenishment_parent_segment parent_seg
                            where
                                parent_seg.id = seg.parent_id and seg.state in ('draft', 'complete') and seg_line.segment_id = seg.id and parent_seg.location_config_id = %s and parent_seg.hidden='f'

                        )
                    group by pol.product_id
                ''', (tuple(amc_location_ids), loc_config.id))

            for prod in cr.fetchall():
                if prod[0] in found_prod:
                    continue
                found_prod.add(prod[0])
                if prod[0] not in existing_prod:
                    self.pool.get('replenishment.segment.line').create(cr, uid, {'state': 'active', 'product_id': prod[0], 'segment_id': hidden_seg}, context=context)

            no_more_pipes = [existing_prod[x] for x in existing_prod if x not in found_prod]
            if no_more_pipes:
                self.pool.get('replenishment.segment.line').unlink(cr, uid, no_more_pipes, context=context)

        return True

replenishment_location_config()


class replenishment_parent_segment(osv.osv):
    _name = 'replenishment.parent.segment'
    _description = 'Replenishment Parent Segment'
    _inherits = {'replenishment.location.config': 'location_config_id'}
    _rec_name = 'name_parent_seg'
    _order = 'id desc'


    def _get_date(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        for seg in self.read(cr, uid, ids, ['previous_order_rdd', 'time_unit_lt', 'order_preparation_lt', 'order_creation_lt', 'order_validation_lt', 'supplier_lt', 'handling_lt', 'order_coverage', 'date_next_order_received_modified', 'ir_requesting_location'], context=context):
            ret[seg['id']] = {
                'date_preparing': False,
                'date_next_order_validated': False,
                'date_next_order_received': False,
                'ir_requesting_location_rdo': seg['ir_requesting_location'] and seg['ir_requesting_location'][0],
            }
            ret[seg['id']].update(self.compute_next_order_received(cr, uid, ids, seg['time_unit_lt'], seg['order_preparation_lt'],
                                                                   seg['order_creation_lt'], seg['order_validation_lt'], seg['supplier_lt'], seg['handling_lt'], seg['order_coverage'], seg['previous_order_rdd'], seg['date_next_order_received_modified'], context=context).get('value', {}))
            ret[seg['id']]['order_rdd'] = seg['date_next_order_received_modified'] or ret[seg['id']]['date_next_order_received']
        return ret

    def _get_lt(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        for seg in self.read(cr, uid, ids, ['order_preparation_lt', 'order_creation_lt', 'order_validation_lt', 'supplier_lt', 'handling_lt'], context=context):
            ret[seg['id']] = {
                'internal_lt': seg['order_preparation_lt'] + seg['order_creation_lt'] + seg['order_validation_lt'],
                'external_lt': seg['supplier_lt'] + seg['handling_lt'],
                'total_lt': seg['order_preparation_lt'] + seg['order_creation_lt'] + seg['order_validation_lt'] + seg['supplier_lt'] + seg['handling_lt'],
            }
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

    def _get_has_inprogress_cal(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        for _id in ids:
            ret[_id] = False
        cr.execute('''select parent_segment_id from replenishment_order_calc where state not in ('cancel', 'closed') and parent_segment_id in %s group by parent_segment_id''', (tuple(ids),))
        for x in cr.fetchall():
            ret[x[0]] = True
        return ret


    _columns = {
        'name_parent_seg': fields.char('Reference', size=64, readonly=1, select=1),
        'description_parent_seg': fields.char('Description', required=1, size=28, select=1),
        'location_config_id': fields.many2one('replenishment.location.config', 'Location Config', required=1, ondelete='cascade'),
        'amc_location_txt': fields.function(_get_amc_location_ids, type='text', method=1, string='AMC locations'),

        'ir_requesting_location': fields.many2one('stock.location', string='IR Requesting Location', domain="[('usage', '=', 'internal'), ('location_category', 'in', ['stock', 'consumption_unit', 'eprep'])]", required=0),
        'ir_requesting_location_rdo': fields.function(_get_date, type='many2one', method=1, relation='stock.location', string='IR Requesting Location', multi='get_date'),
        'state_parent': fields.selection([('draft', 'Draft'), ('complete', 'Complete'), ('cancel', 'Cancelled'), ('archived', 'Archived')], 'State', readonly=1),
        'time_unit_lt': fields.selection([('d', 'days'), ('w', 'weeks'), ('m', 'months')], string='Unit of Time', required=1),
        'order_preparation_lt': fields.float_null('Preparation Lead Time', required=1, computation=-1),
        'order_creation_lt': fields.float_null('Order Creation Lead Time', required=1, computation=-1),
        'order_validation_lt': fields.float_null('Order Validation Lead Time', required=1, computation=-1),
        'internal_lt': fields.function(_get_lt, type='float', method=1, string='Internal Lead Time', multi='get_lt', computation=-1),
        'supplier_lt': fields.float_null('Supplier Lead Time', required=1, computation=-1),
        'handling_lt': fields.float_null('Handling Lead Time', required=1, computation=-1),
        'external_lt': fields.function(_get_lt, type='float', method=1, string='External Lead Time', multi='get_lt', computation=-1),
        'total_lt': fields.function(_get_lt, type='float', method=1, string='Total Lead Time', multi='get_lt', computation=-1),
        'order_coverage': fields.float_null('Order Coverage', computation=-1),
        'previous_order_rdd': fields.date(string='Previous order RDD Date', readonly=1, help="Generated according to latest IR's RDD (from most recent Order calc which is now closed)."),
        'date_preparing': fields.function(_get_date, type='date', method=True, string='Date to start preparing the order', multi='get_date', help='This does not take account of any stockouts not related to order coverage. Calculation: "Next order RDD date" - Total Lead time.'),
        'date_next_order_validated':  fields.function(_get_date, type='date', method=True, string='Date next order to be validated by', multi='get_date', help='This does not take account of any stockouts not related to order coverage. Calculation: "Next order RDD date" - Total Lead time + Internal LT. This isupdated according to value in "Next order to be received by'),
        'date_next_order_received': fields.function(_get_date, type='date', method=True, string='Next order to be received by (calculated)', multi='get_date', help='Calculated according to last order RDDate + OC.'),
        'order_rdd': fields.function(_get_date, type='date', method=True, string='Order RDD',  multi='get_date',
                                     store={
                                         'replenishment.parent.segment': (lambda self, cr, uid, ids, c=None: ids,
                                                                          ['time_unit_lt', 'order_preparation_lt', 'order_creation_lt', 'order_validation_lt', 'supplier_lt', 'handling_lt', 'date_next_order_received_modified', 'previous_order_rdd'], 10),
                                     }),
        'date_next_order_received_modified': fields.date(string='Next order to be received by (modified)'),
        'child_ids': fields.one2many('replenishment.segment', 'parent_id', 'Segments', readonly=1),
        'hidden': fields.boolean('Hidden', help='Used to store not segemented products with stock/pipeline'),
        'has_inprogress_cal': fields.function(_get_has_inprogress_cal, type='boolean', method=1, internal=1, string='Has in-progess Order Calc.'),
    }

    _defaults = {
        'state_parent': 'draft',
        'time_unit_lt': 'd',
        'hidden': False,
    }

    _sql_constraints = [
        ('oc_positive', 'check(order_coverage>=0)', 'Order Coverage must be positive or 0')
    ]

    def create(self, cr, uid, vals, context=None):
        if 'name_parent_seg' not in vals:
            vals['name_parent_seg'] = self.pool.get('ir.sequence').get(cr, uid, 'replenishment.parent.segment')

        return super(replenishment_parent_segment, self).create(cr, uid, vals, context)

    def on_change_lt(self, cr, uid, ids, time_unit, order_preparation_lt, order_creation_lt, order_validation_lt, supplier_lt, handling_lt, order_coverage, previous_order_rdd, date_next_order_received_modified, context=None):
        allowed = {
            'm': [0, 0.25, 0.5, 0.75],
            'w': [0, 0.5],
            'd': [0],
        }

        error_message = {
            'm': _('The decimal part of lead time/order coverage values  must be 0, 0.25, 0.5 or 0.75. Values have been rounded.'),
            'w': _('The decimal part of lead time/order coverage values must be 0 or 0.5. Values have been rounded.'),
            'd': _('Only integers are allowed for lead time/order coverage values. Values have been rounded.'),
        }

        rounding = {
            'm': 4.,
            'w': 2.,
            'd': 1,

        }

        input_data = {
            'order_preparation_lt': order_preparation_lt,
            'order_creation_lt': order_creation_lt,
            'order_validation_lt': order_validation_lt,
            'supplier_lt': supplier_lt,
            'handling_lt': handling_lt,
            'order_coverage': order_coverage,
        }

        output_values = {}
        message = False
        for field in input_data:
            if input_data[field] and time_unit and input_data[field] % 1 not in allowed.get(time_unit):
                if round(input_data[field] % 1, 2) not in allowed.get(time_unit):
                    message = error_message.get(time_unit)
                output_values[field] = round(input_data[field]*rounding[time_unit])/rounding[time_unit]
                input_data[field] = output_values[field]

        output_values['internal_lt'] = (input_data['order_preparation_lt'] or 0) + (input_data['order_creation_lt'] or 0) + (input_data['order_validation_lt'] or 0)
        output_values['external_lt'] = (input_data['supplier_lt'] or 0) + (input_data['handling_lt'] or 0)
        output_values['total_lt'] = output_values['internal_lt'] + output_values['external_lt']
        output_values.update(self.compute_next_order_received(cr, uid, ids, time_unit, input_data['order_preparation_lt'], input_data['order_creation_lt'], input_data['order_validation_lt'], input_data['supplier_lt'], input_data['handling_lt'], input_data['order_coverage'], previous_order_rdd, date_next_order_received_modified, context).get('value', {}))

        ret = {'value': output_values}
        if message:
            ret['warning'] = {
                'title': _('Warning'),
                'message': message,
            }
        return ret

    def compute_next_order_received(self, cr, uid, ids, time_unit, order_preparation_lt, order_creation_lt, order_validation_lt, supplier_lt, handling_lt, order_coverage, previous_order_rdd, date_next_order_received_modified, context=None):
        ret = {}
        if previous_order_rdd or date_next_order_received_modified:
            previous_rdd = False
            date_next_order_received = False
            if previous_order_rdd:
                previous_rdd = datetime.strptime(previous_order_rdd, '%Y-%m-%d')
                date_next_order_received = previous_rdd + relativedelta(**normalize_td(time_unit, order_coverage))
            if date_next_order_received_modified:
                date_next_order_received_modified = datetime.strptime(date_next_order_received_modified, '%Y-%m-%d')
                previous_rdd = date_next_order_received_modified - relativedelta(**normalize_td(time_unit, order_coverage))

            ret = {
                'date_preparing': (previous_rdd + relativedelta(**normalize_td(time_unit, (order_coverage or 0) -  (order_creation_lt or 0) - (order_preparation_lt or 0) - (order_validation_lt or 0) - (supplier_lt or 0) - (handling_lt or 0)))).strftime('%Y-%m-%d'),
                'date_next_order_validated': (previous_rdd + relativedelta(**normalize_td(time_unit, (order_coverage or 0) - (supplier_lt or 0) - (handling_lt or 0)))).strftime('%Y-%m-%d'),
                'date_next_order_received': date_next_order_received and date_next_order_received.strftime('%Y-%m-%d'),
            }

        return {'value': ret}

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

    def completed(self, cr, uid, ids, context=None):
        for x in self.read(cr, uid, ids, ['name_parent_seg', 'date_next_order_received_modified', 'date_next_order_received'], context=context):
            if not x['date_next_order_received_modified'] and not x['date_next_order_received']:
                raise osv.except_osv(_('Warning'), _('Warning, to complete Parent Segment %s, field "Next order to be received by (modified)" must have date filled') % (x['name_parent_seg'], ))

        self.write(cr, uid, ids, {'state_parent': 'complete'}, context=context)
        return True

    def check_inprogress_order_calc(self, cr, uid, ids, context=None):
        calc_obj = self.pool.get('replenishment.order_calc')
        calc_ids = calc_obj.search(cr, uid, [('parent_segment_id', 'in', ids), ('state', 'not in', ['cancel', 'closed'])], context=context)
        if calc_ids:
            calc_name = calc_obj.read(cr, uid, calc_ids, ['name'], context=context)
            raise osv.except_osv(_('Warning'), _('Please cancel or close the following Order Calc:\n%s') % (', '.join([x['name'] for x in calc_name])))

    def check_confirmed_segment(self, cr, uid, ids, context=None):
        seg_obj = self.pool.get('replenishment.segment')
        seg_ids = seg_obj.search(cr, uid, [('parent_id', 'in', ids), ('state', '=', 'complete')], context=context)
        if seg_ids:
            seg_name = seg_obj.read(cr, uid, seg_ids, ['name_seg'], context=context)
            raise osv.except_osv(_('Warning'), _('Please set the following Segments as Draft:\n%s') % (', '.join([x['name_seg'] for x in seg_name])))

    def set_as_draft(self, cr, uid, ids, context=None):
        self.check_inprogress_order_calc(cr, uid, ids, context=context)
        self.check_confirmed_segment(cr, uid, ids, context=context)
        self.write(cr, uid, ids, {'state_parent': 'draft'}, context=context)
        seg_reset = []
        for parent in self.browse(cr, uid, ids, fields_to_fetch=['child_ids'], context=context):
            for child in parent.child_ids:
                seg_reset.append(child.id)
        if seg_reset:
            self.pool.get('replenishment.segment').reset_gen_date(cr, uid, seg_reset, set_draft=False, context=context)
        return True

    def set_as_archived(self, cr, uid, ids, context=None):
        self.check_inprogress_order_calc(cr, uid, ids, context=context)
        self.write(cr, uid, ids, {'state_parent': 'archived'}, context=context)
        seg_to_archive = []
        for parent in self.browse(cr, uid, ids, fields_to_fetch=['child_ids'], context=context):
            for child in parent.child_ids:
                if child.state not in ('archived', 'cancel'):
                    seg_to_archive.append(child.id)
        if seg_to_archive:
            self.pool.get('replenishment.segment').set_as_archived(cr, uid, seg_to_archive, context=context)
        return True

    def set_as_cancel(self, cr, uid, ids, context=None):
        self.check_inprogress_order_calc(cr, uid, ids, context=context)
        self.write(cr, uid, ids, {'state_parent': 'cancel'}, context=context)
        seg_to_cancel = []
        for parent in self.browse(cr, uid, ids, fields_to_fetch=['child_ids'], context=context):
            for child in parent.child_ids:
                if child.state != 'cancel':
                    seg_to_cancel.append(child.id)
        if seg_to_cancel:
            self.pool.get('replenishment.segment').set_as_cancel(cr, uid, seg_to_cancel, context=context)
        return True

    def generate_order_calc(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        for pseg in self.browse(cr, uid, ids, context):
            if not pseg.previous_order_rdd and not pseg.date_next_order_received_modified:
                raise osv.except_osv(_('Warning'), _('Warning, to complete Parent Segment, field "Next order to be received by (modified)" must have date filled'))

            calc_id = False
            seg_to_gen = []
            missing = False

            if not pseg.location_config_id.local_location_ids:
                missing = True
                self.log(cr, uid, pseg.id, _('Local location is empty, please complete location config %s. ') % (pseg.location_config_id.name))

            for seg in pseg.child_ids:
                if seg.state == 'complete':
                    if seg.missing_order_calc:
                        missing = True
                        self.pool.get('replenishment.segment').log(cr, uid, seg.id, _('%s: data missing from %s. For Main instance please click on "Compute Data". For other instances wait until the next scheduled task or the next sync. ') % (seg.name_seg, seg.missing_order_calc))
                        continue
                    seg_to_gen.append(seg)

            if missing:
                return True
            for seg in seg_to_gen:
                if not calc_id:
                    calc_id = self.pool.get('replenishment.order_calc').create(cr, uid, {
                        'parent_segment_id': pseg.id,
                        'description_seg': pseg.description_parent_seg,
                        'location_config_id': pseg.location_config_id.id,
                        'location_config_description': pseg.location_config_id.description,
                        'total_lt': pseg.total_lt,
                        'time_unit_lt': pseg.time_unit_lt,
                        'local_location_ids': [(6, 0, [x.id for x in pseg.local_location_ids])],
                        'remote_location_ids': [(6, 0, [x.id for x in pseg.remote_location_ids])],
                        'instance_id': pseg.main_instance.id,
                        'new_order_reception_date': pseg.date_next_order_received_modified or pseg.date_next_order_received,
                    }, context=context)
                self.pool.get('replenishment.segment').generate_order_cacl_inv_data(cr, uid, [seg.id], calc_id=calc_id, context=context)
                self.pool.get('replenishment.order_calc').log(cr, uid, calc_id, _('Order Calc generated for %s') % (seg.name_seg, ))

            return True

    def set_as_cancel_and_cancel_order(self, cr, uid, ids, context=None):
        calc_obj = self.pool.get('replenishment.order_calc')
        seg_obj = self.pool.get('replenishment.segment')
        calc_ids = calc_obj.search(cr, uid, [('parent_segment_id', 'in', ids), ('state', 'not in', ['cancel', 'closed'])], context=context)
        if calc_ids:
            calc_obj.write(cr, uid, calc_ids, {'state': 'cancel'}, context=context)
        seg_ids = self.pool.get('replenishment.segment').search(cr, uid, [('parent_id', 'in', ids), ('state', 'in', ['draft', 'complete'])], context=context)
        if seg_ids:
            seg_obj.set_as_cancel(cr, uid, seg_ids, context=context)
        return True



    def trigger_compute_segment_data(self, cr, uid, ids, context):
        cr.execute('''
            select hidden_seg.id from
                replenishment_segment hidden_seg, replenishment_parent_segment parent_hidden, replenishment_segment this, replenishment_parent_segment parent_this, replenishment_location_config config
                where
                    hidden_seg.parent_id = parent_hidden.id and
                    this.parent_id = parent_this.id and
                    parent_this.location_config_id = parent_hidden.location_config_id and
                    config.id = parent_this.location_config_id and
                    parent_hidden.hidden = 't' and
                    config.include_product = 't' and
                    this.state = 'complete' and
                    parent_this.id in %s
            ''', (tuple(ids),))
        seg_ids = [x[0] for x in cr.fetchall()]
        cr.execute('''select id from replenishment_segment where parent_id in %s and state in ('draft', 'complete')''', (tuple(ids), ))
        seg_ids += [x[0] for x in cr.fetchall()]
        return self.pool.get('replenishment.segment.line.amc').generate_segment_data(cr, uid, context=context, seg_ids=seg_ids, force_review=True)

replenishment_parent_segment()


class replenishment_segment(osv.osv):
    _name = 'replenishment.segment'
    _description = 'Replenishment Segment'
    _inherits = {'replenishment.parent.segment': 'parent_id'}
    _rec_name = 'name_seg'
    _order = 'id desc'

    def _get_rule_alert(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        dict_d = {
            'cycle': _('PAS with FMC'),
            'minmax': _('Min'),
            'auto': _('None'),
        }
        dict_label = {
            'cycle': _('RR FMC'),
            'minmax': _('Min'),
            'auto': _('Auto. Supply Qty'),
        }
        for seg in self.read(cr, uid, ids, ['rule'], context=context):
            ret[seg['id']] = {'rule_alert': dict_d.get(seg['rule'],''), 'rr_label': dict_label.get(seg['rule'],'')}
        return ret


    def _get_safety_and_buffer_warn(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}

        if not ids:
            return {}

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

    def _get_ss_month(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        for _id in ids:
            ret[_id] = 0
        for x in self.read(cr, uid, ids, ['safety_stock', 'time_unit_lt'], context=context):
            if x['time_unit_lt'] == 'm':
                ret[_id] = x['safety_stock']
            elif x['time_unit_lt'] == 'w':
                ret[_id] = x['safety_stock'] / 4.35
            else:
                ret[_id] = x['safety_stock'] / 30.44
        return ret

    def _missing_instances(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}

        for seg in self.browse(cr, uid, ids, fields_to_fetch=['main_instance', 'remote_location_ids', 'last_generation', 'location_config_id', 'hidden'], context=context):
            all_instances = set()
            all_instances_review = set()
            if not seg.hidden or seg.location_config_id.include_product:
                instances_name_by_id = {seg.main_instance.id: seg.main_instance.code}
                all_instances = set([seg.main_instance.id])
                for remote_loc in seg.remote_location_ids:
                    all_instances.add(remote_loc.instance_id.id)
                    instances_name_by_id[remote_loc.instance_id.id] = remote_loc.instance_id.code

                all_instances_review = all_instances.copy()
                for data_done in seg.last_generation:
                    if data_done.review_date:
                        try:
                            all_instances_review.remove(data_done.instance_id.id)
                        except KeyError:
                            pass
                    if data_done.full_date:
                        try:
                            all_instances.remove(data_done.instance_id.id)
                        except KeyError:
                            pass

            ret[seg.id] = {'missing_order_calc': ', '.join([instances_name_by_id.get(x, '') for x in all_instances]), 'missing_inv_review': ', '.join([instances_name_by_id.get(x, '') for x in all_instances_review]) }
        return ret


    _columns = {
        'parent_id': fields.many2one('replenishment.parent.segment', 'Parent', required=1, ondelete='cascade', select=1, domain="[('hidden', '=', False), ('state_parent', 'in', ['complete', 'draft']), ('is_current_instance', '=', True)]"),
        'name_seg': fields.char('Reference', size=64, readonly=1, select=1),
        'description_seg': fields.char('Replenishment Segment Description', required=1, size=28, select=1),

        'rule': fields.selection([('cycle', 'Order Cycle'), ('minmax', 'Min/Max'), ('auto', 'Automatic Supply')], string='Replenishment Rule (Order quantity)', required=1, add_empty=True),
        'rule_alert': fields.function(_get_rule_alert, method=1, string='Replenishment Rule (Alert Theshold)', type='char', multi='alert_label'),
        'product_list_id': fields.many2one('product.list', 'Primary product list'),
        'state': fields.selection([('draft', 'Draft'), ('complete', 'Complete'), ('cancel', 'Cancelled'), ('archived', 'Archived')], 'State', readonly=1),
        'fake_state': fields.related('state', string='State internal', readonly=1, write_relate=False, type='char'),
        'safety_stock': fields.float_null('Safety Stock', computation=-1),
        'safety_stock_month': fields.function(_get_ss_month, type='float', method=True, string='Safety Stock in months'),
        'line_ids': fields.one2many('replenishment.segment.line', 'segment_id', 'Products', context={'default_code_only': 1}),
        'file_to_import': fields.binary(string='File to import'),
        'last_generation': fields.one2many('replenishment.segment.date.generation', 'segment_id', 'Generation Date', readonly=1),
        'safety_and_buffer_warn': fields.function(_get_safety_and_buffer_warn, type='boolean', method=1, internal=1, string='Lines has buffer and seg has safety'),
        'last_review_date': fields.datetime('Last review date', readonly=1),
        'have_product': fields.function(_get_have_product, type='boolean', method=1, internal=1, string='Products are set'),
        'missing_order_calc': fields.function(_missing_instances, type='char', method=1, string='Missing OC data', multi='_missing_instances'),
        'missing_inv_review': fields.function(_missing_instances, type='char', method=1, string='Missing Inv.R data', multi='_missing_instances'),
        'specific_period': fields.boolean('Specific Periods Only'),
        'rr_label': fields.function(_get_rule_alert, method=1, string="Field Label", internal=1, type="char", multi='alert_label'),
    }

    _defaults = {
        'state': 'draft',
        'have_product': False,
        'specific_period': False,
    }

    _sql_constraints = [
        ('ss_positive', 'check(safety_stock>=0)', 'Safety Stock must be positive or 0')
    ]

    def create(self, cr, uid, vals, context=None):
        if 'name_seg' not in vals:
            vals['name_seg'] = self.pool.get('ir.sequence').get(cr, uid, 'replenishment.segment')

        return super(replenishment_segment, self).create(cr, uid, vals, context)

    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]
        if not vals:
            return ids

        if not context.get('sync_update_execution'):
            if vals.get('specific_period') is False:
                cr.execute("""
                    select seg.name_seg, count(distinct(line.id))
                    from replenishment_segment seg, replenishment_segment_line line, replenishment_segment_line_period period
                    where
                        seg.id in %s and
                        line.segment_id = seg.id and
                        seg.rule != 'cycle' and
                        seg.specific_period = 't' and
                        period.line_id = line.id and
                        ( period.from_date != '2020-01-01' or period.to_date != '2222-02-28' )
                    group by seg.name_seg
                    """, (tuple(ids), ))
                error = []
                for x in cr.fetchall():
                    error.append('%s: %d lines' % (x[0], x[1]))

                if error:
                    raise osv.except_osv(
                        _('Warning'),
                        _('You can not remove "Specific Periods Only" on a segment with periods on lines:\n%s') % ', '.join(error)
                    )

        return super(replenishment_segment, self).write(cr, uid, ids, vals, context)

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
                replenishment_segment hidden_seg, replenishment_parent_segment parent_hidden, replenishment_segment this, replenishment_parent_segment parent_this, replenishment_location_config config
                where
                    hidden_seg.parent_id = parent_hidden.id and
                    this.parent_id = parent_this.id and
                    parent_this.location_config_id = parent_hidden.location_config_id and
                    config.id = parent_this.location_config_id and
                    parent_hidden.hidden = 't' and
                    config.include_product = 't' and
                    this.state = 'complete' and
                    this.id in %s
            ''', (tuple(ids),))
        other_ids = [x[0] for x in cr.fetchall()]
        seg_ids = ids + other_ids
        return self.pool.get('replenishment.segment.line.amc').generate_segment_data(cr, uid, context=context, seg_ids=seg_ids, force_review=True)


    def convert_time_unit(self, value, from_unit, to_unit):
        days_coeff = {
            'd': 1.,
            'w': 7.,
            'm': 30.44,

        }
        if from_unit == to_unit:
            return value

        return value * days_coeff.get(from_unit, 'd') / days_coeff.get(to_unit, 'd')

    def generate_order_cacl_inv_data(self, cr, uid, ids, review_id=False, calc_id=False, context=None, review_date=False, inv_unit='d'):

        if context is None:
            context = {}

        if review_id:
            context['inv_review'] = True
            coeff = {
                'd': 30.44,
                'w': 4.35,
                'm': 1,
            }.get(inv_unit, 'd')
        order_calc_line = self.pool.get('replenishment.order_calc.line')
        review_line = self.pool.get('replenishment.inventory.review.line')

        for seg in self.browse(cr, uid, ids, context):
            if seg.hidden and (not seg.location_config_id.include_product or not seg.line_ids):
                continue
            missing_instances = ''
            if review_id:
                missing_instances = seg.missing_inv_review
            else:
                missing_instances = seg.missing_order_calc

            if missing_instances:
                raise osv.except_osv(_('Warning'), _('Data from instance(s) is missing, please wait for the next scheduled task or the next sync, or if relates to this instance, please use button "Compute Data". Instances missing data are:\n%s') % (missing_instances, ))

            loc_ids = [x.id for x in seg.local_location_ids]
            if not loc_ids:
                # no more location reset data
                loc_ids = [0]
            cr.execute('''
              select prod_id, min(date) from (
                  select pol.product_id as prod_id, min(coalesce(pol.confirmed_delivery_date, pol.esti_dd, pol.date_planned)) as date
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


            wrong_fmc = {}
            amc_ids_to_reset = []
            cr.execute('''
                select amc.id, line.id
                from
                    replenishment_segment_line_amc amc, replenishment_segment_line line, replenishment_segment seg, product_product p
                where
                    line.id = amc.segment_line_id and
                    line.segment_id = seg.id and
                    seg.id = %s and
                    seg.rule = 'cycle' and
                    p.id = line.product_id and
                    coalesce(amc.fmc_version, '') != coalesce(line.fmc_version, '') and
                    p.perishable='t'
                ''', (seg.id,))
            for x in cr.fetchall():
                wrong_fmc[x[1]] = True
                amc_ids_to_reset.append(x[0])

            if amc_ids_to_reset:
                cr.execute("update replenishment_segment_line_amc set expired_before_rdd=0, expired_between_rdd_oc=0, expired_qty_before_eta=0, fmc_version='X' where id in %s", (tuple(amc_ids_to_reset),))
                cr.execute("delete from replenishment_segment_line_amc_month_exp where line_amc_id in %s", (tuple(amc_ids_to_reset),))
            cr.execute('''
                select segment_line_id, sum(reserved_stock), sum(real_stock - expired_before_rdd), sum(expired_before_rdd), sum(expired_between_rdd_oc), bool_or(open_loan), sum(total_expiry_nocons_qty), sum(real_stock), sum(expired_qty_before_eta), sum(sleeping_qty), bool_or(open_donation)
                    from replenishment_segment_line_amc amc, replenishment_segment_line line
                    where
                        line.id = amc.segment_line_id and
                        line.segment_id = %s
                    group by segment_line_id
            ''', (seg.id,))
            sum_line = {}
            for x in cr.fetchall():
                sum_line[x[0]] = {
                    'reserved_stock_qty': x[1] or 0, # sum(reserved_stock)
                    'pas_no_pipe_no_fmc': x[2] or 0, # sum(real_stock - expired_before_rdd)
                    'expired_before_rdd': x[3] or 0, # sum(expired_before_rdd)
                    'expired_rdd_oc': x[4] or 0, # sum(expired_between_rdd_oc)
                    'open_loan': x[5] or False, # bool_or(open_loan)
                    'open_donation': x[10] or False, # bool_or(open_donation)
                    'total_expiry_nocons_qty': x[6] or 0, # sum(total_expiry_nocons_qty)
                    'real_stock': x[7] or 0, # sum(real_stock)
                    'expired_qty_before_eta': x[8] or 0, # sum(expired_qty_before_eta)
                    'sleeping_qty': x[9] or 0, # sum(sleeping_qty)
                    'missing_exp': wrong_fmc.get(x[0], False)
                }
                if review_id:
                    sum_line[x[0]]['pas_no_pipe_no_fmc'] -= sum_line[x[0]]['expired_rdd_oc']

            today = datetime.now() + relativedelta(hour=0, minute=0, second=0, microsecond=0)


            product_already_exp = {}
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
                                exp.month <= %s
                            group by line.product_id, exp.month
                    ''', (seg.id, rdd.strftime('%Y-%m-%d')))
                    for x in cr.fetchall():
                        end_day_month = (datetime.strptime(x[1], '%Y-%m-%d')+relativedelta(months=1, day=1, days=-1)).strftime('%Y-%m-%d')
                        if end_day_month < today.strftime('%Y-%m-%d'):
                            product_already_exp[x[0]] = product_already_exp.setdefault(x[0], 0) + x[2]
                        else:
                            if x[0] not in exp_by_month:
                                exp_by_month[x[0]] = {}
                            if end_day_month not in exp_by_month[x[0]]:
                                exp_by_month[x[0]][end_day_month] = x[2]
                            else:
                                exp_by_month[x[0]][end_day_month] += x[2]

                past_fmc = {}
                if seg.rule == 'cycle':
                    cr.execute('''
                        select line.product_id, fmc.month, fmc
                        from replenishment_segment_line line
                        inner join replenishment_segment_line_amc_past_fmc fmc on fmc.segment_line_id = line.id
                        where
                            line.segment_id = %s and
                            month <= %s and
                            month >= %s
                    ''', (seg.id, today, today + relativedelta(day=1) - relativedelta(months=seg.rr_amc)))
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
            oc = rdd + relativedelta(**normalize_td(seg.time_unit_lt, seg.order_coverage))

            if not review_id:
                self.save_past_fmc(cr, uid, [seg.id], seg.rule, max_date=oc, context=context)

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

                min_qty = None
                max_qty = None
                auto_qty = None
                if seg.rule == 'cycle':

                    cr.execute('''
                    select date, sum(qty) from (
                        select coalesce(pol.confirmed_delivery_date, pol.esti_dd, pol.date_planned) as date, sum(pol.product_qty) as qty
                        from
                          purchase_order_line pol
                        where
                          pol.product_id=%(product_id)s and
                          pol.state in ('validated', 'validated_n', 'sourced_sy', 'sourced_v', 'sourced_n') and
                          location_dest_id in %(location_id)s and
                          coalesce(pol.confirmed_delivery_date, pol.esti_dd, pol.date_planned) <= %(date)s
                        group by coalesce(pol.confirmed_delivery_date, pol.esti_dd, pol.date_planned)
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
                        pipe_data[datetime.strptime('%s 00:00:00' % (x[0].split(' ')[0], ), '%Y-%m-%d %H:%M:%S')] = x[1]

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

                    for fmc_d in range(1, 19):
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
                                        for x in pipe_date[:]:
                                            # add pipe before end of period
                                            if x <= end:
                                                pas_full += pipe_data[x]
                                                pipe_date.pop(0)
                                            else:
                                                break
                                    else:
                                        # missing stock to cover the full period
                                        if period_conso > pas_full:
                                            # still not enough stock
                                            for x in pipe_date[:]:
                                                if x <= end:
                                                    # compute missing just before the next pipe
                                                    ndays = (x - new_begin).days
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
                        total_expired_qty = sum_line[line.id].get('expired_rdd_oc', 0) + sum_line[line.id].get('expired_before_rdd', 0) - product_already_exp.get(line.product_id.id, 0)
                        for nb_month in range(1, line.segment_id.projected_view+1):
                            end_date = today + relativedelta(months=nb_month, day=1, days=-1)
                            total_expired_qty -= exp_by_month.get(line.product_id.id, {}).get(end_date.strftime('%Y-%m-%d'), 0)
                            rr_fmc_month = fmc_by_month.get(end_date.strftime('%Y-%m-%d'), {}).get('value', False)
                            detailed_pas.append((0, 0, {
                                'date': end_date.strftime('%Y-%m-%d'),
                                'rr_fmc': rr_fmc_month,
                                'projected': rr_fmc_month and max(0, fmc_by_month.get(end_date.strftime('%Y-%m-%d'), {}).get('pas',0)) + total_expired_qty,
                            }))
                    # end if seg.rule == 'cycle'

                elif review_id and loc_ids:
                    for fmc_d in range(1, 19):
                        from_fmc = line['rr_fmc_from_%d'%fmc_d]
                        to_fmc = line['rr_fmc_to_%d'%fmc_d]
                        num_fmc = line['rr_fmc_%d'%fmc_d]
                        if seg.rule == 'minmax':
                            max_fmc = line['rr_max_%d'%fmc_d]

                        to_break = False

                        begin_date = today + relativedelta(day=1)
                        max_date = today + relativedelta(months=line.segment_id.projected_view, day=1, days=-1)
                        if fmc_d == 1 and not from_fmc and not to_fmc and num_fmc is not False:
                            to_break = True
                            upper = max_date.strftime('%Y-%m-%d')
                            key = begin_date + relativedelta(months=1, day=1, days=-1)
                        elif not from_fmc or not to_fmc or num_fmc is False:
                            break
                        else:
                            upper = min(to_fmc, max_date.strftime('%Y-%m-%d'))
                            key = max(datetime.strptime(from_fmc, '%Y-%m-%d') + relativedelta(months=1, day=1, days=-1), begin_date)

                        while key.strftime('%Y-%m-%d') <= upper:
                            fmc_data = {}
                            if seg.rule == 'minmax':
                                if num_fmc is False or max_fmc is False:
                                    to_break = True
                                    break
                                fmc_data['rr_max'] = max_fmc

                            fmc_data.update({
                                'date': key.strftime('%Y-%m-%d'),
                                'rr_fmc': num_fmc,
                            })
                            detailed_pas.append((0, 0, fmc_data))
                            key += relativedelta(months=2, day=1, days=-1)
                        if to_break:
                            break

                #pas = max(0, sum_line.get(line.id, {}).get('pas_no_pipe_no_fmc', 0) + line.pipeline_before_rdd - total_fmc)
                pas = pas_full
                ss_stock = 0
                warnings = []
                warnings_html = []
                qty_lacking_needed_by = False
                proposed_order_qty = 0
                if seg.rule == 'cycle':
                    if calc_id and total_month_oc:
                        # in cas of replacing total_fmc_oc and total_month_oc start from SODate
                        ss_stock = seg.safety_stock_month * total_fmc_oc / total_month_oc
                    elif review_id and total_month:
                        ss_stock = seg.safety_stock_month * total_fmc / total_month
                    if line.status != 'new':
                        if line.status != 'phasingout':
                            if total_month and pas and pas <= line.buffer_qty + seg.safety_stock_month * (total_fmc / total_month):
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
                                wmsg = _('SODate of linked product is %s') % (self.pool.get('date.tools').get_date_formatted(cr, uid, datetime=replaced_lack.strftime('%Y-%m-%d'), context=context))
                                warnings.append(wmsg)
                                warnings_html.append('<span title="%s">%s</span>'  % (misc.escape_html(wmsg), misc.escape_html(_('Replaced SO'))))

                        if lacking:
                            qty_lacking_needed_by = today + relativedelta(days=month_of_supply*30.44)
                            if review_id:
                                lacking_by_prod[line.product_id.id] = qty_lacking_needed_by
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
                    for fmc_d in range(1, 19):
                        from_fmc = getattr(line, 'rr_fmc_from_%d'%fmc_d)
                        to_fmc = getattr(line, 'rr_fmc_to_%d'%fmc_d)
                        min_x = getattr(line, 'rr_fmc_%d'%fmc_d)
                        max_x = getattr(line, 'rr_max_%d'%fmc_d)
                        if from_fmc and to_fmc:
                            from_fmc = datetime.strptime(from_fmc, '%Y-%m-%d')
                            to_fmc = datetime.strptime(to_fmc, '%Y-%m-%d')

                            if review_id:
                                if from_fmc <= today <= to_fmc:
                                    min_qty = min_x
                                    max_qty = max_x
                                    break
                            else:
                                if oc >= from_fmc and rdd <= to_fmc:
                                    min_qty = max(min_qty, min_x)
                                    max_qty = max(max_qty, max_x)
                        elif fmc_d == 1:
                            min_qty = min_x
                            max_qty = max_x
                            break

                    valid_line = isinstance(min_qty, (int, float)) and isinstance(max_qty, (int, float)) and max_qty >= min_qty
                    qty_lacking = False
                    if line.status in ('phasingout', 'replaced'):
                        proposed_order_qty = 0
                    elif valid_line:
                        proposed_order_qty = max(0, max_qty - sum_line.get(line.id, {}).get('real_stock') + sum_line.get(line.id, {}).get('reserved_stock_qty') + sum_line.get(line.id, {}).get('expired_qty_before_eta', 0) - line.pipeline_before_rdd)

                        qty_lacking = min(sum_line.get(line.id, {}).get('real_stock') - sum_line.get(line.id, {}).get('expired_qty_before_eta') - min_qty, 0)
                        if line.status != 'new' and sum_line.get(line.id, {}).get('real_stock') - sum_line.get(line.id, {}).get('expired_qty_before_eta') <= min_qty:
                            if sum_line.get(line.id, {}).get('expired_qty_before_eta'):
                                wmsg = _('Alert: "inventory – batches expiring before ETA <= Min"')
                                warnings.append(wmsg)
                                warnings_html.append('<span title="%s">%s</span>' % (misc.escape_html(wmsg), misc.escape_html(_('Expiries'))))
                            else:
                                wmsg = _('Alert: "inventory <= Min"')
                                warnings.append(wmsg)
                                warnings_html.append('<span title="%s">%s</span>' % (misc.escape_html(wmsg), misc.escape_html(_('Insufficient'))))
                else:
                    for fmc_d in range(1, 19):
                        from_fmc = getattr(line, 'rr_fmc_from_%d'%fmc_d)
                        to_fmc = getattr(line, 'rr_fmc_to_%d'%fmc_d)
                        auto_x = getattr(line, 'rr_fmc_%d'%fmc_d)
                        if from_fmc and to_fmc:
                            from_fmc = datetime.strptime(from_fmc, '%Y-%m-%d')
                            to_fmc = datetime.strptime(to_fmc, '%Y-%m-%d')

                            if review_id:
                                if from_fmc <= today <= to_fmc:
                                    auto_qty = auto_x
                                    break
                            else:
                                if oc >= from_fmc and rdd <= to_fmc:
                                    auto_qty = max(auto_qty, auto_x)
                        elif fmc_d == 1:
                            auto_qty = auto_x
                            break

                    valid_line = isinstance(auto_qty, (int, float))
                    if line.status in ('phasingout', 'replaced'):
                        proposed_order_qty = 0
                    else:
                        proposed_order_qty = auto_qty or 0

                if not valid_rr_fmc:
                    wmsg = _('Invalid FMC')
                    warnings.append(wmsg)
                    warnings_html.append('<span title="%s">%s</span>' % (misc.escape_html(wmsg), misc.escape_html(_('FMC'))))

                if line.status != 'phasingout':
                    if review_id and month_of_supply and month_of_supply*30.44 > (seg_rdd-today).days + line.segment_id.safety_stock_month*30.44 + self.convert_time_unit(seg.order_coverage, seg.time_unit_lt, 'd'):
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
                    'expired_qty_before_eta': False if seg.rule == 'cycle' else round(sum_line.get(line.id, {}).get('expired_qty_before_eta',0)),
                    'warning': False,
                    'warning_html': False,
                    'valid_rr_fmc': valid_line,
                    'status': line.status,
                    'open_loan': sum_line.get(line.id, {}).get('open_loan', False),
                    'open_donation': sum_line.get(line.id, {}).get('open_donation', False),
                    'auto_qty': auto_qty if seg.rule =='auto' else False,
                    'buffer_ss_qty': False,
                    'min_max': '',
                }

                if seg.rule == 'cycle':
                    line_data['buffer_ss_qty'] = '%d / %s' % (line.buffer_qty or 0,  re.sub('\.?0+$', '', '%s' % (round(ss_stock, 2) or '0.0')))
                if seg.rule == 'minmax':
                    min_max_list = []
                    for v in [min_qty, max_qty]:
                        if v is False or v is None:
                            min_max_list.append('')
                        else:
                            min_max_list.append('%d'%v)
                    line_data['min_max'] = ' / '.join(min_max_list)

                # order_cacl
                if not review_id:
                    if warnings_html:
                        line_data['warning_html'] = '<img src="/openerp/static/images/stock/gtk-dialog-warning.png" title="%s" class="warning"/> <div>%s</div> ' % (misc.escape_html("\n".join(warnings)), "<br>".join(warnings_html))
                        line_data['warning'] = "\n".join(warnings)
                    line_data.update({
                        'order_calc_id': calc_id,
                        'rule': seg.rule,
                        'segment_id': seg.id,
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
                        'internal_lt': self.convert_time_unit(seg.internal_lt, seg.time_unit_lt, inv_unit),
                        'external_lt': self.convert_time_unit(seg.external_lt, seg.time_unit_lt, inv_unit),
                        'total_lt': self.convert_time_unit(seg.total_lt, seg.time_unit_lt, inv_unit),
                        'order_coverage': self.convert_time_unit(seg.order_coverage, seg.time_unit_lt, inv_unit),
                        'primay_product_list': line.in_main_list and seg.product_list_id.name,
                        'rule': seg.rule,
                        'min_qty': min_qty,
                        'max_qty': max_qty,
                        'safety_stock_qty': ss_stock and round(ss_stock, 2) or False,
                        'buffer_qty': line.buffer_qty or False,
                        'pas_ids': detailed_pas,
                        'segment_line_id': line.id,
                        'sleeping_qty': round(sum_line.get(line.id, {}).get('sleeping_qty',0)),
                        'std_dev_hmc': std_dev_hmc,
                        'coef_var_hmc': amc and 100 * std_dev_hmc/amc or False,
                        #'avg_error_hmc_fmc': avg_error_hmc_fmc,
                        'std_dev_hmc_fmc': std_dev_hmc_fmc,
                        'coef_var_hmc_fmc': coef_var_hmc_fmc,
                        'missing_exp': sum_line.get(line.id, {}).get('missing_exp', False),
                    })
                    if sum_line.get(line.id, {}).get('missing_exp', False):
                        wmsg = _('Missing data on expiring products')
                        warnings.append(wmsg)
                        warnings_html.append('<span title="%s">%s</span>' % (misc.escape_html(wmsg), misc.escape_html(_('Missing Exp.'))))

                    if review_id and line_data['coef_var_hmc_fmc'] and line_data['coef_var_hmc_fmc'] > line.segment_id.location_config_id.alert_threshold_deviation:
                        wmsg = _('Variation of HMC/FMC')
                        warnings.append(wmsg)
                        warnings_html.append('<span title="%s">%s</span>' % (misc.escape_html(wmsg), misc.escape_html(_('HMC/FMC Dev.'))))

                    if warnings_html:
                        line_data['warning_html'] = '<img src="/openerp/static/images/stock/gtk-dialog-warning.png" height="16" title="%s" class="warning"/> <div>%s</div> ' % (misc.escape_html("\n".join(warnings)), "<br>".join(warnings_html))
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
                    cr.execute('''insert into replenishment_inventory_review_line_exp (review_line_id, date, instance_id, exp_qty, expiry_line_id, name)
                        select review_line.id, exp.month, amc.instance_id, exp.quantity, exp.expiry_line_id, exp.name from
                            replenishment_inventory_review_line review_line
                            left join replenishment_segment_line_amc amc on amc.segment_line_id = review_line.segment_line_id
                            left join replenishment_segment_line seg_line on seg_line.id = review_line.segment_line_id
                            left join replenishment_segment_line_amc_month_exp exp on exp.line_amc_id = amc.id
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
        ids = isinstance(ids, int) and [ids] or ids
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
            file_data = SpreadsheetXML(xmlstring=base64.b64decode(seg.file_to_import))

            existing_line = {}
            for line in seg.line_ids:
                existing_line[line.product_id.default_code] = line.id

            idx = -1

            status = dict([(_(x[1]), x[0]) for x in life_cycle_status])
            error = []
            code_created = {}
            created = 0
            updated = 0
            ignored = 0
            specific_period = True

            for row in file_data.getRows():
                cr.execute("SAVEPOINT seg_line")
                try:
                    idx += 1
                    if idx < 10:
                        # header
                        if idx == 6:
                            if seg.rule != 'cycle' and len(row.cells) > 0:
                                specific_period = row.cells[1].data in (_('Yes'), 'Yes', 'Oui')
                            if len(row.cells) > 4 and row.cells[4].data and {'cycle': _('Order Cycle'), 'minmax': _('Min/Max'), 'auto': _('Automatic Supply')}.get(seg.rule, '').strip().lower() != row.cells[4].data.strip().lower():
                                self.write(cr, uid, seg.id, {'file_to_import': False}, context=context)
                                return wizard_obj.message_box_noclose(cr, uid, title=_('Importation errors'), message=_('Header cell E7: Replenishment Rule on file: "%s" does not match Segment: "%s".') % (row.cells[4].data, {'cycle': _('Order Cycle'), 'minmax': _('Min/Max'), 'auto': _('Automatic Supply')}.get(seg.rule, '')))
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
                    }
                    for fmc in range(1, 19):
                        data_towrite.update({
                            'rr_fmc_from_%d' % fmc: False,
                            'rr_fmc_to_%d' % fmc: False,
                        })
                        if seg.rule == 'minmax':
                            data_towrite['rr_min_max_%d' % fmc] = False
                        else:
                            data_towrite['rr_fmc_%d' % fmc] = False


                    col_replacing = 4
                    col_replaced = 5
                    col_buffer_min_qty = 8

                    if seg.rule == 'cycle':
                        col_first_fmc = 9
                    else:
                        col_first_fmc = 8

                    if cells_nb > col_replacing and row.cells[col_replacing].data and row.cells[col_replacing].data.strip():
                        if data_towrite['status'] not in  ('replaced', 'phasingout'):
                            line_error.append(_('Line %d: you can not set a Replacing product on this line, please change the satus or remove the replacing product') % (idx+1, ))
                        else:
                            replacing_id = product_obj.search(cr, uid, [('default_code', '=ilike', row.cells[col_replacing].data.strip())], context=context)
                            if not replacing_id:
                                line_error.append(_('Line %d: replacing product code %s not found') % (idx+1, row.cells[col_replacing].data))
                            elif row.cells[col_replacing].data.strip().lower() == prod_code.lower():
                                line_error.append(_('Line %d: product code %s you can\'t replace a product by itself !') % (idx+1, prod_code))
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
                            elif row.cells[col_replaced].data.strip().lower() == prod_code.lower():
                                line_error.append(_('Line %d: product code %s you can\'t replace a product by itself !') % (idx+1, prod_code))
                            else:
                                data_towrite['replaced_product_id'] = replaced_id[0]
                    elif data_towrite['status'] in ('replacing', 'activereplacing') and not data_towrite['replaced_product_id']:
                        line_error.append(_('Line %d: replaced product must be set !') % (idx+1, ))


                    if cells_nb > col_buffer_min_qty and seg.rule == 'cycle':
                        if row.cells[col_buffer_min_qty].data and not isinstance(row.cells[col_buffer_min_qty].data, (int, float)):
                            line_error.append(_('Line %d: Buffer Qty must be a number, found %s') % (idx+1, row.cells[col_buffer_min_qty].data))
                        else:
                            data_towrite['buffer_qty'] = row.cells[col_buffer_min_qty].data
                    no_data = False

                    fisrt_period = False
                    for fmc in range(1, 19):
                        if cells_nb - 1 >=  col_first_fmc and row.cells[col_first_fmc].data is not None and row.cells[col_first_fmc].data not in ('', ' / ', '/'):
                            if no_data:
                                line_error.append(_('Line %d: RR-Value %s cannot be empty') % (idx+1, no_data))
                                col_first_fmc += 2
                                continue

                            from_data = False
                            fmc_data = row.cells[col_first_fmc].data
                            if isinstance(fmc_data, str):
                                fmc_data = fmc_data.strip()
                            if fmc == 1:
                                if seg.rule == 'cycle' or cells_nb - 1 >= col_first_fmc+1 and row.cells[col_first_fmc+1].data:
                                    if cells_nb - 1 < col_first_fmc+1:
                                        line_error.append(_('Line %d: FROM %d, date expected') % (idx+1, fmc))
                                        col_first_fmc += 2
                                        continue
                                    if not row.cells[col_first_fmc+1].type == 'datetime':
                                        line_error.append(_('Line %d: FROM %d, date is not valid, found %s') % (idx+1, fmc, row.cells[col_first_fmc+1].data))
                                        col_first_fmc += 2
                                        continue
                                    from_data = row.cells[col_first_fmc+1].data.strftime('%Y-%m-%d')
                                    fisrt_period = True
                                col_first_fmc += 1
                            elif not specific_period and fmc_data and fmc_data != '/':
                                line_error.append(_('Line %d: you can not use periods if "Specific Periods Only" is defined to No.') % (idx+1, ))
                                col_first_fmc += 2
                                continue


                            if fisrt_period and cells_nb - 1 < col_first_fmc+1:
                                line_error.append(_('Line %d: TO %d, date expected') % (idx+1, fmc))
                                col_first_fmc += 2
                                continue
                            if fisrt_period and (not row.cells[col_first_fmc+1].data or row.cells[col_first_fmc+1].type != 'datetime'):
                                line_error.append(_('Line %d: TO %d, date is not valid, found %s') % (idx+1, fmc, row.cells[col_first_fmc+1].data))
                                col_first_fmc += 2
                                continue
                            if seg.rule != 'minmax' and not isinstance(fmc_data, (int, float)):
                                line_error.append(_('Line %d: %d, number expected, found %s') % (idx+1, fmc, fmc_data))
                                col_first_fmc += 2

                            if fmc > 1 and not fisrt_period and (fmc_data and fmc_data != '/' or row.cells[col_first_fmc+1].data):
                                line_error.append(_('Line %d: you can not define a RR-Value %d if the previous period is blank.') % (idx+1, fmc))
                                break

                            if not specific_period and (from_data or row.cells[col_first_fmc+1].data):
                                line_error.append(_('Line %d: you can not use periods if "Specific Periods Only" is defined to No.') % (idx+1, ))
                                break

                            data_towrite.update({
                                'rr_fmc_from_%d' % fmc:from_data,
                                'rr_fmc_to_%d' % fmc: row.cells[col_first_fmc+1].data and row.cells[col_first_fmc+1].data.strftime('%Y-%m-%d'),
                            })
                            if seg.rule =='minmax':
                                data_towrite['rr_min_max_%d' % fmc] = fmc_data
                            else:
                                data_towrite['rr_fmc_%d' % fmc] = fmc_data

                        else:
                            no_data = fmc
                        col_first_fmc += 2

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
                except osv.except_osv as e:
                    error.append(_('Line %d: %s') % (idx+1, misc.ustr(e.value)))
                    ignored += 1
                    cr.execute("ROLLBACK TO SAVEPOINT seg_line")
                    continue
                cr.execute("RELEASE SAVEPOINT seg_line")

        except Exception as e:
            cr.rollback()
            return wizard_obj.message_box_noclose(cr, uid, title=_('Importation errors'), message=_("Unexpected error during import:\n%s") % (misc.get_traceback(e), ))

        self.write(cr, uid, seg.id, {'file_to_import': False}, context=context)
        if error:
            error.insert(0, _('%d line(s) created, %d line(s) updated, %d line(s) in error') % (created, updated, ignored))
            return wizard_obj.message_box_noclose(cr, uid, title=_('Importation errors'), message='\n'.join(error))

        if seg.rule != 'cycle' and specific_period != seg.specific_period:
            self.write(cr, uid, seg.id, {'specific_period': specific_period}, context=context)

        return wizard_obj.message_box_noclose(cr, uid, title=_('Importation Done'), message=_('%d line(s) created, %d line(s) updated') % (created, updated))

    def remove_outdated_fmcs(self, cr, uid, ids, context=None):
        if not ids:
            return

        cr.execute('''
            delete from
                replenishment_segment_line_period p
            using
                replenishment_segment_line l
            where
                l.id = p.line_id and
                l.segment_id in %s and
                to_date < now()
            returning l.id
        ''', (tuple(ids), ))
        nb_fmc = cr.rowcount
        if not nb_fmc:
            self.pool.get('res.log').create(cr, uid, {'name': _('No outdated FMC')}, context=context)
            return True
        nb_line = len(set([x[0] for x in cr.fetchall()]))
        self.pool.get('res.log').create(cr, uid, {'name': _('%d FMC(s) removed on %d line(s)') % (nb_fmc, nb_line)}, context=context)
        # no sync needed
        return True

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
        for _id in ids:
            self.pool.get('replenishment.segment.line')._check_overlaps(cr, uid, segment_ids=[_id], context=context)
        return True


    def check_inprogress_order_calc(self, cr, uid, ids, context=None):
        calc_obj = self.pool.get('replenishment.order_calc')
        for seg in self.browse(cr, uid, ids, fields_to_fetch=['parent_id'], context=context):
            calc_ids = calc_obj.search(cr, uid, [('parent_segment_id', '=', seg.parent_id.id), ('state', 'not in', ['cancel', 'closed'])], context=context)
            if calc_ids:
                calc_name = calc_obj.read(cr, uid, calc_ids, ['name'], context=context)
                raise osv.except_osv(_('Warning'), _('Please cancel or close the following Order Calc:\n%s') % (', '.join([x['name'] for x in calc_name])))

    def set_as_archived(self, cr, uid, ids, context=None):
        self.check_inprogress_order_calc(cr, uid, ids, context=context)
        self.write(cr, uid, ids, {'state': 'archived'}, context=context)
        return True

    def reset_gen_date(self, cr, uid, ids, set_draft=True,context=None):
        # reset last gen
        last_gen_obj = self.pool.get('replenishment.segment.date.generation')
        last_gen_ids = last_gen_obj.search(cr, uid, [('segment_id', 'in', ids)], context=context)
        if last_gen_ids:
            last_gen_obj.write(cr, uid, last_gen_ids, {'full_date': False, 'review_date': False}, context=context)
        data = {'last_review_date': False}
        if set_draft:
            data['state'] = 'draft'
        self.write(cr, uid, ids, data, context=context)

    def set_as_draft(self, cr, uid, ids, context=None):
        self.check_inprogress_order_calc(cr, uid, ids, context=context)
        self.reset_gen_date( cr, uid, ids, set_draft=True, context=context)
        return True

    def set_as_cancel(self, cr, uid, ids, context=None):
        self.check_inprogress_order_calc(cr, uid, ids, context=context)
        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
        return True

    def save_past_fmc(self, cr, uid, ids, rule, max_date, context=None):
        for _id in ids:
            cr.execute('select period.* from replenishment_segment_line_period period, replenishment_segment_line line where period.line_id = line.id and line.segment_id = %s and from_date < %s order by period.line_id, from_date', (_id, max_date))
            for x in cr.dictfetchall():
                to_update = {}
                from_fmc = x['from_date']
                to_fmc = x['to_date']
                num_fmc = x['value']
                if rule == 'minmax':
                    max_fmc = x['max_value']
                if (not from_fmc or from_fmc == '2020-01-01') and (not to_fmc or to_fmc == '2222-02-28') and num_fmc is not False:
                    upper = max_date.strftime('%Y-%m-%d')
                    key = datetime.now() + relativedelta(day=1)
                else:
                    upper = min(to_fmc, max_date.strftime('%Y-%m-%d'))
                    key = datetime.strptime(from_fmc, '%Y-%m-%d')

                while key.strftime('%Y-%m-%d') <= upper:
                    if rule == 'minmax':
                        to_update[key.strftime('%Y-%m-%d')] = '%g / %g' % (num_fmc or 0, max_fmc or 0)
                    else:
                        to_update[key.strftime('%Y-%m-%d')] = num_fmc
                    key+=relativedelta(months=1)

                if to_update:
                    for month in to_update:
                        if rule == 'minmax':
                            cr.execute("""insert into replenishment_segment_line_amc_past_fmc
                                (segment_line_id, month, minmax) values (%s, %s, %s)
                                ON CONFLICT ON CONSTRAINT replenishment_segment_line_amc_past_fmc_unique_seg_month DO UPDATE SET minmax=EXCLUDED.minmax
                            """, (x['line_id'], month, to_update[month]))

                        else:
                            cr.execute("""insert into replenishment_segment_line_amc_past_fmc
                                (segment_line_id, month, fmc) values (%s, %s, %s)
                                ON CONFLICT ON CONSTRAINT replenishment_segment_line_amc_past_fmc_unique_seg_month DO UPDATE SET fmc=EXCLUDED.fmc
                            """, (x['line_id'], month, to_update[month]))

        return True


    def open_history(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
            ids = [ids]

        seg = self.browse(cr, uid, ids[0], fields_to_fetch=['rule', 'name_seg'], context=context)
        view_id = []
        if seg.rule == 'minmax':
            view_id = [self.pool.get('ir.model.data').get_object_reference(cr, uid,  'procurement_cycle', 'replenishment_segment_line_amc_past_minmax_tree')[1]]

        return {
            'name': 'History %s' % (seg.name_seg, ),
            'type': 'ir.actions.act_window',
            'res_model': 'replenishment.segment.line.amc.past_fmc',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'domain': [('segment_id', '=', seg.id), ('month', '<=', time.strftime('%Y-%m-%d'))],
            'view_id': view_id,
        }

    def change_parent_id(self, cr, uid, ids, parent_id, context=None):
        to_populate = [
            'location_config_id', 'time_unit_lt', 'total_lt', 'internal_lt', 'external_lt', 'order_preparation_lt', 'description_parent_seg',
            'order_creation_lt', 'order_validation_lt', 'supplier_lt', 'handling_lt', 'previous_order_rdd', 'date_preparing',
            'date_next_order_validated', 'date_next_order_received', 'date_next_order_received_modified', 'order_coverage',
            'description', 'ir_requesting_location'
        ]
        values = {}
        if not parent_id:
            for f in to_populate:
                values[f] = False
        else:
            parent_data = self.pool.get('replenishment.parent.segment').read(cr, uid, parent_id, to_populate, context=context)
            for f in to_populate:
                values[f] = parent_data[f]
        return {'value': values}
replenishment_segment()

class replenishment_segment_line_period(osv.osv):
    _name = 'replenishment.segment.line.period'
    _desciption = 'RR Periods'
    _rec_name = 'from_date'

    _columns = {
        'line_id': fields.many2one('replenishment.segment.line', 'Segment Line', on_delete='cascade', select=1),
        'value': fields.float_null('Value'),
        'max_value': fields.float_null('Max value', help='Only used for min/max'),
        'from_date': fields.date('From', select=1),
        'to_date': fields.date('To', select=1),
    }
replenishment_segment_line_period()

class replenishment_segment_line(osv.osv):
    _name = 'replenishment.segment.line'
    _description = 'Product'
    _rec_name = 'product_id'
    _order = 'product_id, segment_id'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        view = super(replenishment_segment_line, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if context is None:
            context = {}
        if view_type in ('form', 'tree'):
            arch = etree.fromstring(view['arch'])

            if view_type == 'form':
                # editable only view, click on button to open 18 periods does set rule and specific_period in context
                readonly = ' readonly="0"'
                if 'rule' not in context and context.get('active_id'):
                    seg = self.pool.get('replenishment.segment').browse(cr, uid, context['active_id'], fields_to_fetch=['rule', 'specific_period'], context=context)
                    context['rule'] = seg.rule
                    context['specific_period'] = seg.specific_period
                    readonly = ' readonly="1" '

                added = '''<group colspan="4" col="4">
                    <separator string="%s" colspan="2" />
                    <separator string="From" colspan="1" />
                    <separator string="To" colspan="1" />
                    <newline />
                ''' % context.get('rule')


                if context.get('rule') in ('cycle', 'auto'):
                    added += '''<field name="rr_fmc_1" %s string="%s 1"/>''' % (readonly or 'readonly="0"', context.get('rule') == 'cycle' and _('RR FMC') or _('Auto Supply'))
                elif context.get('rule') == 'minmax':
                    added += '''<field name="rr_min_max_1" %s />''' % (readonly or 'readonly="0"')

                if context.get('rule') == 'cycle' or context.get('specific_period'):
                    if context.get('rule') == 'minmax':
                        added += '''
                            <field name="rr_fmc_from_1" attrs="{'required': [('rr_min_max_1', '!=', False), ('rr_min_max_1', '!=', ' / ')]}" on_change="change_fmc('from', '1', rr_fmc_from_1, False)"  nolabel="1" %(readonly)s/>
                            <field name="rr_fmc_to_1" attrs="{'required': [('rr_min_max_1', '!=', False), ('rr_min_max_1', '!=', ' / ')]}" on_change="change_fmc('to', '1', rr_fmc_to_1, True)" nolabel="1" depends="rr_fmc_from_1" %(readonly)s/>
                        ''' % {'readonly': readonly}

                    else:
                        added += '''
                            <field name="rr_fmc_from_1" attrs="{'required': [('rr_fmc_1', '!=', False)]}" on_change="change_fmc('from', '1', rr_fmc_from_1, False)"  nolabel="1" %(readonly)s/>
                            <field name="rr_fmc_to_1" attrs="{'required': [('rr_fmc_1', '!=', False)]}" on_change="change_fmc('to', '1', rr_fmc_to_1, True)" nolabel="1" depends="rr_fmc_from_1" %(readonly)s/>
                        ''' % {'readonly': readonly}

                    for n in range(2, 19):
                        if context.get('rule') == 'minmax':
                            added += ''' <field name="rr_min_max_%(n)s" %(readonly)s /> ''' % {'n': n, 'readonly': readonly or 'readonly="0"'}
                            added += '''
                                <field name="rr_fmc_from_%(n)s" readonly="1" nolabel="1"/>
                                <field name="rr_fmc_to_%(n)s" attrs="{'required': [('rr_min_max_%(n)s', '!=', False), ('rr_min_max_%(n)s', '!=', ' / ')]}" on_change="change_fmc('to', '%(n)s', rr_fmc_to_%(n)s, True)" nolabel="1" depends="rr_fmc_to_%(n-1)s" %(readonly)s/>
                            ''' % {'n': n, 'n-1': n-1, 'readonly': readonly}
                        else:
                            added += ''' <field name="rr_fmc_%(n)s"  %(readonly)s string="%(label)s %(n)s" /> ''' % {'n': n, 'readonly': readonly, 'label': context.get('rule') == 'cycle' and _('RR FMC') or _('Auto Supply')}
                            added += '''
                                <field name="rr_fmc_from_%(n)s" readonly="1" nolabel="1"/>
                                <field name="rr_fmc_to_%(n)s" attrs="{'required': [('rr_fmc_%(n)s', '!=', False)]}" on_change="change_fmc('to', '%(n)s', rr_fmc_to_%(n)s, True)" nolabel="1" depends="rr_fmc_to_%(n-1)s" %(readonly)s/>
                            ''' % {'n': n, 'n-1': n-1, 'readonly': readonly}

                    added += "</group>"
                    added_etree = etree.fromstring(added)
                    fields = arch.xpath('//group[@name="list_values"]')
                    parent_node = fields[0].getparent()
                    parent_node.remove(fields[0])
                    parent_node.append(added_etree)



            else: # tree view
                if context.get('rule') == 'minmax':
                    added = '''
                    <group>
                    <field name="rr_min_max_1" readonly="0" />
                    <field name="rr_fmc_from_1" readonly="0" invisible="not context.get('specific_period')" attrs="{'required': [('rr_min_max_2', '!=', False), ('rr_min_max_2', '!=', ' / ')]}" on_change="change_fmc('from', '1', rr_fmc_from_1, False)"  nolabel="1"/> 
                    <field name="rr_fmc_to_1" readonly="0" invisible="not context.get('specific_period')" attrs="{'required': [('rr_fmc_from_1', '!=', False)]}" on_change="change_fmc('to', '1', rr_fmc_to_1, False)" nolabel="1" depends="rr_fmc_from_1"/>
                    <field name="rr_min_max_2" readonly="0" invisible="not context.get('specific_period')" />
                    <field name="rr_fmc_to_2" readonly="0" invisible="not context.get('specific_period')" attrs="{'required': [('rr_min_max_2', '!=', False), ('rr_min_max_2', '!=', ' / ')]}" on_change="change_fmc('to', '2', rr_fmc_to_2, False)" nolabel="1" depends="rr_fmc_to_1"/>
                    <field name="rr_min_max_3" readonly="0" invisible="not context.get('specific_period')" />
                    <field name="rr_fmc_to_3" readonly="0" invisible="not context.get('specific_period')" attrs="{'required': [('rr_min_max_3', '!=', False), ('rr_min_max_3', '!=', ' / ')]}" on_change="change_fmc('to', '3', rr_fmc_to_3, False)" nolabel="1" depends="rr_fmc_to_2"/>
                    </group>
                    '''
                else:
                    added = '''
                    <group>
                    <field name="rr_fmc_1"  nolabel="1" string="%(label)s 1"  readonly="0"/>
                    <field name="rr_fmc_from_1" readonly="0" invisible="context.get('rule')!='cycle' and not context.get('specific_period')" attrs="{'required': [('rr_fmc_1', '!=', False), ('line_rule_parent', '=', 'cycle')]}" on_change="change_fmc('from', '1', rr_fmc_from_1, False)"  nolabel="1"/> 
                    <field name="rr_fmc_to_1" readonly="0" invisible="context.get('rule')!='cycle' and not context.get('specific_period')" attrs="{'required': ['&amp;', ('rr_fmc_1', '!=', False), '|', ('line_rule_parent', '=', 'cycle'), ('rr_fmc_from_1', '!=', False)]}" on_change="change_fmc('to', '1', rr_fmc_to_1, False)" nolabel="1" depends="rr_fmc_from_1"/>
                    <field name="rr_fmc_2" readonly="0" nolabel="1" string="%(label)s 2" invisible="context.get('rule')!='cycle' and (context.get('rule')!='auto' or not context.get('specific_period'))"/>
                    <field name="rr_fmc_to_2" readonly="0" invisible="context.get('rule')!='cycle' and not context.get('specific_period')" attrs="{'required': [('rr_fmc_2', '!=', False)]}" on_change="change_fmc('to', '2', rr_fmc_to_2, False)" nolabel="1" depends="rr_fmc_to_1"/>
                    <field name="rr_fmc_3" readonly="0" nolabel="1" string="%(label)s 3" invisible="context.get('rule')!='cycle' and (context.get('rule')!='auto' or not context.get('specific_period'))"/>
                    <field name="rr_fmc_to_3" readonly="0" invisible="context.get('rule')!='cycle' and not context.get('specific_period')" attrs="{'required': [('rr_fmc_3', '!=', False)]}" on_change="change_fmc('to', '3', rr_fmc_to_3, False)" nolabel="1" depends="rr_fmc_to_2"/>
                    </group>
                    ''' % {'label': context.get('rule') == 'cycle' and _('RR FMC') or _('Auto Supply')}

                added_etree = etree.fromstring(added)
                fields = arch.xpath('//group[@name="list_values"]')
                parent_node = fields[0].getparent()
                idx = parent_node.index(fields[0])
                for node in added_etree:
                    parent_node.insert(idx, node)
                    idx += 1

                parent_node.remove(fields[0])

            xarch, xfields = super(replenishment_segment_line, self)._view_look_dom_arch(cr, uid, arch, view_id, context=context)

            view['arch'] = xarch
            view['fields'] = xfields

        return view


    def _get_merge_minmax(self, cr, uid, ids, field_name, arg, context=None):
        if not ids:
            return {}

        if not context:
            context = {}

        ret = {}

        format_digit = lambda a: a
        if context.get('lang'):
            lang_obj_ids = self.pool.get('res.lang').search(cr, uid, [('code', '=', context['lang'])])
            if lang_obj_ids:
                lang_obj = self.pool.get('res.lang').browse(cr, uid, lang_obj_ids[0])
                format_digit = lambda a: lang_obj.format('%g', a, True)

        numbers = []
        get_min_max = False
        for f in field_name:
            if f.startswith('rr_min_max_'):
                get_min_max = True

            pattern = re.search('(\d+)$', f)
            if pattern:
                n = int(pattern.group(1))
                numbers.append(n)

        max_num = max(numbers)
        num = {}
        for _id in ids:
            ret[_id] = {}
            num[_id] = 0
            for x in range(1, max_num+1):
                ret[_id].update({'rr_fmc_from_%d' % x: False, 'rr_fmc_to_%d' % x: False, 'rr_fmc_%d' % x: None, 'rr_max_%d' % x: None, 'rr_min_max_%d' % x: ' / '})

        cr.execute("""
         select line_id, value, from_date, to_date, max_value
          from
            (select
                line_id, value, max_value, from_date, to_date, rank() OVER(PARTITION BY line_id ORDER BY from_date ASC) AS pos
            from
                replenishment_segment_line_period
            where
                line_id in %s
            ) AS s
         where pos <= %s
            """, (tuple(ids), max_num ))

        for x in cr.fetchall():
            num[x[0]] += 1
            if num[x[0]] == 1:
                if x[2] == '2020-01-01' and x[3] == '2222-02-28':
                    x = (x[0], x[1], False, False, x[4])

            ret[x[0]].update({'rr_fmc_%d' % num[x[0]]: x[1], 'rr_fmc_from_%d' % num[x[0]]: x[2], 'rr_fmc_to_%d' % num[x[0]]: x[3], 'rr_max_%d' % num[x[0]]: x[4]})
            if get_min_max:
                ret[x[0]].update({'rr_min_max_%d' % num[x[0]]: '%s / %s' % (isinstance(x[1], (int, float)) and format_digit(x[1]) or x[1], isinstance(x[4], (int, float)) and format_digit(x[4]) or x[4])})

        return ret

    def __init__(self, pool, cr):

        for x in range(1, 19):
            self._columns.update({
                'rr_fmc_%d' %x : fields.function(lambda self, *a, **b: self._get_merge_minmax(*a, **b), method=1, string="RR FMC %d" % x,  related_uom='uom_id', type='float',  digits=(16, 2), with_null=True, multi='merge_minmax', nodrop=1),
                'rr_fmc_from_%d' % x: fields.function(lambda self, *a, **b: self._get_merge_minmax(*a, **b), method=1, string="From %d" % x,  type='date', multi='merge_minmax', nodrop=1),
                'rr_fmc_to_%d' % x: fields.function(lambda self, *a, **b: self._get_merge_minmax(*a, **b), method=1, string="To %d" % x,  type='date', multi='merge_minmax', nodrop=1),
                'rr_max_%d' %x : fields.function(lambda self, *a, **b: self._get_merge_minmax(*a, **b), method=1, string="Max %d" % x,  related_uom='uom_id', type='float',  digits=(16, 2), with_null=True, multi='merge_minmax', nodrop=1),
                'rr_min_max_%d' % x: fields.function(lambda self, *a, **b: self._get_merge_minmax(*a, **b), method=1, string="Min / Max %d" % x, type='char', multi='merge_minmax'),
            })
        super(replenishment_segment_line, self).__init__(pool, cr)

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
                amc = prod_obj.compute_amc(cr, uid, list(segment[seg_id]['prod_seg_line'].keys()), segment[seg_id]['context'])
                for prod_id in amc:
                    ret[segment[seg_id]['prod_seg_line'][prod_id]]['rr_amc'] = amc[prod_id]

                for prod in prod_obj.browse(cr, uid, list(segment[seg_id]['prod_seg_line'].keys()), fields_to_fetch=['qty_available'], context={'location': segment[seg_id]['context']['amc_location_ids']}):
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
                    'to_date_oc': (rdd  + relativedelta(**normalize_td(x.segment_id.time_unit_lt,x.segment_id.order_coverage))).strftime('%Y-%m-%d'),
                    'prod_seg_line': {},
                    'location_ids': [l.id for l in x.segment_id.location_config_id.local_location_ids],
                }
            segment[x.segment_id.id]['prod_seg_line'][x.product_id.id] = x.id

        prod_obj = self.pool.get('product.product')
        for seg_id in segment:
            # compute_child ?
            if 'pipeline_before_rdd' in field_name:
                for prod_id in prod_obj.browse(cr, uid, list(segment[seg_id]['prod_seg_line'].keys()), fields_to_fetch=['incoming_qty'], context={'to_date': segment[seg_id]['to_date_rdd'], 'location': segment[seg_id]['location_ids']}):
                    ret[segment[seg_id]['prod_seg_line'][prod_id.id]]['pipeline_before_rdd'] =  prod_id.incoming_qty


            if not inv_review and 'pipeline_between_rdd_oc' in field_name:
                for prod_id in prod_obj.browse(cr, uid, list(segment[seg_id]['prod_seg_line'].keys()), fields_to_fetch=['incoming_qty'], context={'from_strict_date': segment[seg_id]['to_date_rdd'], 'to_date': segment[seg_id]['to_date_oc'], 'location': segment[seg_id]['location_ids']}):
                    ret[segment[seg_id]['prod_seg_line'][prod_id.id]]['pipeline_between_rdd_oc'] = prod_id.incoming_qty

        return ret

    def _get_list_fmc(self, cr, uid, ids, field_name, arg, context=None):
        ret = {}
        for id in ids:
            ret[id] = ""
        for line in self.browse(cr, uid, ids, context=context):
            add = []
            for x in range(4, 19):
                rr_fmc = getattr(line, 'rr_fmc_%d'%x)
                rr_from = getattr(line, 'rr_fmc_from_%d'%x)
                rr_to = getattr(line, 'rr_fmc_to_%d'%x)
                if rr_fmc is not None and rr_fmc is not False and rr_from and rr_to:
                    rr_from_dt = datetime.strptime(rr_from, '%Y-%m-%d')
                    rr_to_dt = datetime.strptime(rr_to, '%Y-%m-%d')
                    if rr_from_dt.year == rr_to_dt.year:
                        if rr_from_dt.month == rr_to_dt.month:
                            date_txt = '%s' % (misc.month_abbr[rr_from_dt.month])
                        else:
                            date_txt = '%s - %s' % (misc.month_abbr[rr_from_dt.month], misc.month_abbr[rr_to_dt.month])
                    else:
                        date_txt = '%s/%s - %s/%s' % (misc.month_abbr[rr_from_dt.month], rr_from_dt.year, misc.month_abbr[rr_to_dt.month], rr_to_dt.year)
                    if line.segment_id.rule == 'minmax':
                        max_value = getattr(line, 'rr_max_%d'%x) or 0
                        add.append("%s: %g/%g" % (date_txt, round(rr_fmc), round(max_value)))
                    else:
                        add.append("%s: %g" % (date_txt, round(rr_fmc)))
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
        'line_state_parent': fields.related('segment_id', 'state', string='Segment Status', type='char', readonly=True, write_relate=False),
        'line_rule_parent': fields.related('segment_id', 'rule', string='Segment Rule', type='char', readonly=True, write_relate=False),
        'product_id': fields.many2one('product.product', 'Product Code', select=1, required=1),
        'product_description': fields.related('product_id', 'name',  string='Description', type='char', size=64, readonly=True, select=True, write_relate=False),
        'uom_id': fields.related('product_id', 'uom_id',  string='UoM', type='many2one', relation='product.uom', readonly=True, select=True, write_relate=False),
        'in_main_list': fields.function(_get_main_list, type='boolean', method=True, string='Prim. prod. list'),
        'status_tooltip': fields.function(_get_status_tooltip, type='char', method=True, string='Paired product'),
        'display_paired_icon': fields.function(_get_display_paired_icon, type='boolean', method=True, string='Display paired icon'),
        'status': fields.selection(life_cycle_status, string='RR Lifecycle'),
        'min_qty': fields.float_null('Min Qty (deprecated)', related_uom='uom_id', digits=(16, 2)),
        'max_qty': fields.float_null('Max Qty (deprecated)', related_uom='uom_id', digits=(16, 2)),
        'auto_qty': fields.float_null('Auto. Supply Qty (deprecated)', related_uom='uom_id', digits=(16, 2)),
        'buffer_qty': fields.float_null('Buffer Qty', related_uom='uom_id', digits=(16, 2)),
        'real_stock': fields.function(_get_real_stock, type='float', method=True, related_uom='uom_id', string='Real Stock', multi='get_stock_amc'),
        'pipeline_before_rdd': fields.function(_get_pipeline_before, type='float', method=True, string='Pipeline Before RDD', multi='get_pipeline_before'),
        'pipeline_between_rdd_oc': fields.function(_get_pipeline_before, type='float', method=True, string='Pipeline between RDD and OC', multi='get_pipeline_before'),
        'rr_amc': fields.function(_get_real_stock, type='float', method=True, string='RR-AMC', multi='get_stock_amc'),
        'list_fmc': fields.function(_get_list_fmc, method=1, type='char', string='more FMC'),
        'replacing_product_id': fields.many2one('product.product', 'Replacing product', select=1),
        'replaced_product_id': fields.many2one('product.product', 'Replaced product', select=1),
        'warning': fields.function(_get_warning, method=1, string='Warning', multi='get_warn', type='text'),
        'warning_html': fields.function(_get_warning, method=1, string='Warning', multi='get_warn', type='text'),
        'fmc_version': fields.char('FMC timestamp', size=64, select=1),
    }


    def _delete_line_in_hidden_seg(self, cr, uid, ids, context=None):
        # delete line in hidden seg
        cr.execute('''
           delete from replenishment_segment_line where id in (
            select line.id from replenishment_segment_line line
                inner join replenishment_segment seg on seg.id = line.segment_id
                inner join replenishment_parent_segment parent_seg on parent_seg.id = seg.parent_id
                where
                    parent_seg.hidden = 't' and
                    (product_id, parent_seg.location_config_id) in
                    (select product_id, parent_seg2.location_config_id from replenishment_segment_line l2, replenishment_segment seg2, replenishment_parent_segment parent_seg2 where parent_seg2.id=seg2.parent_id and l2.id in %s and seg2.id = l2.segment_id and parent_seg2.hidden = 'f')
            )
            ''', (tuple(ids), ))
        return True

    def _check_overlaps(self, cr, uid, line_ids=False, segment_ids=False, context=None):
        if line_ids:
            ids = line_ids
            cond = 'orig_seg_line.id'
        elif segment_ids:
            ids = segment_ids
            cond = 'orig_seg_line.segment_id'
        else:
            return True
        cr.execute('''
        select prod.default_code, array_agg(distinct(seg.name_seg)), array_agg(distinct(orig_period.to_date))
             from
                replenishment_segment_line orig_seg_line,
                replenishment_segment orig_seg,
                replenishment_segment_line_period orig_period,
                replenishment_parent_segment orig_parent_seg,
                replenishment_segment_line seg_line,
                replenishment_segment seg,
                replenishment_parent_segment parent_seg,
                replenishment_segment_line_period period,
                product_product prod
             where
                 ''' + cond + ''' in (%s) and
                 orig_seg_line.segment_id = orig_seg.id and
                 orig_seg_line.product_id = seg_line.product_id and
                 orig_period.line_id = orig_seg_line.id and
                 orig_seg.parent_id = orig_parent_seg.id and
                 period.line_id = seg_line.id and
                 ( coalesce(orig_period.value, 0) != 0 or  coalesce(orig_period.max_value, 0) != 0 ) and
                 ( coalesce(period.value, 0) != 0 or  coalesce(period.max_value, 0) != 0 ) and
                 (orig_period.from_date, orig_period.to_date) overlaps (period.from_date, period.to_date) and
                 seg_line.segment_id = seg.id and
                 seg.state = 'complete' and
                 orig_seg.state = 'complete' and
                 seg.parent_id = parent_seg.id and
                 prod.id = seg_line.product_id and
                 orig_seg_line.segment_id != seg.id and
                 orig_parent_seg.location_config_id = parent_seg.location_config_id
                 group by prod.default_code, parent_seg.location_config_id
        ''', (tuple(ids), )) # not_a_user_entry

        error = []
        no_date = date(2222, 2, 28)
        for x in cr.fetchall():
            error.append('%s : %s (period to: %s)' % (x[0], " - ".join(x[1]), ' - '.join([z != no_date and z.strftime('%d/%m/%Y') or '-' for z in x[2]])))
            if len(error) > 10:
                error.append('%d more lines' % (len(error) - 10))
                break

        if error:
            raise osv.except_osv(_('Warning'), "The following product(s) have an overlapping setting in segment. Please adapt coverage periods:\n%s" % "\n".join(error))
        return True

    _constraints = [
        (_delete_line_in_hidden_seg, 'Remove from hidden', []),
    ]

    _sql_constraints = [
        ('uniq_segment_id_product_id', 'unique(segment_id, product_id)', 'Product already set in this segment')
    ]

    _defaults = {
        'status': 'active',
        'line_state_parent': 'draft',
        'line_rule_parent': lambda self, cr, uid, c: c and c.get('rule'),
    }

    def _set_merge_minmax(self, cr, uid, vals, context=False):
        '''
            method to split the single field rr_min_max_XX into rr_fmc_XX and rr_max_XX
        '''
        decimal = False
        thousands = False
        if context.get('lang'):
            cr.execute('select decimal_point,thousands_sep from res_lang where code=%s', (context['lang'], ))
            decimal, thousands = cr.fetchone()

        for x in range(1, 19):
            if 'rr_min_max_%d' % x in vals:

                value = vals['rr_min_max_%d' % x]
                if value:
                    value = value.strip()
                if not value or value == '/':
                    vals['rr_fmc_%d'% x] = False
                    vals['rr_max_%d' % x] = False
                elif '/' not in value:
                    raise osv.except_osv(_('Error !'), _('Invalid Min / Max %d value') % x)
                else:
                    if decimal and decimal != '.':
                        value = value.replace(decimal, '.')
                    if thousands:
                        value = value.replace(thousands, '')

                    value_split = value.split('/')
                    min_value = None
                    max_value = None
                    try:
                        if value_split[0]:
                            min_v = value_split[0].strip()
                            if min_v:
                                min_value = float(min_v)
                    except:
                        raise osv.except_osv(_('Error !'), _('Invalid Min %d value %s') % (x, value_split[0]))

                    try:
                        if value_split[1]:
                            max_v = value_split[1].strip()
                            if max_v:
                                max_value = float(max_v)
                    except:
                        raise osv.except_osv(_('Error !'), _('Invalid Max %d value %s') % (x, value_split[1]))

                    if min_value is not None and max_value is not None and min_value > max_value:
                        raise osv.except_osv(_('Error !'), _('Invalid Min / Max %d value') % x)
                    vals['rr_fmc_%d'% x] = min_value
                    vals['rr_max_%d' % x] = max_value

    def _raise_error(self, cr ,uid, vals, msg, context=None):
        if vals.get('product_id'):
            prod = self.pool.get('product.product').browse(cr, uid, vals['product_id'], fields_to_fetch=['default_code'], context=context)
            raise osv.except_osv(_('Error !'), '%s %s' % (prod.default_code, msg))

        raise osv.except_osv(_('Error !'), msg)


    def _clean_data(self, cr, uid, vals, context=None):
        if vals and 'status' in vals:
            if vals['status'] not in  ('replacing', 'activereplacing'):
                vals['replaced_product_id'] = False
            if vals['status'] not in  ('replaced', 'phasingout'):
                vals['replacing_product_id'] = False

        if context and context.get('sync_update_execution'):
            # manage migration: in-pipe updates between UF23.0 and UF24.0
            if vals.get('auto_qty') and not vals.get('rr_fmc_1'):
                vals['rr_fmc_1'] = vals['auto_qty']
            elif (vals.get('min_qty') or vals.get('max_qty')) and not vals.get('rr_fmc_1') and not vals.get('rr_max_1'):
                vals['rr_fmc_1'] = vals['min_qty']
                vals['rr_max_1'] = vals['max_qty']
        else:
            self._set_merge_minmax(cr, uid, vals, context)

        if vals.get('rr_fmc_1') is not False and vals.get('rr_fmc_1') is not None and not vals.get('rr_fmc_from_1') and not vals.get('rr_fmc_to_1'):
            vals['rr_fmc_from_1'] = '2020-01-01'
            vals['rr_fmc_to_1'] = '2222-02-28'

        for x in range(1, 18):
            if x == 1:
                if vals.get('rr_fmc_from_1') and vals.get('rr_fmc_to_1') and vals['rr_fmc_from_1'] > vals['rr_fmc_to_1']:
                    self._raise_error(cr, uid, vals, _('FROM 1 must be before TO 1'), context)
                if bool(vals.get('rr_fmc_from_1')) != bool(vals.get('rr_fmc_to_1')):
                    self._raise_error(cr, uid, vals, _('FROM 1 / TO 1: please fill or empty both values'), context)
                if vals.get('rr_fmc_from_1'):
                    rr_from = datetime.strptime(vals['rr_fmc_from_1'], '%Y-%m-%d')
                    if rr_from.day != 1:
                        self._raise_error(cr, uid, vals, _('FROM 1 must start the 1st day of the month'), context)

            if vals.get('rr_fmc_to_%d'%x):
                rr_to = datetime.strptime(vals['rr_fmc_to_%d'%x], '%Y-%m-%d')
                if rr_to + relativedelta(months=1, day=1, days=-1) != rr_to:
                    self._raise_error(cr, uid, vals,  _('TO %d must be the last day of the month') % (x,), context)

                try:
                    if vals.get('rr_fmc_to_%d' % (x+1)):
                        vals['rr_fmc_from_%d'%(x+1)] = (datetime.strptime(vals['rr_fmc_to_%d'%x], '%Y-%m-%d') + relativedelta(days=1)).strftime('%Y-%m-%d')
                except:
                    pass
                if x > 1 and vals.get('rr_fmc_to_%d' % x) <= vals.get('rr_fmc_to_%d' % (x-1)):
                    self._raise_error(cr, uid, vals, _('TO %d must be before TO %d') % (x-1, x), context)

    def _set_period(self, cr, uid, ids, vals, context=None):
        '''
            store periods in dedicated table replenishment_segment_line_period
        '''


        # if cycle: compute and compare values before and after
        cycle_line_state = {}
        all_fields = []
        cr.execute("select line.id, seg.state from replenishment_segment seg, replenishment_segment_line line where line.segment_id = seg.id and seg.rule = 'cycle'")
        for x in cr.fetchall():
            cycle_line_state[x[0]] = x[1]
        for x in range(1, 19):
            all_fields+=['rr_fmc_%d' % x, 'rr_fmc_from_%d' % x, 'rr_fmc_to_%d' % x]

        for _id in ids:
            p_ids = []
            cr.execute("select id from replenishment_segment_line_period where line_id=%s order by from_date", (_id, ))
            p_ids = [x[0] for x in cr.fetchall()]

            for x in range(1, 19):
                if 'rr_fmc_%d' % x in vals or 'rr_fmc_from_%d' % x in vals or 'rr_fmc_to_%d' % x in vals or 'rr_max_%d' % x in vals:
                    if vals.get('rr_fmc_%d' % x) is not None and not vals.get('rr_fmc_from_%d' % x) and not vals.get('rr_fmc_to_%d' % x) and vals.get('rr_max_%d' % x) is not None:
                        if len(p_ids) >= x:
                            #print cr.mogrify('delete from replenishment_segment_line_period where line_id=%s and id=%s', (_id, p_ids[x-1]))
                            cr.execute('delete from replenishment_segment_line_period where line_id=%s and id=%s', (_id, p_ids[x-1]))
                    else:
                        data = {'line_id': _id}
                        if 'rr_fmc_%d' % x in vals:
                            data['value'] = vals.get('rr_fmc_%d' % x)
                            if data['value'] is False:
                                data['value'] = None
                        if 'rr_fmc_from_%d' % x in vals:
                            data['from_date'] = vals.get('rr_fmc_from_%d' % x) or None
                        if 'rr_fmc_to_%d' % x in vals:
                            data['to_date'] = vals.get('rr_fmc_to_%d' % x) or None
                            try:
                                if vals.get('rr_fmc_to_%d' % (x+1)):
                                    vals['rr_fmc_from_%d'%(x+1)] = (datetime.strptime(vals['rr_fmc_to_%d'%x], '%Y-%m-%d') + relativedelta(days=1)).strftime('%Y-%m-%d')
                            except:
                                pass
                        if 'rr_max_%d' % x in vals:
                            data['max_value'] = vals.get('rr_max_%d' % x)
                            if data['max_value'] is False:
                                data['max_value'] = None

                        if len(p_ids) >= x:
                            data['id'] = p_ids[x-1]

                            #print cr.mogrify('update replenishment_segment_line_period set ' + ', '.join(['%s=%%(%s)s' % (k, k) for k in data]) + ' where line_id=%(line_id)s and id=%(id)s', data)
                            cr.execute('update replenishment_segment_line_period set ' + ', '.join(['%s=%%(%s)s' % (k, k) for k in data]) + ' where line_id=%(line_id)s and id=%(id)s', data) # not_a_user_entry
                        else:
                            d_keys = data.keys()
                            #print cr.mogrify('insert into replenishment_segment_line_period ('+', '.join(d_keys)+') values ('+','.join(['%%(%s)s' % k for k in d_keys])+')', data)
                            cr.execute('insert into replenishment_segment_line_period ('+', '.join(d_keys)+') values ('+','.join(['%%(%s)s' % k for k in d_keys])+')', data) # not_a_user_entry

            cr.execute('delete from replenishment_segment_line_period where line_id=%s and value is NULL', (_id, ))

            if _id in cycle_line_state:
                all_data = ''
                d = self.read(cr, uid, _id, all_fields, context=context)
                for x in all_fields:
                    all_data +='%s'%d[x]
                fmc_version = hashlib.md5(''.join(all_data)).hexdigest()
                cr.execute("update replenishment_segment_line set fmc_version=%s where id=%s and coalesce(fmc_version, '')!=%s returning id", (fmc_version, _id, fmc_version))
                updated = cr.fetchone()
                if updated and cycle_line_state[_id] == 'complete':
                    instance_id = self.pool.get('res.company')._get_instance_id(cr, uid)
                    cr.execute('update replenishment_segment_date_generation gen_date set full_date=NULL from replenishment_segment_line line where line.segment_id=gen_date.segment_id and line.id = %s', (_id, ))
                    cr.execute('update replenishment_segment_date_generation gen_date set review_date=NULL from replenishment_segment_line line where line.segment_id=gen_date.segment_id and line.id = %s and instance_id=%s', (_id, instance_id))

        self._check_overlaps(cr, uid, line_ids=ids, context=context)
        return True

    def create(self, cr, uid, vals, context=None):
        self._clean_data(cr, uid, vals, context=context)
        id = super(replenishment_segment_line, self).create(cr, uid, vals, context=context)
        self._set_period(cr, uid, [id], vals, context=context)
        return id

    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        self._clean_data(cr, uid, vals, context=context)
        a = super(replenishment_segment_line, self).write(cr, uid, ids, vals, context=context)
        # _set_period is called by sync_client/orm.py def write, order matters to track changes in ir.model.data and to trigger sync update
        #self._set_period(cr, uid, ids, vals, context=context)
        return a

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
            msg =  _('FROM %s must be the first day of the month') % (nb,)
        elif ch_type == 'to':
            if fmc_date + relativedelta(months=1, day=1, days=-1) != fmc_date:
                msg = _('TO %s must be the last day of the month') % (nb, )
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
        'amc': fields.float('AMC', digits=(16, 2)),
        'instance_id': fields.many2one('msf.instance', string='Instance', select=1),
        'reserved_stock': fields.float('Reserved Stock', digits=(16, 2)),
        'real_stock': fields.float('Reserved Stock', digits=(16, 2)),
        'expired_before_rdd': fields.float('Expired Qty before RDD', digits=(16, 2)),
        'expired_qty_before_eta': fields.float('Qty expiring before RDD', digits=(16, 2)),
        'expired_between_rdd_oc': fields.float('Expired Qty between RDD and OC', digits=(16, 2)),
        'open_loan': fields.boolean('Open Loan'),
        'open_donation': fields.boolean('Donations pending'),
        'sleeping_qty': fields.float('Sleeping Qty', digits=(16, 2)),
        'total_expiry_nocons_qty': fields.float('Qty expiring no cons.', digits=(16, 2)),
        'fmc_version': fields.char('FMC timestamp', size=64, select=1),
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
            seg_ids = segment_obj.search(cr, uid, [('state', 'in', ['draft', 'complete']), ('state_parent', 'in', ['draft', 'complete'])], context=context)
        elif isinstance(seg_ids, int):
            seg_ids = [seg_ids]

        for segment in segment_obj.browse(cr, uid, seg_ids, context=context):
            if not segment.local_location_ids:
                cr.execute('''
                    delete from replenishment_segment_line_amc_detailed_amc where segment_line_id in
                    (select seg_line.id from replenishment_segment_line seg_line where seg_line.segment_id = %s) ''', (segment.id, )
                           )
                cr.execute('''
                    delete from replenishment_segment_line_amc_month_exp where line_amc_id in
                    (select amc.id from replenishment_segment_line_amc amc, replenishment_segment_line seg_line where seg_line.id = amc.segment_line_id and seg_line.segment_id = %s) ''', (segment.id,)
                           )
                continue
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

            if segment.state == 'complete' and (segment.state_parent == 'complete' or segment.hidden):
                gen_inv_review = force_review
                full_data = True
                if (not segment.next_scheduler or segment.next_scheduler < datetime_now.strftime('%Y-%m-%d %H:%M:%S')) and (not review_date or review_date < datetime_now.strftime('%Y-%m-%d %H:%M:%S')):
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
                if gen_inv_review:
                    last_gen_data['review_date'] = datetime_now
                    if last_gen_id:
                        last_gen_obj.write(cr, uid, last_gen_id, last_gen_data, context=context)
                    else:
                        last_gen_obj.create(cr, uid, last_gen_data, context=context)
                continue
            # update vs create line
            cache_line_amc = {}
            seg_line = {}

            prod_with_stock = []

            line_amc_ids = self.search(cr, uid, [('instance_id', '=', instance_id), ('segment_line_id', 'in', list(lines.values()))], context=context)
            for line_amc in self.browse(cr, uid, line_amc_ids, fields_to_fetch=['segment_line_id'], context=context):
                cache_line_amc[line_amc.segment_line_id.id] = line_amc.id
                seg_line[line_amc.id] = line_amc.segment_line_id
            # real stock - reserved stock
            stock_qties = {}
            qty_fields = ['qty_available']
            if full_data:
                qty_fields += ['qty_reserved']
            for prod_alloc in prod_obj.browse(cr, uid, list(lines.keys()), fields_to_fetch=qty_fields, context={'location': seg_context['amc_location_ids']}):
                stock_qties[prod_alloc['id']] = {'qty_available': prod_alloc.qty_available}
                if full_data:
                    stock_qties[prod_alloc['id']]['qty_reserved'] = -1 * prod_alloc.qty_reserved
                if gen_inv_review and prod_alloc.qty_available:
                    prod_with_stock.append(prod_alloc['id'])

            open_loan = {}
            open_donation = {}
            if full_data:
                cr.execute('''
                    select product_id from purchase_order_line pol, purchase_order po
                    where
                        po.id = pol.order_id and
                        pol.product_id in %s and
                        pol.state not in ('done', 'cancel_r', 'cancel') and
                        po.partner_type != 'internal' and
                        po.order_type in ('loan', 'loan_return')
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
                        so.order_type in ('loan', 'loan_return')
                    group by product_id
                    ''', (tuple(lines.keys()), )
                )
                for loan in cr.fetchall():
                    open_loan[loan[0]] = True

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
                    amc, amc_by_month = prod_obj.compute_amc(cr, uid, list(lines.keys()), context=seg_context, compute_amc_by_month=True)
                else:
                    amc = prod_obj.compute_amc(cr, uid, list(lines.keys()), context=seg_context)
            else:
                amc = {}
            for prod_id in list(lines.keys()):
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
                            (select amc.id from replenishment_segment_line_amc amc, replenishment_segment_line seg_line where seg_line.id = amc.segment_line_id and seg_line.segment_id = %s and amc.instance_id=%s)
                    )''', (segment.id, instance_id))
                    cr.execute('''
                        delete from replenishment_segment_line_amc_month_exp where line_amc_id in
                            (select amc.id from replenishment_segment_line_amc amc, replenishment_segment_line seg_line where seg_line.id = amc.segment_line_id and seg_line.segment_id = %s and amc.instance_id=%s) ''', (segment.id, instance_id)
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
                    oc_date = rdd_date + relativedelta(**normalize_td(segment.time_unit_lt, segment.order_coverage))
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
                            cr.execute('''update replenishment_segment_line_amc amc set fmc_version=seg_line.fmc_version from replenishment_segment_line seg_line where seg_line.id=amc.segment_line_id and seg_line.segment_id=%s and amc.instance_id=%s''', (segment.id, instance_id))
                            cr.execute("""
                                select line.product_id, item.period_start, sum(item.expired_qty), line.id, item.name
                                from product_likely_expire_report_line line, product_likely_expire_report_item item
                                where
                                    item.line_id = line.id and
                                    report_id=%s and
                                    item.period_start <= %s
                                group by line.product_id, item.period_start, line.id, item.name
                                having sum(item.expired_qty) > 0 """, (expired_id, projected_view))
                            for x in cr.fetchall():
                                expire_at_end_of = x[1]
                                name = ''
                                if x[4] == 'expired_qty_col':
                                    name = 'expired_qty_col'
                                    expire_at_end_of = (datetime.now() + relativedelta(day=1, months=-1)).strftime('%Y-%m-%d')
                                month_exp_obj.create(cr, uid, {'line_amc_id': cache_line_amc[lines[x[0]]], 'month': expire_at_end_of, 'quantity': x[2], 'expiry_line_id': x[3], 'name': name}, context=context)

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
        'quantity': fields.float('Qty', digits=(16, 2)),
        'expiry_line_id': fields.many2one('product.likely.expire.report.line', 'Expiry Line'),
        'name': fields.char('Name', size=62),
    }

replenishment_segment_line_amc_month_exp()

class replenishment_segment_line_amc_detailed_amc(osv.osv):
    _name = 'replenishment.segment.line.amc.detailed.amc'
    _rec_name = 'segment_line_id'
    _columns = {
        'segment_line_id': fields.many2one('replenishment.segment.line', 'Seg Line', required=1, select=1, ondelete='cascade'),
        'month': fields.date('Month', required=1, select=1),
        'amc': fields.float('AMC', digits=(16, 2)),
    }
replenishment_segment_line_amc_detailed_amc()

class replenishment_segment_line_amc_past_fmc(osv.osv):
    _name = 'replenishment.segment.line.amc.past_fmc'
    _rec_name = 'segment_line_id'
    _inherits = {'replenishment.segment.line': 'segment_line_id'}
    _order = 'month desc'
    _columns = {
        'segment_line_id': fields.many2one('replenishment.segment.line', 'Seg Line', required=1, select=1, ondelete='cascade'),
        'month': fields.date('Month', required=1, select=1),
        'fmc': fields.float('FMC/Auto', digits=(16, 2)),
        'minmax': fields.char('Min/Max', size=256),
    }

    _sql_constraints = [
        ('unique_seg_month', 'unique(segment_line_id, month)', 'Seg/month must be unique!'),
    ]

replenishment_segment_line_amc_past_fmc()


class common_oc_inv():
    def _selected_data(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if not context.get('button_selected_ids'):
            raise osv.except_osv(_('Warning!'), _('Please select at least one line'))

        main_obj = self.browse(cr, uid, ids[0], context=context)
        loc_ids = [x.id for x in main_obj.location_config_id.local_location_ids]

        if self._name == 'replenishment.inventory.review':
            line_obj = self.pool.get('replenishment.inventory.review.line')
        else:
            line_obj = self.pool.get('replenishment.order_calc.line')

        lines = line_obj.browse(cr, uid, context.get('button_selected_ids'), context=context)

        return {
            'location_ids': loc_ids,
            'products': [x.product_id for x in lines],
            'inv_review': main_obj,
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

    def reserved(self, cr, uid, ids, context=None):
        data = self._selected_data(cr, uid, ids, context=context)
        product_ids = [x.id for x in data['products']]
        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'stock.reserved_products_action', ['tree', 'form'], context=context)
        res['domain'] = [('product_id', 'in', product_ids)]
        res['nodestroy'] = True
        res['target'] = 'new'
        return res

        return res

class replenishment_order_calc(osv.osv, common_oc_inv):
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
        'parent_segment_id': fields.many2one('replenishment.parent.segment', 'Parent Segment', readonly=1),
        'description_seg': fields.char('Description', required=1, size=28, readonly=1),
        'location_config_id': fields.many2one('replenishment.location.config', 'Location Config', required=1, readonly=1),
        'location_config_description': fields.char('Description', size=28, readonly=1),
        'total_lt': fields.float('Total Lead Time', readonly=1, digits=(16, 2)),
        'time_unit_lt': fields.selection([('d', 'days'), ('w', 'weeks'), ('m', 'months')], string='Unit of Time', readonly=1),
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
        file_data = SpreadsheetXML(xmlstring=base64.b64decode(calc.file_to_import))

        existing_line = {}
        for line in calc.order_calc_line_ids:
            existing_line[(line.product_id.default_code, line.segment_id.name_seg)] = line.id

        qty_col = 20
        comment_col = 23
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
            prod_code = prod_code.strip().upper()

            seg_ref = row.cells[3].data
            if not seg_ref:
                continue
            seg_ref = seg_ref.strip()

            if (prod_code, seg_ref) not in existing_line:
                error.append(_('Line %d: product %s not found.') % (idx+1, prod_code))
                continue

            if row.cells[qty_col].data and not isinstance(row.cells[qty_col].data, (int, float)):
                error.append(_('Line %d: Agreed Order Qty  must be a number, found %s') % (idx+1, row.cells[qty_col].data))

            calc_line_obj.write(cr, uid, existing_line[(prod_code, seg_ref)], {
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
                'location_requestor_id': calc.parent_segment_id.ir_requesting_location.id,
                'procurement_request': True,
                'delivery_requested_date': calc.new_order_reception_date,
                'categ': 'other',
                'origin': calc.name,
                'stock_take_date': calc.generation_date,
            })
            line_seen = {}
            for line in calc.order_calc_line_ids:
                if line.agreed_order_qty:
                    if line.product_id.id in line_seen:
                        line_seen[line.product_id.id]['qty'] += line.agreed_order_qty
                        sale_line_obj.write(cr, uid, line_seen[line.product_id.id]['line_id'], {'product_uom_qty': line_seen[line.product_id.id]['qty']}, context=context)
                    else:
                        sale_line_id = sale_line_obj.create(cr, uid, {
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
                        line_seen[line.product_id.id] = {'qty': line.agreed_order_qty, 'line_id': sale_line_id}

            self.write(cr, uid, calc.id, {'state': 'closed', 'ir_generation_date': time.strftime('%Y-%m-%d'), 'ir_id': ir_id}, context=context)
            self.pool.get('replenishment.parent.segment').write(cr, uid, calc.parent_segment_id.id, {'previous_order_rdd': calc.new_order_reception_date, 'date_next_order_received_modified': False}, context=context)
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

    def round_to_soq(self, cr, uid, ids, context=None):
        cr.execute('''
            update replenishment_order_calc_line line
                set
                    agreed_order_qty = agreed_order_qty - mod(agreed_order_qty, prod.soq_quantity) + prod.soq_quantity,
                    rounded_qty = 't'
                from product_product prod
                where
                    prod.id = line.product_id and
                    coalesce(prod.soq_quantity,0) not in (0, 1) and
                    coalesce(agreed_order_qty, 0) != 0 and
                    mod(agreed_order_qty, prod.soq_quantity) != 0 and
                    line.order_calc_id in %s
        ''', (tuple(ids), ))
        return True


    def check_draft_consolidated(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if not context.get('active_ids') or self.search_exists(cr, uid, [('id', 'in', context['active_ids']), ('state', '!=', 'draft')], context=context):
            raise osv.except_osv(_('Warning'), _('Selected OC must be in Draft state'))
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'report_replenishment_order_calc_draft_consolidated_xls',
            'context': context,
        }

replenishment_order_calc()

class replenishment_order_calc_line(osv.osv):
    _name ='replenishment.order_calc.line'
    _description = 'Order Calculation Lines'
    _order = 'product_id, segment_id, order_calc_id'

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

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, int):
            ids = [ids]
        if vals is None:
            vals = {}

        reset_soq_ids = []
        if 'agreed_order_qty' in vals:
            reset_soq_ids = self.search(cr, uid, [('id', 'in', ids), ('rounded_qty', '=', 't'), ('agreed_order_qty', '!=', vals['agreed_order_qty'])], context=context)

        if reset_soq_ids:
            untouched_ids = list(set(ids) - set(reset_soq_ids))
            if untouched_ids:
                super(replenishment_order_calc_line, self).write(cr, uid, untouched_ids, vals, context=context)
            vals['rounded_qty'] = False
            return super(replenishment_order_calc_line, self).write(cr, uid, reset_soq_ids, vals, context=context)

        return super(replenishment_order_calc_line, self).write(cr, uid, ids, vals, context=context)


    _columns = {
        'order_calc_id': fields.many2one('replenishment.order_calc', 'Order Calc', required=1, select=1),
        'segment_id': fields.many2one('replenishment.segment', 'Segment', required=1, select=1, readonly=1),
        'rule': fields.selection([('cycle', 'Order Cycle'), ('minmax', 'Min/Max'), ('auto', 'Automatic Supply')], string='RR Type', readonly=1),
        'product_id': fields.many2one('product.product', 'Product Code', select=1, required=1, readonly=1),
        'product_description': fields.related('product_id', 'name',  string='Description', type='char', size=64, readonly=True, select=True, write_relate=False),
        'status': fields.selection(life_cycle_status, string='Life cycle status', readony=1),
        'uom_id': fields.related('product_id', 'uom_id',  string='UoM', type='many2one', relation='product.uom', readonly=True, select=True, write_relate=False),
        'in_main_list': fields.boolean('Prim. prod. list', readonly=1),
        'valid_rr_fmc': fields.boolean('Valid', readonly=1),
        'real_stock': fields.float('Real Stock', readonly=1, related_uom='uom_id', digits=(16, 2)),
        'pipeline_qty': fields.float('Pipeline Qty', readonly=1, related_uom='uom_id', digits=(16, 2)),
        'eta_for_next_pipeline': fields.date('ETA for Next Pipeline', readonly=1),
        'reserved_stock_qty': fields.float('Reserved Stock Qty', readonly=1, related_uom='uom_id', digits=(16, 2)),
        'projected_stock_qty': fields.float('Projected Stock Level', readonly=1, related_uom='uom_id', digits=(16, 2)),
        'qty_lacking': fields.float_null('Qty lacking before next RDD', readonly=1, related_uom='uom_id', null_value='N/A', digits=(16, 2)),
        'qty_lacking_needed_by': fields.date('Qty lacking needed by', readonly=1),
        'open_loan': fields.boolean('Open Loan', readonly=1),
        'open_donation': fields.boolean('Donations pending', readonly=1),
        'expired_qty_before_cons': fields.float_null('Expired Qty before cons.', readonly=1, related_uom='uom_id', digits=(16, 2)),
        'expired_qty_before_eta': fields.float_null('Expired Qty before RDD', readonly=1, related_uom='uom_id', digits=(16, 2)),
        'proposed_order_qty': fields.float('Proposed Order Qty', readonly=1, related_uom='uom_id', digits=(16,2)),
        'agreed_order_qty': fields.float_null('Agreed Order Qty', related_uom='uom_id', digits=(16,2)),
        'rounded_qty': fields.boolean('Agreed Qty Rounded', readonly=1),
        'cost_price': fields.float('Cost Price', readonly=1, digits_compute=dp.get_precision('Account Computation')),
        'line_value': fields.function(_get_line_value, method=True, type='float', with_null=True, string='Line Value', digits=(16, 2)),
        'order_qty_comment': fields.char('Order Qty Comment', size=512),
        'warning': fields.text('Warning', readonly='1'),
        'warning_html': fields.text('Warning', readonly='1'),
        'buffer_ss_qty': fields.char('Buffer / SS Qty', size=128, readonly=1),
        'auto_qty': fields.float_null('Auto. Supply Qty', related_uom='uom_id', readonly=1, digits=(16, 2)),
        'min_max': fields.char('Min/Max', size=128, readonly=1),
    }

    _defaults = {
        'rounded_qty': False,
    }

replenishment_order_calc_line()



class replenishment_inventory_review(osv.osv, common_oc_inv):
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
        'rule': fields.selection([('cycle', 'Order Cycle'), ('minmax', 'Min/Max'), ('auto', 'Auto Supply')], string='RR Type', required=1), #Seg
        'min_qty': fields.float_null('Min Qty', related_uom='uom_id', digits=(16, 2)), # Seg line
        'max_qty': fields.float_null('Max Qty', related_uom='uom_id', digits=(16, 2)), # Seg line
        'auto_qty': fields.float_null('Auto. Supply Qty', related_uom='uom_id', digits=(16, 2)), # Seg line
        'buffer_qty': fields.float_null('Buffer Qty', related_uom='uom_id', digits=(16, 2)), # Seg line
        'safety_stock_qty': fields.float_null('Safety Stock (Qty)', digits=(16, 2)),
        'min_max': fields.char('Min / Max', size=128),
        'buffer_ss_qty': fields.char('Buffer / SS Qty', size=128, readonly=1),
        'segment_ref_name': fields.char('Segment Ref/Name', size=512), # Seg
        'rr_fmc_avg': fields.float_null('RR-FMC (average for period)', null_value='N/A', digits=(16, 2)),
        'rr_amc': fields.float('RR-AMC', digits=(16, 2)),
        'valid_rr_fmc': fields.boolean('Valid', readonly=1), # OC
        'real_stock': fields.float('Real Stock', readonly=1, related_uom='uom_id', digits=(16, 2)), # OC
        'pipeline_qty': fields.float('Pipeline Qty', readonly=1, related_uom='uom_id', digits=(16, 2)), # OC
        'reserved_stock_qty': fields.float('Reserved Stock Qty', readonly=1, related_uom='uom_id', digits=(16, 2)),# OC
        'expired_qty_before_cons': fields.float_null('Expired Qty before cons.', readonly=1, related_uom='uom_id', null_value='N/A', digits=(16, 2)), # OC
        'total_expired_qty': fields.float('Qty expiring within period', readonly=1, related_uom='uom_id', digits=(16, 2)),
        'sleeping_qty': fields.float('Sleeping Qty', digits=(16, 2)),
        'projected_stock_qty': fields.float_null('RR-FMC Projected Stock Level', readonly=1, related_uom='uom_id', null_value='N/A', digits=(16, 2)), # OC
        'projected_stock_qty_amc': fields.float_null('RR-AMC Projected Stock Level', readonly=1, related_uom='uom_id', null_value='N/A', digits=(16, 2)), # OC
        'unit_of_supply_amc': fields.float_null('Days/weeks/months of supply (RR-AMC)', null_value='N/A', digits=(16, 2)),
        'unit_of_supply_fmc': fields.float_null('Days/weeks/months of supply (RR-FMC)', null_value='N/A', digits=(16, 2)),
        'warning': fields.text('Warning', readonly='1'), # OC
        'warning_html': fields.text('Warning', readonly='1'), # OC
        'open_loan': fields.boolean('Open Loan', readonly=1), # OC
        'open_donation': fields.boolean('Donations pending', readonly=1), # OC
        'qty_lacking': fields.float_null('Qty lacking before next RDD', readonly=1, related_uom='uom_id', null_value='N/A', digits=(16, 2)), # OC
        'qty_lacking_needed_by': fields.date('Qty lacking needed by', readonly=1), # OC
        'eta_for_next_pipeline': fields.date('ETA for Next Pipeline', readonly=1), # Seg

        'date_preparing': fields.date('Start preparing the next order'), # Seg
        'date_next_order_validated': fields.date('Next order to be validated by'), # Seg
        'date_next_order_rdd': fields.date('RDD for next order'), # Seg
        'internal_lt': fields.float('Internal LT', digits=(16, 2)),
        'external_lt': fields.float('External LT', digits=(16, 2)),
        'total_lt': fields.float('Total LT', digits=(16, 2)),
        'order_coverage': fields.float('Order Coverage', digits=(16, 2)),
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
        'rr_fmc': fields.float_null('RR Value', digits=(16, 2)),
        'rr_max': fields.float_null('RR Max', digits=(16, 2)),
        'projected': fields.float_null('Projected', digits=(16, 2)),
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
        'exp_qty': fields.float_null('Exp', digits=(16, 2)),
        'batch_number': fields.char('BN', size=256),
        'life_date': fields.date('ED'),
        'stock_qty': fields.float_null('Stock Qty', digits=(16, 2)),
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
        'exp_qty': fields.float('Exp', digits=(16, 2)),
        'expiry_line_id': fields.many2one('product.likely.expire.report.line', 'Expiry Line'),
        'name': fields.char('Name', size=126),
    }
replenishment_inventory_review_line_exp()

class replenishment_inventory_review_line_stock(osv.osv):
    _name = 'replenishment.inventory.review.line.stock'
    _description = 'Stock by instance'

    _columns = {
        'review_line_id': fields.many2one('replenishment.inventory.review.line', 'Review Line', required=1, select=1, ondelete='cascade'),
        'qty': fields.float('Stock Level', digits=(16, 2)),
        'instance_id': fields.many2one('msf.instance', 'Instance'),
        'local_instance': fields.boolean('Local instance'),
        'total_exp': fields.float('Total Exp.', digits=(16, 2)),
    }

    def fields_get(self, cr, uid, fields=None, context=None, with_uom_rounding=False):
        if context is None:
            context = {}

        fg = super(replenishment_inventory_review_line_stock, self).fields_get(cr, uid, fields=fields, context=context, with_uom_rounding=with_uom_rounding)
        if context.get('review_line_id'):
            cr.execute('''select distinct(date) from replenishment_inventory_review_line_exp where review_line_id=%s and date is not null''', (context.get('review_line_id'),))
            for date1 in cr.fetchall():
                if date1 and date1[0]:
                    dd = date1[0].split('-')
                    fg[date1[0]] =  {'type': 'float', 'string': '%s/%s' % (dd[2], dd[1])}
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
            for dd in cr.fetchall():
                arch += '''<field name="%s" sum="Total"/>''' % dd[0]
                arch += '''<button name="go_to_item" type="object" string="%s" icon="gtk-info" context="{'item_date': '%s', 'review_line_id': %s}" attrs="{'invisible': [('local_instance', '=', False)]}"/>''' % (_('Go to item'), dd[0], context.get('review_line_id'))
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
                left join replenishment_inventory_review_line_exp exp on exp.review_line_id=stock.review_line_id and exp.date is not null and exp.instance_id = stock.instance_id
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
            return list(res.values())

        return super(replenishment_inventory_review_line_stock, self).read(cr, uid, ids, vals, context=context, load=load)

    def go_to_item(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if context.get('review_line_id') and context.get('item_date'):
            exp_obj = self.pool.get('replenishment.inventory.review.line.exp')
            exp_ids = exp_obj.search(cr, uid, [('review_line_id', '=', context.get('review_line_id')), ('date', '=', context.get('item_date'))], context=context)
            if exp_ids:
                exp = exp_obj.read(cr, uid, exp_ids, ['expiry_line_id', 'name'], context=context)[0]
                if exp and exp['expiry_line_id']:
                    if exp['name']:
                        item_ids = self.pool.get('product.likely.expire.report.item').search(cr, uid, [('name', '=', exp['name']), ('line_id', '=', exp['expiry_line_id'][0])], context=context)
                    else:
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
                left join replenishment_segment segment on segment.id = seg_line.segment_id and description_seg!='HIDDEN'
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
        file_data = SpreadsheetXML(xmlstring=base64.b64decode(obj.file_to_import))

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
                line_error.append(_('XLS Line %d: "FROM DATE" date is not valid, found %s') % (idx, row.cells[3].data))
                error += line_error
                continue

            if not row.cells[4].type == 'datetime':
                line_error.append(_('XLS Line %d: "TO DATE" date is not valid, found %s') % (idx, row.cells[4].data))
                error += line_error
                continue

            data_towrite['from_date'] = row.cells[3].data.strftime('%Y-%m-%d')
            data_towrite['to_date'] = row.cells[4].data.strftime('%Y-%m-%d')

            error_date = line_obj.change_date(cr, uid, [existing_line.get(prod_line, 0)], data_towrite['from_date'], data_towrite['to_date'], context=context)
            if error_date.get('warning', {}).get('message'):
                line_error.append(_('XLS Line %d: %s') % (idx, error_date['warning']['message']))


            if cells_nb > 6:
                if row.cells[6].data and not isinstance(row.cells[6].data, (int, float)):
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
                        if not isinstance(row.cells[replace_prod_col+2].data, (int, float)):
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
                left join replenishment_parent_segment parent on parent.id = seg.parent_id
                left join replenishment_location_config config on config.id = parent.location_config_id
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
        'qty_missed': fields.float_null('Qty missed', related_uom='uom_id', digits=(16, 2)),
        'substitute_1_product_id': fields.many2one('product.product', '1. Substitute product', select=1),
        'substitute_1_product_code': fields.related('substitute_1_product_id', 'default_code',  string='1. Substitute product', type='char', size=64, readonly=True, select=True, write_relate=False),
        'substitute_1_product_description': fields.related('substitute_1_product_id', 'name',  string='1. Description', type='char', size=64, readonly=True, select=True, write_relate=False),
        'substitute_1_uom_id': fields.related('substitute_1_product_id', 'uom_id',  string='UoM', type='many2one', relation='product.uom', readonly=True, select=True, write_relate=False),
        'substitute_1_qty': fields.float_null('1. Qty used as substitute', related_uom='substitute_1_uom_id', digits=(16, 2)),

        'substitute_2_product_id': fields.many2one('product.product', '2. Substitute product', select=1),
        'substitute_2_product_code': fields.related('substitute_2_product_id', 'default_code',  string='2. Substitute product', type='char', size=64, readonly=True, select=True, write_relate=False),
        'substitute_2_product_description': fields.related('substitute_2_product_id', 'name',  string='2. Description', type='char', size=64, readonly=True, select=True, write_relate=False),
        'substitute_2_uom_id': fields.related('substitute_2_product_id', 'uom_id',  string='UoM', type='many2one', relation='product.uom', readonly=True, select=True, write_relate=False),
        'substitute_2_qty': fields.float_null('2. Qty used as substitute', related_uom='substitute_2_uom_id', digits=(16, 2)),

        'substitute_3_product_id': fields.many2one('product.product', '3. Substitute product', select=1),
        'substitute_3_product_code': fields.related('substitute_3_product_id', 'default_code',  string='3. Substitute product', type='char', size=64, readonly=True, select=True, write_relate=False),
        'substitute_3_product_description': fields.related('substitute_3_product_id', 'name',  string='3. Description', type='char', size=64, readonly=True, select=True, write_relate=False),
        'substitute_3_uom_id': fields.related('substitute_3_product_id', 'uom_id',  string='UoM', type='many2one', relation='product.uom', readonly=True, select=True, write_relate=False),
        'substitute_3_qty': fields.float_null('3. Qty used as substitute', related_uom='substitute_3_uom_id', digits=(16, 2)),
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
