<%def name="display_open_resource(name)">
<img id="${name}_open" alt="${_('Open')}" title="${_('Open a resource')}"
        src="/openerp/static/images/iconset-d-drop.gif" class="m2o_open"/>
</%def>
<%def name="m2o_container()">
    <div class="m2o_container">
        ${caller.body()}
    </div>
</%def>
% if editable:
    <%self:m2o_container>
            <input type="hidden" id="${name}" name="${name}" class="${css_class}" value="${value}"
                ${py.attrs(attrs, kind=kind, domain=domain, context=ctx,
                relation=relation, required=required and 1 or 0,
                fld_readonly=1 if readonly_before_state else 0)}/>
	% if 'readonlyfield' in css_class:
        <span id="${name}" ${py.attrs(kind=kind, value=value, relation=relation, link=link)}>${text}</span>
            <input type="hidden" id="${name}_text" class="${css_class}" size="1"
                ${py.attrs(attrs, kind=kind, relation=relation, value=text)}/>
	% else:
	        <span id="${name}_ro" />
            <input type="text" id="${name}_text" class="${css_class}" size="1"
                ${py.attrs(attrs, kind=kind, relation=relation, value=text)}/>

            <input type="hidden" id="_hidden_${name}" value=""/>
            % if error:
                <span class="fielderror">${error}</span>
            % endif
<img id="${name}_select" alt="${_('Search')}" title="${_('Search')}"
                src="/openerp/static/images/fields-a-lookup-a.gif" class="m2o_select"/>${self.display_open_resource(name)}
        <div id="autoCompleteResults_${name}" class="autoTextResults"></div>
        <script type="text/javascript">
            new ManyToOne('${name}');
        </script>
	% endif
	% if False and 'readonlyfield' in css_class:
		<script type="text/javascript">
			resizeInput('${name}_text');
		</script>
	% endif
    </%self:m2o_container>
% elif link:
    % if link == '0':
        <span id="${name}" ${py.attrs(kind=kind, value=value, relation=relation, link=link)}>${text}</span>
    % else:
        <span id="${name}" name="${name}" ${py.attrs(kind=kind, value=value, relation=relation, context=ctx, domain=domain, link=link)}>
            <a style="color:#9A0404;" href="javascript: void(0)" onclick="new ManyToOne('${name}').open_record('${value}')">${text}</a>
        </span>
    % endif
% endif

% if default_focus:
	<script type="text/javascript">
	    jQuery('#${name}_text').focus()
	</script>
% endif
