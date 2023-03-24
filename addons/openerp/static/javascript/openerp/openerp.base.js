/**
 * Opens the provided URL in the application content section.
 *
 * If the application content section (#appContent) does not
 * exist, simply change the location.
 *
 * @param url the URL to GET and insert into #appContent
 * @default afterLoad callback to execute after URL has been loaded and
 *                    inserted, if any.
 */

function close_this_frame() {
    /* less intrusive than UF-2513 */
    fr = jQuery('.ui-icon-closethick')
    if (fr && fr.length) {
        fr[0].click();
    }
}

function openLink(url /*optional afterLoad */) {
    var $app = jQuery('#appContent');
    var afterLoad = arguments[1];
    if($app.length) {
        jQuery.ajax({
            url: url,
            complete: function () {
                if(afterLoad) { afterLoad(); }
            },
            success: doLoadingSuccess($app[0], url),
            error: loadingError(url),
            cache: false
        });
        return;
    }
    // Home screen
    if(jQuery('#root').length) {
        window.location.assign(
            '/?' + jQuery.param({next: url}));
        return;
    }
    window.location.assign(url);
}

/**
 * Opens the provided URL inside the application content section.
 *
 * @param url the URL to GET and insert into #appContent
 */
function openLinkFrame(url) {
    jQuery('#appContent').html(
            '<iframe src="' + url + '"></iframe>');
}

/**
 * Displays a fancybox containing the error display
 * @param xhr the received XMLHttpResponse
 */
function displayErrorOverlay(xhr) {
    var options = {
        showCloseButton: true,
        overlayOpacity: 0.7,
        scrolling: 'auto'
    };
    if(xhr.getResponseHeader('X-Maintenance-Error')) {
        options['autoDimensions'] = false;
    }
    jQuery.fancybox(xhr.responseText, options);
}

/**
 * Handles errors when loading page via XHR
 * TODO: maybe we should set this as the global error handler via jQuery.ajaxSetup
 *
 * @param {String} [url] The URL to set, if any, in case of 500 error (so users can just
 * C-R or C-F5).
 */
function loadingError(url) {
    return function (xhr) {
        if(url) { $.hash(url); }
        switch (xhr.status) {
            case 500:
                displayErrorOverlay(xhr);
                break;
            case 401: // Redirect to login, probably
                window.location.assign(
                        xhr.getResponseHeader('Location'));
                break;
            default:
                if(window.console) {
                    console.warn("Failed to load ", xhr.url, ":", xhr.status, xhr.statusText);
                }
        }
        form_hookStateChange();
        form_hookAttrChange();
    };
}

var ELEMENTS_WITH_CALLBACK = '[callback]:enabled:not([type="hidden"]):not([value][value=""]):not([readonly])';

/**
 * Performs initial triggering of all <code>onchange</code> events in form in
 * order to correctly set up initial values
 */
function initial_onchange_triggers() {
    jQuery(ELEMENTS_WITH_CALLBACK).each(function() {
        if (jQuery(this).attr('kind') == 'boolean') {
            onBooleanClicked(jQuery(this).attr('id'));
        } else {
            // We pass an arbitrary parameter to the event so we can
            // differentiate a user event from a trigger
            jQuery(this).trigger('change', [true]);
        }
    });
}
/**
 * Creates a LoadingSuccess execution for the providing app element
 * @param app the element to insert successful content in
 * @param {String} [url] the url being opened, to set as hash-url param
 */
function doLoadingSuccess(app, url) {
    return function (data, status, xhr) {
        var target;
        var active_id;
        var keep_open = false;
        if(xhr.getResponseHeader){
            target = xhr.getResponseHeader('X-Target');
            active_id = xhr.getResponseHeader('active_id');
            keep_open = xhr.getResponseHeader('keep-open');
            popup_message = xhr.getResponseHeader('popup_message');
        }
        if(target) {
            var _openAction;
            if (popup_message) {
                window.top.alert(popup_message);
            }
            if (window.top.openAction) {
                _openAction = window.top.openAction;
            } else {
                _openAction = openAction;
            }
            is_new_doc = xhr.getResponseHeader('is_new_doc');
            if (is_new_doc) {
                editRecord(is_new_doc);
            }
            _openAction(xhr.getResponseHeader('Location'), target, active_id, keep_open, xhr.getResponseHeader('height'), xhr.getResponseHeader('width'));
            return;
        }
        if(url) {
            // only set url when we're actually opening the action
            jQuery.hash(url);
        }
        jQuery(window).trigger('before-appcontent-change');
        var data = xhr.responseText || data;
        if (xhr.getResponseHeader && xhr.getResponseHeader('Content-Type').match(/text\/javascript/)) {
            try {
                var parsed = jQuery.parseJSON(data);
                if (parsed.error) {
                    return error_display(parsed.error);
                }
                if (parsed.reload) {
                    if (parsed.list_grid) {
                        new ListView(parsed.list_grid).reload();
                        var o2mlist = openobject.dom.get('_o2m_' + parsed.list_grid);
                        if (o2mlist) {
                            onChange(o2mlist);
                        }
                    } else {
                        window.location.reload();
                    }
                }
            } catch(e) {
                return error_display(_('doLoadingSuccess: Cannot parse JSON'));
            }
        } else {
            jQuery(app).html(data);
        }
        jQuery(window).trigger('after-appcontent-change');

        // Only auto-call form onchanges if we're on a new object, existing
        // objects should not get their onchange callbacks called
        // automatically on edition
        val = jQuery('#_terp_id').val();
        if (val == 'False' || val == '') {
            initial_onchange_triggers();
        }
        form_hookStateChange();
        form_hookAttrChange();
        var onload = $("[onload]")
        if (onload) {
            onload.trigger('onload');
        }
    };
}

/**
 * Manages navigation to actions
 *
 * @param action_url the URL of the action to open
 * @param target the target, if any, defaults to 'current'
 */
function openAction(action_url, target, terp_id, keep_open, height, width) {
    var $dialogs = jQuery('.action-dialog');
    switch(target) {
        case 'new':
            $frame = jQuery.frame_dialog({
                src: action_url,
                'class': 'action-dialog'
            }, null, {
                width: width?width:'90%',
                height: height?height:'95%'
            });
            $frame.focus();
            if (terp_id && !$dialogs.length) {
                if (jQuery('#_terp_id').val() == 'False') {
                    // we are opening an action on an unsaved record,
                    // we have to reload the current view with the newly given id
                    window.top.editRecord(terp_id);
                }
            }
            break;
        case 'download':
            var $form = jQuery('<form action="" target="_blank" method="POST"><input type="text" name="download" value="true"/></form>').appendTo("body");
            $form.attr("action", action_url);
            $form[0].submit();
            $form.remove();
            break;
        case 'popup':
            window.open(action_url);
            if (terp_id && !$dialogs.length) {
                // reload base model with the record specified by 'terp_id',
                // but only when we're not in a dialog - in that case the
                // 'terp_id' is related to the model from that dialog, not the
                // base model
            	window.top.editRecord(terp_id);
            }
            break;
        case 'iframe':
            openLinkFrame(action_url);
            break;
        case 'current':
        default:
            openLink(action_url);
    }
    if (!keep_open) {
        $dialogs.dialog('close');
    }
}
function closeAction() {
    jQuery('.action-dialog').dialog('close');
}

/**
 * selector for delegation to links nobody handles
 */
var UNTARGETED_LINKS_SELECTOR = 'a[href]:not([target]):not([href^="#"]):not([href^="javascript"]):not([rel=external]):not([href^="http://"]):not([href^="https://"]):not([href^="//"])';

// Prevent action links from blowing up when clicked before document.ready()
jQuery(document).delegate(UNTARGETED_LINKS_SELECTOR, 'click', function (e) {
    e.preventDefault();
});
jQuery(document).ready(function () {
    // cleanup preventer
    jQuery(document).undelegate(UNTARGETED_LINKS_SELECTOR);
    var $app = jQuery('#appContent');
    if ($app.length) {
        jQuery('body').delegate(UNTARGETED_LINKS_SELECTOR, 'click', function(event){
            if (!validate_action()) {
                event.stopImmediatePropagation();
                return false;
            }
        });

        // open un-targeted links in #appContent via xhr. Links with @target are considered
        // external links. Ignore hash-links.
        jQuery(document).delegate(UNTARGETED_LINKS_SELECTOR, 'click', function () {
            openLink(jQuery(this).attr('href'));
            return false;
        });
        // do the same for forms
        jQuery(document).delegate('form:not([target])', 'submit', function () {
            var $form = jQuery(this);
            $form.ajaxSubmit({
                data: {'requested_with': 'XMLHttpRequest'},
                success: doLoadingSuccess($app[0]),
                error: loadingError()
            });
            return false;
        });
    } else {
        if(jQuery(document).find('div#root').length) {
            jQuery(document).delegate(UNTARGETED_LINKS_SELECTOR, 'click', function() {
                jQuery.ajax({
                    url: jQuery(this).attr('href'),
                    success: doLoadingSuccess(jQuery(this).attr('href'))
                });
                return false;
            });
        }
        // For popup like o2m submit actions.
        else {
            jQuery(document).delegate('form#view_form:not([target])', 'submit', function () {
                var $form = jQuery('#view_form');
                // Make the wait box appear immediately
                $form.ajaxSubmit({
                    data: {'requested_with': 'XMLHttpRequest'},
                    success: doLoadingSuccess(jQuery('body')),
                    error: loadingError(),
                    complete: function(res, status) {
                        $form[0].issubmitted = false;
                    },
                });
                return false;
            });
        }
    }

    // wash for hash changes
    jQuery(window).bind('hashchange', function () {
        var newUrl = $.hash();
        if(!newUrl || newUrl == $.hash.currentUrl) {
            //Only autocall form onchanges when o2m open in popup.
             if (jQuery('[callback]').length){
                name = jQuery('[callback]').first().attr('id');
                var parent_prefix = name.indexOf('/') > -1 ? name.slice(0, name.lastIndexOf('/') + 1) : '';
                if (parent_prefix != ''){
                    if(jQuery(idSelector(parent_prefix + '_terp_id')).val() == 'False'){
                        initial_onchange_triggers();
                    }
                }
            }
            return;
        }
        openLink(newUrl);
    });
    // if the initially loaded URL had a hash-url inside
    jQuery(window).trigger('hashchange');
});

// Hook onclick for boolean alteration propagation
jQuery(document).delegate(
        'input.checkbox:enabled:not(.grid-record-selector)',
        'click', function () {
    if(window.onBooleanClicked) {
        onBooleanClicked(jQuery(this).attr('id').replace(/_checkbox_$/, ''));
    }
});

jQuery(document).bind('ready', function (){
    var $caller = jQuery(ELEMENTS_WITH_CALLBACK);
    $caller.each(function(){
        if (!jQuery(this).val()) {
            if (jQuery(this).attr('kind') == 'boolean') {
                onBooleanClicked(jQuery(this).attr('id'));
            }
            else {
                jQuery(this).change();
            }
        }
    });
});

// Hook onchange for all elements
jQuery(document).delegate('[callback], [onchange_default]', 'change', function () {
    if (jQuery(this).is(':input.checkbox:enabled')
            || !jQuery(this).is(':input')
            || !window.onChange) {
        return;
    }
    onChange(this);
});

/**
 * Updates existing concurrency info with the data provided
 * @param info a map of {model: {id: concurrency info}} serialized into the existing concurrency info inputs
 */
function updateConcurrencyInfo(info) {

    // we cache all the IDs because we know we are going to access them
    //  several times. If we don't use that we'll have to browse the DOM dozens
    //  of times.
    var input_by_id = {}
    var elements_by_id = jQuery("#view_form *[id][name='_terp_concurrency_info']");
    elements_by_id.each(function(id){
        var id_elem = $(this).attr("id");
        var lst = input_by_id[id_elem] || []
        lst.push($(this))
        input_by_id[id_elem] = lst;
    });

    jQuery.each(info, function (model, model_data) {
        jQuery.each(model_data, function (id, concurrency_data) {
            var formatted_key = "'" + model + ',' + id + "'";
            var formatted_concurrency_value = (
                    "(" + formatted_key + ", " +
                            "'" + concurrency_data + "'" +
                            ")"
                    );

            var id_to_look_for = model.replace(/\./g, '-') + '-' + id;

            jQuery.each(input_by_id[id_to_look_for] || [], function(a,b){
                b.val(formatted_concurrency_value);
            });
        });
    });
}

var LOADER_THROBBER;
var THROBBER_DELAY = 300;
function loader_throb() {
    var $loader = jQuery('#ajax_loading');
    if(/\.{3}$/.test($loader.text())) {
        // if we have three dots, reset to three nbsp
        $loader.html($loader.text().replace(/\.{3}$/, '&nbsp;&nbsp;&nbsp;'));
    } else {
        // otherwise replace first space with a dot
        $loader.text($loader.text().replace(/(\.*)(\s)(\s*)$/, '$1.$3'));
    }
    LOADER_THROBBER = setTimeout(loader_throb, THROBBER_DELAY);
}

function load_timeout() {
    console.log(openobject.http.getCookie('session_expired').replaceAll('"',''));
    a = Date.parse(openobject.http.getCookie('session_expired').replaceAll('"',''));
    b = Date.parse("2023-03-24T16:16:16");
    console.log("2023-03-24T16:16:16"==openobject.http.getCookie('session_expired'));
    console.log(a);
    console.log(b);
}
jQuery(document).bind({
    ready: load_timeout(),
    ajaxStart: function() {
        var $loader = jQuery('#ajax_loading');
        if(!$loader.length) {
            $loader = jQuery('<div id="ajax_loading">'
                             + _('Loading')
                             + '&nbsp;&nbsp;&nbsp;</div>'
            ).appendTo(document.body);
        }
        $loader.css({
            left: (jQuery(window).width() - $loader.outerWidth()) / 2
        }).show();
        loader_throb();
    },
    ajaxStop: function () {
        clearTimeout(LOADER_THROBBER);
        jQuery('#ajax_loading').hide();
    },
    ajaxComplete: function (e, xhr) {
        if(!xhr) return;
        var concurrencyInfo = xhr.getResponseHeader('X-Concurrency-Info');
        if(!concurrencyInfo) return;
        updateConcurrencyInfo(jQuery.parseJSON(concurrencyInfo));

    }
});

var global_list_refresh;
var unique_id ='';
