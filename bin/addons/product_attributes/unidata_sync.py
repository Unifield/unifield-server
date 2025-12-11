# encoding: utf-8
from osv import fields, osv
from osv.orm import browse_record, browse_null
from tools.translate import _
import tools
from datetime import datetime
from dateutil import tz
import time
import pprint
from tools.safe_eval import safe_eval

import logging
import logging.handlers
from os import path, remove
import sys
import threading
import pooler
from dateutil.relativedelta import relativedelta
from bs4 import BeautifulSoup

import requests

class UDException(Exception):
    pass

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

    def _get_msl_product_count(self, cr, uid, ids, fields, arg, context=None):
        '''
        Count the number of msl products
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        res = {}
        for obj in self.browse(cr, uid, ids, fields_to_fetch=['msl_product_ids'], context=context):
            res[obj.id] = len(obj.msl_product_ids)

        return res

    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Instance', readonly=1, domain=[('level', '!=', 'section')]),
        'instance_name': fields.related('instance_id', 'code', type='char', size=64, string='Instance', store=True, readonly=1),
        'uf_active': fields.boolean('Active'),
        'country_id': fields.many2one('unidata.country', 'Country', readonly=1),
        'msl_product_ids': fields.many2many('product.product', 'product_msl_rel', 'unifield_instance_id', 'product_id', 'Product Code', readonly=1, order_by='default_code', sql_rel_domain="product_msl_rel.creation_date is not null"),
        'unidata_project_ids': fields.one2many('unidata.project', 'unifield_instance_id', 'UniData Project', readonly=1),
        'is_published': fields.function(_get_is_published, type='boolean', method=True, string='Published', fnct_search=_search_is_published),
        'msl_product_count': fields.function(_get_msl_product_count, type='integer', method=True, string='Product Count'),
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
            unifield_instance_id = vals['unifield_instance_id']
            if not unifield_instance_id:
                # replace False in sync update by None, sql execute will change it to NULL
                unifield_instance_id = None
            cr.execute('update product_msl_rel set unifield_instance_id=%s where msl_id in %s', (unifield_instance_id, tuple(ids)))
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
    _description = 'UD Pull Report'
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
        'number_products_created': fields.integer('# products created', readonly=1),
        'number_products_errors': fields.integer('# products errors', readonly=1),

        'nomen_created': fields.integer('# nomen. created', readonly=1),
        'nomen_updated': fields.integer('# nomen. updated', readonly=1),
        'nomen_error': fields.integer('# nomen. errors', readonly=1),

        'sync_error': fields.one2many('unidata.pull_product.log', 'session_id', 'Sync Error', readonly=1),
        'error': fields.text('Error', readonly=1),
        'page_size': fields.integer('page size', readonly=1),
        'state': fields.selection([('running', 'Running'), ('error', 'Error'), ('done', 'Done')], 'State', readonly=1),
        'sync_type': fields.selection([('full', 'Full'), ('cont', 'Continuation'), ('diff', 'Based on last modification date'),('single', 'Single MSFID')], 'Sync Type', readonly=1),
        'msfid_min': fields.integer('Min Msfid', readonly=1),
        'last_date': fields.char('Last Date', size=64, readonly=1),
        'log_file': fields.char('Path to log file', size=128, readonly=1),
        'log_exists': fields.function(_get_log_exists, type='boolean', method=1, string='Log file exists'),
        'start_uid': fields.many2one('res.users', 'Started by', readonly=1),
        'server': fields.selection([('msl', 'MSL'), ('ud', 'unidata')], 'Server', readonly=1),
        'number_lists_pulled': fields.integer('# projects pulled', readonly=1),
    }

    _defaults = {
    }

unidata_sync_log()


class ud_sync():

    def __init__(self, cr, uid, pool, max_retries=4, logger=False, hidden_records=False, context=None):
        self.cr = cr
        self.uid = uid
        self.pool = pool
        self.max_retries = max_retries
        self.context = context
        self.logger = logger
        self.oc = self.pool.get('sync.client.entity').get_entity(self.cr, self.uid, context).oc
        if self.oc == 'waca':
            self.oc = 'ocp'
        if self.oc == 'ubuntu':
            self.oc = 'ocb'

        sync_id = self.pool.get('ir.model.data').get_object_reference(self.cr, self.uid, 'product_attributes', 'unidata_sync_config')[1]
        config = self.pool.get('unidata.sync').read(self.cr, self.uid, sync_id, context=self.context)
        self.unidata_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_6')[1]

        self.page_size = config['page_size'] or 500
        self.ud_params = {
            'login': config['login'],
            'password': config['password'],
            'size': self.page_size,
            'publishonweb': False,
            'mode': 2,
        }
        if hidden_records:
            self.ud_params.update({
                'mode': 3,
                'all': True,
            })
        self.url = config['url']
        self.url_msl = config['url_msl']
        self.timeout = config['ud_timeout']
        self.nb_keep_log = config['nb_keep_log']
        self.country_cache = {}
        self.project_cache = {}
        self.msf_intance_cache = {}
        self.uf_instance_cache = {}
        self.uf_product_cache = {}
        self.categ_account_cache = {}

        self.default_oc_values = {}
        default_ids = self.pool.get('unidata.default_product_value').search(self.cr, self.uid, [])
        for default in self.pool.get('unidata.default_product_value').browse(self.cr, self.uid, default_ids):
            if default.field in ('perishable', 'batch_management'):
                if default.value == 't':
                    default.value = True
                else:
                    default.value = False

            self.default_oc_values.setdefault(default.nomenclature.id, {}).update({default.field: default.value})

        if self.pool.get('res.company')._get_instance_level(self.cr, self.uid) != 'section':
            raise osv.except_osv(_('Error'), _('UD/MSL sync can only be started at HQ level.'))

        self.uf_config = {
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
                'nomen_level': 1,
            },
            'nomen_manda_2': {
                'ud': 'family/code',
                'relation': 'product.nomenclature',
                'key_field': 'msfid',
                'nomen_level': 2,
            },
            'nomen_manda_3': {
                'ud': 'root/code',
                'relation': 'product.nomenclature',
                'key_field': 'msfid',
                'nomen_level': 3,
            },
            'name': {
                'lang': {
                    'en_MF': {'ud': 'labels/english'},
                    'fr_MF': {'ud': 'labels/french'},
                    'es_MF': {'ud': 'labels/spanish'},
                },
                'function': lambda a: a.strip(),
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
            },
            'controlled_substance': {
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
            #'fit_value': { # see def map_ud_fields
            #},
            #'form_value': { # see def map_ud_fields
            #},
            #'function_value': { # see def map_ud_fields
            #},
            'cold_chain': {
                'ud': 'supply/thermosensitiveGroup/thermosensitiveInfo/code',
                'relation': 'product.cold_chain',
                'key_field': 'ud_code',
            },
            'heat_sensitive_item': {
                'ud': 'supply/thermosensitiveGroup/thermosensitive',
                'relation': 'product.heat_sensitive',
                'key_field': 'code',
                'mapping': {
                    "Don't know": 'no_know',
                    False: 'no',
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
            'international_status': {
                'value': self.unidata_id,
            },
            #'name_template': tbc
            'xmlid_code': {
                'ud': 'id',
                'on_update': False,
                'function': lambda a: a and '%s'%a or False,
            },
            'old_code': {
                'ud': 'formerCodes',
                'function': lambda a: ';'.join(a),
            },
            'product_catalog_path': {
                'ud': 'unicatURL',
            },
            'short_shelf_life': {
                'ud': 'medical/shortShelfLifeGroup/shortShelfLife',
                'mapping': {
                    'Yes': 'True',
                    'No': 'False',
                    "Don't know": 'no_know',
                    False: 'no_know',
                },
            },
            'single_use': {
                'ud': 'medical/singleUse',
                'mapping': {
                    'Single use': 'yes',
                    'Single patient multiple use': 'yes',
                    'Reusable': 'no',
                    'Implantable Device': 'no_know',
                    "Don't know": 'no_know',
                    'Not Applicable': 'no',
                    False: 'no',
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
                    '01. Temporary Golden': 'stopped',
                    '01. Temporary Merge': 'stopped',
                    '07. Parked': 'archived',
                },
            },
            'golden_status': {
                'ud': 'state',
            },
            'new_code': {
                'ud': 'mergeToCode',
                'ignore_missing': True,
            },
            'sterilized': {
                'ud': 'medical/sterile',
                'mapping': {
                    'Yes': 'yes',
                    'No': 'no',
                    "Don't know": 'no_know',
                    False: 'no_know',
                }
            },
            'dangerous_goods': {
                'ud': 'supply/dangerousGroup/dangerous',
                'mapping': {
                    "Don't know": 'no_know',
                    'Yes': 'True',
                    'No': 'False',
                    False: 'False',
                }
            },
            'un_code': {
                'ud': 'supply/dangerousGroup/dangerousInfo/number',
            },
            'hs_code': {
                'ud': 'supply/hsCode',
            },
            'oc_subscription': {
                'ud': 'ocSubscriptions/%s' % self.oc,
            },
            'oc_validation': {
                'ud': 'ocValidations/%s/valid' % self.oc,
            },
            'oc_validation_date': {
                'ud': 'ocValidations/%s/lastValidationDate' % self.oc,
                'type': 'date',
            },
            'oc_devalidation_date': {
                'ud': 'ocValidations/%s/lastDevalidationDate' % self.oc,
                'type': 'date',
            },
            'oc_devalidation_reason': {
                'ud': 'ocValidations/%s/devalidationReason' % self.oc,
            },
            'oc_comments': {
                'ud': 'ocValidations/%s/comments' % self.oc,
            }
        }

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

            self.cr.execute("update product_msl_rel set to_delete='t', unifield_instance_id=%s where msl_id=%s", (self.uf_instance_cache.get(msl.instance_id.code), msl.id))
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
        # new format 2020-01-19T23:00:00Z[UTC]
        try:
            date_fmt = datetime.strptime(date, '%Y-%m-%dT%H:%M:%S')
        except:
            try:
                date_fmt = datetime.strptime(date, '%Y-%m-%dT%H:%M')
            except:
                date_fmt = datetime.strptime(date[0:16], '%Y-%m-%dT%H:%M')

        return date_fmt.replace(tzinfo=tz.tzutc()).astimezone(tz.tzlocal()).strftime('%Y-%m-%d %H:%M:00')

    def query(self, q_filter, page=1, url=None):
        params = self.ud_params.copy()

        if url is not None and (url.endswith('families') or url.endswith('roots')):
            params['all'] = False

        params['page'] = page
        if q_filter:
            params['filter'] = q_filter

        request_ok = False
        retry = 0
        while not request_ok:
            try:
                self.log('OC: %s Page: %d, Filter: %s' % (self.oc, page, params.get('filter', '')))
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

    def remove_tag(self, text):
        if not text:
            return text
        return BeautifulSoup(text, 'html.parser').get_text(' ', strip=True)

    def map_ud_fields(self, ud_data, new_prod, session_id=False, create_missing_nomen=False):
        uf_values = {'en_MF': {}, 'fr_MF': {}}
        map_ff_fields = {
            'Form': 'form_value',
            'Function': 'function_value',
            'Fit': 'fit_value',
        }

        for k, v in map_ff_fields.items():
            uf_values['en_MF'][v] = False
            uf_values['fr_MF'][v] = False

        if ud_data.get('description', {}).get('status') == '53. Valid':
            for part in ud_data.get('description', {}).get('parts', []):
                if part.get('header', {}).get('english') in map_ff_fields:
                    uf_values['en_MF'][map_ff_fields[part['header']['english']]] = self.remove_tag(part.get('text', {}).get('english', False))
                    fr_text = self.remove_tag(part.get('text', {}).get('french', False))
                    if not fr_text:
                        fr_text = uf_values['en_MF'][map_ff_fields[part['header']['english']]]
                    uf_values['fr_MF'][map_ff_fields[part['header']['english']]] = fr_text

        for uf_key in self.uf_config:
            for lang in self.uf_config[uf_key].get('lang', ['default']):
                if lang == 'default':
                    lang_values = uf_values['en_MF']
                    field_desc = self.uf_config[uf_key]
                else:
                    lang_values = uf_values.get(lang, {})
                    field_desc = self.uf_config[uf_key]['lang'][lang]

                if field_desc.get('value'):
                    if new_prod or field_desc.get('on_update', True):
                        lang_values[uf_key] = field_desc['value']
                    continue

                uf_value = ud_data
                ignore_missing = False

                for key in field_desc['ud'].split('/'):
                    if self.uf_config[uf_key].get('ignore_missing') and key not in uf_value:
                        ignore_missing = True
                        break
                    uf_value = uf_value.get(key, {})

                if ignore_missing:
                    continue

                if not uf_value:
                    uf_value = False

                if field_desc.get('mapping'):
                    if uf_value not in field_desc['mapping']:
                        raise UDException('Mapping error, uf_key: %s, uf_value: %s' % (uf_key, uf_value))
                    else:
                        uf_value =  field_desc['mapping'][uf_value]

                if 'ignored_values' in field_desc and uf_value in field_desc.get('ignored_values'):
                    uf_value = False

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

                    #if previous_nom not in lang_values:
                    #    continue
                    cache_key = (uf_key, lang_values[previous_nom], msfid)

                    if cache_key not in self.uf_product_cache[uf_key]:
                        domain = [('level', '=', self.uf_config[uf_key]['nomen_level']), ('parent_id', '=', uf_values['en_MF'][previous_nom]), ('msfid', '=', msfid)]
                        nomen_ids = self.pool.get('product.nomenclature').search(self.cr, self.uid, domain, context=self.context)
                        if nomen_ids:
                            if len(nomen_ids) > 1:
                                raise UDException('%s error %d records not found %s' % (uf_key, len(nomen_ids), cache_key))
                            self.uf_product_cache[uf_key][cache_key] = nomen_ids[0]
                        elif create_missing_nomen and uf_key in ('nomen_manda_2', 'nomen_manda_3'):
                            nom_created, nom_updated, nom_error, nomen_id = self.update_single_nomenclature( uf_key=='nomen_manda_2' and 'families' or 'roots' , nomen_msf_id=msfid, session_id=session_id)
                            self.uf_product_cache[uf_key][cache_key] = nomen_id

                    nomen_id = self.uf_product_cache[uf_key].get(cache_key)
                    if not nomen_id:
                        raise UDException('%s error %s not found %s' % (uf_key, cache_key, nomen_id))

                    if uf_key == 'nomen_manda_2' and new_prod:
                        if msfid not in self.categ_account_cache:
                            self.categ_account_cache[msfid] = self.pool.get('product.nomenclature').browse(self.cr, self.uid, nomen_id).category_id.property_account_income_categ.code

                        prod_account_code = ud_data.get('accountCode', {}).get('code')

                        if prod_account_code != self.categ_account_cache[msfid]:
                            account_ids = self.pool.get('account.account').search(self.cr, self.uid, [('type', '!=', 'view'), ('code', '=', prod_account_code)])
                            if not account_ids:
                                raise UDException('Account code %s not found' % (ud_data.get('accountCode', {}).get('code')))
                            account_id = account_ids[0]
                            lang_values['property_account_income'] = account_id
                            lang_values['property_account_expense'] = account_id

                    lang_values[uf_key] = nomen_id

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
                        raise UDException('Field error %s: uf_value: %s, records found in UF: %d, %s' % (uf_key, uf_value, len(self.uf_product_cache[uf_key][uf_value]), self.uf_product_cache[uf_key][uf_value]))
                    else:
                        if new_prod or field_desc.get('on_update', True):
                            lang_values[uf_key] = self.uf_product_cache[uf_key][uf_value][0]
                elif field_desc.get('function'):
                    if new_prod or field_desc.get('on_update', True):
                        lang_values[uf_key] = field_desc['function'](uf_value)
                else:
                    if uf_value and field_desc.get('type') == 'date':
                        uf_value = self.ud_date(uf_value)

                    if new_prod or field_desc.get('on_update', True):
                        lang_values[uf_key] = uf_value
        if new_prod:
            for nomen in ['nomen_manda_0', 'nomen_manda_1', 'nomen_manda_2', 'nomen_manda_3']:
                if uf_values['en_MF'].get(nomen) and uf_values['en_MF'][nomen] in self.default_oc_values:
                    uf_values['en_MF'].update(self.default_oc_values[uf_values['en_MF'][nomen]])

        if uf_values['en_MF'].get('batch_management'):
            uf_values['en_MF']['perishable'] = True

        return uf_values

    def update_single_nomenclature(self, nom_type, nomen_msf_id="", session_id=False):
        nom_obj = self.pool.get('product.nomenclature')
        categ_obj = self.pool.get('product.category')
        pull_log = self.pool.get('unidata.pull_product.log')

        page = 1
        parent_cache = {}
        account_cache = {}
        created = 0
        updated = 0
        nb_errors = 0

        if nom_type == 'families':
            level = 2
        elif nom_type == 'roots':
            level = 3
        else:
            raise Exception('update_single_nomenclature nom_type %s incorrect' % nom_type)

        url = self.url.replace('articles', nom_type)
        if nomen_msf_id:
            split_parts = nomen_msf_id.split('-')
            url = '%s/%s' % (url, "".join(split_parts[2:]))

        current_id = False


        while True:
            js = self.query("", page=page, url=url)
            if not js.get('rows'):
                break
            for x in js.get('rows'):
                try:
                    self.log('UD %s %s' % (nom_type, x))
                    parent_msfid = ''
                    current_msfid = ''
                    self.cr.execute("SAVEPOINT nom_ud_update")

                    if level == 2:
                        if not x.get('main', {}).get('code') or not x.get('group',{}).get('code') or not x.get('id'):
                            raise UDException('Missing info in UD: main.code, group.code or id')
                        parent_msfid = '%s-%s' % (x.get('main', {}).get('code'), x.get('group',{}).get('code'))
                        current_msfid = '%s-%s' % (parent_msfid, x.get('id'))
                        name_prefix = x.get('id')
                    else:
                        if not x.get('main', {}).get('code') or not x.get('family', {}).get('id') or not x.get('code'):
                            raise UDException('Missing info in UD:  main.code, family.id or code')
                        parent_msfid = '%s-%s-%s' % (x.get('main', {}).get('code'), x.get('family', {}).get('id')[0], x.get('family', {}).get('id'))
                        current_msfid = '%s-%s' % (parent_msfid, x.get('code'))
                        name_prefix = x.get('code')

                    if nomen_msf_id and nomen_msf_id != current_msfid:
                        # case of single pull (from product)
                        continue

                    if not x.get('labels', {}).get('english'):
                        raise UDException('Missing UD english label')

                    if parent_msfid not in parent_cache:
                        parent_ids = nom_obj.search(self.cr, self.uid, [('msfid', '=', parent_msfid), ('level', '=', level -1)])
                        if not parent_ids:
                            parent_cache[parent_msfid] = False
                        else:
                            parent_cache[parent_msfid] = parent_ids[0]

                    if not parent_cache[parent_msfid]:
                        if 'Archived' in x.get('status', {}).get('label', ''):
                            continue
                        raise UDException('Parent nomenclature %s not found in UF' % (parent_msfid,))
                    current_ids = nom_obj.search(self.cr, self.uid, [('msfid', '=', current_msfid), ('level', '=', level)])
                    current_id = False
                    if current_ids:
                        current_id = current_ids[0]

                    nomen_data = {
                        'name': '%s - %s' % (name_prefix, x['labels']['english']),
                        'msfid': current_msfid,
                        'parent_id': parent_cache[parent_msfid],
                        'level': level,
                        'status': 'Archived' in x.get('status', {}).get('label', '') and 'archived' or 'valid',
                    }

                    sync_action = False
                    if not current_id:
                        if nomen_data['status'] == 'archived' or 'Valid' not in x.get('status', {}).get('label', ''):
                            self.log('Nomen %s creation ignored, status: %s' % (current_id, x.get('status', {}).get('label')))
                            continue
                        self.log('Nomen %s created' % (current_msfid, ))
                        current_id = nom_obj.create(self.cr, self.uid, nomen_data, context={'lang': 'en_MF'})
                        sync_action = 'created'
                    elif not nom_obj.search_exists(self.cr, self.uid, [('id', '=', current_id), ('name', '=ilike', nomen_data['name']), ('status', '=', nomen_data['status'])], context={'lang': 'en_MF'}):
                        self.log('Nomen %s updated uf id:%s' % (current_msfid, current_id))
                        nom_obj.write(self.cr, self.uid, current_id, nomen_data, context={'lang': 'en_MF'})
                        sync_action = 'updated'

                    french_label = False
                    if x['labels']['french']:
                        french_label = '%s - %s' % (name_prefix, x['labels']['french'])
                        if french_label and (not current_ids or not nom_obj.search_exists(self.cr, self.uid, [('id', '=', current_id), ('name', '=ilike', french_label)], context={'lang': 'fr_MF'})):
                            nom_obj.write(self.cr, self.uid, current_id, {'name': french_label}, context={'lang': 'fr_MF'})

                    if level == 2:
                        if x.get('accountCode') not in account_cache:
                            account_ids = self.pool.get('account.account').search(self.cr, self.uid, [('type', '!=', 'view'), ('code', '=', x.get('accountCode'))])
                            if account_ids:
                                account_cache[x['accountCode']] = account_ids[0]
                        account_id = account_cache.get(x.get('accountCode'))
                        if not account_id:
                            raise UDException('%s account code %s not found' % (current_msfid, x.get('accountCode')))
                        categ_ids = categ_obj.search(self.cr, self.uid, [('family_id', '=', current_id)])
                        categ_data = {
                            'name': x['labels']['english'],
                            'msfid': current_msfid,
                            'family_id': current_id,
                            'property_account_income_categ': account_id,
                            'property_account_expense_categ': account_id,
                        }
                        if not categ_ids:
                            self.log('Category %s created' % (current_msfid, ))
                            categ_id = categ_obj.create(self.cr, self.uid, categ_data, context={'lang': 'en_MF'})
                        else:
                            categ_id = categ_ids[0]
                            if not categ_obj.search_exists(self.cr, self.uid, [
                                ('id', '=', categ_ids[0]),
                                ('name', '=ilike', x['labels']['english']),
                                ('msfid', '=', current_msfid),
                                ('property_account_income_categ', '=', account_id),
                                ('property_account_expense_categ', '=', account_id)
                            ], context={'lang': 'en_MF'}):
                                self.log('Category %s updated uf id:%s' % (current_msfid, categ_id))
                                categ_obj.write(self.cr, self.uid, categ_id, categ_data, context={'lang': 'en_MF'})
                        if x['labels']['french'] and not categ_obj.search_exists(self.cr, self.uid, [('id', '=', categ_id), ('name', '=ilike', x['labels']['french'])], context={'lang': 'fr_MF'}):
                            categ_obj.write(self.cr, self.uid, categ_id, {'name': x['labels']['french']}, context={'lang': 'fr_MF'})

                    if sync_action == 'created':
                        created += 1
                    elif sync_action == 'updated':
                        updated += 1

                except Exception as e:
                    self.cr.execute("ROLLBACK TO SAVEPOINT nom_ud_update")
                    nb_errors += 1
                    if isinstance(e, UDException):
                        error = e.args[0]
                    else:
                        error = tools.misc.get_traceback(e)
                    self.log('ERROR %s'% error)
                    if session_id:
                        pull_log.create(self.cr, self.uid, {
                            'code': current_msfid,
                            'log': 'Nomenclature %s: %s' % (nom_type, error),
                            'json_data': x,
                            'session_id': session_id,
                        })
                    if current_msfid:
                        self.cr.execute('''insert into unidata_products_error (unique_key, type, code, date, first_date, log, json_data)
                            values (%(code)s, 'nomenclature', %(code)s, NOW(), NOW(), %(log)s, %(json_data)s)
                            on conflict (unique_key)  do update SET code = %(code)s, date=NOW(), log=%(log)s, json_data=%(json_data)s, fixed_date=NULL
                        ''', {
                            'code': current_msfid,
                            'log': '%s: %s' % (nom_type, error),
                            'json_data': '%s'%x,
                        })
                finally:
                    self.cr.execute("RELEASE SAVEPOINT nom_ud_update")

            page += 1
            if len(js.get('rows')) < self.page_size:
                break
        return created, updated, nb_errors, current_id


    def update_nomenclature(self, session_id=False):
        created = 0
        updated = 0
        nb_errors = 0
        self.cr.execute("update unidata_products_error set fixed_date=NOW() where type='nomenclature'")
        for nom_type in ['families', 'roots']:
            tmp_created, tmp_updated, tmp_nb_errors, last_id = self.update_single_nomenclature(nom_type, session_id=session_id)
            created += tmp_created
            updated += tmp_updated
            nb_errors += tmp_nb_errors
        return created, updated, nb_errors

    def update_products(self, q_filter, record_date, session_id=False, create_missing_nomen=False, is_full=False):
        country_obj = self.pool.get('unidata.country')
        project_obj = self.pool.get('unidata.project')
        prod_obj = self.pool.get('product.product')
        pull_log = self.pool.get('unidata.pull_product.log')


        page = 1
        date_to_record = False
        prod_updated = 0
        rows_seen = 0
        nb_errors = 0
        nb_created = 0
        while True:
            js = self.query(q_filter, page=page)

            if record_date:
                date_to_record = js.get('context', {}).get('executeDate')
            record_date = False

            if not js.get('rows'):
                break

            for x in js.get('rows'):
                self.log('is_full: %s, UD: %s' % (is_full, x))
                rows_seen += 1
                try:
                    self.cr.execute("SAVEPOINT nom_ud_update")
                    prod_ids = []
                    if not x.get('id'):
                        raise UDException('No msfid in API')


                    prod_ids = prod_obj.search(self.cr, self.uid, [('msfid', '=', x.get('id')), ('active', 'in', ['t', 'f']), ('international_status', '=', self.unidata_id)], context=self.context)
                    if len(prod_ids) > 1:
                        raise UDException('%s products found for msfid %s: %s' % (len(prod_ids), x.get('id'), prod_obj.read(self.cr, self.uid, prod_ids, ['default_code'])))

                    if len(prod_ids) == 0:
                        if not x.get('ocSubscriptions').get(self.oc):
                            self.log('%s product ignored: ocSubscriptions False' % x.get('formerCodes'))
                            continue
                        if x.get('state') != 'Golden':
                            self.log('%s product ignored, not exists in UF, golden: %s' % (x.get('formerCodes'), x.get('state')))
                            continue
                        if x.get('lifeCycleStatus') in ('01. Preparation', '06. Rejected', '01. Temporary Golden', '01. Temporary Merge', '07. Parked'):
                            self.log('%s product ignored, not exists in UF, lifeCycleStatus: %s' % (x.get('formerCodes'), x.get('lifeCycleStatus')))
                            continue
                        self.log('%s product to create' % (x.get('formerCodes'), ))
                    else:
                        if not x.get('ocSubscriptions').get(self.oc):
                            if not prod_obj.search(self.cr, self.uid, [('id', 'in', prod_ids), ('oc_subscription', '=', True), ('active', 'in', ['t', 'f'])], context=self.context):
                                if x.get('state') != 'Golden' or is_full:
                                    to_write = {'ud_seen': True, 'golden_status': x.get('state')}
                                    if x.get('mergeToCode'):
                                        to_write['new_code'] = x.get('mergeToCode')
                                        self.log('Write New code %s on product id: %s' % (to_write['new_code'], prod_ids[0]))
                                    prod_obj.write(self.cr, self.uid, [prod_ids[0]], to_write)
                                self.log('%s product ignored: ocSubscriptions False in UD and UF' % x['code'])
                                continue

                        self.log('%s product found %s' % (x.get('formerCodes'), prod_ids[0]))

                    if not x.get('formerCodes'):
                        raise UDException('No formerCodes code')
                    if not x.get('type') or not x.get('group', {}).get('code') or not x.get('family', {}).get('code') or not x.get('root', {}).get('code'):
                        raise UDException('Nomenclature not set in UD')

                    product_values = self.map_ud_fields(x, new_prod=not bool(prod_ids), session_id=session_id, create_missing_nomen=create_missing_nomen)

                    c_restriction = []
                    p_restriction = []
                    oc_data = x.get('ocValidations', {}).get(self.oc, {})
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

                    product_values['en_MF'].update({
                        'oc_country_restrictions': [(6, 0, list(set(c_restriction)))],
                        'oc_project_restrictions':  [(6, 0, list(set(p_restriction)))],
                    })


                    if prod_ids:
                        diff = []
                        for lang in ['en_MF', 'fr_MF', 'sp_MF']:
                            if not product_values.get(lang):
                                continue
                            current_value = prod_obj.browse(self.cr, self.uid, prod_ids[0], fields_to_fetch=product_values[lang].keys(), context={'lang': lang})
                            for key, value in product_values[lang].items():
                                tmp_diff = False
                                if value and current_value[key] and self.uf_config.get(key, {}).get('type') == 'date':
                                    tmp_diff = value[0:10] !=  current_value[key][0:10]
                                    if tmp_diff:
                                        self.log('Field diff (date) %s, uf: *%s*, ud: *%s*'% (key, current_value[key], value))
                                elif key in ('oc_country_restrictions', 'oc_project_restrictions'):
                                    if set(value[0][2]) != set([x.id for x in current_value[key]]):
                                        self.log('Field diff %s, uf: *%s*, ud: *%s*'% (key, [x.id for x in current_value[key]], value[0][2]))
                                        tmp_diff = True
                                elif isinstance(current_value[key], browse_record):
                                    if current_value[key]['id'] != value:
                                        self.log('Field diff m2o empty %s, uf: *%s*, ud: *%s*'% (key, current_value[key]['id'], value))
                                        tmp_diff = True
                                elif isinstance(current_value[key], browse_null):
                                    if value:
                                        self.log('Field diff m2o %s, uf: *%s*, ud: *%s*'% (key, current_value[key]['id'], value))
                                        tmp_diff = True
                                elif key == 'old_code':
                                    if current_value[key] and value:
                                        tmp_diff = set(current_value[key].split(';')) != set(value.split(';'))
                                    else:
                                        tmp_diff = current_value[key] != value
                                    if tmp_diff:
                                        self.log('Field diff old_code, uf: *%s*, ud: *%s*'% (current_value[key], value))
                                elif current_value[key] != value and (value is False and current_value[key] or value is not False):
                                    self.log('Field diff %s, uf: *%s*, ud: *%s*'% (key, current_value[key], value))
                                    tmp_diff = True
                                if tmp_diff:
                                    diff.append(key)
                            if diff:
                                # not not check fr/sp
                                break

                        if not diff:
                            if is_full:
                                self.cr.execute("update product_product set ud_seen='t' where id=%s", (prod_ids[0], ))
                            self.log('==== same values %s %s' % (product_values.get('en_MF', {}).get('default_code'), prod_ids[0]))
                            continue
                        else:
                            self.log('==== diff values %s %s, key: %s' % (product_values.get('en_MF', {}).get('default_code'), prod_ids[0], diff))

                    try:
                        self.cr.execute("SAVEPOINT prod_ud_update")
                        if is_full:
                            product_values['en_MF']['ud_seen'] = True
                        if prod_ids:
                            self.log('==== write product id: %d, code: %s, msfid: %s, data: %s' % (prod_ids[0], x['code'], x['id'], product_values['en_MF']))
                            prod_obj.write(self.cr, self.uid, prod_ids[0], product_values['en_MF'], context={'lang': 'en_MF'})
                            prod_updated += 1
                        else:
                            prod_ids = [prod_obj.create(self.cr, self.uid, product_values['en_MF'], context={'lang': 'en_MF'})]
                            self.log('==== create product id: %d, code: %s, msfid: %s, data: %s' % (prod_ids[0], x['code'], x['id'], product_values['en_MF']))
                            nb_created += 1

                        for lang in ['fr_MF', 'sp_MF']:
                            if product_values.get(lang):
                                self.log('==== write [%s] product id: %d, code: %s, msfid: %s, data: %s' % (lang, prod_ids[0], x['code'], x['id'], product_values[lang]))
                                prod_obj.write(self.cr, self.uid, prod_ids[0], product_values[lang], context={'lang': lang})
                    except Exception as e:
                        self.cr.execute("ROLLBACK TO SAVEPOINT prod_ud_update")
                        raise UDException(tools.misc.get_traceback(e))
                    else:
                        self.cr.execute("RELEASE SAVEPOINT prod_ud_update")

                except UDException as e:
                    self.cr.execute("ROLLBACK TO SAVEPOINT nom_ud_update")
                    self.log('ERROR %s'% e.args[0])
                    if session_id:
                        data_log = {
                            'msfid': x.get('id', ''),
                            'code': x.get('code', ''),
                            'former_codes': x.get('formerCodes', ''),
                            'log': e.args[0],
                            'json_data': x,
                            'session_id': session_id,
                        }
                        to_write = []
                        if x.get('id', ''):
                            to_write =  pull_log.search(self.cr, self.uid,[('msfid', '=', x.get('id', '')), ('session_id', '=', session_id)])

                        if to_write:
                            pull_log.write(self.cr, self.uid, to_write, data_log)
                        else:
                            pull_log.create(self.cr, self.uid, data_log)
                            nb_errors += 1
                    else:
                        nb_errors += 1
                    if x.get('id', ''):
                        self.cr.execute('''insert into unidata_products_error (unique_key, msfid, code, former_codes, date, first_date, log, uf_product_id, json_data, type)
                            values (%(msfid)s, %(msfid)s, %(code)s, %(former_codes)s, NOW(), NOW(), %(log)s, %(uf_product_id)s, %(json_data)s, 'product')
                            on conflict (unique_key) do update SET code = %(code)s, former_codes=%(former_codes)s, date=NOW(), log=%(log)s, uf_product_id=%(uf_product_id)s, json_data=%(json_data)s, fixed_date=NULL
                        ''', {
                            'msfid': x.get('id'),
                            'code': x.get('code', ''),
                            'former_codes': '%s' % x.get('formerCodes', ''),
                            'log': e.args[0],
                            'uf_product_id': ','.join([str(x) for x in prod_ids]),
                            'json_data': '%s'%x,
                        })
                else:
                    self.cr.execute("RELEASE SAVEPOINT nom_ud_update")

            page += 1
            if len(js.get('rows')) < self.page_size:
                break

        return date_to_record, rows_seen, prod_updated, nb_created, nb_errors




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

        cr.execute("select start_date, end_date, state, sync_type from unidata_sync_log where server='ud' and coalesce(sync_type, '')!='single' order by id desc limit 1")
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
                        pass

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
            raise Exception(self._error)
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
        total_nb_errors = 0
        total_nb_created = 0

        if full:
            param_obj.set_param(cr, 1, 'LAST_UD_DATE_SYNC', '')
            param_obj.set_param(cr, 1, 'LAST_MSFID_SYNC','')

        sync_type = 'full'
        last_ud_date_sync = param_obj.get_param(cr, 1, 'LAST_UD_DATE_SYNC') or False
        if last_ud_date_sync:
            sync_type = 'diff'


        oc = self.pool.get('sync.client.entity').get_entity(cr, uid, context).oc
        logger = logging.getLogger('unidata-sync-%s'% oc)
        sync_obj = ud_sync(cr, uid, self.pool, logger=logger, hidden_records=True, context=context)
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

        is_full = not last_ud_date_sync

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

        nomen_created, nomen_updated, nomen_error = sync_obj.update_nomenclature(session_id)
        session_obj.write(cr, uid, session_id, {
            'nomen_created': nomen_created,
            'nomen_updated': nomen_updated,
            'nomen_error': nomen_error
        }, context=context)
        cr.commit()

        if is_full:
            cr.execute('''
                update product_product p set ud_seen='f'
                    from product_international_status st
                    where
                        st.id = p.international_status and
                        st.code = 'unidata'
                ''')

        try:
            cr.execute('SAVEPOINT unidata_sync_log')
            last_loop = False
            max_id = 0
            # first tries previous errors
            cr.execute('select distinct(msfid) from unidata_products_error where fixed_date is null and coalesce(msfid, 0)!=0')
            query = []
            all_msfids = [x[0] for x in cr.fetchall()]
            if all_msfids:
                min_index = 0
                intervall = 15
                while nr_msfid := all_msfids[min_index:min_index+intervall]:
                    query = []
                    for x in nr_msfid:
                        query.append("msfIdentifier=%s" % x)
                    cr.execute('update unidata_products_error set fixed_date=NOW() where msfid in %s', (tuple(nr_msfid),))
                    trash1, tmp_nb_prod, tmp_updated, tmp_total_nb_created, tmp_total_nb_errors = sync_obj.update_products(" or ".join(query), False, session_id, is_full=is_full)
                    nb_prod += tmp_nb_prod
                    updated += tmp_updated
                    total_nb_created += tmp_total_nb_created
                    total_nb_errors += tmp_total_nb_errors
                    min_index += intervall

            first_merged = param_obj.get_param(cr, 1, 'UD_GETALL_MERGED')
            if first_merged == '1':
                if not full:
                    trash1, tmp_nb_prod, tmp_updated, tmp_total_nb_created, tmp_total_nb_errors = sync_obj.update_products('(./metaData/state!="Golden")', False, session_id, is_full=is_full)
                    nb_prod += tmp_nb_prod
                    updated += tmp_updated
                    total_nb_created += tmp_total_nb_created
                    total_nb_errors += tmp_total_nb_errors
                param_obj.set_param(cr, 1, 'UD_GETALL_MERGED', '0')
                cr.commit()


            max_ud_msfid = 100000
            existing_done = False
            last_tries = False # max msfid hard coded, last_tries to check if products existed after this value
            while not last_loop:
                cr.execute('SAVEPOINT unidata_sync_log')
                if not existing_done:
                    cr.execute("select min(msfid), max(msfid) from product_product p where id in (select id from product_product where coalesce(msfid,0)!=0 and msfid>%s order by msfid limit %s)", (min_msfid, page_size))
                    min_id, max_id = cr.fetchone()
                    original_min_msfid = min_msfid
                    min_msfid = max_id or 0

                if not min_id:
                    if not existing_done:
                        existing_done = True
                        min_msfid = original_min_msfid
                    if last_tries:
                        last_loop = True
                        cr.execute("select max(msfid) from product_product p")
                        min_msfid = cr.fetchone()[0] or 0
                        q_filter = "(msfIdentifier>=%s)" % max_ud_msfid
                    else:
                        q_filter = "(msfIdentifier>=%s and msfIdentifier<%s)"%(min_msfid, min_msfid + page_size)
                        min_msfid = min_msfid + page_size
                        if min_msfid >= max_ud_msfid:
                            last_tries = True
                else:
                    if first_query:
                        min_id = 0
                    q_filter = "(msfIdentifier>=%s and msfIdentifier<=%s)"%(min_id, max_id)

                if last_ud_date_sync:
                    lastsync = (datetime.strptime(last_ud_date_sync.split('T')[0], '%Y-%m-%d') + relativedelta(hours=-24)).strftime('%Y-%m-%dT00:00:00')
                    createdOn = (datetime.strptime(last_ud_date_sync.split('T')[0], '%Y-%m-%d') + relativedelta(days=-3)).strftime('%Y-%m-%dT00:00:00')
                    q_filter = '(date-greater-or-equal(./metaData/mostRecentUpdate, "%(last_ud_date_sync)s") or date-greater-or-equal(./metaData/createdOn, "%(createdOn)s")) and %(filter)s' %{
                        'filter': q_filter,
                        'last_ud_date_sync': lastsync,
                        'createdOn': createdOn,
                    }

                s_date_to_record, rows_seen, prod_updated, nb_created, nb_errors = sync_obj.update_products(q_filter, first_query, session_id, is_full=is_full)
                if first_query and s_date_to_record:
                    logger.info('Set last date: %s', s_date_to_record)
                    param_obj.set_param(cr, 1, 'LAST_UD_DATE_SYNC', s_date_to_record)
                first_query = False
                param_obj.set_param(cr, 1, 'LAST_MSFID_SYNC', min_msfid)

                updated += prod_updated
                nb_prod += rows_seen
                total_nb_errors += nb_errors
                total_nb_created += nb_created

                session_obj.write(cr, uid, session_id, {'number_products_pulled': nb_prod, 'number_products_updated': updated, 'number_products_created': total_nb_created, 'number_products_errors': total_nb_errors}, context=context)
                cr.commit()

                # end of sql loop

        except Exception as e:
            cr.execute('ROLLBACK TO SAVEPOINT unidata_sync_log')
            error = tools.misc.get_traceback(e)
            logger.error('End of Script with error: %s' % error)
            handler.close()
            logger.removeHandler(handler)
            session_obj.write(cr, uid, session_id, {
                'end_date': fields.datetime.now(),
                'state': 'error',
                'number_products_pulled': nb_prod,
                'error': error,
                'number_products_updated': updated,
                'number_products_created': total_nb_created,
                'number_products_errors': total_nb_errors,
            }, context=context)
            return False

        if is_full:
            prod_obj = self.pool.get('product.product')
            unidata_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_6')[1]

            not_seen_ud_ids = prod_obj.search(cr, uid, [('ud_seen', '=', False), ('international_status', '=', unidata_id), ('active', 'in', ['t', 'f'])])

            if not_seen_ud_ids:
                prod_obj.write(cr, uid, not_seen_ud_ids, {'golden_status': ''})

        logger.info('End of Script')
        handler.close()
        logger.removeHandler(handler)
        session_obj.write(cr, uid, session_id, {
            'end_date': fields.datetime.now(),
            'state': 'done',
            'number_products_pulled': nb_prod,
            'number_products_updated': updated,
            'number_products_created': total_nb_created,
            'number_products_errors': total_nb_errors
        }, context=context)
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
    _description = 'OC Default values'

    def _get_number_incompatible_products(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        ud_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_6')[1]
        prod_obj = self.pool.get('product.product')
        for oc_val in self.browse(cr, uid, ids, fields_to_fetch=['nomenclature', 'value', 'field'], context=context):
            value = oc_val.value
            if value == 'f':
                value = False
            res[oc_val.id] = prod_obj.search(cr, uid, [('international_status', '=', ud_id), ('nomen_manda_%d' % oc_val.nomenclature.level, '=', oc_val.nomenclature.id), (oc_val.field, '!=', value)], count=True, context=context)

        return res

    _columns = {
        'field': fields.selection([('perishable', 'Expiry Date Mandatory'), ('batch_management', 'Batch Number Mandatory'), ('procure_method','Procurement Method'), ('type', 'Product Type'), ('subtype', 'Product SubType')], 'Field Name', required=1, select=1),
        'value': fields.char('Value', size=256, required=1, select=1),
        'nomenclature': fields.many2one('product.nomenclature', required=1, string="Nomenclature"),
        'number_incompatible_products': fields.function(_get_number_incompatible_products, method=True, type='integer', string='Nb inconsistent prod'),
    }

    _sql_constraints = [
        ('unique_nomenclature_field', 'unique(field, nomenclature)', 'Field / nomenclature already exists')
    ]

    def _check_value(self, cr, uid, ids, context=None):
        if not ids:
            return True
        for oc in self.browse(cr, uid, ids, context=context):
            if oc.field in ['perishable', 'batch_management'] and oc.value not in ['t', 'f']:
                raise osv.except_osv(_('Error'), _('Expiry Date Mandatory and Batch Number Mandatory: only t or f are allowed'))
            if oc.field == 'procure_method' and oc.value not in ['make_to_stock', 'make_to_order']:
                raise osv.except_osv(_('Error'), _('Procurement Method: only make_to_stock or make_to_order are allowed'))
            if oc.field == 'type' and oc.value not in ['product', 'consu', 'service_recep']:
                raise osv.except_osv(_('Error'), _('Product Type only product, consu or service_recep are allowed'))
            if oc.field == 'subtype' and oc.value not in ['single', 'kit', 'asset', '']:
                raise osv.except_osv(_('Error'), _("Product SubType only single, kit, asset or '' are allowed"))

        return True


    _constraints = [
        (_check_value, 'Value not allowed', [])
    ]

    def open_products(self, cr, uid, ids, context=None):
        txt = []
        for d in self.browse(cr, uid, ids, context=context):
            txt.append('%s %s not %s' % (d.nomenclature.name, d.field, d.value))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'domain': [('incompatible_oc_default_values', 'in', ids)],
            'name': ' or '.join(txt)
        }

unidata_default_product_value()

class unidata_pull_product_log(osv.osv):
    _name = 'unidata.pull_product.log'
    _order = 'id desc'
    def _get_json_data_formated(self, cr, uid, ids, field_name, args, context=None):
        res = {}

        for j in self.browse(cr, uid, ids, fields_to_fetch=['json_data'], context=context):
            try:
                res[j.id] = pprint.pformat(safe_eval(j.json_data), width=160)
            except:
                res[j.id] = False
        return res

    _columns = {
        'msfid': fields.integer_null('MSF ID', select=1),
        'code': fields.char('UD Code', size=64, select=1),
        'former_codes': fields.char('Former Code', size=1024, select=1),
        'date': fields.datetime('Date', required=1, select=1),
        'log': fields.text('Log'),
        'json_data': fields.text('UD Json'),
        'json_data_formated': fields.function(_get_json_data_formated, method=1, type='text',string='UD Json'),
        'session_id': fields.many2one('unidata.sync.log', 'Session', select=1),
    }

    _defaults = {
        'date': lambda *a, **b: fields.datetime.now(),
    }
unidata_pull_product_log()

class unidata_products_error(osv.osv):
    _name = 'unidata.products_error'
    _order = 'date desc, msfid'
    def _get_json_data_formated(self, cr, uid, ids, field_name, args, context=None):
        res = {}

        for j in self.browse(cr, uid, ids, fields_to_fetch=['json_data'], context=context):
            try:
                res[j.id] = pprint.pformat(safe_eval(j.json_data), width=160)
            except:
                res[j.id] = False
        return res

    _columns = {
        'unique_key': fields.char('Record key', size=64, required=1, readonly=1),
        'msfid': fields.integer_null('MSF ID', select=1, readonly=1),
        'code': fields.char('UD Code', size=64, select=1, readonly=1),
        'former_codes': fields.char('Former Code', size=1024, readonly=1),
        'date': fields.datetime('Date of last error', required=1, select=1, readonly=1),
        'first_date': fields.datetime('Date of first error', select=1, readonly=1),
        'fixed_date': fields.datetime('Fixed at',  select=1, readonly=1),
        'log': fields.text('Log', readonly=1),
        'uf_product_id': fields.text('UF product db id', readonly=1),
        'json_data': fields.text('UD Json', readonly=1),
        'json_data_formated': fields.function(_get_json_data_formated, method=1, type='text',string='UD Json'),
        'type': fields.selection([('product', 'Product'), ('nomenclature', 'Nomenclature')], string="Object", required=1, select=1, readonly=1),
    }

    _sql_constraints = [
        ('unique_key', 'unique(unique_key)', 'key already exists.'),
    ]
    _defaults = {
        'date': lambda *a, **b: fields.datetime.now(),
        'type': 'product',
    }
unidata_products_error()
