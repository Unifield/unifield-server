# encoding: utf-8
from osv import fields, osv
from tools.translate import _
import tools
from datetime import datetime
from dateutil import tz
import time

import logging
import logging.handlers
from os import path, remove
import sys
import threading
import pooler
from dateutil.relativedelta import relativedelta

import requests

class unidata_country(osv.osv):
    _name = 'unidata.country'
    _description = 'UniData Country'
    _order = 'name'

    _columns = {
        'name': fields.char('Name', size=256, required=1, readonly=1, select=1),
        'unidata_project_ids': fields.one2many('unidata.project', 'country_id', 'Projects', readonly=1),
    }

    _sql_constraints = [
        ('unique_name', 'unique(name)', 'Name already exists.'),
    ]

unidata_country()

class product_msl_rel(osv.osv):
    _name = 'product.msl.rel'
    _table = 'product_msl_rel'

    _columns = {
        'msl_id': fields.many2one('unidata.project', 'MSL', required=1, select=1),
        'product_id': fields.many2one('product.product', 'Product', required=1, select=1),
        'creation_date': fields.datetime('Date added'),
        'deletion_date': fields.datetime('Date removed'),
        'version': fields.integer('Version number'),
        'to_delete': fields.boolean('to delete'),
    }

    _sql_constraints = [
        ('unique_msf_product', 'unique(msl_id,product_id)', 'MSL/Product exists')
    ]
product_msl_rel()

class unidata_project(osv.osv):
    _name = 'unidata.project'
    _description = 'UniData Project'
    _rec_name = 'code'
    _order = 'code'

    def name_get(self, cr, uid, ids, context=None):
        if not len(ids):
            return []
        res = []
        for proj in self.browse(cr, uid, ids, fields_to_fetch=['name', 'code'], context=context):
            res.append((proj.id, '%s - %s' % (proj['name'], proj['code'])))

        return res

    def _search_ud_sync_needed(self, cr, uid, obj, name, args, context=None):
        for arg in args:
            if arg[1] != '=' or not arg[2]:
                raise osv.except_osv('Error', 'Filter on ud_sync_needed not implemented')

            cr.execute('''
                select p.id from
                    unidata_project p
                where
                    p.msl_sync_date is null
                    or p.msl_sync_date < p.publication_date
            ''')
        return [('id', 'in', [x[0] for x in cr.fetchall()])]

    _columns = {
        'code': fields.char('UD Code', size=126, required=1, readonly=1, select=1),
        'name': fields.char('Name', size=256, readonly=1),
        'instance_id': fields.many2one('msf.instance', 'Instance', readonly=1),
        'msl_active': fields.boolean('MSL Active', readonly=1),
        'uf_active': fields.boolean('Active', readonly=1),
        'msfid': fields.integer('MSFID', readonly=1, select=1),
        'msl_status': fields.char('MSL Status', size=64, readonly=1),
        'publication': fields.integer('Publication', readonly=1),
        'publication_date': fields.datetime('Pulbication Date', readonly=1),
        'country_id': fields.many2one('unidata.country', 'Country', readonly=1),

        'msl_product_ids': fields.many2many('product.product', 'product_msl_rel', 'msl_id', 'product_id', 'MSL Products', readonly=1, order_by='default_code'),
        'msl_sync_date': fields.datetime('MSL sync date', type='char', size=60, readonly=1),
        'msl_sync_needed': fields.function(tools.misc.get_fake, fnct_search=_search_ud_sync_needed, method=True, type='boolean', string='To be ud synced'),
        'alpa_msfids': fields.text('Alpa msfids', readonly=1),
    }
    _sql_constraints = [
        ('unique_code', 'unique(code)', 'Code already exists.'),
        ('unique_msfid', 'unique(msfid)', 'MSID must be unique'),
    ]

    _defauls = {
        'uf_active': False
    }
unidata_project()


class unidata_sync_log(osv.osv):
    _name = 'unidata.sync.log'
    _description = 'UD Validation Sync'
    _rec_name = 'start_date'
    _order = 'id desc'

    def __init__(self, pool, cr):
        super(unidata_sync_log, self).__init__(pool, cr)
        if cr.column_exists('unidata_sync_log', 'state'):
            cr.execute("update unidata_sync_log set state='error', error='Server stopped' where state='running'")

    def _get_log_exists(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for log in self.read(cr, uid, ids, ['log_file'], context=context):
            res[log['id']] = log['log_file'] and path.exists(log['log_file'])
        return res

    def get_log_file(self, cr, uid, ids, context=None):
        d = self.read(cr, uid, ids[0], ['start_date', 'log_file', 'log_exists'], context=context)
        if not d['log_exists']:
            raise osv.except_osv(_('Error'), _('Log file does not exist.'))
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'product_attributes.unidata_sync_log_download',
            'datas': {'ids': [ids[0]], 'target_filename': path.basename(d['log_file'])}
        }

    _columns = {
        'start_date': fields.datetime('Start Date', readonly=1),
        'end_date': fields.datetime('End Date', readonly=1),
        'number_products_pulled': fields.integer('# products pulled', readonly=1),
        'number_products_updated': fields.integer('# products updated', readonly=1),
        'error': fields.text('Error', readonly=1),
        'page_size': fields.integer('page size', readonly=1),
        'state': fields.selection([('running', 'Running'), ('error', 'Error'), ('done', 'Done')], 'State', readonly=1),
        'sync_type': fields.selection([('full', 'Full'), ('cont', 'Continuation'), ('diff', 'Based on last modification date')], 'Sync Type', readonly=1),
        'msfid_min': fields.integer('Min Msfid', readonly=1),
        'last_date': fields.char('Last Date', size=64, readonly=1),
        'log_file': fields.char('Path to log file', size=128, readonly=1),
        'log_exists': fields.function(_get_log_exists, type='boolean', method=1, string='Log file exists'),
        'start_uid': fields.many2one('res.users', 'Started by', readonly=1),
        'server': fields.selection([('msl', 'MSL'), ('ud', 'unidata')], 'Server', readonly=1),
    }

unidata_sync_log()


class ud_sync():

    def __init__(self, cr, uid, pool, max_retries=4, logger=False, context=None):
        self.cr = cr
        self.uid = uid
        self.pool = pool
        self.max_retries = max_retries
        self.context = context
        self.logger = logger
        self.oc = self.pool.get('sync.client.entity').get_entity(self.cr, self.uid, context).oc

        sync_id = self.pool.get('ir.model.data').get_object_reference(self.cr, self.uid, 'product_attributes', 'unidata_sync_config')[1]
        config = self.pool.get('unidata.sync').read(self.cr, self.uid, sync_id, context=self.context)

        self.page_size = config['page_size'] or 500
        self.ud_params = {
            'login': config['login'],
            'password': config['password'],
            'size': self.page_size,
            'publishonweb': False,
        }
        self.url = config['url']
        self.url_msl = config['url_msl']
        self.timeout = config['ud_timeout']
        self.nb_keep_log = config['nb_keep_log']
        self.country_cache = {}
        self.project_cache = {}
        self.msf_intance_cache = {}

        if self.pool.get('res.company')._get_instance_level(self.cr, self.uid) != 'section':
            raise osv.except_osv(_('Error'), _('UD/MSL sync can only be started at HQ level.'))

    def create_msl_list(self):
        oc_number = {
            'oca': 5,
            'ocb': 4,
            'ocg': 7,
            'ocp': 8,
        }

        url = '%s/projects' % (self.url_msl, )
        q_filter = "ocId='%s'" % (oc_number.get(self.oc),)


        country_obj = self.pool.get('unidata.country')
        project_obj = self.pool.get('unidata.project')
        instance_obj = self.pool.get('msf.instance')
        prod_obj = self.pool.get('product.product')

        # TODO
        #prod_cache = {}
        page = 1
        while True:
            js = self.query(q_filter, page=page, url=url)
            if not js.get('rows'):
                break
            for x in js.get('rows'):
                self.log(x)
                if x.get('uniFieldCode'):
                    if x['uniFieldCode'] not in self.msf_intance_cache:
                        msf_ids = instance_obj.search(self.cr, self.uid, [('code', '=', x['uniFieldCode'])], context=self.context)
                        self.msf_intance_cache[x['uniFieldCode']] = msf_ids and msf_ids[0] or False
                if x.get('country', {}).get('labels', {}).get('english'):
                    if x['country']['labels']['english'] not in self.country_cache:
                        c_ids = country_obj.search(self.cr, self.uid, [('name', '=', x['country']['labels']['english'])], context=self.context)
                        if c_ids:
                            self.country_cache[x['country']['labels']['english']] = c_ids[0]
                        else:
                            self.country_cache[x['country']['labels']['english']] = country_obj.create(self.cr, self.uid, {'name': x['country']['labels']['english']}, context=self.context)

                project_data = {
                    'instance_id': self.msf_intance_cache.get(x.get('uniFieldCode')),
                    'msl_active': x.get('active'),
                    'msfid': x.get('id'),
                    'msl_status': x.get('mslStatus', {}).get('english'),
                    'name': x.get('name', {}).get('english'),
                    'publication': x.get('publication'),
                    'publication_date': x.get('publicationDate') and self.ud_date(x.get('publicationDate')) or False,
                    'code': x['code'],
                    'country_id': self.country_cache.get(x.get('country', {}).get('labels', {}).get('english')),
                    'alpa_msfids': '',
                }

                if x.get('publicationDate'):
                    project_data['alpa_msfids'] = ','.join(l['id'] for l in x.get('lists', []))
                else:
                    project_data['msl_product_ids'] = [(6, 0, [])]

                if x.get('code') not in self.project_cache:
                    proj_ids = project_obj.search(self.cr, self.uid, [('code', '=', x.get('code'))], context=self.context)
                    if proj_ids:
                        self.project_cache[x['code']] = proj_ids[0]
                if not self.project_cache.get(x.get('code')):
                    self.project_cache[x['code']] = project_obj.create(self.cr, self.uid, project_data, context=self.context)
                else:
                    project_obj.write(self.cr, self.uid, self.project_cache[x['code']], project_data, context=self.context)

            page += 1
            if 'nextPage' not in js['pagination']:
                break


        list_url = '%s/lists' % (self.url_msl, )
        msl_ids = project_obj.search(self.cr, self.uid, [('msl_sync_needed', '=', True)], context=self.context)
        exec_date = False
        for msl in project_obj.browse(self.cr, self.uid, msl_ids, fields_to_fetch=['alpa_msfids'], context=self.context):
            prod_ids = set()
            if msl.alpa_msfids:
                for list_msfid in msl.alpa_msfids.split(','):
                    page = 1
                    q_filter = "id='%s'" % (list_msfid,)
                    exec_date = False
                    while True:
                        js = self.query(q_filter, page=page, url=list_url)
                        page += 1
                        self.log(js)
                        if not exec_date:
                            exec_date = self.ud_date(js.get('context', {}).get('executeDate'))
                        for row in js.get('rows', []):
                            for x in row.get('articles', []):
                                p_id = prod_obj.search(self.cr, self.uid, [('active', 'in', ['t', 'f']), ('msfid', '=', x['id'])], context=self.context)
                                if not p_id:
                                    self.warn('Product %s msfid:%s not found' % x['code'], x['msfid'])
                                else:
                                    prod_ids.add(p_id[0])

                        if 'nextPage' not in js['pagination']:
                            break
            if not exec_date:
                exec_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            project_obj.write(self.cr, self.uid, msl.id, {'msl_product_ids': [(6, 0, list(prod_ids))], 'msl_sync_date': exec_date}, context=self.context)
            # TODO: increment
            version = 1
            self.cr.execute("update product_msl_rel set to_delete='t' where msl_id=%s", (msl.id,))
            for prod_id in prod_ids:
                self.cr.execute("insert into product_msl_rel (msl_id, product_id, creation_date, version) values (%s, %s, NOW(), %s) ON CONFLICT (msl_id, product_id) DO UPDATE SET to_delete='f'", (msl.id, prod_id, version))
            # update version on resurected links
            self.cr.execute("update product_msl_rel set version=%s, deletion_date=NULL where to_delete='f' and deletion_date is not null and msl_id=%s", (version, msl.id))
            # mark as to delete
            self.cr.execute("update product_msl_rel set version=%s, deletion_date=NOW() where to_delete='t' and deletion_date is null and msl_id=%s", (version, msl.id))

            offset = 0
            search_page = 500
            while True:
                rel_ids = self.pool.get('product.msl.rel').search(self.cr, self.uid, [('msl_id', '=', msl.id)], order='id', offset=offset, limit=search_page, context=self.context)
                if not rel_ids:
                    break
                offset += search_page
                self.pool.get('product.msl.rel').get_sd_ref(self.cr, 1, rel_ids)
                if len(rel_ids) < search_page:
                    break
            self.cr.execute("""
                update
                    ir_model_data d
                set
                    last_modification=NOW(),
                    touched='[''product_id'']'
                from
                    product_msl_rel r
                where
                    d.model = 'product.msl.rel'
                    and d.module = 'sd'
                    and d.res_id = r.id
                    and r.version = %s
            """, (version, ))


    def ud_date(self, date):
        date = date.split('.')[0] # found 3 formats in UD: 2021-03-30T06:32:51.500, 2021-03-30T06:32:51  and 2021-03-30T06:32
        try:
            date_fmt = datetime.strptime(date, '%Y-%m-%dT%H:%M:%S')
        except:
            date_fmt = datetime.strptime(date, '%Y-%m-%dT%H:%M')
        return date_fmt.replace(tzinfo=tz.tzutc()).astimezone(tz.tzlocal()).strftime('%Y-%m-%d %H:%M:%S')

    def query(self, q_filter, page=1, url=None):
        params = self.ud_params.copy()
        params['page'] = page
        params['filter'] = q_filter

        request_ok = False
        retry = 0
        while not request_ok:
            try:
                self.log('OC: %s Page: %d, Filter: %s' % (self.oc, page, params['filter']))
                if url is None:
                    url = self.url

                r = requests.get(url, params, timeout=self.timeout)
                if r.status_code != requests.codes.ok:
                    r.raise_for_status()
                request_ok = True
            except Exception as e:
                if retry < self.max_retries:
                    retry += 1
                    self.log('Query error %d, retry in 5sec: %s' % (retry, tools.misc.get_traceback(e)), 'warn')
                    time.sleep(5)
                else:
                    raise
        return r.json()

    def log(self, msg, level=None):
        if self.logger:
            if level == 'warn':
                llevel = logging.WARNING
            elif level == 'error':
                llevel = logging.ERROR
            else:
                llevel = logging.INFO
            self.logger.log(llevel, msg)

    def update_products(self, q_filter, record_date):
        country_obj = self.pool.get('unidata.country')
        project_obj = self.pool.get('unidata.project')
        prod_obj = self.pool.get('product.product')

        page = 1
        date_to_record = False
        prod_updated = 0
        rows_seen = 0
        while True:
            js = self.query(q_filter, page=page)

            if record_date:
                date_to_record = js.get('context', {}).get('executeDate')
            record_date = False

            if not js.get('rows'):
                break

            for x in js.get('rows'):
                self.log('UD: %s' % x)
                rows_seen += 1
                prod_id = prod_obj.search(self.cr, self.uid, [('msfid', '=', x['id']), ('active', 'in', ['t', 'f'])], context=self.context)
                if not prod_id:
                    self.log('Product not found in UF, msfid: %s, code: %s' % (x['id'], x['code'], ))
                    continue

                oc_data = x.get('ocValidations', {}).get(self.oc, {})
                data = {
                    'oc_validation': oc_data.get('valid'),
                    'oc_validation_date': False,
                    'oc_devalidation_date': False,
                    'oc_devalidation_reason': oc_data.get('devalidationReason'),
                    'oc_comments': oc_data.get('comments'),

                }

                if oc_data.get('lastValidationDate'):
                    data['oc_validation_date'] = self.ud_date(oc_data['lastValidationDate'])
                if oc_data.get('lastDevalidationDate'):
                    data['oc_devalidation_date'] = self.ud_date(oc_data['lastDevalidationDate'])

                c_restriction = []
                p_restriction = []
                for mr in oc_data.get('missionRestrictions', []):
                    if mr.get('country', {}).get('labels', {}).get('english'):
                        if mr['country']['labels']['english'] not in self.country_cache:
                            c_id = country_obj.search(self.cr, self.uid, [('name', '=', mr['country']['labels']['english'])], context=self.context)
                            if not c_id:
                                c_id = country_obj.create(self.cr, self.uid, {'name': mr['country']['labels']['english']}, context=self.context)

                                self.log('Create country %s' % (mr['country']['labels']['english'],))
                                self.country_cache[mr['country']['labels']['english']] = c_id
                            else:
                                self.country_cache[mr['country']['labels']['english']] = c_id[0]
                        c_restriction.append(self.country_cache[mr['country']['labels']['english']])

                    for pr in mr.get('projectRestrictions', []):
                        if pr.get('code'):
                            if pr.get('code') not in self.project_cache:
                                p_id = project_obj.search(self.cr, self.uid, [('code', '=', pr['code'])], context=self.context)
                                if not p_id:
                                    self.log('Create project %s' % (pr['code'], ))
                                    self.project_cache[pr['code']] = project_obj.create(self.cr, self.uid, {'code': pr['code'], 'name': pr.get('name')}, context=self.context)
                                else:
                                    self.project_cache[pr['code']] = p_id[0]
                            p_restriction.append(self.project_cache[pr['code']])

                data.update({
                    'oc_country_restrictions': [(6, 0, list(set(c_restriction)))],
                    'oc_project_restrictions':  [(6, 0, list(set(p_restriction)))],
                })
                self.log('Write product id: %d, code: %s, msfid: %s, data: %s' % (prod_id[0], x['code'], x['id'], data))
                prod_obj.write(self.cr, self.uid, prod_id[0], data, context=self.context)
                prod_updated += 1
            page += 1
            if len(js.get('rows')) < self.page_size:
                break

        return date_to_record, rows_seen, prod_updated




class unidata_sync(osv.osv):
    _name = 'unidata.sync'
    _description = "UniData Sync"
    _lock = threading.RLock()

    def _get_log(self, cr, uid, ids, field_name, args, context=None):
        res = {}

        cr.execute("select start_date, end_date, state, sync_type from unidata_sync_log order by id desc limit 1")
        one = cr.fetchone()
        if one:
            last_execution_start_date = one[0]
            last_execution_end_date = one[1]
            last_execution_status = one[2]
            last_execution_sync_type = one[3]
        else:
            last_execution_start_date = last_execution_end_date = last_execution_status = last_execution_sync_type = False

        param_obj = self.pool.get('ir.config_parameter')
        eligible_for_full_sync = bool(param_obj.get_param(cr, 1, 'LAST_MSFID_SYNC')) or bool(param_obj.get_param(cr, 1, 'LAST_UD_DATE_SYNC')) or False
        for _id in ids:
            res[_id] = {
                'last_execution_start_date': last_execution_start_date,
                'last_execution_end_date': last_execution_end_date,
                'last_execution_status': last_execution_status,
                'last_execution_sync_type': last_execution_sync_type,
                'eligible_for_full_sync': eligible_for_full_sync,
            }

        return res

    def _get_next_planned_date(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        cron_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'ir_cron_unidata_sync')[1]
        cron_date = self.pool.get('ir.cron').read(cr, uid, cron_id, ['nextcall'])['nextcall']
        for _id in ids:
            res[_id] = cron_date
        return res

    _columns = {
        'url': fields.char('URL', size=256, required=1),
        'url_msl': fields.char('MSL URL', size=256, required=1),
        'login': fields.char('Login', size=256),
        'password': fields.char('Password', size=256),

        'next_run_date': fields.datetime('Force next execution date'),
        'next_planned_date': fields.function(_get_next_planned_date,  method=True, type='datetime', string='Next Scheduled date'),
        'page_size': fields.integer('UD Page size'),
        'nb_keep_log': fields.integer('Number of log files to keep'),
        'ud_timeout': fields.integer('UD Timeout in second'),
        'last_execution_start_date': fields.function(_get_log, method=True, multi='get_log', type='datetime', string="Last Execution Start Date"),
        'last_execution_end_date': fields.function(_get_log, method=True, multi='get_log', type='datetime', string="Last Execution End Date"),
        'last_execution_sync_type': fields.function(_get_log, method=True, multi='get_log', type='selection', selection=[('full', 'Full'), ('cont', 'Continuation'), ('diff', 'Based on last modification date')], string="Last Execution Sync Type"),
        'last_execution_status': fields.function(_get_log, method=True, multi='get_log', type='selection', selection=[('running', 'Running'), ('error', 'Error'), ('done', 'Done')], string="Last Execution State"),
        'eligible_for_full_sync': fields.function(_get_log, method=True, multi='get_log', type='boolean', string="Eligible for full sync"),
        'is_active': fields.boolean('Active'),
        'interval': fields.integer('Scheduler interval (hours)'),
    }

    _defaults = {
        'is_active': False,
        'interval': 24,
        'page_size': 500,
        'ud_timeout': 30,
        'nb_keep_log': 30,
    }

    def _purge_log(self, cr, uid, context=None):
        sync_obj = ud_sync(cr, uid, self.pool, context=context)
        if sync_obj.nb_keep_log:
            log_obj = self.pool.get('unidata.sync.log')
            log_ids = log_obj.search(cr, uid, [('log_file', '!=', False)], offset=sync_obj.nb_keep_log, order='id desc', context=context)
            to_reset = []
            for log in log_obj.read(cr, uid, log_ids, ['log_file', 'log_exists'], context=context):
                if log['log_exists']:
                    try:
                        remove(log['log_file'])
                        to_reset.append(log['id'])
                    except:
                        raise

            if to_reset:
                log_obj.write(cr, uid, to_reset, {'log_file': False}, context=context)

        return True


    def create(self, cr, uid, vals, context=None):
        if self.search_exists(cr, uid, [], context=context):
            raise osv.except_osv(_('Error'), _('Only 1 UniData config record is allowed'))
        return super(unidata_sync, self).create(cr, uid, vals, context=context)

    def test_connection(self, cr, uid, ids, vals, context=None):
        try:
            ud_sync(cr, uid, self.pool, max_retries=0).query(q_filter='msfIdentifier=1234')
        except requests.exceptions.HTTPError as e:
            raise osv.except_osv(_('Error'), e.message)
        raise osv.except_osv(_('OK'), _('Login successful'))


    def write(self, cr, uid, ids, vals, context=None):
        cron_data = {}
        if 'is_active' in vals:
            cron_data['active'] = vals['is_active']
        if 'interval' in vals:
            cron_data['interval_number'] = vals['interval']
            cron_data['interval_type'] = 'hours'
        if vals.get('next_run_date'):
            cron_data['nextcall'] = vals['next_run_date']
            vals['next_run_date'] = False
        if cron_data:
            cron_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'ir_cron_unidata_sync')[1]
            self.pool.get('ir.cron').write(cr, uid, cron_id, cron_data, context=context)

        return super(unidata_sync, self).write(cr, uid, ids, vals, context=context)


    def set_as_full(self, cr, uid, ids, context=None):
        param_obj = self.pool.get('ir.config_parameter')
        param_obj.set_param(cr, 1, 'LAST_UD_DATE_SYNC', '')
        param_obj.set_param(cr, 1, 'LAST_MSFID_SYNC','')
        return True

    def _start_bg(self, dbname, uid, context=None):
        cr = pooler.get_db(dbname).cursor()
        try:
            self.start_ud_sync(cr, uid, context=context)
        except Exception, e:
            # TODO
            raise
            self._error = e
        finally:
            cr.commit()
            cr.close(True)
        return True

    def start_manual(self, cr, uid, ids, context=None):
        self._error = ''
        new_thread = threading.Thread(
            target=self._start_bg,
            args=(cr.dbname, uid, context)
        )
        new_thread.start()
        new_thread.join(3.0)
        if not new_thread.isAlive() and self._error:
            raise self._error
        return True

    def start_ud_sync(self, cr, uid, context=None):
        if self.pool.get('res.company')._get_instance_level(cr, uid) != 'section':
            raise osv.except_osv(_('Error'), _('UD sync can only be started at HQ level.'))

        if not self._lock.acquire(blocking=False):
            raise osv.except_osv(_('Error'), _('A sync is already running ...'))
        try:
            sync_obj = ud_sync(cr, uid, self.pool, logger=logging.getLogger('msl'), context=context)
            sync_obj.create_msl_list()
            #self._start_ud_sync(cr, uid, context=context)
        finally:
            self._lock.release()

    def _start_ud_sync(self, cr, nuid, full=False, context=None):

        uid = self.pool.get('ir.model.data').get_object_reference(cr, nuid, 'base', 'user_unidata_pull')[1]

        session_obj = self.pool.get('unidata.sync.log')
        param_obj = self.pool.get('ir.config_parameter')



        nb_prod = 0
        updated = 0

        if full:
            param_obj.set_param(cr, 1, 'LAST_UD_DATE_SYNC', '')
            param_obj.set_param(cr, 1, 'LAST_MSFID_SYNC','')

        sync_type = 'full'
        last_ud_date_sync = param_obj.get_param(cr, 1, 'LAST_UD_DATE_SYNC') or False
        if last_ud_date_sync:
            sync_type = 'diff'


        logger = logging.getLogger('unidata-sync')
        sync_obj = ud_sync(cr, uid, self.pool, logger=logger, context=context)
        page_size = sync_obj.page_size

        min_msfid = param_obj.get_param(cr, 1, 'LAST_MSFID_SYNC') or 0
        if min_msfid:
            # do not update last sync date
            first_query = False
            sync_type = 'cont'
            last_ud_date_sync = param_obj.get_param(cr, 1, 'FORMER_UD_DATE_SYNC')
        else:
            # full or diff
            first_query = True
            param_obj.set_param(cr, 1, 'FORMER_UD_DATE_SYNC', last_ud_date_sync or '')

        nuid = hasattr(nuid, 'realUid') and nuid.realUid or nuid
        session_id = session_obj.create(cr, uid, {'start_date': fields.datetime.now(), 'state': 'running', 'page_size': page_size, 'msfid_min': min_msfid, 'last_date': last_ud_date_sync, 'sync_type': sync_type, 'start_uid': nuid}, context=context)

        formatter = logging.Formatter('%(asctime)s : %(levelname)s : %(message)s')
        if tools.config['logfile']:
            log_file = path.join(path.dirname(tools.config['logfile']), 'ud-sync-%s-%s.log' % (session_id, datetime.now().strftime('%Y-%m-%d-%H%M')))
            handler = logging.FileHandler(log_file)
            session_obj.write(cr, uid, session_id, {'log_file': log_file}, context=context)
        else:
            handler = logging.StreamHandler(sys.stdout)

        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False

        self._purge_log(cr, uid, context=context)
        # commit to display running session
        cr.commit()
        logger.info('Sync start, page size: %s, last msfid: %s, last date: %s' % (page_size, min_msfid, last_ud_date_sync))

        try:
            while True:
                cr.execute('SAVEPOINT unidata_sync_log')
                cr.execute("select min(msfid), max(msfid) from product_product p where id in (select id from product_product where coalesce(msfid,0)!=0 and msfid>%s order by msfid limit %s)", (min_msfid, page_size))
                min_id, max_id = cr.fetchone()
                min_msfid = max_id
                if not min_id:
                    break

                q_filter = "(msfIdentifier>=%s and msfIdentifier<=%s)"%(min_id, max_id)
                if last_ud_date_sync:
                    createdOn = (datetime.strptime(last_ud_date_sync.split('T')[0], '%Y-%m-%d') + relativedelta(days=-3)).strftime('%Y-%m-%dT00:00:00')
                    q_filter = '(date-greater-or-equal(./metaData/mostRecentUpdate, "%(last_ud_date_sync)s") or date-greater-or-equal(./metaData/createdOn, "%(createdOn)s")) and %(filter)s' %{
                        'filter': q_filter,
                        'last_ud_date_sync': last_ud_date_sync,
                        'createdOn': createdOn,
                    }

                s_date_to_record, rows_seen, prod_updated = sync_obj.update_products(q_filter, first_query)
                if first_query and s_date_to_record:
                    logger.info('Set last date: %s', s_date_to_record)
                    param_obj.set_param(cr, 1, 'LAST_UD_DATE_SYNC', s_date_to_record)
                first_query = False
                param_obj.set_param(cr, 1, 'LAST_MSFID_SYNC', min_msfid)

                updated += prod_updated
                nb_prod += rows_seen

                session_obj.write(cr, uid, session_id, {'number_products_pulled': nb_prod, 'number_products_updated': updated}, context=context)
                cr.commit()

                # end of sql loop

        except Exception as e:
            cr.execute('ROLLBACK TO SAVEPOINT unidata_sync_log')
            error = tools.misc.get_traceback(e)
            logger.error('End of Script with error: %s' % error)
            handler.close()
            logger.removeHandler(handler)
            session_obj.write(cr, uid, session_id, {'end_date': fields.datetime.now(), 'state': 'error', 'number_products_pulled': nb_prod, 'error': error, 'number_products_updated': updated}, context=context)
            return False

        logger.info('End of Script')
        handler.close()
        logger.removeHandler(handler)
        session_obj.write(cr, uid, session_id, {'end_date': fields.datetime.now(), 'state': 'done', 'number_products_pulled': nb_prod, 'number_products_updated': updated}, context=context)
        param_obj.set_param(cr, 1, 'LAST_MSFID_SYNC', '')
        return True


    def open_menu(self, cr, uid, ids, context=None):
        res_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'unidata_sync_config')[1]
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'unidata.sync',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': res_id
        }

unidata_sync()

