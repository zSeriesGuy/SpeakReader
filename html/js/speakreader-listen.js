// Global Variables
var noSleep = new NoSleep();
var sessionID = getCookie('session_id');
var transcriptStream = "";

// Determine where the scroll target is.
if ( $('#transcript-container').parent().prop('tagName') === 'BODY' ) {
    var scrollDoc = true;
    var scrollTarget = $('html');
} else {
    var scrollDoc = false;
    var scrollTarget = $("#transcript-container");
}

function setFont() {
    var fontsize = getCookie("fontsize");
    $( ".transcript" ).css({"font-size": fontsize + "px"});
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
    transcriptStream = new EventSource('/addListener?type=transcript&sessionID=' + sessionID);
    transcriptStream.onmessage = function (e) {
        var data = JSON.parse(e.data);

        switch (data.event) {
            case 'close':
                transcriptStream.close();
                transcriptStream = "";
                break;

            case 'transcript':
                var offset = scrollDoc ? window.innerHeight - scrollTarget.prop("clientHeight") + 2 : 0;
                atBottom = scrollTarget.prop("scrollTop") + scrollTarget.prop("clientHeight") + offset >= scrollTarget.prop("scrollHeight");

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
        }
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

function showButton(e) {
    var atBottom = scrollTarget.prop("scrollTop") + scrollTarget.prop("clientHeight") >= scrollTarget.prop("scrollHeight");
    if ( atBottom ) {
        $('#bottom-button').hide();
    } else {
        $('#bottom-button').show();
        if ( !scrollDoc ) {
            var top = $('#transcript-container').prop("offsetTop") + $('#transcript-container').parent().prop("offsetTop") + 5;
            var left = $('#transcript-container').prop("offsetLeft") + $('#transcript-container').parent().prop("offsetLeft") + $('#transcript-container').prop("scrollWidth") - $('#bottom-button').prop("offsetWidth") - 5;
            $( "#bottom-button" ).css({"top": top + "px", "left": left + "px"});
            if ( e.type === "resize") {
                window.scrollTo(window.scrollX, window.scrollY - 1);
                window.scrollTo(window.scrollX, window.scrollY + 1);
            }
        }
    }
};
window.addEventListener('scroll', showButton, true);
window.addEventListener('resize', showButton, true);

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
    fontsize = parseInt($(".transcript").css('font-size'));
    setCookie("fontsize", fontsize, 365);
}

setFont();
showButton();