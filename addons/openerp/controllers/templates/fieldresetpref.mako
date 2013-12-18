<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>

<%def name="header()">
    <title>${_("Field Preferences")}</title>
    <script type="text/javascript">
    jQuery(document).ready(function(){
        if(openobject.dom.get('click_ok').value)
            window.frameElement.close();
        });
    </script>

</%def>

<%def name="content()">
<form action="/openerp/fieldpref/reset_apply" method="post">

    <input id="_terp_model" name="_terp_model" value="${model}" type="hidden"/>
    <input id="_terp_model" name="_terp_field" value="${field}" type="hidden"/>
    <input id="click_ok" name="click_ok" value="${click_ok}" type="hidden"/>

    <table class="view" cellspacing="5" border="0" width="100%">
        <tr>
            <td>
                <table width="100%" class="titlebar">
                    <tr>
                        <td width="100%"><h1>${string} ${_("field: Reset Preferences")}</h1></td>
                    </tr>
                </table>
            </td>
        </tr>
        <tr>
            <td>
                <div class="box2">
                % if values:
                    <table border="0" width="100%" align="center">
                     <tr>
                        <th>&nbsp;</th>
                        <th>Value</th>
                        <th>Applicable for</th>
                        <th>Condition</th>
                     </tr>
                      % for v in values:
                        <tr>
                            <td><input type="checkbox" name="_terp_to_del/${v['id']}" value="${v['id']}" ${len(values)==1 and 'checked="checked"' or ''}></td>
                            <td align="center">${v['real_value']}</td>
                            <td align="center">${v['user_id'] and _('Only for you') or _('For all')}</td>
                            <td align="center">${v['key2'] or _("Always applicable!")}</td>
                        </tr>
                     % endfor
                    </table>
                % else:
                    ${_('No default value')}
                % endif
                </div>
                <div class="toolbar">
                    <table border="0" cellpadding="0" cellspacing="0" width="100%">
                        <tr>
                            <td width="100%">
                        </td>
                        <td>
                            <a class="button-a" href="javascript: void(0)" onclick="window.frameElement.close()">${_("Close")}</a>
                        </td>
                        <td>
                          % if values:
                            <button type="submit">${_("Delete selection")}</button>
                          % endif
                        </td>
                        </tr>
                    </table>
                </div>

            </td>
        </tr>
    </table>
</form>
</%def>
