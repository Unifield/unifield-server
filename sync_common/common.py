import re
import sys
import traceback
import pprint
import hashlib
import json


import tools
from tools.translate import _

MODELS_TO_IGNORE = [
                    'ir.actions.wizard',
                    'ir.actions.act_window.view',
                    'ir.report.custom',
                    'ir.ui.menu',
                    'ir.actions.act_window.view',
                    'ir.actions.wizard',
                    'ir.report.custom',
                    'ir.ui.menu',
                    'ir.ui.view',
                    'ir.sequence',
                    'ir.actions.url',
                    'ir.values',
                    'ir.report.custom.fields',
                    'ir.cron',
                    'ir.actions.report.xml',
                    'ir.property',
                    'ir.actions.todo',
                    'ir.sequence.type',
                    #'ir.actions.act_window',
                    'ir.module.module',
                    'ir.ui.view',
                    'ir.module.repository',
                    'ir.model.data',
                    'ir.model.fields',
                    'ir.ui.view_sc',
                    'ir.config_parameter',

                    #'sync.monitor',
                    'sync.client.rule',
                    'sync.client.push.data.information',
                    'sync.client.update_to_send',
                    'sync.client.update_received',
                    'sync.client.entity',
                    'sync.client.sync_server_connection',
                    'sync.client.message_rule',
                    'sync.client.message_to_send',
                    'sync.client.message_received',
                    'sync.client.message_sync',
                    'sync.client.orm_extended',

                    'sync.server.test',
                    'sync_server.version.manager',
                    'sync.server.entity_group',
                    'sync.server.entity',
                    'sync.server.group_type',
                    'sync.server.entity_group',
                    'sync.server.entity',
                    'sync.server.sync_manager',
                    'sync_server.sync_rule',
                    'sync_server.message_rule',
                    'sync_server.sync_rule.forced_values',
                    'sync_server.sync_rule.fallback_values',
                    'sync_server.rule.validation.message',
                    'sync.server.update',
                    'sync.server.message',
                    'sync_server.version',
                    'sync.server.puller_logs',
                    'audittrail.log.sequence',
                    'audittrail.log.line',

                    'res.widget',
                    'product.likely.expire.report',
                    'product.likely.expire.report.line',
                    'internal.move.processor',
                    'internal.picking.processor',
                  ]

MODELS_TO_IGNORE_DOMAIN = [
        'sync_client.%',
        'sync_server.%',
        'res.widget%',
        'base%',
        'board%',
        'audittrail%',
        'workflow%',
    ]

TOUCH_FIELDS_TO_IGNORE = {
    'purchase.order': ['allocation_report_lines'],
}
def __compile_models_to_ignore():
    global MODELS_TO_IGNORE_DOMAIN
    simple_patterns = []
    exact_models = []
    for model in MODELS_TO_IGNORE_DOMAIN:
        if model.find('%') >= 0:
            simple_patterns.append(model)
        else:
            exact_models.append(model)
    MODELS_TO_IGNORE_DOMAIN[:] = [('model','not in',exact_models)]
    for pattern in simple_patterns:
        MODELS_TO_IGNORE_DOMAIN.extend(['!',('model','=like',pattern)])

__compile_models_to_ignore()



def xmlid_to_sdref(xmlid):
    if not xmlid: return None
    head, sep, tail = xmlid.partition('.')
    if sep:
        assert head == 'sd', "The xmlid %s is not owned by module sd, which is wrong"% xmlid
        return tail
    else:
        return head



# TODO deprecated, should disappear
def sync_log(obj, message=None, level='debug', ids=None, data=None, traceback=False):
    if not hasattr(obj, '_logger'):
        raise Exception("No _logger specified for object %s!" % obj._name)
    output = ""
    if traceback:
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
