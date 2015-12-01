# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import osv
from osv import fields
import base64
from os.path import join as opj
from tools.translate import _
import tools
import os
import logging
from threading import Lock

class patch_scripts(osv.osv):
    _name = 'patch.scripts'

    _columns = {
        'model': fields.text(string='Model', required=True),
        'method': fields.text(string='Method', required=True),
        'run': fields.boolean(string='Is ran ?'),
    }

    _defaults = {
        'model': lambda *a: 'patch.scripts',
    }

    def launch_patch_scripts(self, cr, uid, *a, **b):
        ps_obj = self.pool.get('patch.scripts')
        ps_ids = ps_obj.search(cr, uid, [('run', '=', False)])
        for ps in ps_obj.read(cr, uid, ps_ids, ['model', 'method']):
            method = ps['method']
            model_obj = self.pool.get(ps['model'])
            getattr(model_obj, method)(cr, uid, *a, **b)
            self.write(cr, uid, [ps['id']], {'run': True})

    def us_332_patch(self, cr, uid, *a, **b):
        context = {}
        user_obj = self.pool.get('res.users')
        usr = user_obj.browse(cr, uid, [uid], context=context)[0]
        level_current = False

        if usr and usr.company_id and usr.company_id.instance_id:
            level_current = usr.company_id.instance_id.level

        if level_current == 'section':
            # create MSFID for product.nomenclature
            nomen_obj = self.pool.get('product.nomenclature')
            nomen_ids = nomen_obj.search(cr, uid, [('msfid', '=', False)], order='level asc, id')

            for nomen_id in nomen_ids:
                nomen = nomen_obj.browse(cr, uid, nomen_id, context={})
                msfid = ""
                if not nomen.msfid:
                    nomen_parent = nomen.parent_id
                    if nomen_parent and nomen_parent.msfid:
                        msfid = nomen_parent.msfid + "-"
                    name_first_word = nomen.name.split(' ')[0]
                    msfid += name_first_word
                    # Search same msfid
                    ids = nomen_obj.search(cr, uid, [('msfid', '=', msfid)])
                    if ids:
                        msfid += str(nomen.id)
                    nomen_obj.write(cr, uid, nomen.id, {'msfid': msfid})

            # create MSFID for product.category
            categ_obj = self.pool.get('product.category')
            categ_ids = categ_obj.search(cr, uid, [('msfid', '=', False), ('family_id', '!=', False)], order='id')

            for categ in categ_obj.browse(cr, uid, categ_ids, context={}):
                msfid = ""
                if not categ.msfid and categ.family_id and categ.family_id.name:
                    msfid = categ.family_id.name[0:4]
                    ids = categ_obj.search(cr, uid, [('msfid', '=', msfid)])
                    if ids:
                        msfid += str(categ.id)
                    categ_obj.write(cr, uid, categ.id, {'msfid': msfid})

    def update_parent_budget_us_489(self, cr, uid, *a, **b):
        logger = logging.getLogger('update')
        c = self.pool.get('res.users').browse(cr, uid, uid).company_id
        instance_name = c and c.instance_id and c.instance_id.name
        if instance_name == 'BD_DHK_OCA':
            budget_obj = self.pool.get('msf.budget')
            parent_id = budget_obj.search(cr, uid, [('type', '=', 'view'), ('id', '=', 2)])
            child_id = budget_obj.search(cr, uid, [('type', '=', 'normal'), ('id', '=', 4)])
            if not parent_id or not child_id:
                logger.warn('US-489: budget not found, parent: %s, child: %s' % (parent_id, child_id))
                return False
            budget_obj.write(cr, uid, parent_id, {'state': 'draft'})
            budget_obj.unlink(cr, uid, parent_id)
            fields = ['cost_center_id', 'fiscalyear_id', 'decision_moment_id']
            data = budget_obj.read(cr, uid, child_id[0], fields)
            vals = {}
            for f in fields:
                vals[f] = data[f] and data[f][0]
            budget_obj._check_parent(cr, uid, vals)
            budget_obj.update_parent_budgets(cr, uid, child_id)
            logger.warn('US-489: parent budget %s updated' % (parent_id,))

    def us_394_2_patch(self, cr, uid, *a, **b):
        obj = self.pool.get('ir.translation')
        obj.clean_translation(cr, uid, context={})
        obj.add_xml_ids(cr, uid, context={})

    def us_394_3_patch(self, cr, uid, *a, **b):
        self.us_394_2_patch(cr, uid, *a, **b)

    def update_us_435_2(self, cr, uid, *a, **b):
        period_obj = self.pool.get('account.period')
        period_state_obj = self.pool.get('account.period.state')
        periods = period_obj.search(cr, uid, [])
        for period in periods:
            period_state_obj.update_state(cr, uid, period)

        return True

    def update_us_133(self, cr, uid, *a, **b):
        p_obj = self.pool.get('res.partner')
        po_obj = self.pool.get('purchase.order')
        pl_obj = self.pool.get('product.pricelist')

        # Take good pricelist on existing partners
        p_ids = p_obj.search(cr, uid, [])
        fields = [
            'property_product_pricelist_purchase',
            'property_product_pricelist',
        ]
        for p in p_obj.read(cr, uid, p_ids, fields):
            p_obj.write(cr, uid, [p['id']], {
                'property_product_pricelist_purchase': p['property_product_pricelist_purchase'][0],
                'property_product_pricelist': p['property_product_pricelist'][0],
            })

        # Take good pricelist on existing POs
        pl_dict = {}
        po_ids = po_obj.search(cr, uid, [
            ('pricelist_id.type', '=', 'sale'),
        ])
        for po in po_obj.read(cr, uid, po_ids, ['pricelist_id']):
            vals = {}
            if po['pricelist_id'][0] in pl_dict:
                vals['pricelist_id'] = pl_dict[po['pricelist_id'][0]]
            else:
                pl_currency = pl_obj.read(cr, uid, po['pricelist_id'][0], ['currency_id'])
                p_pl_ids = pl_obj.search(cr, uid, [
                    ('currency_id', '=', pl_currency['currency_id'][0]),
                    ('type', '=', 'purchase'),
                ])
                if p_pl_ids:
                    pl_dict[po['pricelist_id'][0]] = p_pl_ids[0]
                    vals['pricelist_id'] = p_pl_ids[0]

            if vals:
                po_obj.write(cr, uid, [po['id']], vals)

    def disable_crondoall(self, cr, uid, *a, **b):
        cron_obj = self.pool.get('ir.cron')
        cron_ids = cron_obj.search(cr, uid, [('doall', '=', True), ('active', 'in', ['t', 'f'])])
        if cron_ids:
            cron_obj.write(cr, uid, cron_ids, {'doall': False})

patch_scripts()


class ir_model_data(osv.osv):
    _inherit = 'ir.model.data'
    _name = 'ir.model.data'

    def _update(self,cr, uid, model, module, values, xml_id=False, store=True, noupdate=False, mode='init', res_id=False, context=None):
        """
            Store in context that we came from _update
        """
        if not context:
            context = {}
        ctx = context.copy()
        ctx['update_mode'] = mode
        return super(ir_model_data, self)._update(cr, uid, model, module, values, xml_id, store, noupdate, mode, res_id, ctx)

    def patch13_install_export_import_lang(self, cr, uid, *a, **b):
        mod_obj = self.pool.get('ir.module.module')
        mod_ids = mod_obj.search(cr, uid, [('name', '=', 'export_import_lang')])
        if mod_ids and mod_obj.read(cr, uid, mod_ids, ['state'])[0]['state'] == 'uninstalled':
            mod_obj.write(cr, uid, mod_ids[0], {'state': 'to install'})

    def us_254_fix_reconcile(self, cr, uid, *a, **b):
        c = self.pool.get('res.users').browse(cr, uid, uid).company_id
        sql_file = opj('msf_profile', 'data', 'us_254.sql')
        instance_name = c and c.instance_id and c.instance_id.name
        if instance_name in ['OCBHT101', 'OCBHT143', 'OCBHQ']:
            logger = logging.getLogger('update')
            try:
                fp = tools.file_open(sql_file, 'r')
                logger.warn('Execute us-254 sql')
                cr.execute(fp.read())
                fp.close()
                logger.warn('Sql done')
                os.rename(fp.name, "%sold" % fp.name)
                logger.warn('Sql file renamed')
            except IOError, e:
                # file does not exist
                pass

    def _us_268_gen_message(self, cr, uid, obj, id, fields, values):
        msg_obj = self.pool.get("sync.client.message_to_send")
        xmlid = obj.get_sd_ref(cr, uid, id)
        data = {
            'identifier': 'us_268_fix_%s_%s' % (obj._name, id),
            'sent': False,
            'generate_message': True,
            'remote_call': "ir.model.data._query_from_sync",
            'arguments':"['%s', '%s', %r, %r]" % (obj._name, xmlid, fields, values),
            'destination_name': 'OCBHQ',
        }
        msg_obj.create(cr, uid, data)

    def us_268_fix_seq(self, cr, uid, *a, **b):
        msg_obj = self.pool.get("sync.client.message_to_send")
        if not msg_obj:
            return True
        c = self.pool.get('res.users').browse(cr, uid, uid).company_id
        instance_name = c and c.instance_id and c.instance_id.name
        touch_file = opj('msf_profile', 'data', 'us_268.sql')
        # TODO: set as done
        if instance_name == 'OCBHT143':
            logger = logging.getLogger('update')
            try:
                fp = tools.file_open(touch_file, 'r')
                logger.warn('Execute us-268 sql')
                cr.execute(fp.read())
                fp.close()
                logger.warn('Sql done')
                os.rename(fp.name, "%sold" % fp.name)
                logger.warn('Sql file renamed')
            except IOError, e:
                # file does not exist
                pass

        elif instance_name == 'OCBHT101' and msg_obj:
            logger = logging.getLogger('update')
            try:
                fp = tools.file_open(touch_file, 'r')
                fp.close()
            except IOError, e:
                return True
            logger.warn('Execute US-268 queries')
            journal_obj = self.pool.get('account.journal')
            instance_id = c.instance_id.id
            account_move_obj = self.pool.get('account.move')
            analytic_obj = self.pool.get('account.analytic.line')
            invoice_obj = self.pool.get('account.invoice')

            journal_id = journal_obj.search(cr, uid, [('type', '=', 'purchase'), ('is_current_instance', '=', True)])[0]
            journal = journal_obj.browse(cr, uid, journal_id)

            analytic_journal_id = journal.analytic_journal_id.id

            move_ids_to_fix = [453, 1122, 1303]

            instance_xml_id = self.pool.get('msf.instance').get_sd_ref(cr, uid, instance_id)
            journal_xml_id = journal_obj.get_sd_ref(cr, uid, journal_id)
            analytic_journal_xml_id = self.pool.get('account.analytic.journal').get_sd_ref(cr, uid, analytic_journal_id)

            move_prefix = c.instance_id.move_prefix

            for move in account_move_obj.browse(cr, uid, move_ids_to_fix):
                if move.instance_id.id == instance_id:
                    # fix already applied
                    continue

                seq_name = self.pool.get('ir.sequence').get_id(cr, uid, journal.sequence_id.id, context={'fiscalyear_id': move.period_id.fiscalyear_id.id})
                reference = '%s-%s-%s' % (move_prefix, journal.code, seq_name)

                cr.execute('update account_move set instance_id=%s, journal_id=%s, name=%s where id=%s', (instance_id, journal_id, reference, move.id))
                invoice_ids = invoice_obj.search(cr, uid, [('move_id', '=', move.id)])
                if invoice_ids:
                    cr.execute('update account_invoice set journal_id=%s, number=%s where id=%s', (journal_id, reference, invoice_ids[0]))

                self._us_268_gen_message(cr, uid, account_move_obj, move.id,
                    ['instance_id', 'journal_id', 'name'], [instance_xml_id, journal_xml_id, reference]
                )
                for line in move.line_id:
                    cr.execute('update account_move_line set instance_id=%s, journal_id=%s where id=%s', (instance_id, journal_id, line.id))
                    self._us_268_gen_message(cr, uid, self.pool.get('account.move.line'), line.id,
                        ['instance_id', 'journal_id'], [instance_xml_id, journal_xml_id]
                    )

                    analytic_ids = analytic_obj.search(cr, uid, [('move_id', '=', line.id)])

                    for analytic_id in analytic_ids:
                        cr.execute('update account_analytic_line set instance_id=%s, entry_sequence=%s, journal_id=%s where id=%s', (instance_id, reference, analytic_journal_id, analytic_id))
                        self._us_268_gen_message(cr, uid, analytic_obj, analytic_id,
                            ['instance_id', 'entry_sequence', 'journal_id'], [instance_xml_id, reference, analytic_journal_xml_id]
                        )
            os.rename(fp.name, "%sold" % fp.name)
            logger.warn('Set US-268 as executed')


ir_model_data()

class account_installer(osv.osv_memory):
    _inherit = 'account.installer'
    _name = 'account.installer'

    _defaults = {
        'charts': 'msf_chart_of_account',
    }

    # Fix for UF-768: correcting fiscal year and name
    def execute(self, cr, uid, ids, context=None):
        super(account_installer, self).execute(cr, uid, ids, context=context)
        # Retrieve created fiscal year
        fy_obj = self.pool.get('account.fiscalyear')
        for res in self.read(cr, uid, ids, context=context):
            if 'date_start' in res and 'date_stop' in res:
                f_ids = fy_obj.search(cr, uid, [('date_start', '<=', res['date_start']), ('date_stop', '>=', res['date_stop']), ('company_id', '=', res['company_id'])], context=context)
                if len(f_ids) > 0:
                    # we have one
                    new_name = "FY " + res['date_start'][:4]
                    new_code = "FY" + res['date_start'][:4]
                    if int(res['date_start'][:4]) != int(res['date_stop'][:4]):
                        new_name = "FY " + res['date_start'][:4] +'-'+ res['date_stop'][:4]
                        new_code = "FY" + res['date_start'][2:4] +'-'+ res['date_stop'][2:4]
                    vals = {
                        'name': new_name,
                        'code': new_code,
                    }
                    fy_obj.write(cr, uid, f_ids, vals, context=context)
        return

account_installer()

class res_config_view(osv.osv_memory):
    _inherit = 'res.config.view'
    _name = 'res.config.view'
    _defaults={
        'view': 'extended',
    }
res_config_view()

class base_setup_company(osv.osv_memory):
    _inherit = 'base.setup.company'
    _name = 'base.setup.company'

    def default_get(self, cr, uid, fields_list=None, context=None):
        ret = super(base_setup_company, self).default_get(cr, uid, fields_list, context)
        if not ret.get('name'):
            ret.update({'name': 'MSF', 'street': 'Rue de Lausanne 78', 'street2': 'CP 116', 'city': 'Geneva', 'zip': '1211', 'phone': '+41 (22) 849.84.00'})
            company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
            ret['name'] = company.name
            addresses = self.pool.get('res.partner').address_get(cr, uid, company.id, ['default'])
            default_id = addresses.get('default', False)
            # Default address
            if default_id:
                address = self.pool.get('res.partner.address').browse(cr, uid, default_id, context=context)
                for field in ['street','street2','zip','city','email','phone']:
                    ret[field] = address[field]
                for field in ['country_id','state_id']:
                    if address[field]:
                        ret[field] = address[field].id
            # Currency
            cur = self.pool.get('res.currency').search(cr, uid, [('name','=','EUR')])
            if company.currency_id:
                ret['currency'] = company.currency_id.id
            elif cur:
                ret['currency'] = cur[0]

            fp = tools.file_open(opj('msf_profile', 'data', 'msf.jpg'), 'rb')
            ret['logo'] = base64.encodestring(fp.read())
            fp.close()
        return ret

base_setup_company()

class res_users(osv.osv):
    _inherit = 'res.users'
    _name = 'res.users'

    def _get_default_ctx_lang(self, cr, uid, context=None):
        config_lang = self.pool.get('unifield.setup.configuration').get_config(cr, uid).lang_id
        if config_lang:
            return config_lang
        if self.pool.get('res.lang').search(cr, uid, [('translatable','=',True), ('code', '=', 'en_MF')]):
            return 'en_MF'
        return 'en_US'

    _defaults = {
        'context_lang': _get_default_ctx_lang,
    }
res_users()

class email_configuration(osv.osv):
    _name = 'email.configuration'
    _description = 'Email configuration'

    _columns = {
        'smtp_server': fields.char('SMTP Server', size=512, required=True),
        'email_from': fields.char('Email From', size=512, required=True),
        'smtp_port': fields.integer('SMTP Port', required=True),
        'smtp_ssl': fields.boolean('Use SSL'),
        'smtp_user': fields.char('SMTP User', size=512),
        'smtp_password': fields.char('SMTP Password', size=512),
        'destination_test': fields.char('Email Destination Test', size=512),
    }
    _defaults = {
        'smtp_port': 25,
        'smtp_ssl': False,
    }

    def set_config(self, cr):
        data = ['smtp_server', 'email_from', 'smtp_port', 'smtp_ssl', 'smtp_user', 'smtp_password']
        cr.execute("""select """+','.join(data)+"""
            from email_configuration
            limit 1
        """)
        res = cr.fetchone()
        if res:
            for i, key in enumerate(data):
                tools.config[key] = res[i] or False
        return True

    def __init__(self, pool, cr):
        super(email_configuration, self).__init__(pool, cr)
        cr.execute("SELECT relname FROM pg_class WHERE relkind IN ('r','v') AND relname=%s", (self._table,))
        if cr.rowcount:
            self.set_config(cr)

    def _update_email_config(self, cr, uid, ids, context=None):
        self.set_config(cr)
        return True

    def test_email(self, cr, uid, ids, context=None):
        cr.execute('select destination_test from email_configuration limit 1')
        res = cr.fetchone()
        if not res or not res[0]:
            raise osv.except_osv(_('Warning !'), _('No destination email given!'))
        if not tools.email_send(False, [res[0]], 'Test email from UniField', 'This is a test.'):
            raise osv.except_osv(_('Warning !'), _('Could not deliver email'))
        return True

    _constraints = [
        (_update_email_config, 'Always true: update email configuration', [])
    ]
email_configuration()

class ir_cron_linux(osv.osv_memory):
    _name = 'ir.cron.linux'
    _description = 'Start memory cleaning cron job from linux crontab'
    _columns = {
    }

    def __init__(self, *a, **b):
        self._logger = logging.getLogger('ir.cron.linux')
        self._jobs = {
            'memory_clean': ('osv_memory.autovacuum', 'power_on', ()),
            'save_puller': ('sync.server.update', '_save_puller', ())
        }
        self.running = {}
        for job in self._jobs:
            self.running[job] = Lock()

        super(ir_cron_linux, self).__init__(*a, **b)

    def execute_job(self, cr, uid, job, context=None):
        if job not in self._jobs:
            raise osv.except_osv(_('Warning !'), _('Job does not exists'))
        if uid != 1:
            raise osv.except_osv(_('Warning !'), _('Permission denied'))
        if not self.running[job].acquire(False):
            self._logger.info("Linux cron: job %s already running" % (job, ))
            return False
        try:
            self._logger.info("Linux cron: starting job %s" % (job, ))
            obj = self.pool.get(self._jobs[job][0])
            fct = getattr(obj, self._jobs[job][1])
            args = self._jobs[job][2]
            fct(cr, uid, *args)
            self._logger.info("Linux cron: job %s done" % (job, ))
        except Exception, e:
            self._logger.warning('Linux cron: job %s failed' % (job, ), exc_info=1)
        finally:
            self.running[job].release()
        return True

ir_cron_linux()
