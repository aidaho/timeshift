#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A tiny utility for mass timestamp shifting forwards or backwards in time.

Copyright (C) 2015 Sergey Frolov

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation, version 3
of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
"""
import os
import re
import sys
import argparse
import datetime
import locale

version = '0.1'
long_help = """
TimeShift - shifts timestamps in file(s) forwards or backwards in time.

usage: timeshift.py [options] file1 [file2 file3 ...]

    TimeShift deals with the task of updating all time stamps in the
file with relative offset, thus making an impression certain logged
sequence of events took place at different time interval.
    Such desire may arise when dealing with event logs, timestamped in
local time, or to cover up for bugs in importing software that messes
up conversion of local timestamps to UTC for various reasons.
    The reverse situation also happens: some software prefers to
interpret all time stamps as of they were made in local time, making
an unnecessary conversion to UTC when source is already in UTC. We
need to shift those into local time before moving forward.

    For example, you can shift the following:
    * IM logs
    * server logs
    * GPS tracks


==========================================
Establishing data source time stamp format

    To shift some particular log you should identify log timestamps
and provide correct timestamp format with -f option using info from this link:
https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior

    Say, you have an IM log at hand which look like this:

    ...
    (20:49:47) aidaho: Hey, did you know we found liquid water on Mars?
    (21:11:12) kerry: Woah! Awesome news!
    ...

    Brackets contain timestamps we need. Using link above we can describe
them as "%H:%M:%S". Another example would be a GPS track:

    ...
    <trkpt lat="48.89335" lon="37.50699">
      <ele>102</ele>
      <time>2015-08-07T11:07:42Z</time>
    </trkpt>
    ...

    Again, by referring to the link above we are able to describe time
format as "%Y-%m-%dT%H:%M:%SZ".

    IMPORTANT NOTICE: all names, and abbrevs, like for month or day of
the week, are interpreted in user current locale and therefore wouldn't
work if data source has them in some different language.
In this case you should set $LANG to appropriate locale first.


=========================
Specifying required shift

    Now that we identified and described timestamps we will be acting upon,
we need to tell TimeShift where to shift them. In order to do so, use -t
key. Argument format is:

    +/-Hours[:Minutes[:Seconds[:Milliseconds]]]

    Let's look at practical examples:
1. shift two hours into the future:
    "+2"
   you can skip remaining positions;
2. shift by one and a half hours into the past:
    "-1:30";
3. shift 20 seconds into the future:
    "+0:0:30"
   you can't skip preceding positions, nullify them instead;
4. shift four hours and 45 seconds into the past:
    "-4:0:45"


========
Examples

1. Shift IM log half an hour into the future:
timeshift.py --format="%H:%M:%S" --time-diff="+0:30" chat.log

2. Shift GPS track two hours and three minutes into the past:
timeshift.py --format="%Y-%m-%dT%H:%M:%SZ" --time-diff="-02:03" track.gpx

"""
if '--long-help' in sys.argv:
    print long_help
    sys.exit()

def time_diff(timediff):
    """
    Validates and converts timediff string.

    :returns: {'delta': datetime.timedelta(), 'timediff': basestring} dict
    """
    timediff = str(timediff)
    timediff_reo = re.compile(
        '^(?P<sign>[+-])(?P<hours>\d+)(:(?P<minutes>\d+))?(:(?P<seconds>\d+))?(:(?P<milliseconds>\d+))?$')
    match = timediff_reo.match(timediff)
    if not match:
        raise argparse.ArgumentError("Time difference should be described as '+-H[:M:S:MS]'.")

    delta = datetime.timedelta(
        hours=int(match.group('hours')),
        minutes=int(match.group('minutes')) if match.group('minutes') else 0,
        seconds=int(match.group('seconds')) if match.group('seconds') else 0,
        milliseconds=int(match.group('milliseconds')) if match.group('milliseconds') else 0,
    )
    if match.group('sign') == '-':
        delta = -delta
    return {'delta': delta, 'timediff': timediff}

## Options
parser = argparse.ArgumentParser(
    description="Shift timestamps in file(s) forwards or backwards in time",
    version=version
)
parser.add_argument('--long-help', dest='help', default=False,
                    action='store_true', help='show detailed usage info')
parser.add_argument('--overwrite', dest='overwrite', default=False,
                    help="write into source files.", action='store_true')
parser.add_argument('-f', '--format', dest='format', default="%Y-%m-%dT%H:%M:%S", type=str,
                    help="provide a timestamp format using syntax described here: "
                    "https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior",
                    metavar='TIME_FORMAT')
parser.add_argument('-t', '--time-diff', dest='timediff', type=time_diff,
                    help="shift by this time difference", metavar='+-H[:M:S:MS]')
parser.add_argument('-n', '--not-really', dest='not_really', action='store_true',
                    default=False, help="print changes instead of doing them. "
                    "Implies '--verbose'.")
parser.add_argument('--verbose', dest='verbose', action='store_true',
                    default=False, help="print processed lines.")
parser.add_argument(dest='files', type=argparse.FileType('r'), nargs='+',
                    help="input file(s)", metavar='FILE')

options = parser.parse_args()  # parse the command-line

if options.not_really:  # increase verbosity in dummy mode
    options.verbose = True

def get_regexp_for_datetime_directive(directives_regexps, directive):
    """
    Convenience regexp getter for given datetime.strptime() directive.

    :param directives_regexps: {'directive': 'expression'} dictionary
    :type directives_regexps: dict
    :param directive: datetime.strptime() directive, should begin with '%' char
    :type directive: basestring
    :rtype: basestring
    """
    assert directive[0] == '%', "Directive should begin with '%' sign!"
    assert directive in directives_regexps, "Unknown directive: '%s'" % directive
    return directives_regexps[directive]

def make_regexp_for_time_format(time_format, directives_regexps):
    """
    Constructs regexp that will match provided .strptime() time format string.

    :param directives_regexps: {'directive': 'expression'} dictionary
    :type directives_regexps: dict
    :param time_format: datetime.strptime() time format
    :type time_format: basestring
    :returns: regexp string
    """
    parts = time_format.split('%')
    regexp = parts[0]
    for part in parts[1:]:
        regexp += get_regexp_for_datetime_directive(directives_regexps, '%%%s' % part[0])
        regexp += ''.join(part[1:])
    return regexp

class ClassProperty(object):
    def __init__(self, func):
        self.func = func

    def __get__(self, inst, cls):
        return self.func(cls)


class Constants(object):
    weekdays_abbrevs = [locale.nl_langinfo(
        getattr(locale, 'ABDAY_%d' % day)) for day in range(1, 8)]
    weekdays = [locale.nl_langinfo(
        getattr(locale, 'DAY_%d' % day)) for day in range(1, 8)]
    months_abbrevs = [locale.nl_langinfo(
        getattr(locale, 'MON_%d' % day)) for day in range(1, 13)]
    months = [locale.nl_langinfo(
        getattr(locale, 'ABMON_%d' % day)) for day in range(1, 13)]
    # FIXME: How to get these from locale?
    parts_of_the_day = ('am', 'pm')

    @ClassProperty
    def simple_directives(cls):
        directives = {
            '%a': r'(%s)' % '|'.join(cls.weekdays_abbrevs),  # weekday as locale’s abbreviated name
            '%A': r'(%s)' % '|'.join(cls.weekdays),  # weekday as locale’s full name
            '%w': r'[0-6]',  # weekday as a decimal number
            '%d': r'[0-3]?[0-9]',  # day of the month
            '%e': r'\s+[1-3]?[0-9]',  # day of the month, leading zero is replaced by a space
            '%b': r'(%s)' % '|'.join(cls.months_abbrevs),  # month as locale’s abbreviated name
            '%B': r'(%s)' % '|'.join(cls.months),  # month as locale’s full name
            '%m': r'[0-1]?[0-9]',  # month as a zero-padded decimal number
            '%y': r'[0-9]{1,2}',  # year without century
            '%Y': r'[0-9]{1,4}',  # year with century
            '%H': r'[0-2]?[0-9]',  # hour (24-hour clock)
            '%I': r'[0-1]?[0-9]',  # hour (12-hour clock)
            '%p': r'(%s)' % '|'.join(cls.parts_of_the_day),  # locale’s equivalent of either AM or PM
            '%M': r'[0-5]?[0-9]',  # minute
            '%S': r'[0-5]?[0-9]',  # second
            '%f': r'\d{1,6}',  # microsecond as a decimal number
            '%z': r'[+-]\d{4}',  # UTC offset
            '%Z': r'(UTC|EST|CST)',  # time zone name
            '%j': r'[0-3]?[0-9]?[0-9]',  # day of the year
            '%U': r'[0-5]?[0-9]',  # week number (Sunday as the first day of the week)
            '%W': r'[0-5]?[0-9]',  # week number (Monday as the first day of the week)
            '%%': r'%',
        }
        return directives

    @ClassProperty
    def recursive_directives(cls):
        directives = {
            # Locale’s appropriate date and time representation
            '%c': make_regexp_for_time_format(
                locale.nl_langinfo(locale.D_T_FMT),
                directives_regexps=Constants.simple_directives
            ),
            # Locale’s appropriate date representation
            '%x': make_regexp_for_time_format(
                locale.nl_langinfo(locale.D_FMT),
                directives_regexps=Constants.simple_directives
            ),
            # Locale’s appropriate time representation
            '%X': make_regexp_for_time_format(
                locale.nl_langinfo(locale.T_FMT),
                directives_regexps=Constants.simple_directives
            ),
        }
        return directives

    @ClassProperty
    def directives(cls):
        if getattr(cls, '_directives', None):
            return cls._directives

        cls._directives = cls.simple_directives
        cls._directives.update(cls.recursive_directives)
        return cls._directives

def make_time_format_reo(time_format):
    """
    Returns compiled regexp object for matching .strptime() time format string.

    :param time_format: datetime.strptime() time format
    :type time_format: basestring
    :returns: regexp object
    """
    return re.compile(make_regexp_for_time_format(
        time_format, directives_regexps=Constants.directives), re.IGNORECASE)

def update_timestamp(timestamp_match):
    """
    Callback for re.sub(). Returns updated timestamp string.

    :param timestamp_match: regexp match object
    :rtype: basestring
    """
    time = datetime.datetime.strptime(timestamp_match.group(), options.format)
    return datetime.datetime.strftime(time + options.timediff['delta'], options.format)

time_reo = make_time_format_reo(options.format)
# Process input files:
for f in options.files:
    source_filename = f.name
    print "Processing: %s" % source_filename
    filename, extension = os.path.splitext(source_filename)
    destination_filename = "%s %s%s" % (
        filename, options.timediff['timediff'], extension)

    if not options.not_really:
        output = open(destination_filename, 'w')
    # Process input files
    for line in f.readlines():
        match = time_reo.findall(line)
        if match:
            newline = time_reo.sub(update_timestamp, line)
        else:
            newline = line
        if options.verbose:
            print newline,
        if not options.not_really:
            output.write(newline)
    f.close()
    if options.not_really:
        print "\n"  # for better readability in dry run mode
    else:
        output.close()

    # Replace original file with output if overwrite was requested:
    if not options.not_really and options.overwrite:
        os.remove(source_filename)
        os.rename(destination_filename, source_filename)
