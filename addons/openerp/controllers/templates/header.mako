<%
# put in try block to prevent improper redirection on connection refuse error
try:
    ROOT = cp.request.pool.get_controller("/openerp")
    SHORTCUTS = cp.request.pool.get_controller("/openerp/shortcuts")
    REQUESTS = cp.request.pool.get_controller("/openerp/requests")

    shortcuts = SHORTCUTS.my()
    requests, total_request = REQUESTS.my()
except:
    ROOT = None

    shortcuts = []
    requests = []
    requests_message = None

if rpc.session.is_logged():
    logged = True
else:
    logged = False

css_style_dict = {
    'blue': "background: rgb(0, 0, 255); background: rgba(0, 0, 155, .8);",
    'red': "background: rgb(255, 0, 0); background: rgba(155, 0, 0, .8);",
    'green': "background: rgb(0, 255, 0); background: rgba(0, 100, 0, .8);",
}

css_style = ""
add_style = cp.config('server.environment') in css_style_dict.keys()
if add_style:
    css_style = css_style_dict.get(cp.config('server.environment'), "")
%>
<td id="top"
    % if add_style:
        style="${css_style}"
    % endif
    colspan="3">
    <p id="cmp_logo">
        <a href="/" target="_top">
            <img alt="UniField" id="company_logo" src="/openerp/static/images/unifield.png" height="60"/>
        </a>
    </p>
    % if logged:
        <h1 id="title-menu">
           ${_("%(company)s", company=rpc.session.company_name or '')} (${rpc.session.db})
           <small>${_("%(user)s", user=rpc.session.user_name)}</small>
        </h1>
    % endif
    <ul id="skip-links">
        <li><a href="#nav" accesskey="n">Skip to navigation [n]</a></li>
        <li><a href="#content" accesskey="c">Skip to content [c]</a></li>
        <li><a href="#footer" accesskey="f">Skip to footer [f]</a></li>
    </ul>
    % if logged:
        % if add_style:
        <div id="corner"
            % if add_style:
                style="${css_style}"
            % endif
        >
            <ul class="tools"
                % if add_style:
                    style="${css_style}"
                % endif
            >
        % else:
        <div id="corner">
            <ul class="tools">
        % endif
                <li><a href="https://doc.unifield.org/" target="_blank" class="user_manuals"
                       % if add_style:
                           style="background-position: -94px 0px;"
                           onMouseOver="this.style.opacity=0.6"
                           onMouseOut="this.style.opacity=1.0"
                       % endif
                >${_("User Manuals")}</a>
                    <ul>
                        <li class="first last"><a href="https://doc.unifield.org/" target="_blank">${_("User Manuals")}</a></li>
                    </ul>
                </li>

                <li><a href="${py.url('/openerp')}" target="_top" class="home"
                       % if add_style:
                           style="background-position: -22px 0px;"
                           onMouseOver="this.style.opacity=0.6"
                           onMouseOut="this.style.opacity=1.0"
                       % endif
                >${_("Home")}</a>
                    <ul>
                        <li class="first last"><a href="${py.url('/openerp')}" target="_top">${_("Home")}</a></li>
                    </ul>
                </li>

                <li class="preferences">
                    <a href="${py.url('/openerp/pref/create')}"
                       % if add_style:
                           style="background-position: -70px 0px;"
                           onMouseOver="this.style.opacity=0.6"
                           onMouseOut="this.style.opacity=1.0"
                       % endif
                       class="preferences" target="_blank">${_("Preferences")}</a>
                    <ul>
                        <li class="first last"><a href="${py.url('/openerp/pref/create')}"
                                                  target="_blank">${_("Edit Preferences")}</a></li>
                    </ul>
                </li>

                <li>
                    <a href="${py.url('/openerp/unifield_version')}" class="info"
                       % if add_style:
                           style="background-position: -118px 0px;"
                           onMouseOver="this.style.opacity=0.6"
                           onMouseOut="this.style.opacity=1.0"
                       % endif
                    ></a>
                    <ul>
                        <li class="first last"><a href="${py.url('/openerp/unifield_version')}">${_("Version")}</a></li>
                    </ul>
                </li>
            </ul>
            <p class="logout" 
                % if add_style:
                    style="${css_style}"
                % endif
            >
                <a href="${py.url('/openerp/logout')}"
                   target="_top"
                   % if add_style:
                        style="${css_style}"
                       onMouseOver="this.style.opacity=0.6"
                       onMouseOut="this.style.opacity=1.0"
                   % endif
               >${_("Logout")}</a>
            </p>
        </div>
    % endif
    
    <div id="shortcuts" class="menubar">
    % if logged and display_shortcut:
        <ul>
            % for i, sc in enumerate(shortcuts):
                <li class="${i == 0 and 'first' or ''}">
                    <a id="shortcut_${sc['res_id']}"
                       href="${py.url('/openerp/tree/open', id=sc['res_id'], model='ir.ui.menu')}">
                       <span>${sc['name']}</span>
                    </a>
                </li>
            % endfor
        </ul>
        <div style="position: absolute; right: 5px; top: 6px;">
        <a id="fullscreen-mode" onclick="fullscreen(true);" accesskey="0">${_("Full Screen")}</a>
        <a id="leave-fullscreen-mode" onclick="fullscreen(false);" accesskey="9">${_("Leave Full Screen")}</a>
        </div>
    % endif
    </div>
</td>
<script type="text/javascript">
    jQuery('.tools li.preferences a').click(function (e) {
        e.preventDefault();
        jQuery.frame_dialog({
            src:this.href
        }, null, {
            height: 350,
            width: 900
        }).focus();
    });
</script>
