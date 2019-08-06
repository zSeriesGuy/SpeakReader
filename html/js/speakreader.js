var p = {
    name: 'Unknown',
    version: 'Unknown',
    os: 'Unknown'
};
if (typeof platform !== 'undefined') {
    p.name = platform.name;
    p.version = platform.version;
    p.os = platform.os.toString();
}

if (['IE', 'Microsoft Edge', 'IE Mobile'].indexOf(p.name) > -1) {
    $('body').prepend('<div id="browser-warning"><i class="fa fa-exclamation-circle"></i>&nbsp;' +
        'SpeakReader does not support Internet Explorer or Microsoft Edge! ' +
        'Please use a different browser such as Chrome or Firefox.</div>');
    var offset = $('#browser-warning').height();
    var navbar = $('.navbar-fixed-top');
    if (navbar.length) {
        navbar.offset({top: navbar.offset().top + offset});
    }
    var container = $('.body-container');
    if (container.length) {
        container.offset({top: container.offset().top + offset});
    }
}

function initConfigCheckbox(elem, toggleElem, reverse) {
    toggleElem = (toggleElem === undefined) ? null : toggleElem;
    reverse = (reverse === undefined) ? false : reverse;
    var config = toggleElem ? $(toggleElem) : $(elem).closest('div').next();
    config.css('overflow', 'hidden');
    if ($(elem).is(":checked")) {
        config.toggle(!reverse);
    } else {
        config.toggle(reverse);
    }
    $(elem).click(function () {
        var config = toggleElem ? $(toggleElem) : $(this).closest('div').next();
        if ($(this).is(":checked")) {
            config.slideDown()
        } else {
            config.slideUp()
        }
    });
}

// Our countdown plugin takes a callback, a duration, and an optional message
$.fn.countdown = function (callback, duration, message) {
    // If no message is provided, we use an empty string
    message = message || "";
    // Get reference to container, and set initial content
    var container = $(this[0]).html(duration + message);
    // Get reference to the interval doing the countdown
    var countdown = setInterval(function () {
        // If seconds remain
        if (--duration) {
            // Update our container's message
            container.html(duration + message);
            // Otherwise
        } else {
            // Clear the countdown interval
            clearInterval(countdown);
            // And fire the callback passing our container as `this`
            callback.call(container);
        }
        // Run interval every 1000ms (1 second)
    }, 1000);
};

function setCookie(cname, cvalue, exdays) {
    var d = new Date();
    d.setTime(d.getTime() + (exdays * 24 * 60 * 60 * 1000));
    var expires = "expires=" + d.toUTCString();
    document.cookie = cname + "=" + cvalue + "; " + expires;
}

function getCookie(cname) {
    var name = cname + "=";
    var decodedCookie = decodeURIComponent(document.cookie);
    var ca = decodedCookie.split(';');
    for(var i = 0; i <ca.length; i++) {
        var c = ca[i];
        while (c.charAt(0) == ' ') {
            c = c.substring(1);
        }
        if (c.indexOf(name) == 0) {
            return c.substring(name.length, c.length);
        }
    }
    return "";
}