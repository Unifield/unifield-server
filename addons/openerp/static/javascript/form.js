////////////////////////////////////////////////////////////////////////////////
//
// Copyright (C) 2007-TODAY OpenERP SA. All Rights Reserved.
//
// $Id$
//
// Developed by OpenERP (http://openerp.com) and Axelor (http://axelor.com).
//
// The OpenERP web client is distributed under the "OpenERP Public License".
// It's based on Mozilla Public License Version (MPL) 1.1 with following
// restrictions:
//
// -   All names, links and logos of OpenERP must be kept as in original
//     distribution without any changes in all software screens, especially
//     in start-up page and the software header, even if the application
//     source code has been changed or updated or code has been added.
//
// You can see the MPL licence at: http://www.mozilla.org/MPL/MPL-1.1.html
//
////////////////////////////////////////////////////////////////////////////////

var form_controller;

function showActionSdref(ev, action_name, model, action_id)
{
    if(ev.ctrlKey === true) {

        openobject.http.postJSON('/openerp/form/display_action_sd_ref', {
            'action_name': action_name,
            'model': model,
            'action_id': action_id,
        }).addCallback(function(obj){
            if (obj) {
                alert(
                    'Name : ' + action_name + '\n' +
                    'Action sdref: sd.' + obj.sdref + '\n' +
                    'Action Id: '+ action_id +'\n' +
                    'Groups: '+ obj.groups +'\n' +
                    'Model name: ' + model + '\n' +
                    'Model sdref: sd.'+ obj.model_sdref + '\n'
                );
            }
        });
        ev.preventDefault();
    }
}
function showBtnSdref(ev, btn_name, btn_model, btn_id, src)
{
    if(ev.ctrlKey === true) {
        var prefix = src && src != '_terp_list' ? src + '/' : '';
        if (prefix !== '') {
            // In case of one2many, get the o2m view id and the parent model
            o2m_view_id = openobject.dom.get(prefix + '_terp_view_id').value;
            o2m_model = openobject.dom.get(prefix + '_terp_model').value;
            parent_model = openobject.dom.get('_terp_model').value;
            parent_view_id = openobject.dom.get('_terp_view_id').value;

            if (o2m_view_id === 'False' || o2m_view_id === false) {
                view_id = parent_view_id;
                btn_model = parent_model;
            }
            else {
                view_id = o2m_view_id;
                btn_model = o2m_model;
            }
        }
        else {
            view_id = openobject.dom.get('_terp_view_id').value;
            if (btn_model === false || btn_model === '') {
                btn_model = openobject.dom.get('_terp_model').value;
            }
        }

        openobject.http.postJSON('/openerp/form/display_button_sd_ref', {
            'view_id': view_id,
            'btn_name': btn_name,
            'btn_model': btn_model,
            'btn_id': btn_id,
        }).addCallback(function(obj){
            if (obj.admin === true) {
                model_name_msg = obj.model != false ? obj.model : 'No model found';
                model_sdref_msg = obj.model_sdref != false ? obj.model_sdref : 'No model found';
                btn_name_msg = obj.name != false ? obj.name : 'No button found';
                btn_id_msg = obj.btn_id != false ? obj.btn_id : 'No button found';
                bar_sdref_msg = obj.bar_sdref != false ? obj.bar_sdref : 'No BAR found';
                group_names_msg = obj.group_names != false ? obj.group_names : 'No group defined for this rule';

                alert(
                    'Model name: ' + model_name_msg + '\n' + 
                    'Model SDRef: ' + model_sdref_msg + '\n' + 
                    'Button name: ' + btn_name_msg + '\n' + 
                    //'Button ID: ' + btn_id_msg + '\n' + 
                    'BAR SDRef: ' + bar_sdref_msg + '\n' +
                    'Groups: ' + group_names_msg
                );
            }
        });
        ev.preventDefault();
    }
}

function get_form_action(action, params){
    var act = typeof(form_controller) == 'undefined' ? '/openerp/form' : form_controller;
    act = action && action.indexOf('/') == 0 ? action : act + '/' + action;
    return openobject.http.getURL(act, params);
}

function openRecord(id, src, target, readonly){

    var kind = getNodeAttribute(src + '_set', 'kind');

    if (!kind && openobject.dom.get('_o2m_' + src)) {
        kind = "one2many";
    }

    if (kind == "one2many") {
        new One2Many(src).edit(id, readonly);
        return;
    }

    var prefix = src && src != '_terp_list' ? src + '/' : '';

    // Here we do a sanity check that there aren't multiple element with
    // the same id 'prefix/_terp_model'
    // If this is the case, we introduce some delay (call back the same
    // function later)
    //
    // This can happen in some asynchronous edge-case where the DOM is not 
    // fully loaded yet and in particular there's a remaining element with 
    // _terp_model =  ir.ui.menu
    // which might trigger the opening of a completely unrealted view
    //
    // You might reproduce the issue by monitoring the value of
    //    openobject.dom.get(prefix + '_terp_model').value
    // when loading for instance the list of Commitment Vouchers
    //
    // See https://jira.unifield.org/browse/US-3589
    //
    if ($("[id="+prefix+"_terp_model]").length > 1) {
        callLater(0.1, openRecord, id, src, target, readonly);
        return;
    }

    var args = {
        'model': openobject.dom.get(prefix + '_terp_model').value,
        'id': id || 'False',
        'ids': openobject.dom.get(prefix + '_terp_ids').value,
        'view_ids': openobject.dom.get(prefix + '_terp_view_ids').value,
        'traget_action_id': openobject.dom.get(prefix + '_terp_target_action_id').value,
        'view_mode': openobject.dom.get(prefix + '_terp_view_mode').value,
        'view_type': openobject.dom.get(prefix + '_terp_view_type').value,
        'domain': openobject.dom.get(prefix + '_terp_domain').value,
        'context': openobject.dom.get(prefix + '_terp_context').value,
        'offset': openobject.dom.get(prefix + '_terp_offset').value,
        'limit': openobject.dom.get(prefix + '_terp_limit').value,
        'count': openobject.dom.get(prefix + '_terp_count').value,
        'approximation': openobject.dom.get(prefix + '_terp_approximation').value,
        'search_domain': jQuery('#_terp_search_domain').val() || null,
        'search_data': jQuery('#_terp_search_data').val() || null,
        'filter_domain': jQuery('#_terp_filter_domain').val() || [],
        'notebook_tab': jQuery('#_terp_notebook_tab').val() || 0,
        'action_id': jQuery('#_terp_action_id').val() || null
    };
    get_sidebar_status(args, true);
    var action = readonly ? 'view' : 'edit';

    if (target == '_blank') {
        window.open(get_form_action(action, args));
        return;
    }

    if (kind == 'many2many') {
        args['source'] = src;
        action = readonly ? '/openerp/openm2m/view' : '/openerp/openm2m/edit';
        jQuery.frame_dialog({src:openobject.http.getURL(get_form_action(action, args))});
        return;
    }

    openLink(get_form_action(action, args));
}

function editRecord(id, src, target){
    return openRecord(id, src, target, false);
}

function viewRecord(id, src){
    return openRecord(id, src, null, true);
}

function editSelectedRecord(){

    var lst = new ListView('_terp_list');
    var ids = lst.getSelectedRecords();

    if (ids && ids.length > 5) {
        var msg = _('You selected to open %(tabs)s tabs - do you want to continue?');
        msg = msg.replace('%(tabs)s', ids.length);
        if (!confirm(msg)) {
            return;
        }
    }

    forEach(ids, function(id){
        editRecord(id, '_terp_list', '_blank');
    });
}

function switchView(view_type, src){
    if (view_type=='diagram' && !jQuery('#_terp_ids').val()) {
    	alert('There are no records to display diagram view.')
    	return;
    }

    if (openobject.dom.get('_terp_list')) {
        var ids = new ListView('_terp_list').getSelectedRecords();
        if (ids.length > 0) {
            openobject.dom.get('_terp_id').value = ids[0];
        }
    }

    submit_form(get_form_action('switch', {
            '_terp_source': src,
            '_terp_source_view_type': view_type
    }));
}

function validate_required(form){

    if (typeof form == 'string') {
        form = jQuery('#' + form).get(0);
    }

    if (!form) {
        return true;
    }

    var elements = MochiKit.Base.filter(function(el){
        return !el.disabled && el.id && el.name && el.id.indexOf('_terp_listfields/') == -1 && hasElementClass(el, 'requiredfield');
    }, form.elements);

    var result = true;
    var err_msg = false;

    for (var i = 0; i < elements.length; i++) {
        var elem = elements[i];
        var elem2 = elem;
        var value = elem.value;
        var kind = jQuery(elem).attr('kind');
        // Custom message for a required field to display if it's empty
        // TODO: Improve for multiple fields with this attr

        if (kind == 'many2many') {
            elem2 = openobject.dom.get(elem.name + '_set') || elem;
            value = value == '[]' ? '' : value;
        }

        if (kind == 'many2one' || kind == 'reference') {
            elem2 = openobject.dom.get(elem.id + '_text') || elem;
        }

        if (!value) {
            jQuery(elem2).addClass('errorfield');
            err_msg = jQuery(elem).attr('required_error_msg');
            result = false;
        } else if (kind == 'float' && jQuery(elem).attr('en_thousand_sep') && value.indexOf(',') !== -1) {
            if (result) {
                err_msg = _('Comma character "," not accepted in this field');
            }
            jQuery(elem2).addClass('errorfield');
            result = false;
        } else
            if (jQuery(elem2).hasClass('errorfield')) {
                jQuery(elem2).removeClass('errorfield');
            }
    }

    email_error = false;
    jQuery('#view_form').find('input[kind=email], input[kind=msf_email]').each(function () {
        if (!this.checkValidity()) {
            jQuery(this).addClass('errorfield');
            if (!email_error) {
                email_error = _('Invalid Email address.')
                if (err_msg) {
                    err_msg = err_msg + '\n' + email_error;
                } else {
                    err_msg = email_error;
                }
            }
            result = false;
        } else if (jQuery(this).attr('kind') == 'msf_email' && this.value && !this.value.endsWith('msf.org')) {
            jQuery(this).addClass('errorfield');
            msg_error = _('Email address must end with msf.org.')
            if (err_msg) {
                    err_msg = err_msg + '\n' + msg_error;
                } else {
                    err_msg = msg_error;
                }
            result = false;
        } else {
            jQuery(this).removeClass('errorfield');
        }
    });
    if (!result) {
        if (err_msg && err_msg != 'False') {
            error_display(err_msg);
        }
        else {
            error_display(_("Invalid form, correct red fields."));
        }
    }
    return result;
}

function validate_binary_size(form){

    if (typeof form == 'string') {
        form = jQuery('#' + form).get(0);
    }

    if (!form) {
        return true;
    }

    var elements = MochiKit.Base.filter(function(el){
        return !el.disabled && el.id && el.name && el.id.indexOf('_terp_listfields/') == -1 && hasElementClass(el, 'binary');
    }, form.elements);

    var result = true;

    for (var i = 0; i < elements.length; i++) {
        var elem = elements[i];
        var kind = jQuery(elem).attr('kind');

        if (kind == 'binary') {
            return check_attachment_size(elem);
        }
    }
    return result;
}


function error_display(msg, title='Warning Message') {
    var error = jQuery("<table>",{'width': '100%', 'height': '100%'}
                ).append(
                    jQuery("<tr>").append(
                        jQuery("<td>", {'colspan': 2, 'class': 'error_message_header'}).text(_(title))
                    ),
                    jQuery("<tr>").append(
                        jQuery("<td>", {'css': 'padding: 4px 2px;'}).append(
                            jQuery("<img>", {'src': '/openerp/static/images/warning.png'})
                        ),
                        jQuery("<td>", {'class': 'error_message_content'}).text(msg)
                    ),
                    jQuery("<tr>").append(
                        jQuery("<td>", {'colspan': 2, align: 'right'}).append(
                            jQuery("<a>", {'class': 'button-a', 'href': 'javascript: void(0)'})
                            //.click(function(){jQuery.fancybox.close();})
                            .click(function(){window.top.jQuery.fancybox.close();})
                            .text('OK')
                        )
                ));
    if (jQuery('div#fancybox-wrap').is(':visible')) {
        // chaining warning pop: IR, new line, qty:11 digits, hit return
        jQuery('div#fancybox-wrap').fadeOut(5000, function() {
            window.top.jQuery.fancybox(error, {
                scrolling: 'no',
                onComplete: function () {
                    $(this).find(".button-a").focus()
                    }
                });
            });
    } else {
        error.find('.button-a').focus()
        window.top.jQuery.fancybox(error, {
            scrolling: 'no',
            onComplete: function () {
                $(this).find(".button-a").focus()
            }
        });
    }
    return error;
}

function get_sidebar_status(args, noterp) {
    var sidebar = $('#a_main_sidebar')
    var view_type=$('#_terp_view_type')
    if (sidebar && view_type && view_type.val() == 'form') {
        if (sidebar.hasClass('closed')) {
            if (noterp) {
                args['sidebar_closed'] = 1;
            } else {
                args['_terp_sidebar_closed'] = 1;
            }
        }
    }
}

function submit_form(action, src, target, test_double){

    if (openobject.http.AJAX_COUNT > 0) {
        callLater(1, submit_form, action, src, target);
        return;
    }

    if (action == 'delete' && !confirm(_('Do you really want to delete this record?'))) {
        return;
    }

    var args = {
        _terp_source: src ? (typeof(src) == "string" ? src : src.name) : null
    };
    if (action == 'save_and_edit') {
        action = 'save';
        args['_terp_return_edit'] = 1;
    }

    if(action == 'save_and_close') {
        action = 'save';
        args['_terp_close'] = 1;
    }
    get_sidebar_status(args);
    action = get_form_action(action, args);

    var $form = jQuery('#view_form');
    if (/\/save(\?|\/)?/.test(action) && !validate_required($form[0])) {
        return;
    }

    // check there is no binary data exceding the maximum size
    if (/\/save(\?|\/)?/.test(action) && !validate_binary_size($form[0])) {
        return;
    }

    // Cant use $form.attr due to http://dev.jquery.com/ticket/3113 as there is a form with a field called
    // action when creating an activity

    $form[0].setAttribute('action', action);
    previous_target = $form.attr("target");
    $form.attr("target", target);
    if (!test_double) {
        $form.submit();
    } else {
        if (!$form[0].issubmitted) {
            $form[0].issubmitted = true;
            $form.submit();
        }
    }
    $form.attr("target", previous_target);
}

function pager_action(src){
    var $src = jQuery(src);
    var action = $src.attr('action');
    var relation = $src.attr('relation');
    if (relation) {
        var lv = ListView(relation);
        var sel = lv.$getSelectedItems().map(function () {
                return parseInt(this.value, 10);
            }).get()
        lv.set_previously_selected(sel);
    }
    return relation ? new ListView(relation).go(action) : submit_form(action ? action : 'find');
}

function buttonClicked(name, btype, model, id, sure, target, context, set_ids, ignore_access_error){

    // to be able to get selected lines ids
    s_ids = [];
    s_dom = [];
    if (set_ids) {
        if (set_ids.indexOf(',') > -1 ) {
            s_ids = ''
            forEach(set_ids.split(','), function(field) {
                s_ids += "'"+ field +"': [" + ListView(field).getSelectedRecords().join(',') + "],"
            })
            s_ids = '{' + s_ids + '}'
        } else if (jQuery('[id="' + set_ids + '"]').length > 0) {
            if ($('#'+set_ids+'_check_all').length) {
                // lines can be ticked
                s_ids = ListView(set_ids).getSelectedRecords();

            } else {
                // no tickbox on lines, get the filter
                s_dom = openobject.dom.get(set_ids + '/_terp_domain').value;
            }
        }
    }
    else {
        if (jQuery('[id="order_line"]').length > 0) {
            s_ids = ListView('order_line').getSelectedRecords();
        } else if (jQuery('[id="move_lines"]').length > 0){
            s_ids = ListView('move_lines').getSelectedRecords();
        } else if (model == 'shipment' && jQuery('[id="pack_family_memory_ids"]').length > 0){
            s_ids = ListView('pack_family_memory_ids').getSelectedRecords();
        } else if (['wizard.compare.rfq', 'supplier.catalogue'].includes(model) && jQuery('[id="line_ids"]').length > 0){
            s_ids = ListView('line_ids').getSelectedRecords();
        }
    }

    if (sure && !confirm(sure.replace('%(number_selected)s',s_ids.length))) {
        return;
    }

    var params = {
        '_terp_button/name': name,
        '_terp_button/btype': btype,
        '_terp_button/model': model,
        '_terp_button/id': id,
        '_terp_button/selected_ids': s_ids,
        '_terp_button/selected_domain': s_dom,
        '_terp_button/ignore_access_error': ignore_access_error,
    };

    // if works as expected can be extended to other buttons
    test_double = (name == 'import_file' && btype == 'object' && model == 'initial.stock.inventory') || ((name == 'copy_all' || name == 'uncopy_all')  && model == 'stock.incoming.processor')
    if (!context || context == "{}") {
        var act = get_form_action(btype == 'cancel' ? 'cancel' : 'save', params);
        submit_form(act, null, target, test_double);
        return;
    }

    var req = eval_domain_context_request({
        source: "",
        domain: "[]",
        context: context
    });
    req.addCallback(function(obj){
        params['_terp_button/context'] = obj.context || 0;

        var act = get_form_action(btype == 'cancel' ? 'cancel' : 'save', params);
        submit_form(act, null, target, test_double);
    });
}

/**
 * Transpose status of a clicked boolean widget (checkbox) to the associated hidden input
 * @param name the identifier of the hidden input (postfixed by `_checkbox_` on the checkbox)
 */
function onBooleanClicked(name){
    if (name.indexOf('_checkbox_') > -1) {
        name = name.slice(0, name.indexOf('_checkbox_'))
    }
    var $source = jQuery(openobject.dom.get(name + '_checkbox_'));
    var $target = jQuery(openobject.dom.get(name));
    $target.val($source.is(':checked') ? 1 : '').change();
}

/**
 * get key-pair object of the form data
 *
 * if extended is
 *    1 then give form data with type info
 *    2 then give form data with type info + required flag
 * else gives simple key-value pairs
 *
 * @param extended format to return
 * @param include_readonly whether the serialized form data should include
 * readonly fields (default: excludes disabled fields and fields with
 * readonly="True"
 */
function getFormData(extended, include_readonly, parentNode) {

    var from_evaldom_ctx = false;
    if (!parentNode) {
        var parentNode = openobject.dom.get('_terp_list') || document.forms['view_form'];
        if (extended == 1) {
            from_evaldom_ctx = true;
        }
    }

    var frm = {};

    var is_editable = jQuery('#_terp_editable').val() == 'True' || jQuery(parentNode).attr('id') == 'search_form';

    var $fields = jQuery(parentNode).find('img[kind=picture]');
    if (is_editable) {
        if (include_readonly) {
            $fields = $fields.add('input, textarea, select', parentNode);
        } else {
            // Warning: :enabled seems to not yield the same thing as
            // :not(:disabled), and prunes too much
            $fields = $fields.add('input:not([readonly="True"]):not(:disabled), textarea:not([readonly="True"]):not(:disabled), select:not([readonly="True"]):not(:disabled)', parentNode);
        }
    } else {
        $fields = $fields.add('[kind=value], [name$=/__id]');
    }

    $fields.each(function(){
        var $this = jQuery(this);
        var name = is_editable ? this.name : this.id;

        if (this.tagName.toLowerCase() != 'img' && !name) {
            return;
        }

        name = name.replace('_terp_listfields/', '');

        // don't include _terp_ fields except _terp_id
        if (/_terp_/.test(name) && !/_terp_id$/.test(name)) {
            return;
        }

        if (/_reference$/.test(this.id)) {
            return;
        }
        // work around to skip o2m values (list mode)
        var value;
        if (name.indexOf('/__id') > 0) {

            name = name.replace('/__id', '');

            if (openobject.dom.get(name + '/_terp_view_type').value == 'form') {
                frm[name + '/__id'] = openobject.dom.get(name + '/__id').value;
                return;
            }
            // skip if editable list's editors are visible
            if (openobject.dom.select("[name^=_terp_listfields/" + name + "]").length) {
                return;
            }

            value = openobject.dom.get(name + '/_terp_ids').value;
            if (extended) {
                value = serializeJSON({
                    'value': value,
                    'type': 'one2many',
                    'relation': openobject.dom.get(name + '/_terp_model').value
                });
            }

            frm[name] = value;
            return;
        }

        if (extended && name.indexOf('/__id') == -1) {
            var attrs = {};

            value = (is_editable ? this.value : $this.attr('value')) || "";
            var kind = $this.attr('kind') || "char";

            //take care of _terp_id
            if (/_terp_id$/.test(name)) {

                //  only the resource id and all O2M
                name = name.replace(/_terp_id$/, '');
                if (name && !openobject.dom.get(name + '__id')) {
                    return;
                }

                name = name + 'id';

                if (!openobject.dom.get(name) && extended != 3) {
                    return;
                }

                kind = 'integer';
                value = value == 'False' ? '' : value;
            }

            attrs['value'] = typeof(value) == "undefined" ? '' : value;

            if (kind) {
                attrs['type'] = kind;
            }

            if (extended && (kind == 'many2one' || kind == 'many2many')) {
                attrs['relation'] = $this.attr('relation');
            }

            if (extended > 1 && $this.hasClass('requiredfield')) {
                attrs['required'] = 1;
            }

            /* onchange: extended =1, save extended = 3 */
            if ((extended == 3 || !from_evaldom_ctx) && kind == 'float' && $this.attr('en_thousand_sep')) {
                attrs['en_thousand_sep'] = $this.attr('en_thousand_sep');
            }

            switch (kind) {
                case "picture":
                    name = this.id;
                    break;
                case 'reference':
                    if (!value) {
                        break;
                    }
                    attrs['value'] = "[" + value + ",'" + $this.attr('relation') + "']";
                    break;
            }
            // stringify the attr object
            frm[name] = serializeJSON(attrs);

        }
        else {
            frm[name] = this.value;
        }
    });
    return frm;
}

/*
 * get key-value pair of form params (_terp_)
 * @param name: only return values for given param
 */
function getFormParams(name){

    var parentNode = document.forms['view_form'];

    var frm = {};
    var fields = openobject.dom.select('input', parentNode);

    forEach(fields, function(e){

        if (!e.name || e.name.indexOf('_terp_listfields/') > -1 || e.name.indexOf('_terp_') == -1) {
            return
        }

        if (name && e.name != name) {
            return;
        }

        if (typeof(frm[e.name]) != "undefined") {
            frm[e.name] = MochiKit.Base.flattenArray([frm[e.name], e.value]);
        }
        else {
            frm[e.name] = e.value;
        }
    });

    return frm;
}



//
// The onChange / onChangePop is triggered by some elements when their content
// changes. It will trigger the python function defined in the "callback"
// attribute (e.g. callback="order_line_change") on the server's side
// (e.g. the function order_line_change in sale/sale_order.py)
//
// N.B. : in the HTML, the "callback" attribute actually corresponds to the
// "on_change" attribute in the XML view.
//
// Since many onChange events can be triggered at the same time and/or during 
// an AJAX request, onChange will add item to a set of element to be updated.
// Then onChangePop will be called regularly until there's no ongoing AJAX
// request.
//
// The choice of the data structure for onChangeQueue (i.e. Set()) was motivated
// to :
// - guarantee uniqueness of elements in the queue (e.g. avoid updating the same
// object hundreds of time in a row !)
// - at the time of writing this, there does not seem to be any constrain on
// the queue being ordered/unordered
//

var onChangeQueue = new Set();

function onChange(caller){

    // Do not register multiple pending onChange call for the same object...
    if (onChangeQueue.has(caller))
    {
        return;
    }

    // Register a pending call
    onChangeQueue.add(caller);

    // Apply the call when possible
    onChangePop(caller);

}

function onChangePop(caller){


    // *************** WARNING ***********************
    // TestField:  this method is monkey patched in TF
    // ***********************************************


    if (openobject.http.AJAX_COUNT > 0) {
        // Delay the call
        callLater(1, onChangePop, caller);
        return;
    }
    
    onChangeQueue.delete(caller);
    
    var $caller = jQuery(openobject.dom.get(caller));
    var $form = $caller.closest('form');

    var callback = $caller.attr('callback');
    var change_default = $caller.attr('change_default');

    if (!(callback || change_default) || $caller[0].__lock_onchange) {
        return;
    }

    var is_list = $caller.attr('id').indexOf('_terp_listfields') == 0;
    var prefix = $caller.attr('name') || $caller.attr('id');
    prefix = prefix.slice(0, prefix.lastIndexOf('/') + 1);

    var id_slice_offset = is_list ? 17 : 0;
    var id_prefix = prefix.slice(id_slice_offset);
    var select = function (id) { return $form.find(idSelector(id_prefix + id)); };

    var post_url = callback ? '/openerp/form/on_change' : '/openerp/form/change_default_get';

    // From http://bazaar.launchpad.net/~openerp-dev/openobject-client-web/6.0-opw-4079-cpa/revision/4726
    // Running onChange on a one2many with a lines being currently edited
    // triggers some issue. To fix that, simply save/remove the line before
    // continuing 
    if (($('tr.editors').length) && (!$caller.closest('tr.editors').length)) 
    {
        var terp_id = select('_terp_id').val();
        if (terp_id && terp_id != 'False') {
            var edit_line_id = $('tr.editors').attr('record');
            if(edit_line_id != "-1"){
                o2m_id = $('tr.editors').closest('.gridview').attr('id');
                new One2Many(o2m_id).save(edit_line_id);
            }
            $('tr.editors').remove();
        }
    }



    var form_data = getFormData(1, true, $form);
    /* testing if the record is an empty record, if it does not contain anything except
     * an id, the on_change method is not called
     */
    var nbr_elems = 0;
    var elem_id;
    for(var key in form_data) {
    	nbr_elems++;
    	if (nbr_elems > 1)
    		break;
    	elem_id = key;
    }
    if(nbr_elems == 1 && /\/__id$/.test(elem_id)) {
    	return;
    }

    openobject.http.postJSON(post_url, jQuery.extend({}, form_data, {
        _terp_callback: callback,
        _terp_caller: $caller.attr('id').slice(id_slice_offset),
        _terp_value: $caller.val(),
        _terp_model: select('_terp_model').val(),
        _terp_context: select('_terp_context').val(),
        id: select('_terp_id').val()
    })).addCallback(function(obj){
        if (obj.error) {
            return error_popup(obj)
        }

        var values = obj['value'];
        var domains = obj['domain'];

        domains = domains ? domains : {};
        var fld;
        for (var domain in domains) {
            fld = openobject.dom.get(prefix + domain);
            if (fld) {
                jQuery(fld).attr('domain', domains[domain]);
            }
        }
        var flag;
        var value;
        for (var k in values) {
            flag = false;
            var $fld = jQuery(idSelector(prefix + k));
            if(!$fld.length)
                continue;
            fld = $fld[0];
            value = values[k];
            value = value === false || value === null ? '' : value;

            // prevent recursive onchange
            fld.__lock_onchange = true;

            if (openobject.dom.get(prefix + k + '_id')) {
                fld = openobject.dom.get(prefix + k + '_id');
                flag = true;
            }

            if ((fld.value !== value) || flag) {
                fld.value = value;
                var $current_field = jQuery(fld);
                var kind = $current_field.attr('kind')
                var type2 = $current_field.attr('type2')

                //o2m and m2m
                if ($current_field.hasClass('gridview') && !kind){
                    if (jQuery('#_terp_id').val()=='False') {//default o2m
                        var $o2m_current = jQuery(fld);
                        var k_o2m = k;
                        var $default_o2m = jQuery(idSelector('_terp_default_o2m/'+k));

                        if ($default_o2m.length && !value) {
                            if($default_o2m.val()) {
                                $default_o2m.val('');
                                new ListView(prefix + k).reload();
                            } else {
                                continue;
                            }
                        } else if (value) {
                            jQuery.ajax({
                                // This request should not be asynchronous in order to keep onChange precedence
                                // If asynchronous is needed, the onChange function design should be reviewed
                                async : false,
                                type: 'POST',
                                url: '/openerp/listgrid/get_o2m_defaults',
                                dataType : 'json',
                                data: {
                                    o2m_values: serializeJSON(value),
                                    model: jQuery('#_terp_model').val(),
                                    o2m_model: jQuery(idSelector(prefix+k+'/_terp_model')).val(),
                                    name: k,
                                    view_type: jQuery('#_terp_view_type').val(),
                                    view_id: jQuery('#_terp_view_id').val(),
                                    o2m_view_type: jQuery(idSelector(prefix+k+'/_terp_view_type')).val(),
                                    o2m_view_id: jQuery(idSelector(prefix+k+'/_terp_view_id')).val(),
                                    editable: jQuery(idSelector(prefix+k+'/_terp_editable')).val(),
                                    limit: jQuery(idSelector(prefix+k+'/_terp_limit')).val(),
                                    offset: jQuery(idSelector(prefix+k+'/_terp_offset')).val(),
                                    o2m_context: jQuery(idSelector(prefix+k+'/_terp_context')).val(),
                                    o2m_domain: jQuery(idSelector(prefix+k+'/_terp_domain')).val()
                                },
                                success: function(obj) {
                                    $o2m_current.closest('.list-a').replaceWith(obj.view);
                                    if ($default_o2m.length) {
                                        $default_o2m.val(obj.formated_o2m_values);
                                    } else {
                                        jQuery(idSelector(k_o2m)).parents('td.o2m_cell').append(
                                            jQuery('<input>', {
                                                id: '_terp_default_o2m/'+k_o2m,
                                                type: 'hidden',
                                                name:'_terp_default_o2m/'+k_o2m,
                                                value: obj.formated_o2m_values
                                            })
                                        );
                                    }
                                    $o2m_current.attr('__lock_onchange', false);
                                }
                            });
                        }
                    } else if(value){
                        new ListView(prefix + k).reload();
                    }
                }
                switch (kind) {
                    case 'full_text':
                        $('#' + prefix + k).text(value || '');
                        break;
                    case 'picture':
                        fld.src = value;
                        break;
                    case 'many2many':
                    	var fld_val = '[]';
                        if(value){
                        	fld_val = '['+ value.join(',') + ']';
                        }
                        if (!jQuery(fld).attr('name')) {
                            // guess we are in editable tree view
                            jQuery(idSelector(prefix + k)).val(fld_val);
                            break;
                        }
                        //fld.value = fld_val;
                        var fld_name = jQuery(fld).attr('name');
                        var old_m2m = jQuery(idSelector(fld_name)).closest('.list-a');
                        $(idSelector(fld_name+'/_terp_id')).val('');
                        $(idSelector(fld_name+'/_terp_ids')).val(fld_val);
                        jQuery.ajax({
                            url: '/openerp/listgrid/get_m2m',
                            context: old_m2m,
                            data: {
                                'name': fld_name,
                                'model': jQuery('#_terp_model').val(),
                                'view_id': jQuery('#_terp_view_id').val(),
                                'view_type': jQuery('#_terp_view_type').val(),
                                'm2m_model': jQuery(idSelector(prefix+k+'/_terp_model')).val(),
                                'm2m_view_id': jQuery(idSelector(prefix+k+'/_terp_view_id')).val(),
                                'm2m_view_type': jQuery(idSelector(prefix+k+'/_terp_view_type')).val(),
                                'm2m_context': jQuery(idSelector(prefix+k+'/_terp_context')).val(),
                                'ids': fld_val,
                                'disabled': jQuery(fld).attr('disabled'),
                            },
                            dataType: 'json',
                            error: loadingError(),
                            success: function(obj){
                                $(this).replaceWith(obj.m2m_view);
                            }
                        });
                        break;
                    case 'many2one':
                        if (value.length > 2 || typeof(value[0])=='object') {
                            // bug: quick switch from list to form view on product, should be fixed in 6.1 :)
                            fld.__lock_onchange = false;
                            return;
                        }
                        fld.value = value[0] || '';
                        try {
                            openobject.dom.get(prefix + k + '_text').value = value[1] || '';
                            fld._m2o.change_icon();
                        }
                        catch (e) {
                        }
                        break;
                    case 'boolean':
                        obj1 = openobject.dom.get(prefix + k + '_checkbox_')
                        if (obj1) {
                            obj1.checked = value || 0;
                        } else {
                            openobject.dom.get(prefix + k).value = value || 0;
                        }
                        break;
                    case 'null_boolean':
                        if (value === 'X') {
                            fld.outerHTML = '<input type="checkbox" kind="' + kind + '" class="checkbox" id="' + fld.getAttribute('id') + '" disabled="disabled" value="1" checked="checked">';
                        } else if (value === '?') {
                            fld.outerHTML = '<span class="text_null_boolean" kind="' + kind + '" name="' + fld.getAttribute('name') + '" id="' + fld.getAttribute('id') + '" value="?">?</span>';
                        } else {
                            fld.outerHTML = '<input type="checkbox" kind="' + kind + '" class="checkbox" id="' + fld.getAttribute('id') + '" disabled="disabled" value="0">';
                        }
                        break;
                    case 'text_html':
                        $('#' + prefix + k).val(value || '');
                        break;
                    case 'selection':
                        // quick fix: better to check if typeof(value[0])=='object' instead of name of field
                        // we need to make distinction between:
                        //   1/ list of selection sent by server (i.e: product nomen in search view) 
                        //   2/ or a value of a m2o widget  selection (reason type in picking)
                        if (type2 == 'many2one' && typeof(value)=='object' && k == 'reason_type_id') {
                            fld.value = value[0];
                        }
                        else if (typeof(value)=='object') {
                            var opts = [OPTION({'value': ''})];
                            for (var opt = 0; opt < value.length; opt++) {
                                if (value[opt].length > 1 && value[opt][2]=='selected') {
                                    opts.push(OPTION({'value': value[opt][0], 'selected': 'selected'}, value[opt][1]));
                                } else if (value[opt].length > 0) {
                                    opts.push(OPTION({'value': value[opt][0]}, value[opt][1]));
                                } 
                            }
                            MochiKit.DOM.replaceChildNodes(fld, opts);
                            if (jQuery.browser.msie && $fld.attr('callback')) {
                                jQuery(fld).live("change", function(){
                                    onChange(this);
                                });
                            }
                        }
                        else {
                            fld.value = value;
                        }
                        break;
                    case 'progress':
                        var progress = values['progress'].toString() + '%';
                        jQuery('.progress-bar').text(progress).append(jQuery('<div>', {
                            'width': progress
                        }));
                        break;
                    case 'reference':
                        if (value) {
                            ref = openobject.dom.get(prefix + k + '_reference');
                            if (typeof(value)=='object') {
                                var opts = [OPTION({'value': ''})];
                                for (var opt in value['options']) {
                                    opts.push(OPTION({'value': value['options'][opt][0]}, value['options'][opt][1]));
                                }
                                MochiKit.DOM.replaceChildNodes(ref, opts);
                                value = value['selection'];
                            }
                            v = value.split(',');
                            ref.value = v[0];
                            fld._m2o.on_reference_changed();
                            if (v[1] == '0') {
                                v[1] = '';
                            }
                            fld.value = v[1] || '';
                            if (v[1]) {
                                fld._m2o.on_change();
                            }
                            try {
                                openobject.dom.get(prefix + k + '_text').value = v[2] || '';
                            } catch(e) {
                            }
                        }
                        break;
                    case 'char':

                        fld.value = value;
                        fld.setAttribute("value",value);

                        // In 'Edit' mode, this is a <select> 
                        if (fld.nodeName == "SELECT")
                        {
                            $(fld).val(value)
                        }
                        // In 'Read' mode, this is a <span>
                        else
                        {

                            if ((obj['display_strings']) 
                            &&  (obj['display_strings'][k]) 
                            &&  (obj['display_strings'][k][value]))
                            {
                                fld.innerHTML = obj['display_strings'][k][value];
                            }
                            else
                            {
                                fld.innerHTML = value;
                            }
                        }
                        break;
                    default:
                    // do nothing on default
                }
                $fld.trigger('change');
                MochiKit.Signal.signal(window.document, 'onfieldchange', fld);

                var fld_ro = jQuery(idSelector(prefix + k + '_ro'));
                    if (fld_ro) {
                        if (fld.nodeName == 'SELECT') {
                            fld_ro.html($fld.children("option:selected").html());
                        } else {
                            fld_ro.html($fld.val());
                        }
                    }
            }

            fld.__lock_onchange = false;

        }

        if (obj.warning && obj.warning.message) {
            error_display(obj.warning.message);
        }
    });
}

/**
 * This function will be used by many2one field to get display name.
 *
 * @param name name/instance of the widget
 * @param relation the OpenERP model
 */
function getName(name, relation){
    var value_field = openobject.dom.get(name);
    var text_field = openobject.dom.get(value_field.name + '_text');

    relation = relation ? relation : jQuery(value_field).attr('relation');

    if (value_field.value == '') {
        text_field.value = ''
    }

    if (value_field.value) {
        var req = openobject.http.getJSON('/openerp/search/get_name', {
            model: relation,
            id: value_field.value
        });
        req.addCallback(function(obj){
            text_field.value = obj.name;
        });
    }
}

function eval_domain_context_request(options){

    if ((!options.domain || options.domain == '[]') && (!options.context || options.context == '{}')) {
        return new MochiKit.Async.succeed(-1);
    }

    var prefix = options.source.split("/");
    prefix.pop();

    // editable listview fields
    if (prefix[0] == '_terp_listfields') {
        prefix.shift();
    }
    var params = jQuery.extend(getFormData(1, true), {
        '_terp_domain': options.domain,
        '_terp_context': options.context,
        '_terp_prefix': prefix.join('/'),
        '_terp_active_id': openobject.dom.get(prefix.concat('_terp_id').join('/')).value,
        '_terp_active_ids': openobject.dom.get(prefix.concat('_terp_ids').join('/')).value,
        '_terp_search_domain': '[]'
    });
    if (options.from_search_mode) {
        params['_terp_search_mode'] = 'true';
    }

    if (options.group_by_ctx && options.group_by_ctx.length > 0)
        params['_terp_group_by'] = options.group_by_ctx;
    else
        params['_terp_group_by'] = '[]';

    if (options.active_id) {
        params['_terp_active_id'] = options.active_id;
        params['_terp_active_ids'] = options.active_ids;
        params['_terp_previous_active_id'] = openobject.dom.get(prefix.concat('_terp_id').join('/')).value;
    }

    var parent_context = openobject.dom.get(prefix.concat('_terp_context').join('/'));
    var search_domain = openobject.dom.get(prefix.concat('_terp_search_domain').join('/'));
    if (search_domain) {
        params['_terp_search_domain'] = search_domain.value;
    }
    if (parent_context) {
        params['_terp_parent_context'] = parent_context.value;
    }

    var req = openobject.http.postJSON('/openerp/search/eval_domain_and_context', params);
    return req.addCallback(function(obj){

        if (obj.error_field) {

            var fld = openobject.dom.get(obj.error_field) || openobject.dom.get('_terp_listfields/' + obj.error_field);

            if (fld && jQuery(fld).attr('kind') == 'many2one') {
                fld = openobject.dom.get(fld.id + '_text');
            }

            if (fld) {
                fld.focus();
                fld.select();
            }
        }

        if (obj.error) {
            // 'TinyForm' error case : obj.error is a string
            if (obj.error_field) {
                // Retrieve the label associated to the label and display the
                // error
                var error_field_label = $('label[for="'+obj.error_field+'"]').text().trim()
                return error_display(error_field_label+" : "+obj.error);
            }
            // General exception case (no obj.error_field given)
            // obj.error is a full HTML page (and error_popup will display it)
            else {
                return error_popup(obj); 
            }
        }

        return obj;
    });
}

var KIND_M2O = 1;
var KIND_M2M = 2;
function open_search_window(relation, domain, context, source, kind, text){
    if (kind == KIND_M2M && source.indexOf('_terp_listfields/') == 0) {
        text = "";
    }

    eval_domain_context_request({
        'source': source,
        'domain': domain,
        'context': context
    }).addCallback(function(obj){
        var options = {
            'model': relation,
            'domain': obj.domain,
            'context': obj.context,
            'source': source,
            'kind': kind,
            'text': text
        };
        switch(kind) {
            case KIND_M2O:
                jQuery.m2o(options);
                break;
            case KIND_M2M:
                jQuery.m2m(options);
                break;
        }
    });
}

function makeContextMenu(id, kind, relation, val, hide_default_menu){
    var act = get_form_action('get_context_menu');

    var prefix = id.indexOf('/') > -1 ? id.slice(0, id.lastIndexOf('/')) : '';
    if ((prefix.split('/')[0]) == '_terp_listfields') {
        prefix = (prefix.split('/')[1]);
    }

    var model = prefix ? openobject.dom.get(prefix + '/_terp_model').value : openobject.dom.get('_terp_model').value;

    openobject.http.postJSON(act, {
        'model': model,
        'field': id,
        'kind': kind,
        'relation': relation,
        'value': val,
        'hide_default_menu': hide_default_menu
    }).addCallback(function(obj){
        var $tbody = jQuery('<tbody>');
        jQuery.each(obj.defaults, function (_, default_) {

            jQuery('<tr>').append(jQuery('<td>').append(
                jQuery('<span>').click(function () {
                    hideContextMenu();
                    return eval(default_.action);
                }).text(default_.text))).appendTo($tbody);
        });
        if (obj.actions.length) {
            $tbody.append('<hr>');
            jQuery.each(obj.actions, function (_, action) {
                jQuery('<tr>').append(jQuery('<td>').append(
                    jQuery('<span>', {'field': action.field || '', 'relation': action.relation || ''})
                        .attr('class', action.action ? '' : 'disabled')
                        .click(function () {
                            if(action.action) {
                                hideContextMenu();
                                return eval(action.action);
                            }
                        }).text(action.text))).appendTo($tbody);
            });
        }
        if (obj.relates.length) {
            $tbody.append('<hr>');

            jQuery.each(obj.relates, function (_, relate) {
                jQuery('<tr>').append(jQuery('<td>').append(
                    jQuery('<span>',
                        {
                            'class': relate.action ? '' : 'disabled',
                            'domain': relate.domain,
                            'context': relate.domain,
                            'field': relate.field || '',
                            'relation': relate.relation || ''
                        }).click(function () {
                            if(relate.action) {
                                hideContextMenu();
                                return eval(relate.action);
                            }
                        }).text(relate.text))).appendTo($tbody);
            });
        }
        var $menu = jQuery('#contextmenu');
        $menu.empty().append(
            jQuery('<table cellpadding="0" cellspacing="0">').append($tbody));

        var menu_width = $menu.width();
        var body_width = jQuery(document.body).width();
        if (parseInt($menu.css("left")) + menu_width > body_width) {
            $menu.css({left: body_width - menu_width - 10 + 'px'});
        }
        showContextMenu();
    });
}

function makeListContextMenu(rec_id, init_value){
        sd = $('#sidebar');

        var $menu = jQuery('#contextmenu');
        $menu.attr('rec_id', rec_id);
        $menu.attr('init_value', init_value);
        $menu.empty().append(
            jQuery('<table cellpadding="0" cellspacing="0">').append(sd.html()));

        var menu_width = $menu.width();
        var body_width = jQuery(document.body).width();
        if (parseInt($menu.css("left")) + menu_width > body_width) {
            $menu.css({left: body_width - menu_width - 10 + 'px'});
        }
        showContextMenu();
}

function showContextMenu(){
    var $menu = jQuery('#contextmenu');
    var $ifrm = jQuery('#contextmenu_frm');

    $menu.show();
    if ($ifrm.length) {
        $ifrm.offset($menu.offset())
             .css({
                  width: $menu.offsetWidth(),
                  height: $menu.offsetHeight(),
                  zIndex: 6
              }).show();
    }
}

function hideContextMenu(){
    jQuery('#contextmenu, #contextmenu_frm').hide();
    ctx = jQuery('#contextmenu')
    if (ctx.attr('init_value') == 'false') {
        new ListView('_terp_list').onBooleanClicked(true, ctx.attr('rec_id'), true);
        jQuery('#_terp_list\\/'+ctx.attr('rec_id'))[0].checked = false;
    }
}

function set_to_default(field_id, model){
    openobject.http.postJSON(get_form_action('get_default_value'), {
        'model': model,
        'field': field_id
    }).addCallback(function(obj){
        if (!obj.value) {
            obj.value = null;
        }
        jQuery('[id="' + field_id + '"]')
                .val(obj.value);
        // jQuery().change doesn't trigger Mochikit's handler?
        f = $('#'+field_id)
        if (f && f.attr('kind') == 'many2one') {
            ManyToOne(field_id).on_change();
        } else {
            signal(field_id, "onchange");
        }
    });
}

function set_as_default(field, model){
    openobject.http.postJSON(
        '/openerp/fieldpref/get',
        jQuery.extend({}, getFormData(1, false), {
            _terp_model: model,
            _terp_field: field
    })).addCallback(function(obj){
        if (!obj.text) { return; }
        jQuery.frame_dialog({src:openobject.http.getURL('/openerp/fieldpref', {
                '_terp_model': model,
                '_terp_field/name': field,
                '_terp_field/string': obj.text,
                '_terp_field/value': openobject.dom.get(field).value,
                '_terp_deps': obj.deps
            })
        });
    });
}

function reset_default(field, model){
    jQuery.frame_dialog({src:openobject.http.getURL('/openerp/fieldpref/reset_default', {
                '_terp_model': model,
                '_terp_field': field,
            })
        });
}

function do_report(id, relation){

    id = openobject.dom.get(id).value;

    var act = get_form_action('report');
    var params = {
        '_terp_model': relation,
        '_terp_id': id
    };

    window.open(openobject.http.getURL(act, params));
}

function do_action(src, context_menu) {
    var params = {};
    var $src = jQuery(src);
    var field = $src.attr('field') || '_terp_id';
    var source = jQuery('[id="'+field+'"]').attr('id');

    if (openobject.dom.get('_terp_list')) {
        params['_terp_selection'] = '[' +
            new ListView('_terp_list').getSelectedRecords().join(',') +
            ']';
        if (eval(params['_terp_selection']).length == 0) {
            var ids = eval(jQuery('#_terp_ids').val());
            if (ids && ids.length > 0){
                params['_terp_selection'] = '[' + ids[0] + ']';
            } else if ($src.attr('empty_ids')!="1") {
                return error_display(_('You must select one or several records !'));
            }
        }
        var id = eval(params['_terp_selection'])[0]
    } else {
        var id = jQuery('[id="'+field+'"]').val();
        if (id == 'False') {
        	error_display(_("You must save this record to perform the action !"));
            return;
        }
    }

    var action_id = $src.attr('action_id') || null;
    var relation = $src.attr('relation');
    var datas = $src.attr('data') || null;

    var domain = $src.attr('domain');
    var context = $src.attr('context');
    var context_menu = context_menu ? true: null;

    eval_domain_context_request({
        'active_id': id,
        'active_ids': params['_terp_selection'],
        'source': source,
        'domain': domain,
        'context': context
    }).addCallback(function(obj) {
        openLink(openobject.http.getURL(
            get_form_action('action'),
            jQuery.extend(params, {
                '_terp_action': action_id,
                '_terp_domain': obj.domain,
                '_terp_context': obj.context,
                '_terp_id': id,
                '_terp_model': relation,
                'datas': datas,
                'context_menu': context_menu
            })
        ));

    });
}

function translate_fields(src, params){
    var $src = jQuery(src);
    jQuery.frame_dialog({src:openobject.http.getURL('/openerp/translator',{
        _terp_model: (src ? $src.attr('relation') : params['relation']),
        _terp_id: (src ? $src.attr('id') : params['id']),
        _terp_context: (src ? $src.attr('data') : params['data']),
        _terp_clicked_field: (src ? $src.attr('clicked_field') : params['clicked_field'])
    })}, null, {
        height: 400
    });
}

/**
 * Adapts targets for functions which may be bound using both jQuery and
 * MochiKit event handlers
 *
 * @param evt the library's event
 */
function targetDammit(evt) {
    if(typeof(evt.target) == 'function') {
        // mochikit
        return evt.target();
    }
    return evt.target;
}
/**
 * Adapts mouse position on page for functions which may be bound using both
 * jQuery and MochiKit event handlers
 *
 * @param evt the library's events
 */
function mousePositionDammit(evt) {
    if(evt.mouse) {
        // mochikit
        return evt.mouse().page;
    }
    return {
        x: evt.pageX,
        y: evt.pageY
    }
}
/**
 * Forces event to stop whether it was generated using jQuery or Mochikit
 *
 * @param evt the event
 */
function stopEventDammit(evt) {
    if(evt.stop) {
        evt.stop();
        return;
    }
    evt.stopPropagation();
    evt.preventDefault();
}
function on_context_menu(evt, target){
    var $target = jQuery(target || targetDammit(evt));

    var kind = $target.attr('kind');
    sidebar = false;
    if (!(kind && $target.is(':input, :enabled'))) {
        if (!$target.parents('#_terp_list').length) {
            return;
        }
        grid = $target.parents('.grid-row')
        if (!grid.length || !grid.attr('record')) {
            return;
        }
        tick_box = grid.find('#_terp_list\\/'+grid.attr('record'))
        if (!tick_box.length || tick_box.disabled) {
            return;
        }
        sidebar = true;
        checked = true;
        if (!tick_box[0].checked) {
            new ListView('_terp_list').onBooleanClicked(false, grid.attr('record'), true)
            tick_box[0].checked=true;
            checked = false;
        }
    }
    var $menu = jQuery('#contextmenu').show();

    if (!$menu.length) {
        $menu = jQuery('<div id="contextmenu" class="contextmenu">')
                .css({position: 'absolute'})
                .hover(showContextMenu, hideContextMenu)
                .appendTo(document.body).show();

        if (jQuery(document.documentElement).hasClass('ie')) {
            jQuery('<iframe id="contextmenu_frm" src="#" frameborder="0" scrolling="no">')
                    .css({position: 'absolute'})
                    .hide().appendTo(document.body);
        }
    }

    var src = $target.attr('id');
    if (kind == 'many2one' || kind == 'reference') {
        src = src.slice(0, -5);
    }
    var $src = jQuery('[id="' + src + '"]');

    var click_position = mousePositionDammit(evt);
    $menu.offset({top: 0, left: 0});
    $menu.offset({top: click_position.y - 5, left: click_position.x - 5});
    $menu.hide();

    if (sidebar) {
        makeListContextMenu(grid.attr('record'), checked);
    } else {
        makeContextMenu(src, kind, $src.attr('relation'), $src.val(), $src.attr('hide_default_menu')||$src.is(':disabled'));
    }
    stopEventDammit(evt);
}

function open_url(site){
    var web_site;

    if (jQuery(document.documentElement).hasClass('ie') && site.indexOf('@') > -1) {
        site = site.split('@');
        site = site[1]
    }

    if (site.indexOf("://") == -1) {
        web_site = 'http://' + site;
    } else {
        web_site = site;
    }

    if (site.length) {
        window.open(web_site);
    }
}

function submenu_action(action_id, model){
    openLink(openobject.http.getURL("/openerp/form/action_submenu", {
        _terp_action_id: action_id,
        _terp_model: model,
        _terp_id: openobject.dom.get('_terp_id').value
    }));
}

/**
 * @event click
 *
 * Requests the deletion of an attachment based on data provided by the trigger's parent's @data-id
 */
function removeAttachment() {
    var $attachment_line = jQuery(this).parent();
    if(!confirm(_('Do you really want to delete the attachment')+' {' +
                jQuery.trim($attachment_line.find('> a.attachment').text()) +
            '} ?')) {
        return false;
    }
    jQuery.ajax({
        url: '/openerp/attachment/remove/',
        type: 'POST',
        data: {
            'id': $attachment_line.attr('data-id')
        },
        dataType: 'json',
        success: function(obj) {
            if(obj.error) {
                error_display(obj.error);
            }
            $attachment_line.remove();
        }
    });

    return false;
}

function check_attachment_size(obj) {
    var $datas = jQuery(obj);
    var $max_size = $datas.attr('max-size');
    if (typeof $max_size !== "undefined" && obj.files && obj.files[0]) {
        var $file_size = obj.files[0].size;
        if ($file_size > $max_size) {
            var $mb_size = $file_size/1024/1024;
            $mb_size = parseFloat($mb_size).toFixed( 2 );
            var $mb_max_size = $max_size/1024/1024;
            $mb_max_size = parseFloat($mb_max_size).toFixed( 2 );
            var msg = _('You cannot upload files bigger than %(max_size)sMB, current size is %(size)sMB');
            msg = msg.replace('%(size)s', $mb_size);
            msg = msg.replace('%(max_size)s', $mb_max_size);
            return error_display(msg);
        };
    };
    return true;
}


/**
 * @event form submission
 *
 * Used by the sidebar to create a new attachment.
 *
 * Creates a new line in #attachments if the creation succeeds.
 */
function createAttachment(){

    // Check attachment size is not bigger than max attachment size
    // refuse it if bigger.
    if (check_attachment_size(this.children.datas) !== true) {
        return false
    }

    var $form = jQuery(this);
    if(!jQuery(idSelector('_terp_id')).val() || jQuery(idSelector('_terp_id')).val() == 'False') {
        return error_display(_('No record selected ! You can only attach to existing record.'));
    }
    if(!$form.find(':file, :text')
             .filter(function () {return jQuery(this).val();})
             .length) {
        return false;
    }
    $form.ajaxSubmit({
        dataType: 'json',
        data: {'requested_with': 'XMLHttpRequest'},
        type: 'POST',
        success: function(data) {
            if ('error' in data) {
                // display error message from server
                return error_display(data['error']);
            }
            var $attachment_line = jQuery('<li>', {
                'id': 'attachment_item_' + data['id'],
                'data-id': data['id']
            });

            jQuery([
                jQuery('<a>', {
                    'target': '_blank',
                    'href': data.url || openobject.http.getURL(
                            '/openerp/attachment/get', {
                        'record': data['id']}),
                    'class': 'attachment'
                }).text(data['name']),
                jQuery('<span>|</span>'),
                jQuery("<a href='#' class='close'>Close</a>")
            ]).appendTo($attachment_line);

            jQuery('#attachments').append($attachment_line);
            $form.resetForm();
            $form.hide();
            var submit_callback =  $form.data('submit_callback');
            if (typeof submit_callback !== "undefined") {
                submit_callback($attachment_line);
            }
        }
    });
    return false;
}

function setupAttachments(){
    jQuery('#attachments').delegate('li a.close', 'click', removeAttachment);

    var $attachmentsForm = jQuery('#attachment-box').hide();
    jQuery('#add-attachment').click(function(e){
        $attachmentsForm.show();
        e.preventDefault();
    });
    $attachmentsForm.bind({
        change: createAttachment,
        // leave that one just in case, but should generally not activate
        submit: createAttachment
    });
}

function error_popup(obj){
    try {
        var error_window = window.open("", "error", "status=1, scrollbars=yes, width=550, height=400");
        error_window.document.write(obj.error);
        error_window.document.title += _("OpenERP - Error");
        error_window.document.close();
    }
    catch (e) {
        error_display(e)
    }
}

// Setup by the view, the id of the current object
var RESOURCE_ID;
/**
 * Create a shortcut bar item for the provided menu ID
 */
function add_shortcut_to_bar(id){
    jQuery.getJSON('/openerp/shortcuts/by_resource', function(data){
        if (data[id]) {
            var $shortcuts = jQuery('#shortcuts');
            var $shortcuts_list = $shortcuts.children('ul');
            $shortcuts_list.append(jQuery('<li>', {
                'class': $shortcuts_list.children().length ? '' : 'first'
            }).append(jQuery('<a>', {
                'id': 'shortcut_' + id,
                'href': openobject.http.getURL('/openerp/tree/open', {
                    'id': id,
                    'model': 'ir.ui.menu'
                })
            }).append(jQuery('<span>').text(data[id]['name']))));
            $shortcuts.trigger('altered');
        }
    });
}

/**
 * Toggle the shortcut for the current resource (create or delete it depending on current status)
 */
function toggle_shortcut(){
    var adding = jQuery(this).hasClass('shortcut-add');
    jQuery.ajax({
        url: adding ? '/openerp/shortcuts/add' : '/openerp/shortcuts/delete',
        context: this,
        type: 'POST',
        data: {
            'id': RESOURCE_ID
        },
        success: function(){
            jQuery(this).toggleClass('shortcut-add shortcut-remove');
            if (adding) {
                add_shortcut_to_bar(RESOURCE_ID);
            } else {
                jQuery('#shortcut_' + RESOURCE_ID).parent().remove();
                jQuery('#shortcuts').trigger('altered');
            }
        },
        error: function(XMLHttpRequest, textStatus, errorThrown) {
            jQuery.fancybox(XMLHttpRequest.responseText, {scrolling: 'no'});
        }
    });
}


// This function is triggered when a change occurs in a form. If some info
// changed, it will set a flag 'is_form_changed' to true, such that later,
// if user attempts to leave the page with unsaved changes, it will warn/ask
// the user about them. (c.f. validate_action)
function validateForm(){
    jQuery('#view_form table tr td:first').find('input:not([type=hidden]), select').change(function(e, automatic){

        // Ignore some items
        // (e.g. paging filters like the 'Show/hide cancel' selector for 
        // order lines)
        var eClassList = e.currentTarget.classList;
        if (eClassList.contains("ignore_changes_when_leaving_page")
        ||  eClassList.contains("readonlyfield"))
        {
            return;
        }
        if (!automatic) {
            jQuery('#view_form').data('is_form_changed', true);
        }
    });
}

function validate_action() {
    var $form = jQuery('#view_form');
    if ($form.data('is_form_changed')
        && !confirm(_('Warning, the record has been modified,\nyour changes will be discarded.'))) {
        return false;
    }
    $form.removeData('is_form_changed');
    if (arguments.length) {
        var params = arguments[0];
        var action = arguments[1];
        action(params);
    }
    return true;
}

function fullscreen(mode) {
    // switch left panel
    $('#nav2').toggle(!mode);
    $('#main-sidebar-toggler').toggleClass('closed', mode);

    // switch right panel
    var to_remove = mode && 'open' || 'closed';
    var to_add = mode && 'closed' || 'open';
    $('#tertiary,#a_main_sidebar').addClass(to_add).removeClass(to_remove);
}
