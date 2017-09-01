#!/usr/bin/env python3

import sys
import re
import time
import argparse
import logging
import re
import plotly.offline as py
from plotly import tools
from plotly.graph_objs import Scatter, Data

class TracesGroup(object):
    def __init__(self, name, traces):
        self.name = name
        self.traces = traces

def plot(*args):
    cols = 2
    rows = len(args) // cols + (1 if len(args) % cols != 0 else 0)
    fig = tools.make_subplots(cols=cols, rows=rows, subplot_titles=[group.name for group in args])
    i = 0

    for group in args:
        for trace in group.traces:
            col = i  % cols + 1
            row = i // cols + 1
            print(col, row)
            print(trace)
            x = [i for i in range(len(trace[1]))]
            fig.append_trace(Scatter(x=x, y=trace[1], name=trace[0]), row, col)

        i += 1

    py.plot(fig, filename='out.html')


class SendTreadStatAnalyzer(object):
    def __init__(self):
        self.re = re.compile(r'^.*loop_time=([0-9]+)us, wait_time=([0-9]+)us, process_queue_time=([0-9]+)us, process_packets_time=([0-9]+)us, check_timeout_time=([0-9]+)us.*$')
        self.fields = ['loop_time', 'wait_time', 'process_queue_time', 'process_packets_time', 'check_timeout_time']
        self.traces = {key: [] for key in self.fields}

    def process_line(self, line):
        m = self.re.match(line)
        i = 1
        if m:
            for field in self.fields:
                self.traces[field].append(float(m.group(i)))
                i += 1
        return m

    def get_traces(self):
        return [TracesGroup('udp EventsThread timing', [(field, self.traces[field]) for field in self.fields])]


class UTP2AckStatAnalyzer(object):
    def __init__(self):
        # selack - ack=1257116127, processed=1, last_pr=1257116127, loss=0.00/0, rtt=231/11940us, pdelay=11us, buf=0/6468619 B, in_flight=0, seq=1257116128
        self.re = re.compile(r'^.*([0-9a-zx]+)?.*acked=([0-9]+),.*loss=[0-9\.]+\%\/([0-9]+), rtt=([0-9]+)\/([0-9]+)us, pdelay=([0-9]+)us, buf=([0-9]+)\/([0-9]+) B, in_flight=([0-9]+).*$')

        self.fields = ['processed_packets', 'loss_packets', 'min_rtt', 'avr_rtt', 'packets_delay', 'actual_sndbuf', 'max_sndbuf', 'inflight_packets']
        self.groups = {'utp packets': ['processed_packets', 'loss_packets', 'inflight_packets'], 'rtt': ['min_rtt', 'avr_rtt'], 'delay': ['packets_delay'], 'sndbuf': ['actual_sndbuf', 'max_sndbuf']}
        self.traces = {}

    def process_line(self, line):
        m = self.re.match(line)

        if m:
            sock_addr = m.group(1)
            i = 2

            if sock_addr not in self.traces:
                self.traces[sock_addr] = {key: [] for key in self.fields}

            for field in self.fields:
                self.traces[sock_addr][field].append(float(m.group(i)))
                i += 1
        return m

    def get_traces(self):
        result = []
        for sock_addr, sock_traces in self.traces.items():
            for group_name, fields in self.groups.items():
                result.append(TracesGroup('utp2 %s %s' % (sock_addr, group_name), [(field, sock_traces[field]) for field in fields]))

        return result


class PeerConnectionStatAnalyzer(object):
    def __init__(self):
        self.re = re.compile(r'^.*PC\[([x0-9a-z]+)\]\[([x0-9a-z]+)\] pending=([0-9]+) requests=([0-9]+) unwritten=([0-9]+)$')
        self.re2 = re.compile(r'^.*PC\[([x0-9a-z]+)\]\[([x0-9a-z]+)\] pending:([0-9]+) requests:([0-9]+) unwirtten:([0-9]+)$')
        self.fields = ['pending', 'requests', 'unwritten']
        self.traces = dict()

    def process_line(self, line):
        m = self.re.match(line) or self.re2.match(line)
        if m:
            pc = m.group(1)
            if pc not in self.traces:
                self.traces[pc] = {key: [] for key in self.fields}

            i = 0
            values = m.groups()[2:]
            for field in self.fields:
                self.traces[pc][field].append(values[i])
                i += 1

        return m

    def get_traces(self):
        return [TracesGroup('PeerConnection ' + pc, [(field, groups[field]) for field in self.fields]) for pc, groups in self.traces.items()]


class PeerConnectionPieceStat(object):
    def __init__(self):
        self.re = re.compile(r'^.*PC\[([x0-9a-z]+)\]\[([x0-9a-z]+)\] Got Piece:.*rtt:([0-9]+)$')
        self.fields = ['rtt']
        self.traces = dict()

    def process_line(self, line):
        m = self.re.match(line)
        if m:
            pc = m.group(1)
            if pc not in self.traces:
                self.traces[pc] = {key: [] for key in self.fields}

            i = 0
            values = m.groups()[2:]
            for field in self.fields:
                self.traces[pc][field].append(values[i])
                i += 1

        return m

    def get_traces(self):
        return [TracesGroup('PeerConnection ' + pc, [(field, groups[field]) for field in self.fields]) for pc, groups in self.traces.items()]


if __name__ == "__main__":
    lines = sys.stdin.readlines()
    analyzers = [SendTreadStatAnalyzer(), UTP2AckStatAnalyzer(), PeerConnectionStatAnalyzer(), PeerConnectionPieceStat()]

    for l in lines:
        for a in analyzers:
            a.process_line(l)

    groups = []
    for a in analyzers:
        groups += a.get_traces()

    groups = [TracesGroup(group.name, [trace for trace in group.traces if len(trace[1]) > 0]) for group in groups]

    plot(*groups)
