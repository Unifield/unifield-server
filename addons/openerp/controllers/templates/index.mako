<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>

<%def name="header()">
    <title>UniField</title>

    <script type="text/javascript" src="/openerp/static/javascript/accordion.js"></script>
    <script type="text/javascript" src="/openerp/static/javascript/treegrid.js"></script>
    <script type="text/javascript" src="/openerp/static/javascript/notebook/notebook.js"></script>

    <script type="text/javascript">
        var DOCUMENT_TO_LOAD = "${load_content|n}";
        var CAL_INSTANCE = null;

        // Make user home widgets deletable
        jQuery(document).delegate('#user_widgets a.close', 'click', function(e) {
            var $widget = jQuery(this);
            jQuery.post(
                $widget.attr('href'),
                {widget_id: $widget.attr('id')},
                function(obj) {
                    if(obj.error) {
                        error_display(obj.error);
                        return;
                    }
                    var $root = $widget.closest('.sideheader-a');
                    $root.next()
                         .add($root)
                         .remove();
                }, 'json');
            return false;
        });

        jQuery(document).ready(function () {
            jQuery('.web_dashboard').hover(function () {
                var $dashboard_item = jQuery(this);
                if(!$dashboard_item.find('img.hover')) {
                    return;
                }
                $dashboard_item.find('img').toggle();
            });

            // Don't load doc if there is a hash-url, it takes precedence
            if(DOCUMENT_TO_LOAD && !$.hash()) {
                openLink(DOCUMENT_TO_LOAD);
                return
            }
        });
        // Make system logs deletable
        jQuery('#system-logs a.close-system-log').click(function() {
            var $link = jQuery(this);
            jQuery.post(
                $link.attr('href'),
                { log_id: $link.attr('id').replace('system-log-', '') },
                function(obj) {
                    if(obj.error) {
                        error_display(obj.error);
                        return;
                    }
                    if ($link.parents('table').eq(0).find('tr').length == 1) {
                        $('#system-logs').prev().hide();
                        $('#system-logs').hide();
                    } else {
                        $link.parents('tr').eq(0).remove();
                    }
                }, 'json');
            return false;
        });
    </script>
</%def>

<%def name="content()">

    <div id="root">
        <table id="content" class="three-a open" width="100%" height="100%">
            <tr>
                <%include file="header.mako"/>
            </tr>
            <tr>
                <td id="main_nav" colspan="4">
                    <div id="applications_menu">
                        <ul>
                            %for parent in parents:
                                <li>
                                    <a href="${py.url('/openerp/menu', active=parent['id'])}"
                                       target="_top" class="${parent.get('active', '')}">
                                        <span>${parent['name']}</span>
                                    </a>
                                </li>
                            % endfor
                        </ul>
                    </div>
                </td>
            </tr>
            <tr>
                <%include file="banner.mako"/>
            </tr>
            <tr>
                <%include file="shortcut_tooltip.mako"/>
            </tr>
            % if tools is not None:
                <tr>
                    <td id="secondary" class="sidenav-open">
                    <a onclick="$('#nav2').toggle();$('#main-sidebar-toggler').toggleClass('closed');" id="main-sidebar-toggler">Toggle Menu</a>
                        <div class="wrap" id="nav2">
                            <ul id="sidenav-a" class="accordion">
                                % for tool in tools:
                                    % if tool.get('action'):
                                      <li class="accordion-title" id="${tool['id']}">
                                    % else:
                                      <li class="accordion-title">
                                    % endif
                                        <span>${tool['name']}</span>
                                    </li>
                                    <li class="accordion-content" id="content_${tool['id']}">
                                       ${tool['tree'].display()}
                                    </li>
                                % endfor
                            </ul>
                            <script type="text/javascript">
                                new Accordion("sidenav-a");
                            </script>
                        </div>
                    </td>
                    <td></td><td id="primary">
                        <div class="wrap">
                            <div id="appContent"></div>
                        </div>
                    </td>
                </tr>
            % else:
                <tr>
                    <td colspan="4" height="100%" valign="top">
                        <table width="100%" height="100%">
                            <tr>
                                <td id="primary" class="first-page-primary">
                                    <div class="wrap" style="padding: 10px;">
                                        <ul class="sections-a">
                                            % for parent in parents:
                                                <li class="web_dashboard" id="${parent['id']}">
                                                    <span class="wrap">
                                                        <a href="${py.url('/openerp/menu', active=parent['id'])}" target="_top">
                                                            <table width="100%" height="100%" cellspacing="0" cellpadding="1">
                                                                <tr>
                                                                    <td align="center" style="height: 100px;">
                                                                        % if parent['web_icon_data']:
                                                                            <img src="data:image/png;base64,${parent['web_icon_data']}" alt=""/>
                                                                        % endif
                                                                        %if parent['web_icon_hover_data']:
                                                                            <img class="hover" src="data:image/png;base64,${parent['web_icon_hover_data']}" alt=""/>
                                                                        % endif
                                                                    </td>
                                                                </tr>
                                                                <tr>
                                                                    <td>
                                                                        <span>
                                                                            <strong>${parent['name']}</strong>
                                                                        </span>
                                                                    </td>
                                                                </tr>
                                                            </table>
                                                        </a>
                                                    </span>
                                                </li>
                                            % endfor
                                        </ul>
                                    </div>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            % endif
            <tr>
                <td id="footer_section" colspan="4">
                    <div class="footer-a">
                        <p class="one">
                            <span>${rpc.session.protocol}://${_("%(user)s", user=rpc.session.loginname)}@${rpc.session.host}:${rpc.session.port}</span>
                            <span>${cp.locale()}</span>
                        </p>
                        <p class="powered">${_("Powered by %(openerp)s ",
                                            openerp="""<a target="_blank" href="http://www.openerp.com/">openerp.com</a>""")|n}</p>
                    </div>
                </td>
            </tr>
        </table>
    </div>
</%def>

