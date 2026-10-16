#!/usr/bin/env python3
import csv,json,math,os
os.environ.setdefault("MPLCONFIGDIR","/workspace/prefill-profile-cache/matplotlib")
os.environ.setdefault("XDG_CACHE_HOME","/workspace/prefill-profile-cache")
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
H=Path(__file__).resolve().parent;E=H/'evidence';RAW=Path('/workspace/prefill-cpu-raw');A=[5000,10000,20000,50000]
rows=json.loads((E/'run-ledger.json').read_text());lookup={r['id']:r for r in rows};timing={a:{r['name']:r for r in json.loads((E/str(a)/'timing.json').read_text())} for a in A};samples={a:json.loads((E/str(a)/'sample-summary.json').read_text()) for a in A}
lines=['# NoBalance CPU Profiling','', '基线 `a5aa51ab19c251c9220872d4b74f30bbcae25889`；native `d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b`。本模块只增加诊断、报告和独立构建插桩，无优化。', '', '## 方法与边界','', 'EP64/E128/top-k8、single-switch、trace RNG seed20261016 weighted sampling prefixes（payload-byte seed沿用20261015，见 fixed-runtime-config.json）、H64/I128/bf16/3 matrices；只测 NoBalance A=5K/10K/20K/50K，T=A/8。每档固定顺序 baseline → perf → timed，各一次。原执行器和 native 库 `-O3 -DNDEBUG`；计时版 `-O3 -DNDEBUG -g` 加 scope 头文件和计时库。helper 的 `-O2` 不代表执行器设置。完整 flags、CMakeCache、链接命令和 ELF/build-id 在 evidence/build-*。原版有符号表但没有 DWARF debug 信息；调用栈通过 DWARF unwinding/.eh_frame 和符号表解析，内联函数可能归属调用者。', '', '`perf 6.12.107` 软件 `cpu-clock:u`、99 Hz、DWARF8192。硬件 cycles 不支持；未改变安全设置。Top20 为真实采样叶帧数量占总有效栈样本比例；perf 自身 period-weighted 结果另存 perf-symbols.txt，两者不可冒充硬件周期。火焰图宽度是 inclusive 栈样本数，不得相加。unknown 栈明确保留。', '', '高频定点计时用 CLOCK_MONOTONIC_RAW；粗阶段还测 CLOCK_THREAD_CPUTIME_ID。inclusive/exclusive wall 中 exclusive 仅扣除已插桩子 scope，不能解释为纯函数自身 CPU。粗阶段 CPU exclusive 只扣除已测 CPU 的粗阶段。RSS 为阶段退出时进程历史高水位，并非该阶段独有峰值；阶段内部不能由高水位差推算分配量。进程级 RSS/user/sys 使用 wait4；perf 包括 recorder 与其子进程的 CPU，ru_maxrss 是被等待进程及后代的最大单进程高水位，不是 RSS 求和。另存0.5秒采样的进程树RSS。wall 为0.5秒 guard轮询精度。计时和重编译扰动一起测量；仅一次固定顺序配对，无置信区间或可推广的精确 overhead。', '', '## 整进程资源与扰动','', '|A|variant|wall s|user s|sys s|peak RSS MiB|RSS Δ MiB|wall vs baseline|CPU vs baseline|','|---:|---|---:|---:|---:|---:|---:|---:|---:|']
resources=[]
for a in A:
 b=lookup[f'{a}-baseline']['stages']['ns3'];bcpu=b['user_cpu_seconds']+b['system_cpu_seconds']
 for v in ['baseline','perf','timed']:
  r=lookup[f'{a}-{v}']['stages']['ns3'];cpu=r['user_cpu_seconds']+r['system_cpu_seconds'];lines.append(f"|{a}|{v}|{r['wall_seconds']:.3f}|{r['user_cpu_seconds']:.3f}|{r['system_cpu_seconds']:.3f}|{r['peak_rss_kib']/1024:.1f}|{(r['peak_rss_kib']-b['peak_rss_kib'])/1024:+.2f}|{100*(r['wall_seconds']/b['wall_seconds']-1):+.2f}%|{100*(cpu/bcpu-1):+.2f}%|");resources.append(dict(A=a,variant=v,**{k:r[k] for k in ['wall_seconds','user_cpu_seconds','system_cpu_seconds','peak_rss_kib']}))
(E/'resources.json').write_text(json.dumps(resources,indent=2)+'\n')
lines+=['','## 内部粗阶段（计时版）','','阶段为嵌套观测，main 包含其他阶段；Topology 包含 CreateJetty；SimulatorRun 包含 SubmitWqe 等。下表只展示 inclusive，不做跨层求和。main 不含动态加载和退出后 profiler 写 CSV。','','|A|phase|wall s|thread CPU s|RSS high-water MiB|','|---:|---|---:|---:|---:|']
phases=['app.main','app.Read','app.WriteArtifacts','app.Topology','phase.SimulatorRun','app.WritePayloads','phase.cleanup']
for a in A:
 for p in phases:
  r=timing[a][p];lines.append(f"|{a}|{p}|{r['inclusive_seconds']:.6f}|{r['cpu_inclusive_seconds']:.6f}|{r['rss_highwater_kib']/1024:.1f}|")
lines+=['','## 关键函数测量','','|A|scope|calls|inclusive wall s|exclusive wall s|inclusive µs/call|','|---:|---|---:|---:|---:|---:|']
funcs=['UbFunction::CreateJetty','UbJetty::Init','Jetty.AckWindow.ResizeReset','UbJettyManager::RegisterJetty','UbJettyManager::GetJetty','UbJettyManager::IsJettyExists','UbFunction::SubmitWqe','UbJettyManager::ResolveWqeLifecycleLocalId','UbJettyManager::RegisterWqe']
for a in A:
 for p in funcs:
  r=timing[a][p];lines.append(f"|{a}|{p}|{r['calls']}|{r['inclusive_seconds']:.6f}|{r['exclusive_seconds']:.6f}|{(format(1e6*r['inclusive_seconds']/r['calls'], '.3f') if r['calls'] else 'n/a')}|")
lines+=['','ACK ResizeReset 仅含显式 Resize/Reset；CreateJetty inclusive 还含 CreateObject 默认成员分配、Init 和注册。不能把二者相加，也不能将 CreateJetty 减 Init 自动认定全部是 ACK 分配。CreateJetty 两个互不调用的重载合并计数。','','## 真实 CPU 样本与调用栈','']
for a in A:
 s=samples[a];lines += [f"### A={a}",'',f"有效栈样本 {s['samples']}；unknown leaf {s['unknown_leaf']}；平均深度 {s['mean_depth']:.2f}。[完整 Top20](evidence/{a}/top20.csv) · [调用栈火焰图](evidence/{a}/flame.svg) · [原始 perf 报告](evidence/{a}/perf-report.txt)",'','|rank|self symbol|samples|self %|','|---:|---|---:|---:|']
 for i,r in enumerate(s['top20'],1):lines.append(f"|{i}|`{r['symbol']}`|{r['samples']}|{r['percent']:.3f}|")
lines+=['','## 随规模增长','','|scope|5K→50K time ratio|empirical exponent log(ratio)/log(10)|','|---|---:|---:|']
for p in ['app.main','app.Topology','phase.SimulatorRun']+funcs:
 if not timing[5000][p]['calls']:lines.append(f'|{p}|n/a (zero calls)|n/a|');continue
 ratio=timing[50000][p]['inclusive_seconds']/timing[5000][p]['inclusive_seconds'];lines.append(f'|{p}|{ratio:.3f}|{math.log10(ratio):.3f}|')
lines+=['','这些是本机、固定 trace 前缀、一次运行的区间经验增长，不是渐近复杂度证明。源代码扫描路径仅用于解释已经测得的 CPU 样本与时间增长。','','## 校验与证据','','12 个 case 均需 strict verifier PASS，所有规模 baseline/perf/timed 的整个 run/ 文件集合逐文件 SHA256 相同。包含原始 native 日志、应用时间线、payload、模拟事件数、WQE/TA、完成计数与 summary。精确清单见 evidence/run-ledger.json 和 parity-*.json。完整输入、输出、resource-samples、perf-script 和计时 CSV 以 archives/ 无损保存。原始 perf.data 留在本地；发布副本仅对继承环境凭据字节等长脱敏，逐字节验证解码调用栈不变，详见 evidence/publication-redactions.json。准备和验证阶段的 wall/user/sys/RSS 在各 stage/resource.json，不与 ns3 CPU 混算。','','## 后续候选（尚未实现）','','结论及候选的定量排序见 conclusions.md。任何候选都必须保留现有 WQE/TA/Jetty 生命周期、事件顺序、完整日志与 payload 校验；本次不实现候选。']
dominant=100*samples[50000]['inclusive_stack_samples'].get('ns3::UbTransaction::GetJettiesUsingTpn(unsigned int)',0)/samples[50000]['samples']
lines[2:2]=[f'50K 的主要热点是 TP→Jetty 查找路径：GetJettiesUsingTpn 子树覆盖 {dominant:.2f}% 实际 CPU 栈样本。12 个 case 完成且全输出哈希一致；完整结论和未实现候选见 [conclusions.md](conclusions.md)。', '']
(H/'README.md').write_text('\n'.join(lines)+'\n')
fig,axes=plt.subplots(1,2,figsize=(12,4.4))
for p in ['app.main','app.Topology','phase.SimulatorRun','UbJettyManager::ResolveWqeLifecycleLocalId']:
 axes[0].loglog(A,[timing[a][p]['inclusive_seconds'] for a in A],marker='o',label=p.replace('UbJettyManager::',''))
axes[0].set(xlabel='Assignments A',ylabel='Scoped inclusive wall seconds');axes[0].legend(fontsize=7);axes[0].grid(alpha=.3)
for v in ['baseline','perf','timed']:axes[1].plot(A,[lookup[f'{a}-{v}']['stages']['ns3']['wall_seconds'] for a in A],marker='o',label=v)
axes[1].set(xlabel='Assignments A',ylabel='Whole process wall seconds');axes[1].legend();axes[1].grid(alpha=.3)
fig.tight_layout();fig.savefig(E/'scaling.png',dpi=160);fig.savefig(E/'scaling.svg');plt.close(fig)
# External phases have true process CPU and process peak RSS, independently of timers.
external=[]
for a in A:
 for phase in ['generate','planner','adapter']:
  r=json.loads((RAW/f'common-{a}'/'stages'/phase/'resource.json').read_text());external.append(dict(A=a,variant='common',phase=phase,**{k:r[k] for k in ['wall_seconds','user_cpu_seconds','system_cpu_seconds','peak_rss_kib','status']}))
 for v in ['baseline','perf','timed']:
  for phase,r in lookup[f'{a}-{v}']['stages'].items():external.append(dict(A=a,variant=v,phase=phase,**{k:r[k] for k in ['wall_seconds','user_cpu_seconds','system_cpu_seconds','peak_rss_kib','status']}))
with (E/'external-phases.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(external[0]),lineterminator='\n');w.writeheader();w.writerows(external)
with (H/'README.md').open('a') as f:f.write('\n[全部外部阶段 wall/user/sys/RSS](evidence/external-phases.csv) · [增长图](evidence/scaling.svg)\n')
reg=json.loads((E/'regression-guard/resource.json').read_text())
with (H/'README.md').open('a') as f:
 f.write(f'\n## 回归与发布\n\n回归 guard：{reg["status"]}，wall {reg["wall_seconds"]:.2f}s，峰值 RSS {reg["peak_rss_kib"]/1024:.1f} MiB。原版与计时版各通过48个 Relay 场景，normal/-O 各120个 oracle案例和8个live faults；原版链还通过 Direct 26 runs 与 Planner/NoBalancing/ChunkRelay/legacy 回归。测量前后所有记录的 ELF SHA256 一致，原 native tracked source diff 为空。详见 evidence/regressions、evidence/timed-regressions 和 evidence/original-native-clean.txt。\n\n[发布脱敏审计](evidence/publication-redactions.json)记录具体 profile、等长脱敏次数及完整调用栈字节一致性。全部未脱敏原件仍在本地 /workspace/prefill-cpu-raw；发布归档以经过审计的 export 为源。\n')
