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
    _rec_name = 'msl_id'
    _order = 'product_id'

    _columns = {
        'msl_id': fields.many2one('unidata.project', 'MSL', required=1, select=1),
        'product_id': fields.many2one('product.product', 'Product', required=1, select=1),
        'creation_date': fields.datetime('Added date'),
        'deletion_date': fields.datetime('Removed date'),
        'version': fields.integer('Version number'),
        'to_delete': fields.boolean('to delete'),
        'unifield_instance_id': fields.many2one('unifield.instance', 'Instance', select=1)
    }

    _sql_constraints = [
        ('unique_msf_product', 'unique(msl_id,product_id)', 'MSL/Product exists')
    ]

    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        res = dict.fromkeys(ids, False)
        for line in self.browse(cr, uid, ids, fields_to_fetch=['msl_id'], context=context):
            if not line.msl_id.instance_id:
                continue
            if line.msl_id.instance_id.level == 'project':
                res[line.id] = line.msl_id.instance_id.parent_id.instance
            elif line.msl_id.instance_id.level == 'coordo':
                res[line.id] = line.msl_id.instance_id.instance
        return res

product_msl_rel()

class unifield_instance(osv.osv):
    _name = 'unifield.instance'
    _description = 'UniField Instance'
    _rec_name = 'instance_name'
    _order = 'instance_name'


    def _get_is_published(self, cr, uid, ids, field_name, args, context=None):
        if not ids:
            return {}

        ret = {}
        for _id in ids:
            ret[_id] = False
        cr.execute('''
                    select distinct(unifield_instance_id) from
                        unidata_project p
                    where
                        p.publication_date is not null and unifield_instance_id in %s
                ''', (tuple(ids), ))

        for x in cr.fetchall():
            ret[x[0]] = True
        return ret

    def _search_is_published(self, cr, uid, obj, name, args, context=None):
        for arg in args:
            if arg[1] != '=' or not arg[2]:
                raise osv.except_osv('Error', 'Filter on is_published not implemented')

            cr.execute('''
                    select distinct(unifield_instance_id) from
                        unidata_project p
                    where
                        p.publication_date is not null
                ''')
        return [('id', 'in', [x[0] for x in cr.fetchall()])]

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Instance', readonly=1, domain=[('level', '!=', 'section')]),
        'instance_name': fields.related('instance_id', 'code', type='char', size=64, string='Instance', store=True, readonly=1),
        'uf_active': fields.boolean('Active'),
        'country_id': fields.many2one('unidata.country', 'Country', readonly=1),
        'msl_product_ids': fields.many2many('product.product', 'product_msl_rel', 'unifield_instance_id', 'product_id', 'Product Code', readonly=1, order_by='default_code', sql_rel_domain="product_msl_rel.creation_date is not null"),
        'unidata_project_ids': fields.one2many('unidata.project', 'unifield_instance_id', 'UniData Project', readonly=1),
        'is_published': fields.function(_get_is_published, type='boolean', method=True, string='Published', fnct_search=_search_is_published),
    }

    def _ud_project_uf_active(self, cr, uid, ids, value, context=None):
        unidata_project_obj = self.pool.get('unidata.project')
        proj_ids = unidata_project_obj.search(cr, uid, [('unifield_instance_id', 'in', ids)], context=context)
        if proj_ids:
            unidata_project_obj.write(cr, uid, proj_ids, {'uf_active': value}, context=context)


    def activate(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'uf_active': True}, context=context)
        self._ud_project_uf_active(cr, uid, ids, True, context=context)
        return True

    def de_activate(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'uf_active': False}, context=context)
        self._ud_project_uf_active(cr, uid, ids, False, context=context)
        return True

    def wiz_activate(self, cr, uid, fids, state, context=None):
        ids = context.get('active_ids')
        self.write(cr, uid, ids, {'uf_active': state=='active'}, context=context)
        return {'type': 'ir.actions.refresh_o2m', 'o2m_refresh': '_terp_list'}


    _sql_constraints = [
        ('unique_instance_id', 'unique(instance_id)', 'Instance already exists.'),
    ]

unifield_instance()

class unidata_project(osv.osv):
    _name = 'unidata.project'
    _description = 'UniData Project'
    _rec_name = 'instance_name'
    _order = 'code'
    _trace = True

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
        'unifield_instance_id': fields.many2one('unifield.instance', 'UniField Instance', readonly=1),
        'instance_id': fields.many2one('msf.instance', 'Instance', readonly=1),
        'instance_name': fields.related('instance_id', 'code', type='char', size=64, string='Instance', store=True, readonly=1),
        'code': fields.char('UD Code', size=126, required=1, readonly=1, select=1),
        'name': fields.char('Name', size=256, readonly=1),
        'msl_active': fields.boolean('MSL Active', readonly=1),
        'uf_active': fields.boolean('Active'),
        'msfid': fields.integer('MSFID', readonly=1, select=1),
        'msl_status': fields.char('MSL Status', size=64, readonly=1),
        'publication': fields.integer('Publication', readonly=1),
        'publication_date': fields.datetime('Publication Date', readonly=1),
        'country_id': fields.many2one('unidata.country', 'Country', readonly=1),

        'msl_product_ids': fields.many2many('product.product', 'product_msl_rel', 'msl_id', 'product_id', 'Product Code', readonly=1, order_by='default_code', sql_rel_domain="product_msl_rel.creation_date is not null"),
        'msl_sync_date': fields.datetime('MSL sync date', type='char', size=60, readonly=1),
        'msl_sync_needed': fields.function(tools.misc.get_fake, fnct_search=_search_ud_sync_needed, method=True, type='boolean', string='To be ud synced'),
        'alpa_msfids': fields.text('Alpa msfids', readonly=1),
    }
    _sql_constraints = [
        ('unique_code', 'unique(code)', 'Code already exists.'),
        ('unique_msfid', 'unique(msfid)', 'MSFID must be unique'),
    ]

    _defauls = {
        'uf_active': False
    }

    def _set_uf_active_from_parent(self, cr, uid, vals, context=None):
        if 'uf_active' not in vals and 'unifield_instance_id' in vals:
            vals['uf_active'] = self.pool.get('unifield.instance').search_exists(cr, uid, [('uf_active', '=', True), ('id', '=', vals['unifield_instance_id'])], context=context)

    def create(self, cr, uid, vals, context=None):
        self._set_uf_active_from_parent(cr, uid, vals, context=context)
        return super(unidata_project, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, int):
            ids = [ids]
        self._set_uf_active_from_parent(cr, uid, vals, context=context)
        if ids and 'unifield_instance_id' in vals:
            # TODO test NULL
            cr.execute('update product_msl_rel set unifield_instance_id=%s where msl_id in %s', (vals['unifield_instance_id'], tuple(ids)))
        return super(unidata_project, self).write(cr, uid, ids, vals, context=context)

    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        res = dict.fromkeys(ids, False)
        for proj in self.browse(cr, uid, ids, fields_to_fetch=['instance_id'], context=context):
            if proj.instance_id.level == 'project':
                res[proj.id] = proj.instance_id.parent_id.instance
            elif proj.instance_id.level == 'coordo':
                res[proj.id] = proj.instance_id.instance
        return res

    def activate(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'uf_active': True}, context=context)
        return True

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
        'number_lists_pulled': fields.integer('# projects pulled', readonly=1),
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
        self.unidata_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_6')[1]

        self.page_size = config['page_size'] or 500
        self.ud_params = {
            'login': config['login'],
            'password': config['password'],
            'size': self.page_size,
            #'publishonweb': False,
        }
        self.url = config['url']
        self.url_msl = config['url_msl']
        self.timeout = config['ud_timeout']
        self.nb_keep_log = config['nb_keep_log']
        self.country_cache = {}
        self.project_cache = {}
        self.msf_intance_cache = {}
        self.uf_instance_cache = {}
        self.uf_product_cache = {}

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
        uf_instance_obj = self.pool.get('unifield.instance')
        # TODO
        #prod_cache = {}
        page = 1
        nb_lists = 0
        nb_products = 0
        while True:
            self.log('Query %s, page: %s' % (q_filter, page))
            js = self.query(q_filter, page=page, url=url)
            if not js.get('rows'):
                break
            for x in js.get('rows'):
                nb_lists += 1
                self.log(x)
                if x.get('uniFieldCode'):
                    if x['uniFieldCode'] not in self.msf_intance_cache:
                        msf_ids = instance_obj.search(self.cr, self.uid, [('code', '=', x['uniFieldCode'])], context=self.context)
                        self.msf_intance_cache[x['uniFieldCode']] = msf_ids and msf_ids[0] or False
                if x.get('uniFieldCode') and self.msf_intance_cache[x['uniFieldCode']]:
                    if x['uniFieldCode'] not in self.uf_instance_cache:
                        uf_instance_ids = uf_instance_obj.search(self.cr, self.uid, [('instance_id', '=', self.msf_intance_cache[x['uniFieldCode']])], context=self.context)
                        if not uf_instance_ids:
                            self.uf_instance_cache[x['uniFieldCode']] = uf_instance_obj.create(self.cr, self.uid, {
                                'instance_id': self.msf_intance_cache[x['uniFieldCode']],
                            }, context=self.context)
                        else:
                            self.uf_instance_cache[x['uniFieldCode']] = uf_instance_ids[0]
                if x.get('country', {}).get('labels', {}).get('english'):
                    if x['country']['labels']['english'] not in self.country_cache:
                        c_ids = country_obj.search(self.cr, self.uid, [('name', '=', x['country']['labels']['english'])], context=self.context)
                        if c_ids:
                            self.country_cache[x['country']['labels']['english']] = c_ids[0]
                        else:
                            self.country_cache[x['country']['labels']['english']] = country_obj.create(self.cr, self.uid, {'name': x['country']['labels']['english']}, context=self.context)
                    if x.get('uniFieldCode') and x['uniFieldCode'] in self.uf_instance_cache:
                        uf_instance_obj.write(self.cr, self.uid, self.uf_instance_cache[x['uniFieldCode']], {'country_id': self.country_cache[x['country']['labels']['english']]}, context=self.context)

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
                    'unifield_instance_id': self.uf_instance_cache.get(x.get('uniFieldCode')),
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
        #exec_date = False
        self.cr.execute("SELECT nextval('unidata_sync_msl_seq')")
        version = self.cr.fetchone()[0]

        for msl in project_obj.browse(self.cr, self.uid, msl_ids, fields_to_fetch=['alpa_msfids', 'instance_id'], context=self.context):
            prod_ids = set()
            if msl.alpa_msfids:
                for list_msfid in msl.alpa_msfids.split(','):
                    page = 1
                    q_filter = "id='%s'" % (list_msfid,)
                    #exec_date = False
                    while True:
                        js = self.query(q_filter, page=page, url=list_url)
                        page += 1
                        self.log(js)
                        #if not exec_date:
                        #    exec_date = self.ud_date(js.get('context', {}).get('executeDate'))
                        for row in js.get('rows', []):
                            nb_products += 1
                            for x in row.get('articles', []):
                                p_id = prod_obj.search(self.cr, self.uid, [('active', 'in', ['t', 'f']), ('msfid', '=', x['id'])], order='active desc, id', context=self.context)
                                if not p_id:
                                    self.log('Product not found in UF, msfid: %s, code: %s' % (x['id'], x['code']), 'warn')
                                else:
                                    prod_ids.add(p_id[0])

                        if 'nextPage' not in js['pagination']:
                            break

            #if not exec_date:
            #    exec_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            #project_obj.write(self.cr, self.uid, msl.id, {'msl_sync_date': exec_date}, context=self.context)
            self.cr.execute('update unidata_project set msl_sync_date=publication_date where id=%s', (msl.id,))

            self.cr.execute("update product_msl_rel set to_delete='t', unifield_instance_id=%s where msl_id=%s", (self.uf_instance_cache.get(msl.instance_id.code), msl.id)) # TODO SET NULL
            for prod_id in prod_ids:
                self.cr.execute("insert into product_msl_rel (msl_id, product_id, creation_date, version, unifield_instance_id) values (%s, %s, NOW(), %s, %s) ON CONFLICT (msl_id, product_id) DO UPDATE SET to_delete='f'", (msl.id, prod_id, version, self.uf_instance_cache.get(msl.instance_id.code)))
            # update version on resurected links
            self.cr.execute("update product_msl_rel set version=%s, deletion_date=NULL where to_delete='f' and deletion_date is not null and msl_id=%s", (version, msl.id))
            # mark as to delete
            self.cr.execute("update product_msl_rel set version=%s, deletion_date=NOW() where to_delete='t' and deletion_date is null and msl_id=%s", (version, msl.id))

            offset = 0
            search_page = self.page_size
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

        self.log('End MML refresh')

        return nb_lists, nb_products

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

    def map_ud_fields(self, ud_data):

        
        uf_config = {
            'nomen_manda_0': {
                'ud': 'type',
                'relation': 'product.nomenclature',
                'key_field': 'msfid',
                'domain': [('level', '=', 0)],
            },
            'nomen_manda_1': {
                'ud': 'group/code',
                'relation': 'product.nomenclature',
                'key_field': 'msfid',
                'domain': [('level', '=', 1)],
            },
            'nomen_manda_2': {
                'ud': 'family/code',
                'relation': 'product.nomenclature',
                'key_field': 'msfid',
                'domain': [('level', '=', 2)],
            },
            'nomen_manda_3': {
                'ud': 'root/code',
                'relation': 'product.nomenclature',
                'key_field': 'msfid',
                'domain': [('level', '=', 3)],
            },
            'name': {
                'lang': {
                    'en_MF': {'ud': 'labels/english'},
                    'fr_MF': {'ud': 'labels/french'},
                    'es_MF': {'ud': 'labels/spanish'},
                }
            },
            'closed_article': {
                'ud': 'closedInfo/closed',
                'mapping': {
                    'Open': 'no',
                    'Closed': 'yes',
                    'Restricted to': 'recommanded',
                    False: 'no',
                }
            },
            'justification_code_id': {
                'ud': 'supply/justification/code',
                'relation': 'product.justification.code',
                'key_field': 'code',
                'ignored_values': ['SPM', 'PMFE'], # tbc with Raff
            },
            'controlled_substance ': {
                'ud': 'medical/controlledSubstanceGroup/controlledSubstanceInfo/code',
                'mapping': {
                    '!': '!',
                    'N1': 'N1',
                    'N2': 'N2',
                    'P1': 'P1',
                    'P2': 'P2',
                    'P3': 'P3',
                    'P4': 'P4',
                    'DP': 'DP',
                    'Y': 'Y',
                    'True': 'True',
                    False: False
                }
            },
            'default_code': {
                'ud': 'code'
            },
            'fit_value': {
                'lang': {
                    'en_MF': {'ud': 'description/fitEnglishtext'},
                    'fr_MF': {'ud': 'description/fitFrenchtext'},
                }
            },
            'form_value': {
                'lang': {
                    'en_MF': {'ud': 'description/formEnglishtext'},
                    'fr_MF': {'ud': 'description/formFrenchtext'},
                }
            },
            'function_value': {
                'lang': {
                    'en_MF': {'ud': 'description/functionEnglishtext'},
                    'fr_MF': {'ud': 'description/functionFrenchtext'},
                }
            },
            'cold_chain': {
                'ud': 'thermosensitiveGroup/thermosensitiveInfo/code',
                'relation': 'product.cold_chain',
                'key_field': 'code',
            },
            'heat_sensitive_item': {
                'ud': 'thermosensitiveGroup/thermosensitive',
                'relation': 'product.heat_sensitive',
                'key_field': 'code',
                'mapping': {
                    False: 'no_know',
                    'No': 'no',
                    'Yes': 'yes',
                },
            },
            'manufacturer_ref': {
                'ud': 'closedInfo/manufacturerRef',
            },
            'manufacturer_txt': {
                'ud': 'closedInfo/manufacturer',
            },
            'msfid': {
                'ud': 'id',
            },
            'product_international_status': {
                'value': self.unidata_id,
            },
            #'name_template': tbc
            # nomen + account codes: tbc + default OC values
            # xmlid_code 
            'old_code': {
                'ud': 'formerCodes',
                'function': lambda a: ','.join(a),
            },
            'product_catalog_path ': {
                'ud': 'product_catalog_path',
            },
            'short_shelf_life': {
                'ud': 'medical/shortShelfLifeGroup/shortShelfLife',
                'mapping': {
                    'Yes': 'True',
                    'No': 'False',
                    "Don't know": 'no_know',
                },
            },
            'single_use': {
                'ud': 'medical/singleUse',
                'mapping': {
                    'Reusable': 'no',
                    'Single use': 'yes',
                    "Don't know": 'no_know',
                    'Not Applicable': 'no', # tbc with Raff
                    'Implantable Device': 'yes', # tbc with Raff
                    'Single patient multiple use': 'no', # tbc with Raff
                }
            },
            'standard_ok': {
                'ud': 'standardizationLevel',
                'mapping': {
                    'NST': 'non_standard',
                    'STD': 'standard',
                    'NSL': 'non_standard_local',
                }
            },
            'standard_price': {
                'value': 1.0,
                'on_update': False,
            },
            'state_ud': {
                'ud': 'lifeCycleStatus',
                'mapping': {
                    '01. Preparation': 'valid',
                    '02. Valid': 'valid',
                    '03. Outdated': 'outdated',
                    '04. Discontinued': 'discontinued',
                    '05. Forbidden': 'forbidden',
                    '06. Rejected': 'stopped',
                    '08. Archived': 'archived',
                    '01. Temporary Golden:': 'stopped',
                    '01. Temporary Merge': 'stopped',
                    '07. Parked': 'archived',
                },
            },
            'sterilized': {
                'ud': 'medical/sterile',
                'mapping': {
                    'Yes': 'yes',
                    'No': 'no',
                    "Don't know": 'no_know',
                    False: 'no',
                }
            },
            'un_code': {
                'ud': 'supply/dangerousGroup/dangerousInfo/number',
            }
        }
        specifc_lang = {}
        uf_values = {'en_MF': {}}
        for uf_key in uf_config:
            for lang in uf_config[uf_key].get('lang', ['default']):
                if lang == 'default':
                    lang_values = uf_values['en_MF']
                    field_desc = uf_config[uf_key]
                else:
                    lang_values = uf_values.get(lang, {})
                    field_desc = uf_config[uf_key]['lang'][lang]

                if field_desc.get('value'):
                    lang_values[uf_key] = field_desc['value']
                    continue

                uf_value = ud_data
                for key in field_desc['ud'].split('/'):
                    uf_value = uf_value.get(key, {})
                if not uf_value:
                    uf_value = False

                if field_desc.get('mapping'):
                    if uf_value not in field_desc['mapping']:
                        print('Mapping error, uf_key: %s, value:%s , full: %s' % (uf_key, uf_value, ud_data))
                        continue
                    else:
                        uf_value =  field_desc['mapping'][uf_value]

                if 'ignored_values' in field_desc and uf_value in field_desc.get('ignored_values'):
                    lang_values[uf_key] = False
                if uf_key in ['nomen_manda_1', 'nomen_manda_2', 'nomen_manda_3']:
                    previous_nom = {
                        'nomen_manda_1': 'nomen_manda_0',
                        'nomen_manda_2': 'nomen_manda_1',
                        'nomen_manda_3': 'nomen_manda_2',
                    }[uf_key]
                    self.uf_product_cache.setdefault(uf_key, {})

                    if uf_key == 'nomen_manda_1':
                        msfid = '%s-%s' % (ud_data['type'], ud_data['group']['code'])
                    elif uf_key == 'nomen_manda_2':
                        msfid = '%s-%s-%s%s' % (ud_data['type'], ud_data['group']['code'], ud_data['group']['code'], ud_data['family']['code'])
                    else:
                       msfid = '%s-%s-%s%s-%s' % (ud_data['type'], ud_data['group']['code'], ud_data['group']['code'], ud_data['family']['code'], ud_data['root']['code'])

                    if previous_nom not in lang_values:
                        continue
                    cache_key = (uf_key, lang_values[previous_nom], msfid)
                    
                    if cache_key not in self.uf_product_cache[uf_key]:
                        domain = field_desc['domain'] + [('parent_id', '=', uf_values['en_MF'][previous_nom]), ('msfid', '=', msfid)]
                        self.uf_product_cache[uf_key][cache_key] = self.pool.get('product.nomenclature').search(self.cr, self.uid, domain, context=self.context)

                    if not self.uf_product_cache[uf_key][cache_key] or len(self.uf_product_cache[uf_key][cache_key]) != 1:
                        print('%s error %s not found %s' % (uf_key, cache_key, ud_data))
                        continue
                    lang_values[uf_key] = self.uf_product_cache[uf_key][cache_key][0]

                elif field_desc.get('relation'):
                    self.uf_product_cache.setdefault(uf_key, {})
                    if not uf_value:
                        self.uf_product_cache[uf_key][uf_value] = [False]
                    if uf_value not in self.uf_product_cache[uf_key]:
                        domain = [(field_desc['key_field'], '=', uf_value)]
                        if field_desc.get('domain'):
                            domain += field_desc['domain']
                        self.uf_product_cache[uf_key][uf_value] = self.pool.get(field_desc['relation']).search(self.cr, self.uid, domain, context=self.context)
                    if not self.uf_product_cache[uf_key][uf_value] or len(self.uf_product_cache[uf_key][uf_value]) > 1:
                        print('Field error %s %s %s %s' % (uf_key, uf_value, self.uf_product_cache[uf_key][uf_value], ud_data))
                        continue
                    else:
                        lang_values[uf_key] = self.uf_product_cache[uf_key][uf_value][0]
                elif field_desc.get('function'):
                    lang_values[uf_key] = field_desc['function'](uf_value)
                else:
                    lang_values[uf_key] = uf_value
        print(uf_values)

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
                #prod_id = prod_obj.search(self.cr, self.uid, [('msfid', '=', x['id']), ('active', 'in', ['t', 'f'])], order='active desc, id', context=self.context)
                if x.get('state') == 'Golden':
                    continue
                if not x.get('formerCodes'):
                    print('NO FORMER %s' % x)
                    continue
                prod_ids = prod_obj.search(self.cr, self.uid, [('default_code', 'in', x['formerCodes']), ('active', 'in', ['t', 'f']), ('international_status', '=', self.unidata_id)], order='active desc, id', context=self.context)
                if len(prod_ids) == 1:
                    continue
                    print('Product found %s' % x['formerCodes'])
                elif len(prod_ids) == 0:
                    if x.get('ocSubscriptions').get('OCP'):
                        print('To created %s' % x)
                else:
                    prod_ids = prod_obj.search(self.cr, self.uid, [('default_code', 'in', x['formerCodes']), ('active','=', 't'), ('international_status', '=', self.unidata_id)])
                    if len(prod_ids) == 1:
                        continue
                        print('Product found by active')
                    else:
                        print('ISSSSSSSU %s %s' % (prod_ids, x))

                self.map_ud_fields(x)
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
                        # TODO create UF instance
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
    _lock = {}

    def __init__(self, pool, cr):
        self._lock[cr.dbname] = threading.RLock()
        super(unidata_sync, self).__init__(pool, cr)
        cr.execute('CREATE SEQUENCE IF NOT EXISTS  unidata_sync_msl_seq')

    def _get_log(self, cr, uid, ids, field_name, args, context=None):
        res = {}

        cr.execute("select start_date, end_date, state, sync_type from unidata_sync_log where server='ud' order by id desc limit 1")
        one = cr.fetchone()
        if one:
            last_execution_start_date = one[0]
            last_execution_end_date = one[1]
            last_execution_status = one[2]
            last_execution_sync_type = one[3]
        else:
            last_execution_start_date = last_execution_end_date = last_execution_status = last_execution_sync_type = False

        cr.execute("select start_date, end_date, state, sync_type from unidata_sync_log where server='msl' order by id desc limit 1")
        one = cr.fetchone()
        if one:
            last_msl_execution_start_date = one[0]
            last_msl_execution_end_date = one[1]
            last_msl_execution_status = one[2]
            last_msl_execution_sync_type = one[3]
        else:
            last_execution_start_date = last_execution_end_date = last_execution_status = last_execution_sync_type = False
            last_msl_execution_start_date = last_msl_execution_end_date = last_msl_execution_status = last_msl_execution_sync_type = False

        param_obj = self.pool.get('ir.config_parameter')
        eligible_for_full_sync = bool(param_obj.get_param(cr, 1, 'LAST_MSFID_SYNC')) or bool(param_obj.get_param(cr, 1, 'LAST_UD_DATE_SYNC')) or False
        eligible_msl_full_sync = self.pool.get('unidata.project').search_exists(cr, uid, [('msl_sync_date', '!=', False)], context=context)

        for _id in ids:
            res[_id] = {
                'last_execution_start_date': last_execution_start_date,
                'last_execution_end_date': last_execution_end_date,
                'last_execution_status': last_execution_status,
                'last_execution_sync_type': last_execution_sync_type,
                'eligible_for_full_sync': eligible_for_full_sync,

                'last_msl_execution_start_date': last_msl_execution_start_date,
                'last_msl_execution_end_date': last_msl_execution_end_date,
                'last_msl_execution_status': last_msl_execution_status,
                'last_msl_execution_sync_type': last_msl_execution_sync_type,
                'eligible_msl_full_sync': eligible_msl_full_sync,
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
        'url': fields.char('UniData URL', size=256, required=1),
        'url_msl': fields.char('MSL URL', size=256, required=1),
        'login': fields.char('Login', size=256),
        'password': fields.char('Password', size=256),

        'next_run_date': fields.datetime('Force next execution date'),
        'next_planned_date': fields.function(_get_next_planned_date,  method=True, type='datetime', string='Next Scheduled date'),
        'page_size': fields.integer('UD Page size'),
        'nb_keep_log': fields.integer('Number of log files to keep'),
        'ud_timeout': fields.integer('Network Timeout (seconds)'),
        'last_execution_start_date': fields.function(_get_log, method=True, multi='get_log', type='datetime', string="Last UD Execution Start Date"),
        'last_execution_end_date': fields.function(_get_log, method=True, multi='get_log', type='datetime', string="Last UD Execution End Date"),
        'last_execution_sync_type': fields.function(_get_log, method=True, multi='get_log', type='selection', selection=[('full', 'Full'), ('cont', 'Continuation'), ('diff', 'Based on last modification date')], string="Last UD Execution Sync Type"),
        'last_execution_status': fields.function(_get_log, method=True, multi='get_log', type='selection', selection=[('running', 'Running'), ('error', 'Error'), ('done', 'Done')], string="Last UD Execution State"),
        'eligible_for_full_sync': fields.function(_get_log, method=True, multi='get_log', type='boolean', string="Eligible for full UD sync"),
        'last_msl_execution_start_date': fields.function(_get_log, method=True, multi='get_log', type='datetime', string="Last MSL Execution Start Date"),
        'last_msl_execution_end_date': fields.function(_get_log, method=True, multi='get_log', type='datetime', string="Last MSL Execution End Date"),
        'last_msl_execution_status': fields.function(_get_log, method=True, multi='get_log', type='selection', selection=[('running', 'Running'), ('error', 'Error'), ('done', 'Done')], string="Last MSL Execution State"),
        'last_msl_execution_sync_type': fields.function(_get_log, method=True, multi='get_log', type='selection', selection=[('full', 'Full'), ('cont', 'Continuation'), ('diff', 'Based on last modification date')], string="Last MSL Execution Sync Type"),
        'eligible_msl_full_sync': fields.function(_get_log, method=True, multi='get_log', type='boolean', string="Eligible for full MSL sync"),
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
            raise osv.except_osv(_('Error'), e)
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

    def set_msl_as_full(self, cr, uid, ids, context=None):
        cr.execute('update unidata_project set msl_sync_date=NULL')
        return True

    def _start_bg(self, dbname, uid, method, context=None):
        cr = pooler.get_db(dbname).cursor()
        try:
            method(cr, uid, context=context)
        except Exception as e:
            self._error = tools.misc.get_traceback(e)
        finally:
            cr.commit()
            cr.close(True)
        return True

    def msl_start_manual(self, cr, uid, ids, context=None):
        if self.pool.get('res.company')._get_instance_level(cr, uid) != 'section':
            raise osv.except_osv(_('Error'), _('MSL sync can only be started at HQ level.'))
        self._error = ''
        new_thread = threading.Thread(
            target=self._start_bg,
            args=(cr.dbname, uid, self.start_msl_sync, context)
        )
        new_thread.start()
        new_thread.join(3.0)
        if not new_thread.is_alive() and self._error:
            raise Exception(self._error)
        return True

    def start_msl_sync(self, cr, nuid, context=None):

        if not self._lock[cr.dbname].acquire(blocking=False):
            raise osv.except_osv(_('Error'), _('A sync is already running ...'))

        session_obj = self.pool.get('unidata.sync.log')
        try:
            handler = False
            uid = self.pool.get('ir.model.data').get_object_reference(cr, nuid, 'base', 'user_unidata_pull')[1]
            logger = logging.getLogger('msl-sync')
            sync_obj = ud_sync(cr, uid, self.pool, logger=logger, context=context)
            page_size = sync_obj.page_size

            nuid = hasattr(nuid, 'realUid') and nuid.realUid or nuid
            sync_type = 'full'
            if self.pool.get('unidata.project').search_exists(cr, uid, [('msl_sync_date', '!=', False)], context=context):
                sync_type = 'diff'
            session_id = session_obj.create(cr, uid, {'start_date': fields.datetime.now(), 'state': 'running', 'page_size': page_size,  'start_uid': nuid, 'server': 'msl', 'sync_type': sync_type}, context=context)

            formatter = logging.Formatter('%(asctime)s : %(levelname)s : %(message)s')
            if tools.config['logfile']:
                log_file = path.join(path.dirname(tools.config['logfile']), 'msl-sync-%s-%s.log' % (session_id, datetime.now().strftime('%Y-%m-%d-%H%M')))
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
            logger.info('Sync start, page size: %s' % (page_size, ))

            nb_lists, nb_products = sync_obj.create_msl_list()
            session_obj.write(cr, uid, session_id, {'end_date': fields.datetime.now(), 'number_lists_pulled': nb_lists, 'number_products_updated': nb_products,'state': 'done'}, context=context)
        except Exception as e:
            cr.rollback()
            error = tools.misc.get_traceback(e)
            logger.error('End of Script with error: %s' % error)
            session_obj.write(cr, uid, session_id, {'end_date': fields.datetime.now(), 'state': 'error', 'error': error}, context=context)
        finally:
            if handler:
                handler.close()
                logger.removeHandler(handler)
            self._lock[cr.dbname].release()

    def ud_start_manual(self, cr, uid, ids, context=None):
        self._error = ''
        new_thread = threading.Thread(
            target=self._start_bg,
            args=(cr.dbname, uid, self.start_ud_sync, context)
        )
        new_thread.start()
        new_thread.join(3.0)
        if not new_thread.is_alive() and self._error:
            raise self._error
        return True

    def start_ud_sync(self, cr, uid, context=None):
        if self.pool.get('res.company')._get_instance_level(cr, uid) != 'section':
            raise osv.except_osv(_('Error'), _('UD sync can only be started at HQ level.'))

        if not self._lock[cr.dbname].acquire(blocking=False):
            raise osv.except_osv(_('Error'), _('A sync is already running ...'))
        try:
            self._start_ud_sync(cr, uid, context=context)
        finally:
            self._lock[cr.dbname].release()

    def start_msl_ud_sync(self, cr, uid, context=None):
        self.start_msl_sync(cr, uid, context=context)
        cr.commit()
        self.start_ud_sync(cr, uid, context=context)


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
        session_id = session_obj.create(cr, uid, {'start_date': fields.datetime.now(), 'state': 'running', 'page_size': page_size, 'msfid_min': min_msfid, 'last_date': last_ud_date_sync, 'sync_type': sync_type, 'start_uid': nuid, 'server': 'ud'}, context=context)

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
                    lastsync = (datetime.strptime(last_ud_date_sync.split('T')[0], '%Y-%m-%d') + relativedelta(hours=-24)).strftime('%Y-%m-%dT00:00:00')
                    createdOn = (datetime.strptime(last_ud_date_sync.split('T')[0], '%Y-%m-%d') + relativedelta(days=-3)).strftime('%Y-%m-%dT00:00:00')
                    q_filter = '(date-greater-or-equal(./metaData/mostRecentUpdate, "%(last_ud_date_sync)s") or date-greater-or-equal(./metaData/createdOn, "%(createdOn)s")) and %(filter)s' %{
                        'filter': q_filter,
                        'last_ud_date_sync': lastsync,
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

class unidata_default_product_value(osv.osv):
    _name = 'unidata.default_product_value'
    _columns = {
        'field': fields.selection([('perishable', 'Expiry Date Mandatory'), ('batch_management', 'Batch Number Mandatory'), ('procure_method','Procurement Method'), ('type', 'Product Type'), ('subtype', 'Product SubType')], 'Field Name', required=1, select=1),
        'value': fields.char('Value', size=256, required=1, select=1),
        'nomenclature': fields.many2one('product.nomenclature', required=1),
    }

    _sql_constraints = [
        ('unique_nomenclature_field', 'unique(field, nomenclature)', 'Field / nomenclature already exists')
    ]
unidata_default_product_value()

class unidata_pull_product_log(osv.osv):
    _name = 'unidata.pull_product.log'
    _columns = {
        'msfid': fields.integer('MSF ID', required=1),
        'code': fields.char('UD Code', size=64, select=1),
        'former_codes': fields.char('Former Code', size=1024, select=1),
        'date': fields.datetime('Date', required=1, select=1),
        'status': fields.selection([('create', 'Create'), ('Update', 'Update'), ('error', 'Error')], 'Status', select=1),
        'log': fields.text('Log'),
    }

unidata_pull_product_log()
