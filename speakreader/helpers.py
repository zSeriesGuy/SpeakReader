#  This file is part of SpeakReader.
#

import base64
import datetime
from functools import wraps
import hashlib
import imghdr
from itertools import zip_longest
import json
import math
from operator import itemgetter
import os
import re
import shlex
import sys
import time
import unicodedata
from xml.dom import minidom

import speakreader
from speakreader import logger


def checked(variable):
    if variable:
        return 'Checked'
    else:
        return ''


def radio(variable, pos):

    if variable == pos:
        return 'Checked'
    else:
        return ''


def latinToAscii(unicrap):
    """
    From couch potato
    """
    xlate = {
        0xc0: 'A', 0xc1: 'A', 0xc2: 'A', 0xc3: 'A', 0xc4: 'A', 0xc5: 'A',
        0xc6: 'Ae', 0xc7: 'C',
        0xc8: 'E', 0xc9: 'E', 0xca: 'E', 0xcb: 'E', 0x86: 'e',
        0xcc: 'I', 0xcd: 'I', 0xce: 'I', 0xcf: 'I',
        0xd0: 'Th', 0xd1: 'N',
        0xd2: 'O', 0xd3: 'O', 0xd4: 'O', 0xd5: 'O', 0xd6: 'O', 0xd8: 'O',
        0xd9: 'U', 0xda: 'U', 0xdb: 'U', 0xdc: 'U',
        0xdd: 'Y', 0xde: 'th', 0xdf: 'ss',
        0xe0: 'a', 0xe1: 'a', 0xe2: 'a', 0xe3: 'a', 0xe4: 'a', 0xe5: 'a',
        0xe6: 'ae', 0xe7: 'c',
        0xe8: 'e', 0xe9: 'e', 0xea: 'e', 0xeb: 'e', 0x0259: 'e',
        0xec: 'i', 0xed: 'i', 0xee: 'i', 0xef: 'i',
        0xf0: 'th', 0xf1: 'n',
        0xf2: 'o', 0xf3: 'o', 0xf4: 'o', 0xf5: 'o', 0xf6: 'o', 0xf8: 'o',
        0xf9: 'u', 0xfa: 'u', 0xfb: 'u', 0xfc: 'u',
        0xfd: 'y', 0xfe: 'th', 0xff: 'y',
        0xa1: '!', 0xa2: '{cent}', 0xa3: '{pound}', 0xa4: '{currency}',
        0xa5: '{yen}', 0xa6: '|', 0xa7: '{section}', 0xa8: '{umlaut}',
        0xa9: '{C}', 0xaa: '{^a}', 0xab: '&lt;&lt;', 0xac: '{not}',
        0xad: '-', 0xae: '{R}', 0xaf: '_', 0xb0: '{degrees}',
        0xb1: '{+/-}', 0xb2: '{^2}', 0xb3: '{^3}', 0xb4: "'",
        0xb5: '{micro}', 0xb6: '{paragraph}', 0xb7: '*', 0xb8: '{cedilla}',
        0xb9: '{^1}', 0xba: '{^o}', 0xbb: '&gt;&gt;',
        0xbc: '{1/4}', 0xbd: '{1/2}', 0xbe: '{3/4}', 0xbf: '?',
        0xd7: '*', 0xf7: '/'
    }

    r = ''
    if unicrap:
        for i in unicrap:
            if ord(i) in xlate:
                r += xlate[ord(i)]
            elif ord(i) >= 0x80:
                pass
            else:
                r += str(i)

    return r


def convert_milliseconds(ms):

    seconds = ms / 1000
    gmtime = time.gmtime(seconds)
    if seconds > 3600:
        minutes = time.strftime("%H:%M:%S", gmtime)
    else:
        minutes = time.strftime("%M:%S", gmtime)

    return minutes


def convert_milliseconds_to_minutes(ms):

    if str(ms).isdigit():
        seconds = float(ms) / 1000
        minutes = round(seconds / 60, 0)

        return math.trunc(minutes)

    return 0


def convert_seconds(s):

    gmtime = time.gmtime(s)
    if s > 3600:
        minutes = time.strftime("%H:%M:%S", gmtime)
    else:
        minutes = time.strftime("%M:%S", gmtime)

    return minutes


def convert_seconds_to_minutes(s):

    if str(s).isdigit():
        minutes = round(float(s) / 60, 0)

        return math.trunc(minutes)

    return 0


def today():
    today = datetime.date.today()
    yyyymmdd = datetime.date.isoformat(today)

    return yyyymmdd


def now():
    now = datetime.datetime.now()

    return now.strftime("%Y-%m-%d %H:%M:%S")


def utc_now_iso():
    utcnow = datetime.datetime.utcnow()

    return utcnow.isoformat()


def human_duration(s, sig='dhms'):

    hd = ''

    if str(s).isdigit() and s > 0:
        d = int(s / 86400)
        h = int((s % 86400) / 3600)
        m = int(((s % 86400) % 3600) / 60)
        s = int(((s % 86400) % 3600) % 60)

        hd_list = []
        if sig >= 'd' and d > 0:
            d = d + 1 if sig == 'd' and h >= 12 else d
            hd_list.append(str(d) + ' days')

        if sig >= 'dh' and h > 0:
            h = h + 1 if sig == 'dh' and m >= 30 else h
            hd_list.append(str(h) + ' hrs')

        if sig >= 'dhm' and m > 0:
            m = m + 1 if sig == 'dhm' and s >= 30 else m
            hd_list.append(str(m) + ' mins')

        if sig >= 'dhms' and s > 0:
            hd_list.append(str(s) + ' secs')

        hd = ' '.join(hd_list)
    else:
        hd = '0'

    return hd


def get_age(date):

    try:
        split_date = date.split('-')
    except:
        return False

    try:
        days_old = int(split_date[0]) * 365 + int(split_date[1]) * 30 + int(split_date[2])
    except IndexError:
        days_old = False

    return days_old


def bytes_to_mb(bytes):

    mb = int(bytes) / 1048576
    size = '%.1f MB' % mb
    return size


def mb_to_bytes(mb_str):
    result = re.search('^(\d+(?:\.\d+)?)\s?(?:mb)?', mb_str, flags=re.I)
    if result:
        return int(float(result.group(1)) * 1048576)


def piratesize(size):
    split = size.split(" ")
    factor = float(split[0])
    unit = split[1].upper()

    if unit == 'MiB':
        size = factor * 1048576
    elif unit == 'MB':
        size = factor * 1000000
    elif unit == 'GiB':
        size = factor * 1073741824
    elif unit == 'GB':
        size = factor * 1000000000
    elif unit == 'KiB':
        size = factor * 1024
    elif unit == 'KB':
        size = factor * 1000
    elif unit == "B":
        size = factor
    else:
        size = 0

    return size


def replace_all(text, dic, normalize=False):

    if not text:
        return ''

    for i, j in dic.iteritems():
        if normalize:
            try:
                if sys.platform == 'darwin':
                    j = unicodedata.normalize('NFD', j)
                else:
                    j = unicodedata.normalize('NFC', j)
            except TypeError:
                j = unicodedata.normalize('NFC', j.decode(speakreader.SYS_ENCODING, 'replace'))
        text = text.replace(i, j)
    return text


def replace_illegal_chars(string, type="file"):
    if type == "file":
        string = re.sub('[\?"*:|<>/]', '_', string)
    if type == "folder":
        string = re.sub('[:\?<>"|]', '_', string)

    return string


def cleanName(string):

    pass1 = latinToAscii(string).lower()
    out_string = re.sub('[\.\-\/\!\@\#\$\%\^\&\*\(\)\+\-\"\'\,\;\:\[\]\{\}\<\>\=\_]', '', pass1).encode('utf-8')

    return out_string


def cleanTitle(title):

    title = re.sub('[\.\-\/\_]', ' ', title).lower()

    # Strip out extra whitespace
    title = ' '.join(title.split())

    title = title.title()

    return title


def split_path(f):
    """
    Split a path into components, starting with the drive letter (if any). Given
    a path, os.path.join(*split_path(f)) should be path equal to f.
    """

    components = []
    drive, path = os.path.splitdrive(f)

    # Strip the folder from the path, iterate until nothing is left
    while True:
        path, folder = os.path.split(path)

        if folder:
            components.append(folder)
        else:
            if path:
                components.append(path)

            break

    # Append the drive (if any)
    if drive:
        components.append(drive)

    # Reverse components
    components.reverse()

    # Done
    return components


def extract_logline(s):
    # Default log format
    pattern = re.compile(r'(?P<timestamp>.*?)\s\-\s(?P<level>.*?)\s*\:\:\s(?P<thread>.*?)\s\:\s(?P<message>.*)', re.VERBOSE)
    match = pattern.match(s)
    if match:
        timestamp = match.group("timestamp")
        level = match.group("level")
        thread = match.group("thread")
        message = match.group("message")
        return (timestamp, level, thread, message)
    else:
        return None


def split_string(mystring, splitvar=','):
    mylist = []
    for each_word in mystring.split(splitvar):
        mylist.append(each_word.strip())
    return mylist


def create_https_certificates(ssl_cert, ssl_key):
    """
    Create a self-signed HTTPS certificate and store in it in
    'ssl_cert' and 'ssl_key'. Method assumes pyOpenSSL is installed.

    This code is stolen from SickBeard (http://github.com/midgetspy/Sick-Beard).
    """
    from OpenSSL import crypto
    from certgen import createKeyPair, createSelfSignedCertificate, TYPE_RSA

    serial = int(time.time())
    domains = ['DNS:' + d.strip() for d in plexpy.CONFIG.HTTPS_DOMAIN.split(',') if d]
    ips = ['IP:' + d.strip() for d in plexpy.CONFIG.HTTPS_IP.split(',') if d]
    altNames = ','.join(domains + ips)

    # Create the self-signed Tautulli certificate
    logger.debug(u"Generating self-signed SSL certificate.")
    pkey = createKeyPair(TYPE_RSA, 2048)
    cert = createSelfSignedCertificate(("Tautulli", pkey), serial, (0, 60 * 60 * 24 * 365 * 10), altNames) # ten years

    # Save the key and certificate to disk
    try:
        with open(ssl_cert, "w") as fp:
            fp.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        with open(ssl_key, "w") as fp:
            fp.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, pkey))
    except IOError as e:
        logger.error("Error creating SSL key and certificate: %s", e)
        return False

    return True


# Taken from SickRage
def anon_url(*url):
    """
    Return a URL string consisting of the Anonymous redirect URL and an arbitrary number of values appended.
    """
    return '' if None in url else '%s%s' % (speakreader.CONFIG.ANON_REDIRECT, ''.join(str(s) for s in url))


def cast_to_int(s):
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0


def cast_to_float(s):
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0


def convert_xml_to_json(xml):
    o = xmltodict.parse(xml)
    return json.dumps(o)


def convert_xml_to_dict(xml):
    o = xmltodict.parse(xml)
    return o


def get_percent(value1, value2):

    value1 = cast_to_float(value1)
    value2 = cast_to_float(value2)

    if value1 != 0 and value2 != 0:
        percent = (value1 / value2) * 100
    else:
        percent = 0

    return math.trunc(round(percent, 0))


def hex_to_int(hex):
    try:
        return int(hex, 16)
    except (ValueError, TypeError):
        return 0


def parse_xml(unparsed=None):
    if unparsed:
        try:
            xml_parse = minidom.parseString(unparsed)
            return xml_parse
        except Exception as e:
            logger.warn("Error parsing XML. %s" % e)
            return []
        except:
            logger.warn("Error parsing XML.")
            return []
    else:
        logger.warn("XML parse request made but no data received.")
        return []


def get_xml_attr(xml_key, attribute, return_bool=False, default_return=''):
    """
    Validate xml keys to make sure they exist and return their attribute value, return blank value is none found
    """
    if xml_key.getAttribute(attribute):
        if return_bool:
            return True
        else:
            return xml_key.getAttribute(attribute)
    else:
        if return_bool:
            return False
        else:
            return default_return


def process_json_kwargs(json_kwargs):
    params = {}
    if json_kwargs:
        params = json.loads(json_kwargs)

    return params


def sanitize(string):
    if string:
        return unicode(string).replace('<','&lt;').replace('>','&gt;')
    else:
        return ''


def build_datatables_json(kwargs, dt_columns, default_sort_col=None):
    """ Builds datatables json data

        dt_columns:    list of tuples [("column name", "orderable", "searchable"), ...]
    """

    columns = [{"data": c[0], "orderable": c[1], "searchable": c[2]} for c in dt_columns]

    if not default_sort_col:
        default_sort_col = dt_columns[0][0]

    order_column = [c[0] for c in dt_columns].index(kwargs.pop("order_column", default_sort_col))

    # Build json data
    json_data = {"draw": 1,
                 "columns": columns,
                 "order": [{"column": order_column,
                            "dir": kwargs.pop("order_dir", "desc")}],
                 "start": int(kwargs.pop("start", 0)),
                 "length": int(kwargs.pop("length", 25)),
                 "search": {"value": kwargs.pop("search", "")}
                 }
    return json.dumps(json_data)


def humanFileSize(bytes, si=False):
    if str(bytes).isdigit():
        bytes = int(bytes)
    else:
        return bytes

    thresh = 1000 if si else 1024
    if bytes < thresh:
        return str(bytes) + ' B'

    if si:
        units = ('kB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB')
    else:
        units = ('KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB')

    u = -1

    while bytes >= thresh and u < len(units):
        bytes /= thresh
        u += 1

    return "{0:.1f} {1}".format(bytes, units[u])


def parse_condition_logic_string(s, num_cond=0):
    """ Parse a logic string into a nested list
    Based on http://stackoverflow.com/a/23185606
    """
    valid_tokens = re.compile(r'(\(|\)|and|or)')
    conditions_pattern = re.compile(r'{\d+}')

    tokens = [x.strip() for x in re.split(valid_tokens, s.lower()) if x.strip()]

    stack = [[]]

    cond_next = True
    bool_next = False
    open_bracket_next = True
    close_bracket_next = False
    nest_and = 0
    nest_nest_and = 0

    for i, x in enumerate(tokens):
        if open_bracket_next and x == '(':
            stack[-1].append([])
            stack.append(stack[-1][-1])
            cond_next = True
            bool_next = False
            open_bracket_next = True
            close_bracket_next = False
            if nest_and:
                nest_nest_and += 1

        elif close_bracket_next and x == ')':
            stack.pop()
            if not stack:
                raise ValueError('opening bracket is missing')
            cond_next = False
            bool_next = True
            open_bracket_next = False
            close_bracket_next = True
            if nest_and > 0 and nest_nest_and > 0 and nest_and == nest_nest_and:
                stack.pop()
                nest_and -= 1
                nest_nest_and -= 1

        elif cond_next and re.match(conditions_pattern, x):
            try:
                num = int(x[1:-1])
            except:
                raise ValueError('invalid condition logic')
            if not 0 < num <= num_cond:
                raise ValueError('invalid condition number in condition logic')
            stack[-1].append(num)
            cond_next = False
            bool_next = True
            open_bracket_next = False
            close_bracket_next = True
            if nest_and > nest_nest_and:
                stack.pop()
                nest_and -= 1

        elif bool_next and x == 'and' and i < len(tokens)-1:
            stack[-1].append([])
            stack.append(stack[-1][-1])
            stack[-1].append(stack[-2].pop(-2))
            stack[-1].append(x)
            cond_next = True
            bool_next = False
            open_bracket_next = True
            close_bracket_next = False
            nest_and += 1

        elif bool_next and x == 'or' and i < len(tokens)-1:
            stack[-1].append(x)
            cond_next = True
            bool_next = False
            open_bracket_next = True
            close_bracket_next = False

        else:
            raise ValueError('invalid condition logic')

    if len(stack) > 1:
        raise ValueError('closing bracket is missing')

    return stack.pop()


def nested_list_to_string(l):
    for i, x in enumerate(l):
        if isinstance(x, list):
            l[i] = nested_list_to_string(x)
    s = '(' + ' '.join(l) + ')'
    return s


def eval_logic_groups_to_bool(logic_groups, eval_conds):
    first_cond = logic_groups[0]

    if isinstance(first_cond, list):
        result = eval_logic_groups_to_bool(first_cond, eval_conds)
    else:
        result = eval_conds[first_cond]

    for op, cond in zip(logic_groups[1::2], logic_groups[2::2]):
        if isinstance(cond, list):
            eval_cond = eval_logic_groups_to_bool(cond, eval_conds)
        else:
            eval_cond = eval_conds[cond]

        if op == 'and':
            result = result and eval_cond
        elif op == 'or':
            result = result or eval_cond

    return result


def get_plexpy_url(hostname=None):
    if plexpy.CONFIG.ENABLE_HTTPS:
        scheme = 'https'
    else:
        scheme = 'http'

    if hostname is None and plexpy.CONFIG.HTTP_HOST == '0.0.0.0':
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.connect(('<broadcast>', 0))
            hostname = s.getsockname()[0]
        except socket.error:
            try:
                hostname = socket.gethostbyname(socket.gethostname())
            except socket.gaierror:
                pass

        if not hostname:
            hostname = 'localhost'
    elif hostname == 'localhost' and plexpy.CONFIG.HTTP_HOST != '0.0.0.0':
        hostname = plexpy.CONFIG.HTTP_HOST
    else:
        hostname = hostname or plexpy.CONFIG.HTTP_HOST

    if plexpy.CONFIG.HTTP_PORT not in (80, 443):
        port = ':' + str(plexpy.CONFIG.HTTP_PORT)
    else:
        port = ''

    if plexpy.CONFIG.HTTP_ROOT.strip('/'):
        root = '/' + plexpy.CONFIG.HTTP_ROOT.strip('/')
    else:
        root = ''

    return scheme + '://' + hostname + port + root


def momentjs_to_arrow(format, duration=False):
    invalid_formats = ['Mo', 'DDDo', 'do']
    if duration:
        invalid_formats += ['A', 'a']
    for f in invalid_formats:
        format = format.replace(f, '')
    return format


def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx
    args = [iter(iterable)] * n
    return izip_longest(fillvalue=fillvalue, *args)


def traverse_map(obj, func):
    if isinstance(obj, list):
        new_obj = []
        for i in obj:
            new_obj.append(traverse_map(i, func))

    elif isinstance(obj, dict):
        new_obj = {}
        for k, v in obj.iteritems():
            new_obj[traverse_map(k, func)] = traverse_map(v, func)

    else:
        new_obj = func(obj)

    return new_obj


def split_args(args=None):
    if isinstance(args, list):
        return args
    elif isinstance(args, basestring):
        return [arg.decode(plexpy.SYS_ENCODING, 'ignore')
                for arg in shlex.split(args.encode(plexpy.SYS_ENCODING, 'ignore'))]
    return []
