<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>

<%def name="header()">
    <title>${_("Information")}</title>
    <link href="/openerp/static/css/style.css" rel="stylesheet" type="text/css"/>
    <script type="text/javascript">
        get_progress = function () {
            var req = openobject.http.postJSON('/openerp/progressbar/get', {'model': "${model}", 'id': ${id}, "job_id": ${job_id}});
            req.addCallback(function(obj) {
                if (obj.error) {
                    jQuery.fancybox(obj.error, {scrolling: 'no'});
                }
                else {
                    $('#indicator').width((obj.progress*250)/100+'px');
                    $('#percentage').html(obj.progress+'%');
                    if (obj.state != 'done') {
                        setTimeout(get_progress, 1000);
                    } else {
                        $('#boxtitle').html("Done");
                        $('#open_src').show();
                        if (obj.target) {
                            $('#open_target').show();
                            $('#open_target').click(function() {window.openAction(obj.target);jQuery.fancybox.close();});
                        }
                    }
                }
                });

        }
    jQuery(document).ready(function () {
        get_progress();
    });
    </script>

    <style>
        #progressbar {
            width: 250px;
            padding:1px;
            background-color:white;
            border:1px solid black;
            height:28px;
            line-height: 28px;
            vertical-align: middle;
            text-align: center;
            font-weight: bold;
            font-size: 120%;
            }

        #pwidget {
            background-color:lightgray;
            width:254px;
            margin-top: 20px;
            margin-left: auto;
            margin-right: auto;
            padding:2px;
            -moz-border-radius:3px;
            border-radius:3px;
            text-align:center;
            border:1px solid gray;
        }

        #indicator {
            width: 0px;
            background-image: linear-gradient(white, green);
            height: 28px;
            margin: 0;
        }

        #percentage {
            position: absolute;
        }
    </style>
</%def>

<%def name="content()">
    <table class="view" cellspacing="5" border="0" height="200px" width="400px">
        <tr>
            <td>
                <h1 id="boxtitle">${_("In Progress")}</h1>
            </td>
        </tr>
        <tr>
            <td>
                <div id="pwidget">
                    <div id="progressbar">
                    <span id="percentage"></span>
                    <div id="indicator" style="width: 25px"></div>
                    </div>
                </div>
            </td>
        </tr>
        <tr>
            <td>
            <button id="open_src" style="display:none" onclick="window.editRecord(${id});jQuery.fancybox.close();">View Object</button>
            <button id="open_target" style="display:none">View Target</button>
            </td>
        </tr>
    </table>
</%def>
