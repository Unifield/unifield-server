/*##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (c) 2010-2012 Elico Corp. All Rights Reserved.
#    Author: Yannick Gouin <yannick.gouin@elico-corp.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
*/


/* some keys cannot be overriden, for example
* "There is no way to override CTRL-N, CTRL-T, or CTRL-W in Google Chrome since
* version 4 of Chrome (shipped in 2010)."
*/

$.ctrlshift = function(key, callback, args) {
    $(document).keydown(function(e) {
        if (e.ctrlKey && e.shiftKey) {
            var class_to_parse = null
            if (key == 'S'){
                class_to_parse = '.oe_form_button_save, .oe_form_button_save_line, .oe_form_button_save_close';
            }
            else if (key == 'E'){
                class_to_parse = '.oe_form_button_save_edit, .oe_form_button_edit';
            }
            else if (key == '46'){
                class_to_parse = '.oe_form_button_delete';
            }
            else if (key == 'Z'){
                class_to_parse = '.oe_form_button_cancel';
            }
            else if (key == 'C'){
                class_to_parse = '.oe_form_button_create, .oe_form_button_save_create';
            }
            else if (key == 'D'){
                class_to_parse = '.oe_form_button_duplicate';
            }
            else if (key == '13'){
                class_to_parse = '.oe_form_button_search';
            }
            else if (key == 'R'){
                class_to_parse = '.oe_form_button_clear';
            }
            else if (key == '38'){
                class_to_parse = '.oe_button_pager[action="first"]';
            }
            else if (key == '37'){
                class_to_parse = '.oe_button_pager[action="previous"]';
            }
            else if (key == '39'){
                class_to_parse = '.oe_button_pager[action="next"]';
            }
            else if (key == '40'){
                class_to_parse = '.oe_button_pager[action="last"]';
            }
            if (class_to_parse != null){
                //$('.oe_form_button_save')
                $(class_to_parse).each(function() {

                    // do not display tooltips on hidden notebook-page
                    if ($(this).closest('.notebook-page').length && !$(this).closest('.notebook-page-active').length){
                        console.log('notebook page not active');

                    }
                    else {
                        if (key == '46'){
                            key_to_display = 'Del.'
                        }
                        else if (key == '13') {
                            key_to_display = 'Enter&nbsp;&#8629;'  // Enter
                            //key_to_display = 'Enter'  // Enter
                        }
                        else if (key == '38') {
                            key_to_display = '&#8679;'  // UP
                        }
                        else if (key == '37') {
                            key_to_display = '&#8678;'  // Left
                        }
                        else if (key == '39') {
                            key_to_display = '&#8680;'  // Right
                        }
                        else if (key == '40') {
                            key_to_display = '&#8681;'  // Down
                        }
                        else {
                            key_to_display = key
                        }
                        if ($(this).width() == 0) {
                            return false;
                        }
                        var $newdiv1 = $( "<span class='shortcut_tooltip'>" + key_to_display + "</span>" );
                        $( "body" ).append($newdiv1);
                        var postion = $(this).offset();
                        var new_top = postion.top + 20;
                        if ($(this).width() <= 20){
                            var new_left = postion.left - $newdiv1.width()/2;
                        }
                        else {
                            var new_left = postion.left + $(this).width()/2 - $newdiv1.width()/2 + 6;
                        }
                        $newdiv1.css({top: new_top, left: new_left, position:'absolute'});
                        setTimeout(function() {
                            $newdiv1.css({'opacity': '0'});
                        }, 1000);

                        setTimeout(function() {
                           $newdiv1.remove();
                        }, 2000);
                     }
                     return false;
                });
            }
        }
        if(!args) args=[]; // IE barks when args is null
        if((e.keyCode == key.charCodeAt(0) || e.keyCode == key) && e.ctrlKey && e.shiftKey) {
            e.preventDefault();  // override the browser shortcut keys
            if (!document.nb_shortcut_used){
                document.nb_shortcut_used = 1;
            }
            else{
                document.nb_shortcut_used += 1;
            }
            callback.apply(this, args);
            return false;
        }
    });
};

fake_click = function(button) {
    if($(button).parents('div:hidden').length == 0){
        if (button.hasAttribute('onclick')) {
            button.onclick();
        }
        else {
            $(button).trigger('click');
        }
    }
};

//Save the current object
$.ctrlshift('S', function() {
    var saved = false;
    $('.oe_form_button_save_line').each(function() {
        if($(this).parents('div:hidden').length == 0){
            fake_click(this);
            saved = true;  // if a line is under edition, save only this line, not the whole object
        }
    });
    $('.oe_form_button_save_close').each(function() {
        if(!saved && $(this).parents('div:hidden').length == 0){
            fake_click(this);
            saved = true;
        }
    });
    $('.oe_form_button_save').each(function() {
        if (! saved) {
            fake_click(this);
        }
    });
});

//Save & Edit the current object
$.ctrlshift('E', function() {
    $('.oe_form_button_save_edit').each(function() {
        fake_click(this);
    });
    $('.oe_form_button_edit').each(function() {
        fake_click(this);
    });
});

//Delete the current object
$.ctrlshift('46', function() {
    $('.oe_form_button_delete').each(function() {
        fake_click(this);
    });
});

//Cancel the modifiactions
$.ctrlshift('Z', function() {
    $('.oe_form_button_cancel').each(function() {
        fake_click(this);
    });
});

//New object
$.ctrlshift('C', function() {
    $('.oe_form_button_create').each(function() {
        fake_click(this);
    });
    $('.oe_form_button_save_create').each(function() {
        fake_click(this);
    });
});

//Duplicate the current object
$.ctrlshift('D', function() {
    $('.oe_form_button_duplicate').each(function() {
        fake_click(this);
    });
});

//Search (enter)
$.ctrlshift('13', function() {
    $('.oe_form_button_search').each(function() {
        fake_click(this);
    });
});

//Clear search
$.ctrlshift('R', function() {
    $('.oe_form_button_clear').each(function() {
        fake_click(this);
    });
});

//First object (arrow up)
$.ctrlshift('38', function(event) {
    $('.oe_button_pager[action="first"]').each(function() {
        fake_click(this);
        return false;
    });
});

//Previous object (arrow left)
$.ctrlshift('37', function() {
    $('.oe_button_pager[action="previous"]').each(function() {
        fake_click(this);
        return false;
    });
});

//Next object (arrow right)
$.ctrlshift('39', function() {
    $('.oe_button_pager[action="next"]').each(function() {
        fake_click(this);
        return false;
    });
});

//Last object (arrow down)
$.ctrlshift('40', function() {
    $('.oe_button_pager[action="last"]').each(function() {
        fake_click(this);
        return false;
    });
});
