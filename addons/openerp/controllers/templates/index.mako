<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>

<%def name="header()">
    <title>UniField</title>

    <script type="text/javascript" src="/openerp/static/javascript/accordion.js"></script>
    <script type="text/javascript" src="/openerp/static/javascript/treegrid.js?v=uf23.0"></script>
    <script type="text/javascript" src="/openerp/static/javascript/notebook/notebook.js"></script>

    <script type="text/javascript">
        var DOCUMENT_TO_LOAD = "${load_content|n}";
        var CAL_INSTANCE = null;

        var DISPLAY_WARNING = ${display_warning};
        var REFRESH_TIMEOUT = ${refresh_timeout};

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

    <% user_locale = cp.locale().language %>
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
            % if from_login:
            <tr>
               <td id="shortcut_message" colspan="3">${_('Do you have any questions on how to use UniField ? You can click on the button')} <a id="help_banner_icon" href="https://doc.unifield.org/" target="_blank"></a> ${_('on the top right of the screen to reach the User Manuals website.')}</td>
            </tr>
            % endif
            % for goto_survey in goto_surveys:
                % if user_locale == 'fr' and goto_survey.get('name_fr'):
                    <% survery_name = goto_survey.get('name_fr') %>
                % else:
                    <% survery_name = goto_survey.get('name') %>
                % endif
                % if user_locale == 'fr' and goto_survey.get('url_fr'):
                    <% survey_link = goto_survey.get('url_fr') %>
                % else:
                    <% survey_link = goto_survey.get('url_en') %>
                % endif
                <tr>
                    <td id="shortcut_message" colspan="3">${_('Here is the link to the survey')} <a href="${survey_link}" target="_blank">${survery_name}</a></td>
                </tr>
            % endfor

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
                            <span>${user_locale}</span>
                        </p>
                        <p class="powered">${_("Powered by %(openerp)s ",
                                            openerp="""<a target="_blank" href="http://www.openerp.com/">openerp.com</a>""")|n}</p>
                    </div>
                </td>
            </tr>
        </table>
    </div>


    % if survey:
        <div id="survey">
                <div id="survey_title">${_('We welcome your feedback.')}</div>
                <div>${_('Help us improve your experience by taking our short survey.')}</div>
                <div id="survey_name">
                % if user_locale == 'fr' and survey.get('name_fr'):
                    ${survey.get('name_fr')}
                % else:
                    ${survey.get('name')}
                % endif
                </div>
                 <div class="row">
                  <div class="column"><div class="survey_button" onclick="click_answer('goto')">${_('Go to survey')}</div></div>
                  <div class="column"><div class="survey_button" onclick="click_answer('later')">${_('Answer Later')}</div></div>
                  <div class="column" id="button_never"
                    % if survey['nb_displayed'] < 3:
                        style="display: none"
                    % endif
                  ><div class="survey_button" onclick="click_answer('never')">${_('Do not ask me again')}</div></div>
                </div>
        </div>
        <script type="text/javascript">
            % if user_locale == 'fr' and survey.get('url_fr'):
                var survey_url = "${survey.get('url_fr')}";
            % else:
                var survey_url = "${survey.get('url_en')}";
            % endif
            var survey_stat_id = ${survey['stat_id']};
            var survey_id = ${survey['id']};
            var survey_index = 0;

            jQuery('#survey').fancybox({'modal': true, 'height': 250, 'width': 700, 'scrolling': 'no', 'autoDimensions': false, 'autoScale': false});

            jQuery(document).ready(function() {
                jQuery('#survey').trigger('click');
                jQuery('#survey').show();
                jQuery('#survey').unbind('click.fb');
            })


            function click_answer(answer) {
                if (answer == 'goto') {
                    window.open(survey_url,'_blank');
                }
                jQuery.post('/openerp/survey_answer', {'answer': answer, 'survey_id': survey_id, 'stat_id': survey_stat_id});
                next_survey = false;
                % if len(other_surveys):
                    var other_surveys = ${other_surveys|n};
                    if (other_surveys.length > survey_index) {
                        jQuery('#survey').hide();
                        next_survey = other_surveys[survey_index];
                        % if user_locale == 'fr':
                            survey_url = next_survey.url_fr||next_survey.url_en;
                            survey_name = next_survey.name_fr||next_survey.name;
                        % else:
                            survey_url = next_survey.url_en;
                            survey_name = next_survey.name;
                        % endif
                        survey_stat_id = next_survey.stat_id;
                        survey_id = next_survey.id;
                        $('#survey_name').html(survey_name);
                        if (next_survey.nb_displayed > 2) {
                            $('#button_never').show();
                        } else {
                            $('#button_never').hide();
                        }
                        survey_index += 1;
                        setTimeout(function(){jQuery('#survey').show()}, 450);
                    }
                % endif

                if (!next_survey) {
                    jQuery('#survey').hide();
                    jQuery.fancybox.close();
                }
            }
        </script>
    % elif signature_required:
        <div id="survey">
                <div id="survey_title">${_('New signature required')}</div>
                 <div class="row">
                  <div class="column"><div class="survey_button" onclick="click_answer('goto')">${_('Create my signature')}</div></div>
                  <div class="column"><div class="survey_button" onclick="click_answer('later')">${_('Ask Later')}</div></div>
                </div>
        </div>
        <script type="text/javascript">
            jQuery('#survey').fancybox({'modal': true, 'height': 250, 'width': 700, 'scrolling': 'no', 'autoDimensions': false, 'autoScale': false});

            jQuery(document).ready(function() {
                jQuery('#survey').trigger('click');
                jQuery('#survey').show();
                jQuery('#survey').unbind('click.fb');
            });
            function click_answer(answer) {
                if (answer=='goto') {
                    openAction('/openerp/pref/create_signature', 'new', false, false, '400px', '720px');
                }
                jQuery('#survey').hide();
                jQuery.fancybox.close();
            }
        </script>
    % elif email_required:
        <div id="survey">
                <div id="survey_title">${_('Please fill your email address')}</div>
                 <div class="row">
                  <div class="column" style="width: 50%">Email: <input type="email" id="email" /></div>
                  <div class="column"><div class="survey_button" onclick="click_email_answer('goto')">${_('Save email')}</div></div>
                </div>
                 <div class="row">
                  % if nb_email_asked < 2:
                    <div class="column"><div class="survey_button" onclick="click_email_answer('later')">${_('Ask Later')}</div></div>
                  % else:
                    <div class="column"><div class="survey_button" onclick="click_email_answer('never')">${_('Do not ask again')}</div></div>
                  % endif
                </div>
        </div>
        <script type="text/javascript">
            jQuery('#survey').fancybox({'modal': true, 'height': 250, 'width': 700, 'scrolling': 'no', 'autoDimensions': false, 'autoScale': false});

            jQuery(document).ready(function() {
                jQuery('#survey').trigger('click');
                jQuery('#survey').show();
                jQuery('#survey').unbind('click.fb');
                jQuery('#email').focus()
            });
            function click_email_answer(answer) {
                if (answer=='goto') {
                    email_field = jQuery('#email')
                    if (!email_field[0].checkValidity()) {
                        alert(_('Invalid Email address'));
                        return false;
                    }
                    jQuery.post('/openerp/pref/save_email', {'email': email_field.val()});
                } else if (answer=='later') {
                    jQuery.post('/openerp/pref/email_update_nb');
                } else if (answer=='never') {
                    jQuery.post('/openerp/pref/email_dontask');
                }
                jQuery('#survey').hide();
                jQuery.fancybox.close();
            }
        </script>
    % endif
</%def>

