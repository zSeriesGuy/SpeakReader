// **************************************************************************************
// * This file is part of SpeakReader.
// *
// *  SpeakReader is free software: you can redistribute it and/or modify
// *  it under the terms of the GNU General Public License V3 as published by
// *  the Free Software Foundation.
// *
// *  SpeakReader is distributed in the hope that it will be useful,
// *  but WITHOUT ANY WARRANTY; without even the implied warranty of
// *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// *  GNU General Public License for more details.
// *
// *  You should have received a copy of the GNU General Public License
// *  along with SpeakReader.  If not, see <http://www.gnu.org/licenses/gpl-3.0.html>.
// **************************************************************************************

// This JS is used in both the listen.html and manage.html pages.

// Global Variables
var noSleep = new NoSleep();
var sessionID = "";
var transcriptStream = "";

// Determine where the scroll target is.
if ( $('#transcript-container').parent().prop('tagName') === 'BODY' ) {
    var scrollDoc = true;
    var scrollTarget = $('html');
} else {
    var scrollDoc = false;
    var scrollTarget = $("#transcript").parent();
}

function setFont() {
    var fontsize = getCookie("fontsize");
    $( "#transcript" ).css({"font-size": fontsize + "px"});
};

function startTranscriptStream() {

    // Enable wake lock to prevent sleep on mobile devices.
    if ( /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ) {
        document.addEventListener('click', function enableNoSleep() {
            document.removeEventListener('click', enableNoSleep, false);
            noSleep.enable();
        }, false);
    }

    // Create Transcript Stream.
    transcriptStream = new EventSource('/addListener?type=transcript');
    transcriptStream.onmessage = function (e) {
        var data = JSON.parse(e.data);

        switch (data.event) {
            case 'ping':
                return;

            case 'open':
                sessionID = data.sessionID;
                break;

            case 'close':
                transcriptStream.close();
                transcriptStream = "";
                break;

            case 'transcript':
                if ( scrollDoc ) {
                    var ch = window.innerHeight;
                } else {
                    var ch = scrollTarget.prop("clientHeight");
                }
                var atBottom = scrollTarget.prop("scrollTop") + ch >= scrollTarget.prop("scrollHeight") - 10;

                if ( data.final === "reload" ) {
                    $("#transcript").html(data.record);
                } else {
                    $("#transcript p:last-child").html(data.record);
                }

                if (data.final) {
                    $('#transcript').append('<p></p>');
                }

                if ( atBottom ) {
                    scrollTarget.scrollTop(scrollTarget.prop("scrollHeight"));
                }

                break;
        };
    };
    scrollTarget.scrollTop(scrollTarget.prop("scrollHeight"));
};

function stopTranscriptStream() {
    if ( transcriptStream !== "" && transcriptStream.readyState === 1 ) {
        noSleep.disable();
        navigator.sendBeacon("removeListener", JSON.stringify({"type": "transcript", "sessionID": sessionID}));
    }
};

scrollTarget.scrollTop(scrollTarget.prop("scrollHeight"));

$('#bottom-button').click(function() {
    scrollTarget.scrollTop(scrollTarget.prop("scrollHeight"));
    return false;
});

function showButton() {
    if ( scrollDoc ) {
        var ch = window.innerHeight;
    } else {
        var ch = scrollTarget.prop("clientHeight");
    }
    var atBottom = scrollTarget.prop("scrollTop") + ch >= scrollTarget.prop("scrollHeight") - 10;
    if ( atBottom ) {
        $('#bottom-button').hide();
    } else {
        $('#bottom-button').show();
    }
};
window.addEventListener('scroll', showButton, true);

scrollTarget.click(function() {
    var container = $("#transcript-settings");
    if (container.is(":visible")) {
        container.slideUp(1000);
    } else {
        container.slideDown(1000);
    }
});

$('#fontsize-button-down').click(function() {
    var fontsize = parseInt($("#transcript").css('font-size')) - 1;
    if (fontsize < 10) { fontsize = 10; }
    setCookie("fontsize", fontsize, 365);
    setFont();
    return false;
});

$('#fontsize-button-up').click(function() {
    var fontsize = parseInt($("#transcript").css('font-size')) + 1;
    if (fontsize > 32) { fontsize = 32; }
    setCookie("fontsize", fontsize, 365);
    setFont();
    return false;
});

var fontsize = getCookie("fontsize");
if ( fontsize === "" ) {
    fontsize = parseInt($("#transcript").css('font-size'));
    setCookie("fontsize", fontsize, 365);
}

setFont();

function setTheme() {
    var theme = getCookie("theme");
    $('.listen-content').addClass(theme);
    $('.color-theme-button.'+theme).each(function () {
        $(this).children().addClass('fa-check');
    });
}

$('.color-theme-button').click(function () {
    var theme = $(this).val()
    var themes = [];
    $('.color-theme-button').each(function () {
        $(this).children().removeClass('fa-check');
        themes.push($(this).val());
    });
    $(this).children().addClass('fa-check');
    themes.forEach(function (theme) {
        $('.listen-content').removeClass(theme);
    });
    setCookie("theme", theme, 365);
    setTheme();
    return false;
});

var theme = getCookie("theme");
if ( theme === "" ) {
    theme = 'light';
    setCookie("theme", theme, 365);
}
setTheme();
