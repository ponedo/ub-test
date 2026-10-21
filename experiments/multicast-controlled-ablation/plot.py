#!/usr/bin/env python3
"""Plot completed private aggregate analysis; no simulation or publication."""
import argparse
import csv
import json
import os
from pathlib import Path
import tempfile

os.environ.setdefault('MPLCONFIGDIR', tempfile.mkdtemp(prefix='ablation-mpl-'))
os.environ.setdefault('XDG_CACHE_HOME', tempfile.mkdtemp(prefix='ablation-cache-'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


def save(fig, out, name):
    fig.savefig(out / (name + '.png'), dpi=170)
    fig.savefig(out / (name + '.svg'))
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('analysis', type=Path)
    p.add_argument('--out', type=Path)
    args = p.parse_args()
    source = args.analysis.resolve()
    out = (args.out or source / 'figures').resolve()
    if not (out != source and source in out.parents):
        raise ValueError('Figure output must remain beneath private analysis directory')
    if out.exists():
        raise ValueError('Refusing to overwrite prior figures')
    result = json.loads((source / 'analysis.json').read_text())
    if result['status'] != 'PASS':
        raise ValueError('Verified analysis required')
    out.mkdir(parents=False)
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    styles = [('chunk-streaming', 'Chunk-Streaming', '#3274a1'), ('multicast-v2', 'Multicast v2', '#c45b36')]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.7))
    for ax, endpoint, title in zip(axes, ['weight', 'layer'], ['Receiver weight completion', 'Full LayerLatency']):
        for strategy, label, color in styles:
            rows = [r for r in result['timing'] if r['strategy'] == strategy]
            ax.plot([r['window'] for r in rows], [r[endpoint + '_ps'] / 1e6 for r in rows], marker='o', label=label, color=color)
        ax.set(xlabel='Jetty TA window (TP packet window fixed at 1000)', ylabel='Simulated time (µs)', title=title)
        ax.set_xticks([512, 1024, 2048])
        ax.grid(alpha=.2)
    axes[0].legend(frameon=False)
    fig.suptitle('Capacity intervention, not original Multicast v2 performance', weight='bold')
    fig.tight_layout(rect=(0, .06, 1, .93))
    fig.text(.02, .025, '512: fresh exact original baseline. 1024 / 2048: independent window interventions with original allocator.', fontsize=9)
    save(fig, out, 'window-latency')

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.7))
    for strategy, label, color in styles:
        rows = [r for r in result['timing'] if r['strategy'] == strategy]
        axes[0].plot([r['window'] for r in rows], [r['weight_relative_change_percent'] for r in rows], marker='o', label=label, color=color)
    axes[0].set(xlabel='Jetty TA window', ylabel='Weight-time change from own 512 baseline (%)', title='Within-strategy relative changes')
    axes[0].legend(frameon=False)
    axes[1].plot([r['window'] for r in result['contrasts']], [r['weight_difference_in_differences_ps'] / 1e6 for r in result['contrasts']], marker='o', color='#705297')
    axes[1].set(xlabel='Jetty TA window', ylabel='Difference-in-differences (µs)', title='Change in MC minus Chunk weight gap')
    for ax in axes:
        ax.axhline(0, color='#777777', lw=.8)
        ax.set_xticks([512, 1024, 2048])
        ax.grid(alpha=.2)
    fig.tight_layout(rect=(0, .09, 1, 1))
    fig.text(.02, .025, 'Negative values favor shorter time / MC relatively. DID is not an additive original-gap mediator share.', fontsize=9)
    save(fig, out, 'window-contrasts')

    data = read(source / 'occupancy.csv')
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.7))
    for strategy, label, color in styles:
        selected = sorted([r for r in data if r['strategy'] == strategy and r['scope'] == 'source_3' and r['phase'] == 'weight_phase'], key=lambda r: int(r['window']))
        for ax, field, scale in [(axes[0], 'mean_outstanding_tas', 1), (axes[1], 'full_window_fraction', 100)]:
            usable = [r for r in selected if r[field] != '']
            ax.plot([int(r['window']) for r in usable], [float(r[field]) * scale for r in usable], marker='o', color=color, label=label)
            ax.set_xticks([512, 1024, 2048])
            ax.set_xlabel('Jetty TA window')
            ax.grid(alpha=.2)
    axes[0].set(ylabel='Time-weighted outstanding TAs per Jetty', title='Same physical source 3, weight-phase exposure')
    axes[1].set(ylabel='Full-window fraction of observed Jetty-time (%)', title='Capacity state, not automatically blocked work')
    axes[0].legend(frameon=False)
    fig.tight_layout(rect=(0, .1, 1, 1))
    fig.text(.02, .025, 'Pair-exposure weighted; empty/completed exposure included. Sums across pairs are not elapsed wall time.', fontsize=9)
    save(fig, out, 'source3-occupancy')

    data = read(source / 'switch_cohorts.csv')
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.7))
    for ax, traffic in zip(axes, ['weight', 'ACK-response']):
        for strategy, label, color in styles:
            selected = sorted([r for r in data if r['strategy'] == strategy and int(r['port']) == 59 and r['traffic'] == traffic and int(r['metric']) == 0], key=lambda r: int(r['window']))
            ax.plot([int(r['window']) for r in selected], [float(r['mean_ps']) / 1000 for r in selected], marker='o', color=color, label=label + ' mean')
            ax.plot([int(r['window']) for r in selected], [int(r['max']) / 1000 for r in selected], marker='x', linestyle=':', color=color, label=label + ' max')
        ax.set(xlabel='Jetty TA window', ylabel='VOQ residence (ns)', title='Switch egress 59: ' + traffic)
        ax.set_xticks([512, 1024, 2048])
        ax.grid(alpha=.2)
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout(rect=(0, .1, 1, 1))
    fig.text(.02, .025, 'Full residence of packets ending in weight phase. Overlapping packet-times, not additive causal wall time.', fontsize=9)
    save(fig, out, 'switch59-residence')
    print(json.dumps({'status': 'PASS', 'figures': sorted(p.name for p in out.iterdir())}))


if __name__ == '__main__':
    main()
