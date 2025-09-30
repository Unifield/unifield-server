<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>
<%def name="header()">
    <title>Instance creation progression</title>

    <script type="text/javascript" src="/openerp/static/javascript/openerp/openerp.ui.waitbox.js"></script>
    <script type="text/javascript">


            var progess_fct = function(){
                $.ajax({
                    type: 'get',
                    dataType: "json",
                    url: 'get_auto_create_progress',
                    success: function (data) {

                        if (data){
                            if (data.error){
                                var $error_tbl = jQuery('<table class="errorbox">');
                                $error_tbl.append('<tr><td style="padding: 4px 2px;" width="10%"><img src="/openerp/static/images/warning.png"></td><td class="error_message_content">' + data.error + '</td></tr>');
                                $error_tbl.append('<tr><td style="padding: 0 8px 5px 0; vertical-align:top;" align="right" colspan="2"><a class="button-a" id="error_btn" onclick="$error_tbl.dialog(\'close\');">OK</a></td></tr>');

                                jQuery(document).ready(function () {
                                    jQuery(document.body).append($error_tbl);
                                    var error_dialog_options = {
                                        modal: true,
                                        resizable: false,
                                        title: '<div class="error_message_header">Error</div>'
                                    };
                                    $error_tbl.dialog(error_dialog_options);
                                })

                            };
                            $("div.auto_creation_resume textarea").val(data.resume);
                            $("div.progressbar").text((data.progress*100).toPrecision(3)+'%');
                            $("div.progressbar").css({"width":(data.progress*100).toPrecision(3)+'%'});
                            $("div.my_state").text(data.state);
                            if (data.state === 'done') {
                                $("#login-button").css({'display': 'inline'})
                            };
                            if (data.monitor_status) {
                                $("div.my_monitor_status").text(data.monitor_status);
                            };
                        }
                        if (!data || ( !data.error && data.state != 'done')) {
                            setTimeout(progess_fct, 3000);
                        }
                    },
                    error: function (xhr, status, error) {
                        setTimeout(progess_fct, 3000)
                    }
                });
            }

        $(document).ready(function(){
            setTimeout(progess_fct, 15000)
        });
    </script>

    <link rel="stylesheet" type="text/css" href="/openerp/static/css/waitbox.css"/>
    <link rel="stylesheet" type="text/css" href="/openerp/static/css/database.css?v=7.0"/>

</%def>

<%def name="content()">
	<table width="100%">
        <tr><%include file="header.mako"/></tr>
    </table>



    <div class="db-form">
        <h1>Automated instance creation in progress...</h1>

        <div class="my_state"></div>
        <div class="my_monitor_status"></div>

        <div class="instance_creation_progress">
          <div class="progressbar" style="width:${'%d'%(percent*100)}%">${'%d'%(percent*100)}%</div>
        </div>

        <div class="auto_creation_resume">
            <textarea rows="20" cols="80">${resume}</textarea>
        </div>

        <div id="connect_instance" class="auto_creation_resume">
            <a href="/openerp/login/" id="login-button" style="display:none" class="button-a">Open Login Page</a>
        </div>
    </div>
<a class="auto_instance_debug" href="/openerp/login/?style=noauto"><img src="/openerp/static/images/icons/idea.png" alt="debug access" /></a>
<%include file="footer.mako"/>
</%def>
