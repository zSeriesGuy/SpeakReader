// Original source code from Evan Sonderegger  https://github.com/esonderegger/web-audio-peak-meter
//
// The MIT License (MIT)
//
// Copyright (c) 2016 Evan Sonderegger
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.
// © 2019 GitHub, Inc.
//

var audioPeakMeter = (function() {
    'use strict';
    var options = {
        borderSize: 3,
        fontSize: 9,
        backgroundColor: 'black',
        tickColor: '#ddd',
        gradient: ['red 1%', '#ff0 16%', 'lime 45%', '#080 100%'],
        dbRange: 54,
        dbTickSize: 6,
        maskTransition: '0.1s',
    };
    var tickWidth;
    var elementWidth;
    var elementHeight;
    var meterHeight;
    var meterWidth;
    var meterTop;
    var vertical = false;
    var channelCount = 1;
    var channelMasks = [];
    var channelPeaks = [];
    var channelPeakLabels = [];
    var maskSizes = [];
    var textLabels = [];
    var meterStream = '';
    var meterSessionID;
    var meterElement;

    var setOptions = function(userOptions) {
        for (var k in userOptions) {
            if (userOptions.hasOwnProperty(k)) {
                options[k] = userOptions[k];
            }
        }
        tickWidth = options.fontSize * 2.0;
        meterTop = options.fontSize * 1.5 + options.borderSize - 2;
    };

    var createContainerDiv = function(parent) {
        var meterElement = document.createElement('div');
        meterElement.style.position = 'relative';
        meterElement.style.width = elementWidth + 'px';
        meterElement.style.height = elementHeight + 'px';
        meterElement.style.backgroundColor = options.backgroundColor;
        parent.appendChild(meterElement);
        return meterElement;
    };

    var createMeter = function(container, optionsOverrides) {
        var domElement = document.getElementById(container);
        setOptions(optionsOverrides);
        elementWidth = domElement.clientWidth;
        elementHeight = domElement.clientHeight;
        meterElement = createContainerDiv(domElement);
        if (elementWidth > elementHeight) {
            vertical = false;
        }
        meterHeight = elementHeight - meterTop - options.borderSize;
        meterWidth = elementWidth - tickWidth - options.borderSize;
        createTicks(meterElement);
        createRainbow(meterElement, meterWidth, meterHeight, meterTop, tickWidth);
        var channelWidth = meterWidth / channelCount;
        if (!vertical) {
            channelWidth = meterHeight / channelCount;
        }
        var channelLeft = tickWidth;
        if (!vertical) {
            channelLeft = meterTop;
        }
        for (var i = 0; i < channelCount; i++) {
            createChannelMask(meterElement, options.borderSize, meterTop, channelLeft, false);
            channelMasks[i] = createChannelMask(meterElement, channelWidth,
                                                meterTop, channelLeft,
                                                options.maskTransition);
            channelPeaks[i] = -90;
            channelPeakLabels[i] = createPeakLabel(meterElement, channelWidth, channelLeft);
            channelLeft += channelWidth;
            maskSizes[i] = 0;
            textLabels[i] = ' ';
        }
        paintMeter();
        return meterElement;
    };

    var createTicks = function(parent) {
        var numTicks = Math.floor(options.dbRange / options.dbTickSize);
        var dbTickLabel = 0;
        if (vertical) {
            var dbTickTop = options.fontSize + options.borderSize;
            for (var i = 0; i < numTicks; i++) {
                var dbTick = document.createElement('div');
                parent.appendChild(dbTick);
                dbTick.style.width = tickWidth + 'px';
                dbTick.style.textAlign = 'right';
                dbTick.style.color = options.tickColor;
                dbTick.style.fontSize = options.fontSize + 'px';
                dbTick.style.position = 'absolute';
                dbTick.style.top = dbTickTop + 'px';
                dbTick.textContent = dbTickLabel + '';
                dbTickLabel -= options.dbTickSize;
                dbTickTop += meterHeight / numTicks;
            }
        } else {
            tickWidth = meterWidth / numTicks;
            var dbTickRight = options.fontSize * 2;
            for (var i = 0; i < numTicks; i++) {
                var dbTick = document.createElement('div');
                parent.appendChild(dbTick);
                dbTick.style.width = tickWidth + 'px';
                dbTick.style.textAlign = 'right';
                dbTick.style.color = options.tickColor;
                dbTick.style.fontSize = options.fontSize + 'px';
                dbTick.style.position = 'absolute';
                dbTick.style.right = dbTickRight + 'px';
                dbTick.style.borderBottom = '1px solid white';
                dbTick.textContent = dbTickLabel + '';
                dbTickLabel -= options.dbTickSize;
                dbTickRight += tickWidth;
            }
        }
    };

    var createRainbow = function(parent, width, height, top, left) {
        var rainbow = document.createElement('div');
        parent.appendChild(rainbow);
        rainbow.style.width = width + 'px';
        rainbow.style.height = height + 'px';
        rainbow.style.position = 'absolute';
        rainbow.style.top = top + 'px';
        if (vertical) {
            rainbow.style.left = left + 'px';
            var gradientStyle = 'linear-gradient(to bottom, ' +
            options.gradient.join(', ') + ')';
        } else {
            rainbow.style.left = options.borderSize + 'px';
            var gradientStyle = 'linear-gradient(to left, ' +
            options.gradient.join(', ') + ')';
        }
        rainbow.style.backgroundImage = gradientStyle;
        return rainbow;
    };

    var createPeakLabel = function(parent, width, left) {
        var label = document.createElement('div');
        parent.appendChild(label);
        label.style.textAlign = 'center';
        label.style.color = options.tickColor;
        label.style.fontSize = options.fontSize + 'px';
        label.style.position = 'absolute';
        label.textContent = ' ';
        if (vertical) {
            label.style.width = width + 'px';
            label.style.top = options.borderSize + 'px';
            label.style.left = left + 'px';
        } else {
            label.style.width = options.fontSize * 2 + 'px';
            label.style.right = options.borderSize + 'px';
            label.style.top = (width * 0.25) + left + 'px';
        }
        return label;
    };

    var createChannelMask = function(parent, width, top, left, transition) {
        var channelMask = document.createElement('div');
        parent.appendChild(channelMask);
        channelMask.style.position = 'absolute';
        if (vertical) {
            channelMask.style.width = width + 'px';
            channelMask.style.height = meterHeight + 'px';
            channelMask.style.top = top + 'px';
            channelMask.style.left = left + 'px';
        } else {
            channelMask.style.width = meterWidth + 'px';
            channelMask.style.height = width + 'px';
            channelMask.style.top = left + 'px';
            channelMask.style.right = options.fontSize * 2 + 'px';
        }
        channelMask.style.backgroundColor = options.backgroundColor;
        if (transition) {
            if (vertical) {
                channelMask.style.transition = 'height ' + options.maskTransition;
            } else {
                channelMask.style.transition = 'width ' + options.maskTransition;
            }
        }
        return channelMask;
    };

    var maskSize = function(dbVal) {
        var meterDimension = vertical ? meterHeight : meterWidth;
        if (dbVal === 0) {
            return meterDimension;
        } else {
            var d = options.dbRange * -1;
            var returnVal = Math.floor(dbVal * meterDimension / d);
            if (returnVal > meterDimension) {
                return meterDimension;
            } else {
                return returnVal;
            }
        }
    };


    var startMeterStream = function() {
        if ( meterStream !== "" ) {
            return;
        }
        // Create Sound Meter Stream.
        meterStream = new EventSource('/addListener?type=meter');
        meterStream.onmessage = function (e) {
            var data = JSON.parse(e.data);

            switch (data.event) {
                case 'ping':
                    break;

                case 'open':
                    meterSessionID = data.sessionID;
                    break;

                case 'close':
                    meterStream.close();
                    meterStream = "";
                    for (var i = 0; i < channelCount; i++) {
                        maskSizes[i] = 0;
                        textLabels[i] = ' ';
                    }
                    break;

                case 'meterrecord':
                    var i;
                    var channelData = [];
                    var channelMaxes = [];
                    for (i = 0; i < channelCount; i++) {
                        maskSizes[i] = maskSize(data.record.db_rms, meterHeight);
                        textLabels[i] = data.record.db_peak;
                        channelData[i] = data.record.db_rms;
                        channelMaxes[i] = -90;
                        if (data.record.db_rms > channelMaxes[i]) {
                            channelMaxes[i] = data.record.db_rms;
                        }
                        if (channelMaxes[i] > channelPeaks[i]) {
                            channelPeaks[i] = channelMaxes[i];
                        }
                    }
                    break;
            };
        };
    };

    var stopMeterStream = function() {
        if ( meterStream !== "" && meterStream.readyState === 1 ) {
            navigator.sendBeacon("removeListener", JSON.stringify({"type": "meter", "sessionID": meterSessionID}));
        }
    };

    var paintMeter = function() {
        for (var i = 0; i < channelCount; i++) {
            if (vertical) {
                channelMasks[i].style.height = maskSizes[i] + 'px';
            } else {
                channelMasks[i].style.width = maskSizes[i] + 'px';
            }
            channelPeakLabels[i].textContent = textLabels[i];
        }
        window.requestAnimationFrame(paintMeter);
    };

    return {
        createMeter: createMeter,
        startMeterStream: startMeterStream,
        stopMeterStream: stopMeterStream,
    };
})();
