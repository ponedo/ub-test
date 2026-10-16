#!/usr/bin/env python3
"""Generate the diagnosis report from measured artifacts, never old-host results."""
import csv,json,math
from pathlib import Path
H=Path(__file__).resolve().parent
j=lambda p:json.loads(p.read_text())
s=j(H/'evidence/analysis/summary.json');runs=s['runs'];sizes=[5000,10000,20000,50000]
r=lambda a,v:runs[f'{a}-{v}']['resource']
t=lambda a:{x['name']:x for x in runs[f'{a}-timed']['timing']['timers']}
c=lambda a:runs[f'{a}-timed']['timing']['counters']
sp=lambda a:runs[f'{a}-sampled']['sampling']
sec=lambda row:row['inclusive_thread_cpu_ns']/1e9
ack=list(csv.DictReader((H/'evidence/analysis/ack-attribution.csv').open()))
x=sp(50000);g=x['hotspot_subtrees']['GetJettiesUsingTpn'];lc=x['hotspot_subtrees']['ResolveWqeLifecycleLocalId'];checks=j(H/'evidence/checks.json')
lines=['# dot 主机：EP64 NB prefill CPU 诊断','',
 f"## 结论\n\n50K 在本机未插桩基线耗时 **{r(50000,'baseline')['wall_seconds']:.2f}s**。真正的用户态 CPU 样本中，`GetJettiesUsingTpn` 子树占 **{g['percent']:.2f}% ({g['samples']}/{x['sample_count']})**，`ResolveWqeLifecycleLocalId` 子树占 **{lc['percent']:.2f}% ({lc['samples']}/{x['sample_count']})**。因此生命周期 ID 查找不是当前最大瓶颈；更应先检查 TP→Jetty 反查路径。这里是实际内核 CPU-clock 样本，定点计时另列，未将计时比例冒称采样比例。",'',
 '本轮只加入诊断计时、调用/扫描计数及调试符号。没有实施 Jetty 复用、packing、协议/WQE/TA/relay/network/compute/planner/cap 优化，也没有减少应用事件、原生报文日志或 payload 校验。', '',
 '## 主机、编译与固定输入','',
 '- dot 主机：AMD EPYC 9V74，CPU affinity 0–8；可见内存约9.7GiB、无swap。旧容量实验是16GiB cgroup和4核配额；主机不同。',
 '- ub-test基线 `a5aa51ab19c251c9220872d4b74f30bbcae25889`；native `d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b`；tools `29009175f1778f76a22d929063c3a0821cb91e56`。',
 '- 原回归configure日志明确release、NS3_ASSERT=OFF、NS3_LOG=OFF、native optimizations=OFF；本次保持这些选项，用GCC14.2.0、实际 `-O3 -DNDEBUG -g` 重建executor、UB和core。后到的saved环境交付含原executor/UB/core完整compile_commands，已核对原版确为-O3 -DNDEBUG且无-g；编译器同为GCC14.2。仅把这些当编译审计证据，不混入dot测量。主机及重新构建ELF仍不同，不声称精确复现旧283.40s。`build.sh`中的-O2仅用于graph/oracle。',
 '- [本机完整编译命令和build-id](evidence/build-audit.json)、[后到原环境编译命令摘录与来源](evidence/imported-original-build-audit.json)、[CMakeCache](evidence/CMakeCache.txt)、[所有测量ELF前后hash](evidence/binary-hashes-after.json)。原版DSO单独冻结，timed重建不会污染原版；采样文件中的路径对应冻结的精确ELF。',
 '- EP64/E128/k8，H64/I128、bf16、三矩阵SwiGLU、单交换机、原网络与计算参数；直接复用prefill-capacity/stage.py。router seed=20261016，payload seed=20261015（原adapter实际默认值）；不擅自把两种seed统一。',
 '- [旧50K输入哈希核对](evidence/original-input-comparison.json)及run-ledger中的每份输入/输出SHA256。', '',
 '## 资源与测量扰动','', '| assignments | variant | wall s | user CPU s | system CPU s | peak RSS MiB | wall相对原版 |', '|---:|---|---:|---:|---:|---:|---:|']
for a in sizes:
 for v in ['baseline','sampled','timed']:
  q=r(a,v);lines.append(f"| {a} | {v} | {q['wall_seconds']:.2f} | {q['user_cpu_seconds']:.2f} | {q['system_cpu_seconds']:.2f} | {q['peak_rss_kib']/1024:.2f} | {(q['wall_seconds']/r(a,'baseline')['wall_seconds']-1)*100:+.2f}% |")
lines+=['','单次、顺序运行，没有实验/构建并行。负扰动视为运行噪声，不解释为加速。guard每250ms观察完成，wall有最多约一个轮询间隔的量化误差；CPU来自wait4。采样版外层资源包含采集器，采集器console另保留被采程序自己的CPU时间。完整数据见[resources.csv](evidence/analysis/resources.csv)；生成、planner、adapter、仿真、严格校验各外部阶段见[external-phases.csv](evidence/analysis/external-phases.csv)。','',
 '保护：simulator/verify各600s，RSS树6GiB、地址空间7GiB、主机可用内存至少1.5GiB、工作磁盘至少8GiB、/tmp至少2GiB。任何失败阻止更大规模。未运行100K。所有原始guard采样、退出状态和日志保留。','',
 '## 真正CPU样本与热点','', '| A | 样本数 | TPN反查子树 | lifecycle子树 | unknown leaf | 有unknown帧的样本 |', '|---:|---:|---:|---:|---:|---:|']
for a in sizes:
 q=sp(a);lines.append(f"| {a} | {q['sample_count']} | {q['hotspot_subtrees']['GetJettiesUsingTpn']['percent']:.2f}% | {q['hotspot_subtrees']['ResolveWqeLifecycleLocalId']['percent']:.2f}% | {q['unknown_self_samples']} | {q['unknown_any_frame_samples']} |")
lines+=['','- [50K self Top20](evidence/analysis/50000-sampled/self-top20.svg) · [CSV](evidence/analysis/50000-sampled/self-top20.csv)','- [50K inclusive Top20](evidence/analysis/50000-sampled/inclusive-top20.svg) · [CSV](evidence/analysis/50000-sampled/inclusive-top20.csv)','- 50K有unknown祖先帧的27442个样本中，27395个包含同一libc入口未知帧；unknown leaf仅534个（1.93%）。因此99.36%的unknown-any比例不表示99%的热点无法归因。', '- 每档也提供完整symbol表、unknown IP表和count-weighted folded stacks。每个SAMPLE权重=1，不把CPU-clock period纳秒标成samples。inclusive按每个样本的去重栈归属统计，子树相互重叠，不能相加。','',
 '## 调用与扫描量：验证增长，而非仅靠静态O(J²)判断','', '| A | TPN lookup调用 | TPN扫描Jetty记录 | lifecycle调用 | lifecycle扫描Jetty记录 | lifecycle比较WQE条目 |', '|---:|---:|---:|---:|---:|---:|']
for a in sizes:
 z=c(a);v=t(a);lines.append(f"| {a} | {v['GetJettiesUsingTpn']['calls_or_count']} | {z['TpnLookupJettyRecordsScanned']} | {v['ResolveWqeLifecycleLocalId']['calls_or_count']} | {z['JettyRecordsScanned']} | {z['WqeEntriesCompared']} |")
lines += ['',f"从5K到50K，assignments×10，TPN扫描记录×{c(50000)['TpnLookupJettyRecordsScanned']/c(5000)['TpnLookupJettyRecordsScanned']:.2f}，lifecycle扫描记录×{c(50000)['JettyRecordsScanned']/c(5000)['JettyRecordsScanned']:.2f}。这是固定workload上的实测增长，不能外推所有拓扑/活跃集。每档TPN transport比较数与扫描记录数相等，本负载每条记录只有一个live transport；其每次反查仍会构造live-TP向量、检查成员并返回Jetty集合。",'',
 'lifecycle候选ID次数与调用次数完全相等，本轮没有观测到额外碰撞重试；成本主要来自每个候选扫描既有Jetty记录及当前WQE，而非无限重试。它有明显增长，但实际CPU样本不是第一大项。','',
 '## Jetty初始化、ACK存储与注册的独立成本','', '| A | Jetty数 | TP窗口数 | Jetty槽载荷 MiB | TP槽载荷 MiB | Jetty ACK初始化CPU s | CreateJetty总CPU s | RegisterJetty CPU s |', '|---:|---:|---:|---:|---:|---:|---:|---:|']
for v in ack:
 lines.append(f"| {v['assignments']} | {v['jetty_windows']} | {v['tp_windows']} | {int(v['jetty_slot_payload_bytes'])/2**20:.2f} | {int(v['tp_slot_payload_bytes'])/2**20:.2f} | {float(v['jetty_ack_initialization_cpu_seconds']):.4f} | {float(v['jetty_creation_cpu_seconds']):.4f} | {float(v['jetty_register_cpu_seconds']):.4f} |")
lines+=['','每窗2048个uint64槽=16KiB，不是位压缩2048bit。Jetty构造Resize、Init再次Resize及Reset产生三次逻辑写入；销毁Resize(0)清size，不代表立即释放capacity。通用计数还包含每个AppPair的两个TP接收窗口，不能全算成Jetty ACK。四档均验证：growth=Jetty+2×Pair，Resize调用=3×该窗口数，Reset=窗口数，非零Resize槽=2×窗口数×2048。','',
 'Jetty ACK CPU由CreateObjectJetty和JettyInit各自inclusive−exclusive相加取得；这些scope没有其他已插桩子scope。TP初始化用AppPair的差，清理Resize用SimulatorDestroy的差，三者与所有AckResize+AckReset计时精确对账。CreateJetty总计包含ACK成本，不再叠加。数值包含诊断扰动；槽载荷/逻辑写入不是RSS、malloc额外开销或内存总线流量。见[独立归因CSV](evidence/analysis/ack-attribution.csv)。','',
 '## 主要阶段：50K计时版','', '| scope | calls | inclusive CPU s | exclusive CPU s | inclusive wall s |','|---|---:|---:|---:|---:|']
for name in ['AppRead','AppTopology','AppInit','AppPair','CreateJettyBound','RegisterJetty','SubmitWqe','ResolveWqeLifecycleLocalId','AppSimulatorRun','GetJettiesUsingTpn','TransactionInboundTaUnit','TransactionSegmentComplete','AppValidate','AppEvent','AppWriteArtifacts','AppWritePayloads','AppLogClose','AppUbUtilsDestroy','AppSimulatorDestroy','AppLayerDestroy']:
 v=t(50000)[name];lines.append(f"| {name} | {v['calls_or_count']} | {sec(v):.6f} | {v['exclusive_thread_cpu_ns']/1e9:.6f} | {v['inclusive_wall_ns']/1e9:.6f} |")
lines+=['','输入/数据结构包含于AppRead；Topology嵌套节点、TP、Jetty创建；SimulatorRun包含提交、协议事务、校验及事件日志。inclusive不可累加。exclusive仅扣除已插桩子scope，不等于所有指令的真正self CPU。CLOCK_THREAD_CPUTIME_ID计时含该线程的用户和系统CPU，与仅用户态的采样分母不同。详细native trace/port/ACK scopes仅在小parity中启用，正式大规模保持detail关闭；那些零行表示未启用，绝非日志/报文成本为零。大规模的其余热点以真实sample Top20为准。','',
 '## 正确性与回归','',
 f"- 正式12组simulator和严格verify均成功；所有规模原版/sample/timed完整生成文件逐字节一致。自动检查：**{checks['status']}**，见[checks](evidence/checks.json)。",'- 小NB和chunk-streaming在原版、插桩关闭、插桩开启之间全部文件相同，包括latency、WQE、TA、完整timeline及payload；并启用了小例详细日志/packet计时。',
 f"- 完整旧套件重试状态：**{j(H/'evidence/regression-resource.json')['status']}**；[资源与状态](evidence/regression-resource.json)，附件含完整日志。首轮在插桩native上已通过Relay48例及normal/-O故障检测，随后PoC clean-tree前置检查拒绝诊断补丁，未运行PoC。冻结测量ELF后仅反向应用本轮诊断patch恢复native源，再运行完整旧套件。恢复源码后的旧回归与插桩12组/小parity分开计，不把两者混称。",'',
 '## 采样方法与局限','',
 '本容器官方perf record因/sys CPU/PMU发现失败得到0样本（[原始verbose日志](evidence/official-perf-probe.txt)）。小型C采集器直接使用Linux perf_event_open的CPU-clock事件，官方Debian perf负责解码标准perf.data和DWARF。已知hotloop重校准152样本，period和1.535353520s / wait4用户CPU1.538369s=99.804%；leaf全为hot_loop，去除了FP+DWARF重复链。',
 '- 99Hz、8KiB用户栈；只覆盖主线程用户态，继承关闭；不归因内核CPU。正式采样版进程观察到最多1线程，MPI/MTP关闭；这不是任意多线程应用的完整覆盖保证。',
 '- 每档官方decode SAMPLE数与原始record及采集器一致；保留unknown、pid/tid、period与CPU核对数据。未观察到LOST/THROTTLE/UNTHROTTLE记录，不等于证明完全没有丢样；深栈可能截断，未知libc帧不删除。',
 '- 更早的calibration.data因无法恢复白名单启动证据而隔离，不随附件发布；正式结论仅使用白名单calibration2与四档正式profile，见withheld-preliminary-capture.json。', '- 精确ELF与hash归档到symfs。原始header不带build-id元信息，因此不能用被替换的.so解码。executor和全部native.so测量前后hash相同。',
 '- 采集器与被采进程均仅获显式白名单环境，避免DWARF栈带入ambient认证变量；发布前已知值/模式扫描是额外防线，不替代预防。保留secret-scan状态，不记录任何密钥值。','',
 '## 下一阶段建议（本轮均未实施）','',
 '1. 优先验证生命周期一致的TP→活跃Jetty反向索引，避免GetJettiesUsingTpn每次遍历所有记录并临时构造live-TP向量。要求先保持bind/unbind/retire与完整时间线一致。',
 '2. 再评估lifecycle local-ID占用索引，替代每次遍历Jetty/WQE做唯一性检测；必须保留跨Jetty碰撞与回收语义。',
 '3. 若目标转为内存，再独立评估ACK窗口存储和重复初始化。其显著槽载荷与较小初始化CPU成本应分开讨论，不据此宣称能消除当前主要运行时瓶颈。','',
 '## 原始附件与复现','',
 'GitHub只保留源码、报告、图和小证据；完整每档原始输入/日志/profile、校准/回归及匹配ELF以独立Library附件交付。准确文件名、大小及SHA256见[evidence/archives.json](evidence/archives.json)，每文件清单与附件对应；附件不是不可访问的本地路径替代品。README提供解码与symfs复现方法。']
(H/'REPORT.md').write_text('\n'.join(lines)+'\n')
print('REPORT.md generated from dot-host measurements')
