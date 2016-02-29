#!/usr/bin/python
import Gnuplot
import sqlite3
import smtplib
import argparse

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.Utils import COMMASPACE
from time import time
from sys import exit

try:
    from config import *
except ImportError:
    print("Could not load configuration, please copy config.py.default to config.py and set configuration options.")
    exit(1)

################################################################################
# "THE BEER-WARE LICENSE" (Revision 42):                                       #
# <lennartATlacerta.be> wrote this file. As long as you retain this notice you #
# can do whatever you want with this stuff. If we meet some day, and you think #
# this stuff is worth it, you can buy me a beer in return. Lennart Coopmans    #
################################################################################

################################################################################
# CODE - DON'T TOUCH UNLESS YOU KNOW WHAT YOU'RE DOING                         #
################################################################################


def generate_mem_chart(c, group, starttime, endtime, folder):
    c.execute('SELECT time, mem_rss FROM data WHERE name = ? AND TIME BETWEEN ? AND ? ORDER BY time',
              (group, starttime, endtime,))
    rss = [[row[0], row[1] / 1024 / 1024] for row in c]
    c.execute('SELECT time, mem_cache FROM data WHERE name = ? AND TIME BETWEEN ? AND ? ORDER BY time',
              (group, starttime, endtime,))
    cache = [[row[0], row[1] / 1024 / 1024] for row in c]
    c.execute('SELECT time, mem_swap FROM data WHERE name = ? AND TIME BETWEEN ? AND ? ORDER BY time',
              (group, starttime, endtime,))
    swap = [[row[0], row[1] / 1024 / 1024] for row in c]

    for index, value in enumerate(cache):
        cache[index][1] += rss[index][1]

    for index, value in enumerate(swap):
        swap[index][1] += cache[index][1]

    g = Gnuplot.Gnuplot()
    g('set terminal pngcairo enhanced font "arial,10" size 700, 200 ')
    g('set output "%s/%s_mem.png"' % (folder, group,))
    g('set clip two ')
    g('set xdata time ')
    g('set xtics %d ' % ((rss[-1][0] - rss[0][0]) / 8,))
    g('set timefmt "%s"')
    g('set format x "%d/%m %Hh"')
    g('set xrange [ "%d" : "%d" ]' % (rss[0][0] - 1000, rss[-1][0] + 1000,))
    g('set style fill transparent solid 0.50 noborder ')
    g('set style data filledcurves y1=0')

    swap_data = Gnuplot.Data(swap)
    swap_data.set_option(using=(1, 2))
    cache_data = Gnuplot.Data(cache)
    cache_data.set_option(using=(1, 2))
    rss_data = Gnuplot.Data(rss)
    rss_data.set_option(using=(1, 2))
    g.plot(swap_data, cache_data, rss_data)


def generate_cpu_chart(c, group, starttime, endtime, folder):
    c.execute('SELECT time, cpu_usage FROM data WHERE name = ? AND TIME BETWEEN ? AND ? ORDER BY time',
              (group, starttime, endtime,))
    usage = [[row[0], row[1] / 1024 / 1024] for row in c]

    diff = []
    for i in range(0, len(usage) - 1):
        usgdiff = usage[i + 1][1] - usage[i][1]
        value = [usage[i + 1][0], usgdiff]
        diff.append(value)

    g = Gnuplot.Gnuplot()
    g('set terminal pngcairo  enhanced font "arial,10" size 700, 200 ')
    g('set output "%s/%s_cpu.png"' % (folder, group,))
    g('set clip two ')
    g('set xdata time ')
    g('set xtics %d ' % ((diff[-1][0] - diff[0][0]) / 8,))
    g('set timefmt "%s"')
    g('set format x "%d/%m %Hh"')
    g('set xrange [ "%d" : "%d" ]' % (diff[0][0] - 1000, diff[-1][0] + 1000,))
    g('set style fill  transparent solid 0.50 noborder ')
    g('set style data filledcurves y1=0 ')

    usage_data = Gnuplot.Data(diff)
    usage_data.set_option(using=(1, 2))
    g.plot(usage_data)


def send_mail(groups, recipients, baseurl):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "KuroNET LXC Monitor for %s" % (def_serverName,)
    msg['To'] = COMMASPACE.join(recipients)
    msg['From'] = def_fromAddress

    html = """\
    <body style="padding: 20px">
    <div style="background-color: #2f2f2f; width: 720px; padding: 10px; margin-left: 20px;\
     font-family: 'Helvetica Neue', Helvetica, Arial, Geneva, sans-serif;">
    <div>
    <div style="float: left"><a href="http://kevinalberts.nl">
    <img class="site-logo" src="http://junebug.kurocon.nl/ka_logo_lxcmon.png" alt="KevinAlberts.nl"/>
    </a>
    </div>
    <h2 style="color: #FAFAFA; padding: 0; margin: 0; font-size: 1.8em">KuroNET</h2>
    <h3 style="color: #FAFAFA; padding: 0; margin: 0; font-size: .8em">LXC Monitoring</h3>
    </div>
    <div style="clear: both">
    """
    for group in groups:
        html += '<div style="background-color: #FFF; padding: 10px; margin-top: 10px;">'
        html += '<h3 style="font-size: 1em; margin: .2em 0">%s</h3>' % (group,)
        html += '<h4 style="font-size: .7em; margin: .2em 0; float: left; clear: left;">Memory (MB):</h4>'
        html += """
        <ul style="float: left; list-style-type: none; margin: 0">
            <li style="font-size: .7em;  display: inline; padding-left: 5px; border-left: 10px solid #3f5f9f">RSS</li>
            <li style="font-size: .7em;  display: inline; padding-left: 5px; border-left: 10px solid #7fbf3f">Cache</li>
            <li style="font-size: .7em;  display: inline; padding-left: 5px; border-left: 10px solid #ff7f7f">Swap</li>
        </ul>
        """
        html += '<img src="%s/%s_mem.png"/>' % (baseurl, group)
        html += '<h4 style="font-size: .7em; margin: .2em 0; float: left; clear: left;">CPU Usage (per 5m):</h4>'
        html += '<img src="%s/%s_cpu.png"/>' % (baseurl, group)
        html += '</div>'
        html += "\n"

    html += "</div></div></body>"

    part = MIMEText(html, 'html')
    msg.attach(part)
    s = smtplib.SMTP(def_smtp_server_address)
    s.sendmail(def_fromAddress, recipients, msg.as_string())
    s.quit()


def clean_database(con, t):
    con.execute('DELETE FROM data WHERE time < ?', (t,))
    con.commit()
    con.execute('VACUUM')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--days', type=int, default=def_days,
                        help='Parse records from last DAYS days.')
    parser.add_argument('-n', '--noclean', action='store_true',
                        help="Don't clean up database")
    parser.add_argument('-db', '--database', default=def_sqlitedb,
                        help="SQLite database file")
    parser.add_argument('-f', '--folder', default=def_folder,
                        help="Save charts in FOLDER")
    parser.add_argument('-b', '--baseurl', default=def_baseURL,
                        help="Base URL")
    parser.add_argument('-c', '--containers', nargs='+', default=def_containers,
                        help="LXC Containers to create charts for")
    parser.add_argument('-m', '--mail', action='store_true',
                        help='Send mail with the charts')
    parser.add_argument('-r', '--recipients', nargs='+', default=def_recipients,
                        help="Mail recipients")

    args = parser.parse_args()

    endtime = int(time())
    starttime = endtime - (args.days * 24 * 60 * 60)

    con = sqlite3.connect(args.database)
    c = con.cursor()

    for group in args.containers:
        generate_mem_chart(c, group, starttime, endtime, args.folder)
        generate_cpu_chart(c, group, starttime, endtime, args.folder)

    if not args.noclean:
        clean_database(con, starttime)

    c.close()

    if args.mail:
        send_mail(args.containers, args.recipients, args.baseurl)


if __name__ == "__main__":
    main()
