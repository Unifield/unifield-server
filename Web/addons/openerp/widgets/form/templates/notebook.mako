<div id="${name}">
    % for page in children:
    <div ${py.attrs(title=page.string, attrs=page.attributes, widget=fake_widget, view_id=page.view_id, on_change=page.on_change)}>
        <div>${display_member(page)}</div>
    </div>
    % endfor
</div>
<script type="text/javascript">
    new Notebook('${name}', {
        'closable': false,
        'scrollable': true,
        'prefix': '${prefix}',
    });
</script>

