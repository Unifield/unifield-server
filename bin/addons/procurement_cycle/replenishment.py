# -*- coding: utf-8 -*-

from osv import osv, fields
from tools.translate import _
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
import json
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
import base64
from tools import misc
import threading
import logging
import pooler

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
        'is_current_instance': fields.function(_get_instance,  method=True, type='boolean', fnct_search=_search_is_current_instance, string='Defined in the instance', multi='_get_instance'),
        'is_project': fields.function(_get_instance,  method=True, type='boolean', string='Is project instance', multi='_get_instance'),
    }

    def _get_default_synced(self, cr, uid, context=None):
        return self.pool.get('res.company')._get_instance_level(cr, uid) == 'coordo'

    _defaults = {
        'active': True,
        'synched': _get_default_synced,
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
        'rule_alert': fields.function(_get_rule_alert, method=1, string='Replenishment Rule (Alert Theshold)', type='char'),
        'ir_requesting_location': fields.many2one('stock.location', string='IR Requesting Location', domain="[('usage', '=', 'internal'), ('location_category', 'in', ['stock', 'consumption_unit', 'eprep'])]", required=1),
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
        'file_to_import': fields.binary(string='File to import'),
        'last_generation': fields.one2many('replenishment.segment.date.generation', 'segment_id', 'Generation Date', readonly=1),
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

    def replenishment_compute_all_bg(self, cr, uid, ids=False, context=None):
        threaded_calculation = threading.Thread(target=self.replenishment_compute_thread, args=(cr.dbname, uid, ids, context))
        threaded_calculation.start()
        return {'type': 'ir.actions.act_window_close'}

    def replenishment_compute_thread(self, dbname, uid, ids=False, context=None):
        logger = logging.getLogger('RR')
        cr = pooler.get_db(dbname).cursor()
        logger.info("Start RR computation")
        try:
            self.pool.get('replenishment.segment.line.amc').generate_all_amc(cr, uid, context=context)
            logger.info("RR computation done")
            cr.commit()
        except Exception as e:
            cr.rollback()
            logger.error('Error RR: %s' % misc.get_traceback(e))
        finally:
            cr.close(True)

    def trigger_compute(self, cr, uid, ids, context):
        return self.pool.get('replenishment.segment.line.amc').generate_all_amc(cr, uid, context=context, seg_ids=ids)

    def generate_order_calc(self, cr, uid, ids, context):
        # TODO JFB RR: check state, date pulled from projects ...

        order_calc_line = self.pool.get('replenishment.order_calc.line')
        calc_id = False
        for seg in self.browse(cr, uid, ids, context):
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
                select segment_line_id, sum(reserved_stock), sum(real_stock - reserved_stock - expired_before_rrd), sum(expired_before_rrd), sum(expired_between_rrd_oc), bool_or(open_loan)
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
                    'open_loan': x[5] or False
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

                lacking = False
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
                            if not lacking:
                                if total_fmc < sum_line[line.id]['pas_no_pipe_no_fmc']:
                                    month_of_supply += month
                                else:
                                    month_of_supply += ( sum_line[line.id]['pas_no_pipe_no_fmc'] - total_fmc + month*num_fmc ) / num_fmc
                                    lacking = True
                        else:
                            end_oc = min(oc, to_fmc)
                            if end_oc >= begin:
                                month = (end_oc-begin).days/30.44
                                total_month_oc += month
                                total_fmc_oc += month*num_fmc
                pas = max(0, sum_line.get(line.id, {}).get('pas_no_pipe_no_fmc', 0) + line.pipeline_before_rrd - total_fmc)
                ss_stock = 0
                warning = ""
                qty_lacking = 0
                qty_lacking_needed_by = False
                proposed_order_qty = 0
                if seg.rule == 'cycle':
                    if line.status == 'new':
                        if total_month_oc:
                            ss_stock = seg.safety_stock * total_fmc_oc / total_month_oc
                    else:
                        qty_lacking =  max(0, sum_line.get(line.id, {}).get('pas_no_pipe_no_fmc', 0) - total_fmc)
                        if total_month_oc+total_month:
                            ss_stock = seg.safety_stock * ((total_fmc_oc+total_month)/(total_month_oc+total_month))
                        if total_month and pas <= line.buffer_qty + seg.safety_stock * (total_fmc / total_month):
                            warning = '%s '% _('Missing Qties')
                        if qty_lacking:
                            warning += _('Stock-out before next ETA')

                        if lacking:
                            qty_lacking_needed_by = (today + relativedelta(days=month_of_supply*30.44)).strftime('%Y-%m-%d')

                    proposed_order_qty = max(0, total_fmc_oc + ss_stock + line.buffer_qty + sum_line.get(line.id, {}).get('expired_rdd_oc',0) - pas - line.pipeline_between_rrd_oc)

                elif seg.rule == 'minmax':
                    proposed_order_qty = max(0, line.max_qty - line.real_stock + sum_line.get(line.id, {}).get('reserved_stock_qty') + prod_eta.get(line.product_id.id, 0) - line.pipeline_before_rrd)
                    if line.real_stock - sum_line.get(line.id, {}).get('expired_before_rrd') <= line.min_qty:
                        warning = _('Alert: "inventory – batches expiring before ETA <= Min"')
                else:
                    proposed_order_qty = line.auto_qty

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
                    'qty_lacking': qty_lacking,
                    'qty_lacking_needed_by': qty_lacking_needed_by,
                    'expired_qty_before_cons': sum_line.get(line.id, {}).get('expired_before_rrd'),
                    'expired_qty_before_eta': False, #TODO JFB=  RR
                    'proposed_order_qty': proposed_order_qty,
                    'agreed_order_qty': proposed_order_qty,
                    'open_loan': sum_line.get(line.id, {}).get('open_loan', False),
                    'warning': warning,
                }
                order_calc_line.create(cr, uid, line_data, context=context)
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

    def import_lines(self, cr, uid, ids, context=None):
        product_obj = self.pool.get('product.product')
        seg_line_obj = self.pool.get('replenishment.segment.line')

        seg = self.browse(cr, uid, ids[0],  context=context)
        if not seg.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))
        file_data = SpreadsheetXML(xmlstring=base64.decodestring(seg.file_to_import))

        existing_line = {}
        for line in seg.line_ids:
            existing_line[line.product_id.default_code] =line.id

        idx = -1

        status = {
            _('Active'): 'active',
            _('New'): 'new',
        }
        error = []
        created = 0
        updated = 0
        ignored = 0
        for row in file_data.getRows():
            idx += 1
            if idx < 8:
                # header
                continue
            line_error = []
            prod_code = row.cells[0].data
            if not prod_code:
                continue
            prod_code = prod_code.strip()

            if not isinstance(row.cells[4].data, (int, long, float)):
                line_error.append(_('Line %d: Buffer Qty must be a number, found %s') % (idx+1, row.cells[4].data))
            data_towrite = {
                'status': status.get(row.cells[3].data.strip()),
                'buffer_qty': row.cells[4].data,
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


            if seg.rule == 'cycle':
                first_fmc_col = 7 - 3
                for fmc in range(1, 13):
                    first_fmc_col += 3
                    if row.cells[first_fmc_col+1].data:
                        # TODO JFB RR: check date consist. FROM < TO, begin / end mohtn, no gap
                        if not row.cells[first_fmc_col+1].type == 'datetime':
                            line_error.append(_('Line %d: FMC FROM %d, date expected, found %s') % (idx+1, fmc, row.cells[first_fmc_col+1].data))
                            continue
                        if not row.cells[first_fmc_col+2].data or row.cells[first_fmc_col+2].type != 'datetime':
                            line_error.append(_('Line %d: FMC TO %d, date expected, found %s') % (idx+1, fmc, row.cells[first_fmc_col+2].data))
                            continue
                        if not isinstance(row.cells[first_fmc_col].data, (int, long, float)):
                            line_error.append(_('Line %d: FMC %d, number expected, found %s') % (idx+1, fmc, row.cells[first_fmc_col].data))
                            continue
                        data_towrite.update({
                            'rr_fmc_%d' % fmc: row.cells[first_fmc_col].data,
                            'rr_fmc_from_%d' % fmc: row.cells[first_fmc_col+1].data.strftime('%Y-%m-%d'),
                            'rr_fmc_to_%d' % fmc: row.cells[first_fmc_col+2].data.strftime('%Y-%m-%d'),
                        })
            elif seg.rule == 'minmax':
                if not row.cells[4] or not not isinstance(row.cells[4].data, (int, long, float)):
                    line_error.append(_('Line %d: Min Qty, number expected, found %s') % (idx+1, row.cells[4].data))
                elif not row.cells[5] or not not isinstance(row.cells[5].data, (int, long, float)):
                    line_error.append(_('Line %d: Max Qty, number expected, found %s') % (idx+1, row.cells[5].data))
                elif row.cells[5] < row.cells[4]:
                    line_error.append(_('Line %d: Max Qty (%s) must be large than Min Qty (%s)') % (idx+1, row.cells[5].data, row.cells[4].data))
                else:
                    data_towrite.update({
                        'min_qty': row.cells[4].data,
                        'max_qty': row.cells[5].data,
                    })
            else:
                if not row.cells[4] or not not isinstance(row.cells[4].data, (int, long, float)):
                    line_error.append(_('Line %d: Auto Supply Qty, number expected, found %s') % (idx+1, row.cells[4].data))
                else:
                    data_towrite['auto_qty'] = row.cells[4].data

            if prod_code not in existing_line:
                prod_id = product_obj.search(cr, uid, [('default_code', '=ilike', prod_code)], context=context)
                if not prod_id:
                    line_error.append(_('Line %d: product code %s not found') % (idx+1, prod_code))
                else:
                    data_towrite['product_id'] = prod_id
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

        self.write(cr, uid, seg.id, {'file_to_import': False}, context=context)
        wizard_obj = self.pool.get('physical.inventory.import.wizard')
        if error:
            error.insert(0, _('%d line(s) created, %d line(s) updated, %d line(s) in error') % (created, updated, ignored))
            return wizard_obj.message_box(cr, uid, title=_('Importation errors'), message='\n'.join(error))

        return wizard_obj.message_box(cr, uid, title=_('Importation Done'), message=_('%d line(s) created, %d line(s) updated') % (created, updated))

    def completed(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'complete'}, context=context)
        return True

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

            for prod in prod_obj.browse(cr, uid, segment[seg_id]['prod_seg_line'].keys(), fields_to_fetch=['qty_available'], context={'location': segment[seg_id]['context']['amc_location_ids']}):
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
        'rr_fmc_1': fields.float('RR FMC 1', related_uom='uom_id'),
        'rr_fmc_from_1': fields.date('From 1'),
        'rr_fmc_to_1': fields.date('To 1'),
        'rr_fmc_2': fields.float('RR FMC 2', related_uom='uom_id'),
        'rr_fmc_from_2': fields.date('From 2'),
        'rr_fmc_to_2': fields.date('To 2'),
        'rr_fmc_3': fields.float('RR FMC 3', related_uom='uom_id'),
        'rr_fmc_from_3': fields.date('From 3'),
        'rr_fmc_to_3': fields.date('To 3'),
        'rr_fmc_4': fields.float('RR FMC 4', related_uom='uom_id'),
        'rr_fmc_from_4': fields.date('From 4'),
        'rr_fmc_to_4': fields.date('To 4'),
        'rr_fmc_5': fields.float('RR FMC 5', related_uom='uom_id'),
        'rr_fmc_from_5': fields.date('From 5'),
        'rr_fmc_to_5': fields.date('To 5'),
        'rr_fmc_6': fields.float('RR FMC 6', related_uom='uom_id'),
        'rr_fmc_from_6': fields.date('From 6'),
        'rr_fmc_to_6': fields.date('To 6'),
        'rr_fmc_7': fields.float('RR FMC 7', related_uom='uom_id'),
        'rr_fmc_from_7': fields.date('From 7'),
        'rr_fmc_to_7': fields.date('To 7'),
        'rr_fmc_8': fields.float('RR FMC 8', related_uom='uom_id'),
        'rr_fmc_from_8': fields.date('From 8'),
        'rr_fmc_to_8': fields.date('To 8'),
        'rr_fmc_9': fields.float('RR FMC 9', related_uom='uom_id'),
        'rr_fmc_from_9': fields.date('From 9'),
        'rr_fmc_to_9': fields.date('To 9'),
        'rr_fmc_10': fields.float('RR FMC 10', related_uom='uom_id'),
        'rr_fmc_from_10': fields.date('From 10'),
        'rr_fmc_to_10': fields.date('To 10'),
        'rr_fmc_11': fields.float('RR FMC 11', related_uom='uom_id'),
        'rr_fmc_from_11': fields.date('From 11'),
        'rr_fmc_to_11': fields.date('To 11'),
        'rr_fmc_12': fields.float('RR FMC 12', related_uom='uom_id'),
        'rr_fmc_from_12': fields.date('From 12'),
        'rr_fmc_to_12': fields.date('To 12'),
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
            empty = 0
            for x in range(1, 13):
                rr_fmc = getattr(line, 'rr_fmc_%d'%x)
                rr_from = getattr(line, 'rr_fmc_from_%d'%x)
                rr_to = getattr(line, 'rr_fmc_to_%d'%x)
                if rr_from:
                    if empty:
                        error.append(_('%s, FMC FROM %d is not set, you can\'t have gap in FMC (%s is set)') % (line.product_id.default_code, empty, x))
                        continue
                    rr_from = datetime.strptime(rr_from, '%Y-%m-%d')
                    if rr_from.day != 1:
                        error.append(_('%s, FMC FROM %d must start the 1st day of the month') % (line.product_id.default_code, x))
                    if not rr_to:
                        if not rr_fmc:
                            empty = x
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
                elif not empty:
                    empty = x
            if error:
                raise osv.except_osv(_('Error'), _('Please correct the following FMC values:\n%s') % ("\n".join(error)))

            return True

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
        (_valid_fmc, 'FMC is invalid', []),
        (_uniq_prod_location, 'A product in a location may only belong to one segment.', []),
    ]

    _defaults = {
        'status': 'active',
    }

    def create_multiple_lines(self, cr, uid, parent_id, product_ids, context=None):
        for prod_id in product_ids:
            self.create(cr, uid, {'segment_id': parent_id, 'product_id': prod_id}, context=context)
        return True

    def change_fmc(selc, cr, uid, ids, ch_type, nb, value, context=None):
        if not value:
            return {}

        msg = False
        try:
            fmc_date = datetime.strptime(value, '%Y-%m-%d')
        except:
            return {}
        if ch_type == 'from' and fmc_date.day != 1:
            msg =  _('FMC FROM %s must be the first day of the month') % (nb,)
        elif ch_type == 'to':
            if fmc_date + relativedelta(months=1, day=1, days=-1) != fmc_date:
                msg = _('FMC TO %s must be the last day of the month') % (nb, )

        if msg:
            return {'warning': {'message': msg}}

        return {}

replenishment_segment_line()

class replenishment_segment_date_generation(osv.osv):
    _name = 'replenishment.segment.date.generation'
    _description = 'Last Generation'
    _rec_name = 'date'

    _columns = {
        'segment_id': fields.many2one('replenishment.segment', 'Segment', select=1, required=1),
        'instance_id': fields.many2one('msf.instance', string='Instance', select=1, required=1),
        'amc_date': fields.datetime('Date AMC/Stock Data'),
        'full_date': fields.datetime('Date Full Data (exp.)'),
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
        'expired_before_rrd': fields.float('Expired Qty before RRD'),
        'expired_between_rrd_oc': fields.float('Expired Qty between RRD and OC'),
        'open_loan': fields.boolean('Open Loan'),
    }

    _defaults = {
        'open_loan': False
    }
    def generate_all_amc(self, cr, uid, context=None, seg_ids=False):
        # TODO JFB RR
        # check last config mod date / conso mod date / current date and generates new AMC only if something has changed
        segment_obj = self.pool.get('replenishment.segment')
        prod_obj = self.pool.get('product.product')
        last_gen_obj = self.pool.get('replenishment.segment.date.generation')

        instance_id = self.pool.get('res.company')._get_instance_id(cr, uid)
        to_date = datetime.now() + relativedelta(day=1, days=-1)

        if not seg_ids:
            seg_ids = segment_obj.search(cr, uid, [('state', 'in', ['draft', 'complete'])], context=context)
        elif isinstance(seg_ids, (int, long)):
            seg_ids = [seg_ids]

        for segment in segment_obj.browse(cr, uid, seg_ids, context=context):
            last_gen_id = last_gen_obj.search(cr, uid, [('segment_id', '=', segment.id), ('instance_id', '=', instance_id)], context=context)
            last_gen_data = {
                'segment_id': segment.id,
                'instance_id': instance_id,
                'amc_date': datetime.now(),
                'full_date': False,
            }

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

            # AMC
            amc = prod_obj.compute_amc(cr, uid, lines.keys(), context=seg_context)
            for prod_id in amc:
                data = {'amc': amc[prod_id], 'name': to_date, 'reserved_stock': stock_qties.get(prod_id, {}).get('qty_reserved'), 'real_stock': stock_qties.get(prod_id, {}).get('qty_available'), 'open_loan': open_loan.get(prod_id, False)}
                if lines[prod_id] in cache_line_amc:
                    self.write(cr, uid, cache_line_amc[lines[prod_id]], data, context=context)
                else:
                    data['segment_line_id'] = lines[prod_id]
                    data['instance_id'] = instance_id
                    cache_line_amc[lines[prod_id]] = self.create(cr, uid, data, context=context)

            # expired_before_rrd + expired_before_oc
            if segment.state == 'complete':
                last_gen_data['full_date'] = datetime.now()
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

            if last_gen_id:
                last_gen_obj.write(cr, uid, last_gen_id, last_gen_data, context=context)
            else:
                last_gen_obj.create(cr, uid, last_gen_data, context=context)


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
        'location_config_description': fields.char('Desription', size=28, readonly=1),
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
        'state': fields.selection([('draft', 'Draft'), ('validated', 'Validated'), ('cancel', 'Cancel'), ('closed', 'Closed')], 'State', readonly=1),
        'order_calc_line_ids': fields.one2many('replenishment.order_calc.line', 'order_calc_id', 'Products',  context={'default_code_only': 1}),
        'instance_id': fields.many2one('msf.instance', 'Instance', readonly=1),
        'file_to_import': fields.binary(string='File to import'),
    }

    _defaults = {
        'generation_date': lambda *a: time.strftime('%Y-%m-%d'),
        'state': 'draft',
    }

    def import_lines(self, cr, uid, ids, context=None):
        calc_line_obj = self.pool.get('replenishment.order_calc.line')

        calc = self.browse(cr, uid, ids[0],  context=context)
        if not calc.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))
        file_data = SpreadsheetXML(xmlstring=base64.decodestring(calc.file_to_import))

        existing_line = {}
        for line in calc.order_calc_line_ids:
            existing_line[line.product_id.default_code] = line.id

        idx = -1

        error = []
        updated = 0
        for row in file_data.getRows():
            idx += 1
            if idx < 8:
                # header
                continue

            prod_code = row.cells[0].data
            if not prod_code:
                continue
            prod_code = prod_code.strip()

            if prod_code not in existing_line:
                error.append(_('Line %d: product %s not found.') % (idx+1, prod_code))
                continue

            if not isinstance(row.cells[14].data, (int, long, float)):
                error.append(_('Line %d: Agreed Order Qty  must be a number, found %s') % (idx+1, row.cells[14].data))

            calc_line_obj.write(cr, uid, existing_line[prod_code], {
                'agreed_order_qty': row.cells[14].data,
                'order_qty_comment': row.cells[15].data or '',
            }, context=context)
            updated += 1

        self.write(cr, uid, calc.id, {'file_to_import': False}, context=context)
        wizard_obj = self.pool.get('physical.inventory.import.wizard')
        if error:
            error.insert(0, _('%d line(s) updated, %d line(s) in error') % (updated, len(error)))
            return wizard_obj.message_box(cr, uid, title=_('Importation errors'), message='\n'.join(error))

        return wizard_obj.message_box(cr, uid, title=_('Importation Done'), message=_('%d line(s) updated') % (updated, ))


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
                    }, context=context)

            self.write(cr, uid, calc.id, {'state': 'closed', 'ir_generation_date': time.strftime('%Y-%m-%d')}, context=context)
            self.pool.get('replenishment.segment').write(cr, uid, calc.segment_id.id, {'previous_order_rrd': calc.new_order_reception_date}, context=context)
            ir_d = sale_obj.read(cr, uid, ir_id, ['name'], context=context)
            sale_obj.log(cr, uid, ir_id, _('%s created from %s') % (ir_d['name'], calc.name), action_xmlid='procurement_request.action_procurement_request')
        return True

    def validated(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'validated'}, context=context)
        return True

    def cancel(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
        return True
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
        'warning': fields.char('Warning', size=512, readonly='1'),
    }

replenishment_order_calc_line()
