<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>

<%def name="header()">
    <title>${_("%s's fields") % (model,)}</title>
    <link href="/openerp/static/css/style.css" rel="stylesheet" type="text/css"/>
</%def>

<%def name="content()">
    <table class="view" cellspacing="5" border="0" width="100%">
        <tr>
            <td>
                <h1>${_("%s's fields") % (model,)}</h1>
            </td>
        </tr>
        <tr>
            <td>
                <div class="box2">
                    <table border="0" width="100%" align="center">
                        % for k, v in model_fields:
                        <tr>
                            <td valign="top">
                                <span class="process-field-name">${k}:</span>
                            </td>
                            <td valign="top">
                            % for l, m in v.iteritems():
                                % if m:
                                    <span class="process-field-attribute-name">
                                        ${l}${m is not True and ':' or ''}
                                    </span>
                                    % if m is not True:
                                        <span class="process-field-attribute-value">${m}</span>
                                    % endif
                                    <br />
                                % endif
                            % endfor
                            </td>
                        </tr>
                        <tr>
                            <td valign="top" colspan="2">&nbsp;</td>
                        </tr>
                        % endfor
                    </table>
                </div>
            </td>
        </tr>
    </table>
</%def>
