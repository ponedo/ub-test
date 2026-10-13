"""Export trace demand figures with Matplotlib; never infer performance."""
import argparse
import csv
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/nano-ub-phase1-mpl')
os.environ.setdefault('XDG_CACHE_HOME','/tmp/nano-ub-phase1-cache')
Path(os.environ['XDG_CACHE_HOME']).mkdir(parents=True,exist_ok=True)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read(p):
    with p.open() as f:return list(csv.DictReader(f))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-dir',required=True)
    a=p.parse_args();root=Path(a.input_dir)
    hist=read(root/'histograms.csv');jets=read(root/'jetties.csv');summary=read(root/'summary.csv')
    cases=[r['case'] for r in summary if r['case'].startswith('moe_') and r['case']!='moe_high_staggered']
    labels={'moe_low':'32 tokens / capacity 32','moe_high':'4096 tokens / capacity 4096',
            'moe_skew':'4096 tokens / hot-rank factor 2','moe_low_fixed_capacity':'32 tokens / capacity 4096'}
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                         'figure.dpi':130,'savefig.dpi':160,'svg.hashsalt':'nano-ub-phase1'})
    def save(fig,name):
        fig.savefig(root/(name+'.png'),bbox_inches='tight',metadata={'Software':'Nano-UB Phase 1 trace analysis'})
        fig.savefig(root/(name+'.pdf'),bbox_inches='tight',metadata={'CreationDate':None,'ModDate':None})
        plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(12,7),layout='constrained')
    all_sizes=sorted({int(r['payload_bytes']) for r in hist if r['case'] in cases})
    for ax,case in zip(axes.flat,cases):
        h={int(r['payload_bytes']):int(r['wr_count']) for r in hist if r['case']==case};total=sum(h.values())
        ax.bar(range(len(all_sizes)),[100*h.get(v,0)/total for v in all_sizes],color='#326c9b')
        ax.set_xticks(range(len(all_sizes)),[f'{v/1024:.2f}' for v in all_sizes])
        ax.set_ylim(0,105);ax.set_title(labels[case]);ax.set_xlabel('WR payload (KiB, includes transferred padding)')
        ax.set_ylabel('Fraction of WRs (%)');ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    fig.suptitle('MoE-derived WRITE size distribution — CPU-generated demand, not hardware traces',fontsize=13)
    save(fig,'wr_size_histograms')
    fig,axes=plt.subplots(len(cases),2,figsize=(12,11),layout='constrained')
    for i,case in enumerate(cases):
        group=[r for r in jets if r['case']==case]
        for col,field,scale,label in [(0,'wr_count',1,'WR count'),(1,'payload_bytes',1024**2,'Payload (MiB)')]:
            ax=axes[i,col];ax.bar(range(len(group)),[int(r[field])/scale for r in group],color='#326c9b' if col==0 else '#cc7937')
            ax.set_xticks(range(len(group)),[r['jetty_id'] for r in group]);ax.set_xlabel('Jetty / AIV ID (source rank 0)')
            ax.set_title(labels[case]);ax.set_ylabel(label);ax.set_ylim(bottom=0);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    fig.suptitle('Per-Jetty offered work — idle AIVs retained',fontsize=14);save(fig,'jetty_loads')
    fig,ax=plt.subplots(figsize=(10,4),layout='constrained')
    vals=[100*float(next(r for r in summary if r['case']==c)['full_wr_fraction']) for c in cases]
    bars=ax.barh([labels[c] for c in cases],vals,color='#397f69');ax.set_xlim(0,108);ax.set_xlabel('WRs with exactly six SGE pairs (%)')
    ax.bar_label(bars,labels=[f'{v:.2f}%' for v in vals],padding=4);ax.invert_yaxis()
    ax.set_title('Full aggregation depends on tokens per AIV and destination, not total tokens alone')
    save(fig,'full_aggregation')


if __name__=='__main__':main()
