<%inherit file="/openerp/controllers/templates/base_dispatch.mako"/>

<%def name="header()">
    <script type="text/javascript" src="/openobject/static/javascript/MochiKit.js"></script>
    <script type="text/javascript" src="/openobject/static/javascript/MochiKit/Resizable.js"></script>
    <script type="text/javascript" src="/openobject/static/javascript/jQuery/jquery-1.4.2.js"></script>
    <script type="text/javascript">
        jQuery.noConflict();
    </script>
    <script type="text/javascript" src="/openobject/static/javascript/openobject/openobject.base.js"></script>
    <script type="text/javascript" src="/openobject/static/javascript/openobject/openobject.gettext.js"></script>
    <script type="text/javascript" src="/openobject/static/javascript/openobject/openobject.dom.js"></script>
    <script type="text/javascript" src="/openobject/static/javascript/openobject/openobject.http.js"></script>
    <script type="text/javascript" src="/openobject/static/javascript/openobject/openobject.tools.js"></script>
     <script type="text/javascript" src="/openerp/static/javascript/openerp/openerp.ui.textarea.js"></script>

    <script type="text/javascript">    
        jQuery(document).ready(function(){
            if(!window.opener && window.top == window) {
                window.location.href = '/openerp';
                return;
            }
            var topWindow;
            if(window.top != window) {
                % if frompopup:
                if (jQuery(window).attr('frameElement')) {
                    new window.top.frames[0].ListView('${o2m_refresh}').reload()
                    setTimeout(function () {
                      window.frameElement.close();
                    });
                   return;
                }
                % else:
                topWindow = window.top;
                setTimeout(function () {
                    topWindow.closeAction();
                });
                % endif
            } else {
                topWindow = window.opener;
                setTimeout(close);
            }
            /*
            % if reload:
            */
                % if o2m_refresh:
                    new topWindow.ListView('${o2m_refresh}').reload(undefined, undefined, undefined, undefined, undefined, undefined, true);
                % else:
                    var $doc = jQuery(topWindow.document);
                    switch($doc.find('#_terp_view_type').val()) {
                        case 'form':
                            var terp_id = jQuery(idSelector('_terp_id'),$doc).val();
                            if(terp_id == "False") {
                                terp_id = '${active_id}';
                            }
                            if(terp_id == "False" || !terp_id) {
                                topWindow.location.href = '/openerp';
                                return;
                            } else {
                                var editable = jQuery(idSelector('_terp_editable'),$doc).val();
                                if (editable == "True") {
                                    topWindow.editRecord(terp_id);
                                } else {
                                    topWindow.viewRecord(terp_id);
                                }
                                return;
                            }
                        case 'tree':
                            new topWindow.ListView('_terp_list').reload_from_wizard();
                            return;
                    }
                    topWindow.location.reload();
                % endif
            /*
            % endif
            */
        });
    </script>
</%def>

<%def name="content()">

</%def>
