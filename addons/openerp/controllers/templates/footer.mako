<%page args="multi_host=0, sync_user='', dblen=0"/>
<div class="footer_a">
    <div align="center">
        UniField ${rpc.session.unifield_version()}
        <br/>
            ${_("&copy; 2008-2010 %(ooweb)s  SA. All Rights Reserved ",
            ooweb="""<a target="_blank" href="http://openerp.com">OpenERP</a>""")|n}
        <br/>
    </div>
    <div align="center">
        % if multi_host > 1:
            ${multi_host} ${_('databases hosted')}
        % endif
        % if sync_user and (dblen > 1 or multi_host > 1):
            (${sync_user})
        % endif
    </div>
</div>
