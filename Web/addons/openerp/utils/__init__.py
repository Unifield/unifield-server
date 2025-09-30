from openobject.tools._expose import register_template_vars

from . import rpc
from . import rpc_utils
from .tools import expr_eval, node_attributes, xml_locate, get_xpath, get_node_xpath, get_size, context_with_concurrency_info, get_max_attachment_size, TempFileName, is_server_local
from .utils import get_server_version, TinyForm, TinyFormError, TinyDict, noeval, format_datetime_value


__all__ = ['register_template_vars', 'rpc', 'rpc_utils',
           'expr_eval', 'node_attributes', 'xml_locate', 'get_xpath', 'get_node_xpath', 'get_size', 'context_with_concurrency_info', 'get_max_attachment_size', 'TempFileName', 'is_server_local',
           'get_server_version', 'TinyForm', 'TinyFormError', 'TinyDict', 'noeval', 'format_datetime_value'
           ]
def _root_vars():
    return {
        'rpc': rpc,
    }

register_template_vars(_root_vars, None)
del register_template_vars
