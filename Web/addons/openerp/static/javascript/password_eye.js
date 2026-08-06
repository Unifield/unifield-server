function initPasswordEyeToggles(root) {
    var inputs = (root || document).querySelectorAll(
        'input[type="password"].js-password-eye:not(.js-eye-bound)'
    );

    for (var i = 0; i < inputs.length; i++) {
        let input = inputs[i];
        input.classList.add('js-eye-bound');

        input.style.boxSizing = 'border-box';
        input.style.width = '100%';
        input.style.paddingRight = '24px';

        var inputHeight = input.offsetHeight;

        var wrapper = document.createElement('span');
        wrapper.style.position = 'relative';
        wrapper.style.display = 'block';
        wrapper.style.width = '100%';
        wrapper.style.height = inputHeight + 'px';

        var nextEl = input.nextElementSibling;

        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        if (nextEl && nextEl.classList.contains('js-eye-overlay-target')) {
            nextEl.style.position = 'absolute';
            nextEl.style.top = '0';
            nextEl.style.left = '0';
            nextEl.style.width = '100%';
            nextEl.style.height = '100%';
            nextEl.style.boxSizing = 'border-box';
            wrapper.appendChild(nextEl);
        }

        var icon = document.createElement('img');
        icon.src = '/openerp/static/images/eye.png';
        icon.alt = '';
        icon.title = _('Hold to show password');
        icon.style.cssText =
            'width:12px;height:12px;position:absolute;right:8px;top:50%;transform:translateY(-50%);cursor:pointer;';
        wrapper.appendChild(icon);

        icon.addEventListener('mousedown', function () {
            input.type = 'text';
        });

        icon.addEventListener('mouseup', function () {
            input.type = 'password';
        });

        icon.addEventListener('mouseleave', function () {
            input.type = 'password';
        });
    }
}

document.addEventListener('DOMContentLoaded', function () {
    initPasswordEyeToggles();
});

if (window.jQuery) {
    jQuery(window).bind('after-appcontent-change', function () {
        initPasswordEyeToggles();
    });
}