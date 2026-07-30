<div style="position:relative; display:inline-block;">
    <input type="${type}" ${py.attrs(attrs)} class="${css_class}"/>
    <img
        src="/openerp/static/images/eye.png"
        alt=""
        title="${_('Hold to show password')}"
        style="
            width:12px;
            height:12px;
            position:absolute;
            right:8px;
            top:50%;
            transform:translateY(-50%);
            cursor:pointer;
        "
        onmousedown="document.getElementById('show_${replace_for}').type='text';"
        onmouseup="document.getElementById('show_${replace_for}').type='password';"
        onmouseleave="document.getElementById('show_${replace_for}').type='password';"
    />
</div>