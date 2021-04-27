# -*- coding: utf-8 -*-
import openobject.templating

class BaseTemplEditor(openobject.templating.TemplateEditor):
    templates = ['/openobject/controllers/templates/base.mako']

    def edit(self, template, template_text):
        output = super(BaseTemplEditor, self).edit(template, template_text)

        end_head = output.index('</head>')

        output = output[:end_head] + """
        <link rel="stylesheet" type="text/css" href="/sync_client_web/static/css/cs.css"/>
        """ + output[end_head:]

        return output

class HeaderTempEditor(openobject.templating.TemplateEditor):
    templates = ['/openerp/controllers/templates/header.mako']
    BINARY_ATTACHMENTS_FORM = '<ul id="skip-links">'

    def edit(self, template, template_text):
        output = super(HeaderTempEditor, self).edit(template, template_text)

        form_insertion_point = output.index(self.BINARY_ATTACHMENTS_FORM)
        return output[:form_insertion_point] + '''
<div id="client_string_one"></div>
<div id="client_string_two"></div>
<script type="text/javascript">

//refresh divs delay
var delay = 30000;

function UpdateDiv()
{
    $.ajax({
        type: 'post',
        data: {},
        dataType : 'json',
        timeout: 5000,
        url: '/sync_client_web/synchro_client/get_data',
        success: function(res) {
            $('#client_string_one').html(res.status);
            $('#client_string_two').html(res.upgrade_status);
        },
        complete: function() {
            setTimeout("UpdateDiv()", delay);
        }
    });
}
%if rpc.session.uid:
jQuery(document).ready(function() {
    UpdateDiv();
});
%endif
</script>''' + output[form_insertion_point:]
