import re
import sys
import pprint
import hashlib
import json
import traceback

import tools
from tools.translate import _

# model related to synchronization, this model don't have to be ignored.
# list build by getting models of update rules and message rules
WHITE_LIST_MODEL = [
    'account.account',
    'account.account.type',
    'account.analytic.account',
    'account.analytic.journal',
    'account.analytic.line',
    'account.bank.statement',
    'account.bank.statement.line',
    'account.bank.statement.line.deleted',
    'account.cashbox.line',
    'account.destination.link',
    'account.fiscal.position',
    'account.fiscalyear',
    'account.fiscalyear.state',
    'account.invoice',
    'account.journal',
    'account.move',
    'account.move.line',
    'account.move.reconcile',
    'account.payment.term',
    'account.period',
    'account.period.state',
    'account.target.costcenter',
    'account.tax',
    'account.tax.code',
    'analytic.distribution',
    'claim.event',
    'claim.product.line',
    'composition.item',
    'composition.kit',
    'cost.center.distribution.line',
    'country.export.mapping',
    'distribution.line',
    'financing.contract.contract',
    'financing.contract.donor',
    'financing.contract.format',
    'financing.contract.format.line',
    'financing.contract.funding.pool.line',
    'free.1.distribution.line',
    'free.2.distribution.line',
    'funding.pool.distribution.line',
    'hq.entries',
    'hr.employee',
    'hr.employee.marital.status',
    'hr.job',
    'initial.stock.inventory',
    'initial.stock.inventory.line',
    'ir.actions.act_window',
    'ir.filters',
    'ir.model',
    'ir.model.access',
    'ir.model.fields',
    'ir.rule',
    'ir.sequence',
    'ir.translation',
    'ir.ui.menu',
    'ir.ui.view',
    'kit.creation',
    'kit.creation.to.consume',
    'monthly.review.consumption',
    'monthly.review.consumption.line',
    'msf.budget',
    'msf.budget.decision.moment',
    'msf.budget.line',
    'msf.instance',
    'msf_button_access_rights.button_access_rule',
    'msf_field_access_rights.field_access_rule',
    'msf_field_access_rights.field_access_rule_line',
    'pack.type',
    'procurement.order',
    'product.asset',
    'product.asset.type',
    'product.category',
    'product.cold_chain',
    'product.heat_sensitive',
    'product.international.status',
    'product.justification.code',
    'product.list',
    'product.list.line',
    'product.nomenclature',
    'product.pricelist',
    'product.pricelist.type',
    'product.pricelist.version',
    'product.product',
    'product.uom',
    'product.uom.categ',
    'purchase.order',
    'purchase.order.line',
    'real.average.consumption',
    'real.average.consumption.line',
    'res.company',
    'res.country',
    'res.country.restriction',
    'res.country.state',
    'res.currency',
    'res.currency.rate',
    'res.currency.table',
    'res.groups',
    'res.partner',
    'res.partner.address',
    'res.partner.title',
    'res.users',
    'return.claim',
    'sale.order',
    'sale.order.line',
    'sale.order.line.cancel',
    'shipment',
    'stock.frequence',
    'stock.inventory',
    'stock.inventory.line',
    'stock.journal',
    'stock.location',
    'stock.location.chained.options',
    'stock.mission.report',
    'stock.mission.report.line',
    'stock.move',
    'stock.picking',
    'stock.production.lot',
    'stock.reason.type',
    'stock.warehouse',
    'stock.warehouse.automatic.supply',
    'stock.warehouse.automatic.supply.line',
    'stock.warehouse.order.cycle',
    'stock.warehouse.order.cycle.line',
    'stock.warehouse.orderpoint',
    'supplier.catalogue',
    'supplier.catalogue.line',
    'sync.monitor',
    'sync.sale.order.line.split',
    'sync.version.instance.monitor',
    'tender',
    'tender.line',
    'threshold.value',
    'threshold.value.line',
]

OC_LIST = ['OCA', 'OCB', 'OCBA', 'OCG', 'OCP']
OC_LIST_TUPLE = zip([x.lower() for x in OC_LIST], OC_LIST)

def xmlid_to_sdref(xmlid):
    if not xmlid: return None
    head, sep, tail = xmlid.partition('.')
    if sep:
        assert head == 'sd', "The xmlid %s is not owned by module sd, which is wrong"% xmlid
        return tail
    else:
        return head

# TODO deprecated, should disappear
def sync_log(obj, message=None, level='debug', ids=None, data=None, tb=False):
    if not hasattr(obj, '_logger'):
        raise Exception("No _logger specified for object %s!" % obj._name)
    output = ""
    if tb:
        output += traceback.format_exc()
    if message is None:
        previous_frame = sys._getframe(1)
        output += "%s.%s()" % (previous_frame.f_globals['__package__'], previous_frame.f_code.co_name)
    elif isinstance(message, BaseException):
        if hasattr(message, 'value'):
            output += tools.ustr(message.value)
        elif hasattr(message, 'message'):
            output += tools.ustr(message.message)
        else:
            output += tools.ustr(message)
        if output and output[-1] != "\n": output += "\n"
    else:
        output += "%s: %s" % (level.capitalize(), message)
    if ids is not None:
        output += " in model %s, ids %s\n" % (obj._name, ", ".join(ids))
    if data is not None:
        output += " in content: %s\n" % pprint.pformat(data)
    if output and output[-1] != "\n": output += "\n"
    getattr(obj._logger, level)(output[:-1])
    return output



__re_fancy_integer_field_name = re.compile(r'^fancy_(.+)')
def fancy_integer(self, cr, uid, ids, name, arg, context=None):
    global __re_fancy_integer_field_name
    re_match = __re_fancy_integer_field_name.match(name)
    assert re_match is not None, "Invalid field detection for fancy integer display"
    target_field = re_match.group(1)
    res = self.read(cr, uid, ids, [target_field], context=context)
    return dict(zip(
        (rec['id'] for rec in res),
        (rec[target_field] or '' for rec in res),
    ))



re_xml_id = re.compile(r"(?:,|^)([^.,]+\.[^.]+)$")
def split_xml_ids_list(string):
    """
    Split xml_ids string list and return a list.

    Limitations:
    - modules must not have . nor , in its name
    - names must not have . in its name
    """
    result = []
    matches = re_xml_id.search(string)
    while matches:
        result.insert(0, matches.group(1))
        string = string[:-len(matches.group(0))]
        matches = re_xml_id.search(string)
    assert not string, "Still have a string in the list: \"%s\" remains" % string
    return result



def normalize_xmlid(string):
    """
    Try to normalize xmlid given by removing any comma.
    """
    return string.replace(',', '_')

def get_md5(obj):
    return hashlib.md5(json.dumps(obj, sort_keys=True)).hexdigest()

def check_md5(md5, data, add_info=""):
    if md5 != get_md5(data):
        raise Exception(_('Error during data transmission, checksum does not match %s') % add_info)
