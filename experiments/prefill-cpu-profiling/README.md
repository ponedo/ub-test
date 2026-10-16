# NoBalance CPU Profiling

50K 的主要热点是 TP→Jetty 查找路径：GetJettiesUsingTpn 子树覆盖 76.01% 实际 CPU 栈样本。12 个 case 完成且全输出哈希一致；完整结论和未实现候选见 [conclusions.md](conclusions.md)。

基线 `a5aa51ab19c251c9220872d4b74f30bbcae25889`；native `d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b`。本模块只增加诊断、报告和独立构建插桩，无优化。

## 方法与边界

EP64/E128/top-k8、single-switch、trace RNG seed20261016 weighted sampling prefixes（payload-byte seed沿用20261015，见 fixed-runtime-config.json）、H64/I128/bf16/3 matrices；只测 NoBalance A=5K/10K/20K/50K，T=A/8。每档固定顺序 baseline → perf → timed，各一次。原执行器和 native 库 `-O3 -DNDEBUG`；计时版 `-O3 -DNDEBUG -g` 加 scope 头文件和计时库。helper 的 `-O2` 不代表执行器设置。完整 flags、CMakeCache、链接命令和 ELF/build-id 在 evidence/build-*。原版有符号表但没有 DWARF debug 信息；调用栈通过 DWARF unwinding/.eh_frame 和符号表解析，内联函数可能归属调用者。

`perf 6.12.107` 软件 `cpu-clock:u`、99 Hz、DWARF8192。硬件 cycles 不支持；未改变安全设置。Top20 为真实采样叶帧数量占总有效栈样本比例；perf 自身 period-weighted 结果另存 perf-symbols.txt，两者不可冒充硬件周期。火焰图宽度是 inclusive 栈样本数，不得相加。unknown 栈明确保留。

高频定点计时用 CLOCK_MONOTONIC_RAW；粗阶段还测 CLOCK_THREAD_CPUTIME_ID。inclusive/exclusive wall 中 exclusive 仅扣除已插桩子 scope，不能解释为纯函数自身 CPU。粗阶段 CPU exclusive 只扣除已测 CPU 的粗阶段。RSS 为阶段退出时进程历史高水位，并非该阶段独有峰值；阶段内部不能由高水位差推算分配量。进程级 RSS/user/sys 使用 wait4；perf 包括 recorder 与其子进程的 CPU，ru_maxrss 是被等待进程及后代的最大单进程高水位，不是 RSS 求和。另存0.5秒采样的进程树RSS。wall 为0.5秒 guard轮询精度。计时和重编译扰动一起测量；仅一次固定顺序配对，无置信区间或可推广的精确 overhead。

## 整进程资源与扰动

|A|variant|wall s|user s|sys s|peak RSS MiB|RSS Δ MiB|wall vs baseline|CPU vs baseline|
|---:|---|---:|---:|---:|---:|---:|---:|---:|
|5000|baseline|4.512|4.023|0.155|287.9|+0.00|+0.00%|+0.00%|
|5000|perf|4.515|4.302|0.174|287.6|-0.22|+0.06%|+7.17%|
|5000|timed|5.015|4.574|0.129|287.9|+0.02|+11.14%|+12.58%|
|10000|baseline|14.549|13.972|0.252|487.3|+0.00|+0.00%|+0.00%|
|10000|perf|14.052|13.448|0.293|487.2|-0.12|-3.42%|-3.39%|
|10000|timed|14.546|14.124|0.269|487.3|+0.00|-0.02%|+1.19%|
|20000|baseline|50.672|50.085|0.361|860.5|+0.00|+0.00%|+0.00%|
|20000|perf|50.187|49.485|0.459|860.1|-0.33|-0.96%|-0.99%|
|20000|timed|55.190|54.372|0.442|860.5|-0.02|+8.92%|+8.66%|
|50000|baseline|313.117|311.884|1.060|1949.7|+0.00|+0.00%|+0.00%|
|50000|perf|309.160|307.744|1.402|1949.9|+0.22|-1.26%|-1.21%|
|50000|timed|328.660|327.465|1.081|1950.0|+0.29|+4.96%|+4.99%|

## 内部粗阶段（计时版）

阶段为嵌套观测，main 包含其他阶段；Topology 包含 CreateJetty；SimulatorRun 包含 SubmitWqe 等。下表只展示 inclusive，不做跨层求和。main 不含动态加载和退出后 profiler 写 CSV。

|A|phase|wall s|thread CPU s|RSS high-water MiB|
|---:|---|---:|---:|---:|
|5000|app.main|4.676153|4.675507|287.9|
|5000|app.Read|0.002969|0.002973|19.7|
|5000|app.WriteArtifacts|0.002640|0.002642|19.7|
|5000|app.Topology|0.176546|0.176535|262.2|
|5000|phase.SimulatorRun|4.394685|4.394062|287.9|
|5000|app.WritePayloads|0.001485|0.001486|287.9|
|5000|phase.cleanup|0.089807|0.089815|287.9|
|10000|app.main|14.360519|14.359185|487.3|
|10000|app.Read|0.006846|0.006842|23.3|
|10000|app.WriteArtifacts|0.005164|0.005153|23.3|
|10000|app.Topology|0.276659|0.276371|446.7|
|10000|phase.SimulatorRun|13.928967|13.927972|487.3|
|10000|app.WritePayloads|0.002897|0.002895|487.3|
|10000|phase.cleanup|0.120897|0.120884|487.3|
|20000|app.main|54.774307|54.765817|860.5|
|20000|app.Read|0.011909|0.011914|31.2|
|20000|app.WriteArtifacts|0.010498|0.010496|31.2|
|20000|app.Topology|0.469040|0.469035|792.7|
|20000|phase.SimulatorRun|54.042823|54.034352|860.5|
|20000|app.WritePayloads|0.005984|0.005987|860.5|
|20000|phase.cleanup|0.186691|0.186698|860.5|
|50000|app.main|328.528335|328.479487|1950.0|
|50000|app.Read|0.028987|0.028986|54.4|
|50000|app.WriteArtifacts|0.025231|0.025235|54.4|
|50000|app.Topology|0.956148|0.956138|1803.3|
|50000|phase.SimulatorRun|326.877035|326.828222|1950.0|
|50000|app.WritePayloads|0.015646|0.015649|1950.0|
|50000|phase.cleanup|0.484090|0.484088|1950.0|

## 关键函数测量

|A|scope|calls|inclusive wall s|exclusive wall s|inclusive µs/call|
|---:|---|---:|---:|---:|---:|
|5000|UbFunction::CreateJetty|9850|0.069194|0.058157|7.025|
|5000|UbJetty::Init|9850|0.003647|0.000561|0.370|
|5000|Jetty.AckWindow.ResizeReset|9850|0.003085|0.003085|0.313|
|5000|UbJettyManager::RegisterJetty|9850|0.007390|0.007390|0.750|
|5000|UbJettyManager::GetJetty|629294|0.158871|0.158871|0.252|
|5000|UbJettyManager::IsJettyExists|0|0.000000|0.000000|n/a|
|5000|UbFunction::SubmitWqe|9850|0.074079|0.024629|7.521|
|5000|UbJettyManager::ResolveWqeLifecycleLocalId|9850|0.032327|0.032327|3.282|
|5000|UbJettyManager::RegisterWqe|9850|0.001137|0.001137|0.115|
|10000|UbFunction::CreateJetty|19674|0.130944|0.110171|6.656|
|10000|UbJetty::Init|19674|0.007385|0.001036|0.375|
|10000|Jetty.AckWindow.ResizeReset|19674|0.006348|0.006348|0.323|
|10000|UbJettyManager::RegisterJetty|19674|0.013388|0.013388|0.680|
|10000|UbJettyManager::GetJetty|2181124|0.666916|0.666916|0.306|
|10000|UbJettyManager::IsJettyExists|0|0.000000|0.000000|n/a|
|10000|UbFunction::SubmitWqe|19674|0.283887|0.055380|14.430|
|10000|UbJettyManager::ResolveWqeLifecycleLocalId|19674|0.196119|0.196119|9.968|
|10000|UbJettyManager::RegisterWqe|19674|0.002564|0.002564|0.130|
|20000|UbFunction::CreateJetty|39354|0.257108|0.209411|6.533|
|20000|UbJetty::Init|39354|0.017673|0.002201|0.449|
|20000|Jetty.AckWindow.ResizeReset|39354|0.015471|0.015471|0.393|
|20000|UbJettyManager::RegisterJetty|39354|0.030025|0.030025|0.763|
|20000|UbJettyManager::GetJetty|7984604|3.038692|3.038692|0.381|
|20000|UbJettyManager::IsJettyExists|0|0.000000|0.000000|n/a|
|20000|UbFunction::SubmitWqe|39354|1.791542|0.167532|45.524|
|20000|UbJettyManager::ResolveWqeLifecycleLocalId|39354|1.544088|1.544088|39.236|
|20000|UbJettyManager::RegisterWqe|39354|0.008072|0.008072|0.205|
|50000|UbFunction::CreateJetty|98386|0.622318|0.503409|6.325|
|50000|UbJetty::Init|98386|0.039006|0.005596|0.396|
|50000|Jetty.AckWindow.ResizeReset|98386|0.033410|0.033410|0.340|
|50000|UbJettyManager::RegisterJetty|98386|0.079903|0.079903|0.812|
|50000|UbJettyManager::GetJetty|46496792|21.360642|21.360642|0.459|
|50000|UbJettyManager::IsJettyExists|0|0.000000|0.000000|n/a|
|50000|UbFunction::SubmitWqe|98386|14.456861|0.546314|146.940|
|50000|UbJettyManager::ResolveWqeLifecycleLocalId|98386|13.699424|13.699424|139.242|
|50000|UbJettyManager::RegisterWqe|98386|0.020560|0.020560|0.209|

ACK ResizeReset 仅含显式 Resize/Reset；CreateJetty inclusive 还含 CreateObject 默认成员分配、Init 和注册。不能把二者相加，也不能将 CreateJetty 减 Init 自动认定全部是 ACK 分配。CreateJetty 两个互不调用的重载合并计数。

## 真实 CPU 样本与调用栈

### A=5000

有效栈样本 430；unknown leaf 25；平均深度 17.68。[完整 Top20](evidence/5000/top20.csv) · [调用栈火焰图](evidence/5000/flame.svg) · [原始 perf 报告](evidence/5000/perf-report.txt)

|rank|self symbol|samples|self %|
|---:|---|---:|---:|
|1|`std::_Rb_tree_increment(std::_Rb_tree_node_base*)`|45|10.465|
|2|`ns3::UbTransportChannelManager::ResolveLiveTp(unsigned int, ns3::UbLifecycleResourceIdentity const&)`|38|8.837|
|3|`ns3::UbTransaction::GetJettyLiveTps(unsigned int)`|35|8.140|
|4|`[unknown]`|25|5.814|
|5|`cfree`|18|4.186|
|6|`ns3::UbFunction::GetJetty(unsigned int)`|17|3.953|
|7|`malloc`|12|2.791|
|8|`ns3::UbRetransController::GetRetransEnable() const`|12|2.791|
|9|`utils::UbUtils::AppendTraceLine(utils::UbUtils::TraceSinkHandle const&, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >)`|8|1.860|
|10|`utils::UbUtils::GetCachedTraceSink(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&)`|7|1.628|
|11|`(anonymous namespace)::CsvRow(std::initializer_list<std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > >)`|6|1.395|
|12|`__dynamic_cast`|5|1.163|
|13|`ns3::UbTransaction::GetJettiesUsingTpn(unsigned int)`|5|1.163|
|14|`ns3::UbTransportChannel::IsEmpty()`|5|1.163|
|15|`ns3::UbTransportChannelManager::ResolveInboundTp(unsigned int, unsigned int, ns3::Ipv4Address, ns3::Ipv4Address, unsigned char)`|5|1.163|
|16|`std::__cxx11::to_string(unsigned int)`|5|1.163|
|17|`ns3::UbRoundRobinAllocator::SelectNextIngressQueue(ns3::Ptr<ns3::UbPort>)`|4|0.930|
|18|`ns3::UbTransportChannel::TrackInboundTaPacket(ns3::UbTransportChannel::BufferedInboundPacket const&)`|4|0.930|
|19|`ns3::UbPort::TransmitPacket(ns3::Ptr<ns3::Packet>, ns3::Time)`|3|0.698|
|20|`ns3::UbTransportChannel::NotifyLastPacketReceived(ns3::UbTransportChannel::ReceivedDataPacketContext const&)`|3|0.698|
### A=10000

有效栈样本 1330；unknown leaf 70；平均深度 18.05。[完整 Top20](evidence/10000/top20.csv) · [调用栈火焰图](evidence/10000/flame.svg) · [原始 perf 报告](evidence/10000/perf-report.txt)

|rank|self symbol|samples|self %|
|---:|---|---:|---:|
|1|`std::_Rb_tree_increment(std::_Rb_tree_node_base*)`|203|15.263|
|2|`ns3::UbTransportChannelManager::ResolveLiveTp(unsigned int, ns3::UbLifecycleResourceIdentity const&)`|169|12.707|
|3|`ns3::UbTransaction::GetJettyLiveTps(unsigned int)`|160|12.030|
|4|`[unknown]`|70|5.263|
|5|`ns3::UbFunction::GetJetty(unsigned int)`|60|4.511|
|6|`cfree`|51|3.835|
|7|`malloc`|34|2.556|
|8|`__dynamic_cast`|24|1.805|
|9|`ns3::UbTransaction::GetJettiesUsingTpn(unsigned int)`|22|1.654|
|10|`ns3::UbRetransController::GetRetransEnable() const`|18|1.353|
|11|`ns3::UbTransportChannel::IsEmpty()`|17|1.278|
|12|`utils::UbUtils::AppendTraceLine(utils::UbUtils::TraceSinkHandle const&, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >)`|16|1.203|
|13|`ns3::UbTransaction::TryContinueJettyTransmission(unsigned int)`|16|1.203|
|14|`ns3::UbTransportChannel::GetNextPacketSize()`|15|1.128|
|15|`std::_Rb_tree_increment(std::_Rb_tree_node_base const*)`|12|0.902|
|16|`ns3::UbRoundRobinAllocator::SelectNextIngressQueue(ns3::Ptr<ns3::UbPort>)`|11|0.827|
|17|`ns3::UbSwitchAllocator::FindNextEligibleIngressQueue(unsigned int, unsigned int, unsigned int, ns3::Ptr<ns3::UbPort>) const`|11|0.827|
|18|`std::_Rb_tree<ns3::UbLifecycleCoordinator::ResourceKey, std::pair<ns3::UbLifecycleCoordinator::ResourceKey const, ns3::UbLifecycleCoordinator::ResourceState>, std::_Select1st<std::pair<ns3::UbLifecycleCoordinator::ResourceKey const, ns3::UbLifecycleCoordinator::ResourceState> >, std::less<ns3::UbLifecycleCoordinator::ResourceKey>, std::allocator<std::pair<ns3::UbLifecycleCoordinator::ResourceKey const, ns3::UbLifecycleCoordinator::ResourceState> > >::find(ns3::UbLifecycleCoordinator::ResourceKey const&)`|10|0.752|
|19|`ns3::TracedCallback<unsigned int, unsigned int, unsigned int, unsigned int, unsigned int, unsigned int, ns3::PacketType, unsigned int, unsigned int, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >, ns3::UbPacketTraceTag>::operator()(unsigned int, unsigned int, unsigned int, unsigned int, unsigned int, unsigned int, ns3::PacketType, unsigned int, unsigned int, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >, ns3::UbPacketTraceTag) const`|10|0.752|
|20|`(anonymous namespace)::CsvRow(std::initializer_list<std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > >)`|10|0.752|
### A=20000

有效栈样本 4888；unknown leaf 148；平均深度 18.44。[完整 Top20](evidence/20000/top20.csv) · [调用栈火焰图](evidence/20000/flame.svg) · [原始 perf 报告](evidence/20000/perf-report.txt)

|rank|self symbol|samples|self %|
|---:|---|---:|---:|
|1|`std::_Rb_tree_increment(std::_Rb_tree_node_base*)`|1148|23.486|
|2|`ns3::UbTransaction::GetJettyLiveTps(unsigned int)`|677|13.850|
|3|`ns3::UbTransportChannelManager::ResolveLiveTp(unsigned int, ns3::UbLifecycleResourceIdentity const&)`|658|13.462|
|4|`ns3::UbFunction::GetJetty(unsigned int)`|271|5.544|
|5|`cfree`|157|3.212|
|6|`[unknown]`|148|3.028|
|7|`malloc`|111|2.271|
|8|`std::_Rb_tree_increment(std::_Rb_tree_node_base const*)`|106|2.169|
|9|`__dynamic_cast`|95|1.944|
|10|`ns3::UbTransaction::GetJettiesUsingTpn(unsigned int)`|90|1.841|
|11|`ns3::UbTransaction::TryContinueJettyTransmission(unsigned int)`|61|1.248|
|12|`ns3::UbTransportChannel::GetNextPacketSize()`|47|0.962|
|13|`ns3::UbTransportChannel::IsEmpty()`|34|0.696|
|14|`utils::UbUtils::AppendTraceLine(utils::UbUtils::TraceSinkHandle const&, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >)`|33|0.675|
|15|`ns3::UbRetransController::GetRetransEnable() const`|31|0.634|
|16|`ns3::Ptr<ns3::UbTransportChannelManager>::~Ptr()`|29|0.593|
|17|`pthread_mutex_lock`|28|0.573|
|18|`std::_Rb_tree<ns3::UbLifecycleCoordinator::ResourceKey, std::pair<ns3::UbLifecycleCoordinator::ResourceKey const, ns3::UbLifecycleCoordinator::ResourceState>, std::_Select1st<std::pair<ns3::UbLifecycleCoordinator::ResourceKey const, ns3::UbLifecycleCoordinator::ResourceState> >, std::less<ns3::UbLifecycleCoordinator::ResourceKey>, std::allocator<std::pair<ns3::UbLifecycleCoordinator::ResourceKey const, ns3::UbLifecycleCoordinator::ResourceState> > >::find(ns3::UbLifecycleCoordinator::ResourceKey const&)`|26|0.532|
|19|`ns3::UbController::GetTransportChannelManager() const`|25|0.511|
|20|`utils::UbUtils::GetCachedTraceSink(std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&)`|24|0.491|
### A=50000

有效栈样本 30439；unknown leaf 530；平均深度 18.49。[完整 Top20](evidence/50000/top20.csv) · [调用栈火焰图](evidence/50000/flame.svg) · [原始 perf 报告](evidence/50000/perf-report.txt)

|rank|self symbol|samples|self %|
|---:|---|---:|---:|
|1|`std::_Rb_tree_increment(std::_Rb_tree_node_base*)`|10765|35.366|
|2|`ns3::UbTransaction::GetJettyLiveTps(unsigned int)`|4223|13.874|
|3|`ns3::UbTransportChannelManager::ResolveLiveTp(unsigned int, ns3::UbLifecycleResourceIdentity const&)`|3487|11.456|
|4|`ns3::UbFunction::GetJetty(unsigned int)`|1851|6.081|
|5|`std::_Rb_tree_increment(std::_Rb_tree_node_base const*)`|1035|3.400|
|6|`cfree`|741|2.434|
|7|`ns3::UbTransaction::GetJettiesUsingTpn(unsigned int)`|622|2.043|
|8|`malloc`|535|1.758|
|9|`[unknown]`|530|1.741|
|10|`__dynamic_cast`|528|1.735|
|11|`ns3::UbTransaction::TryContinueJettyTransmission(unsigned int)`|442|1.452|
|12|`ns3::UbTransportChannel::GetNextPacketSize()`|291|0.956|
|13|`pthread_mutex_lock`|210|0.690|
|14|`ns3::UbJettyManager::ResolveWqeLifecycleLocalId(unsigned int, unsigned int) const`|203|0.667|
|15|`ns3::UbTransaction::IsOrderedByInitiator(unsigned int, ns3::Ptr<ns3::UbWqe>)`|191|0.627|
|16|`ns3::UbController::GetTransportChannelManager() const`|168|0.552|
|17|`ns3::UbRetransController::GetRetransEnable() const`|133|0.437|
|18|`ns3::UbTransportChannel::IsEmpty()`|127|0.417|
|19|`std::_Rb_tree<ns3::UbLifecycleCoordinator::ResourceKey, std::pair<ns3::UbLifecycleCoordinator::ResourceKey const, ns3::UbLifecycleCoordinator::ResourceState>, std::_Select1st<std::pair<ns3::UbLifecycleCoordinator::ResourceKey const, ns3::UbLifecycleCoordinator::ResourceState> >, std::less<ns3::UbLifecycleCoordinator::ResourceKey>, std::allocator<std::pair<ns3::UbLifecycleCoordinator::ResourceKey const, ns3::UbLifecycleCoordinator::ResourceState> > >::find(ns3::UbLifecycleCoordinator::ResourceKey const&)`|117|0.384|
|20|`ns3::UbRoundRobinAllocator::SelectNextIngressQueue(ns3::Ptr<ns3::UbPort>)`|117|0.384|

## 随规模增长

|scope|5K→50K time ratio|empirical exponent log(ratio)/log(10)|
|---|---:|---:|
|app.main|70.256|1.847|
|app.Topology|5.416|0.734|
|phase.SimulatorRun|74.380|1.871|
|UbFunction::CreateJetty|8.994|0.954|
|UbJetty::Init|10.696|1.029|
|Jetty.AckWindow.ResizeReset|10.828|1.035|
|UbJettyManager::RegisterJetty|10.812|1.034|
|UbJettyManager::GetJetty|134.453|2.129|
|UbJettyManager::IsJettyExists|n/a (zero calls)|n/a|
|UbFunction::SubmitWqe|195.155|2.290|
|UbJettyManager::ResolveWqeLifecycleLocalId|423.780|2.627|
|UbJettyManager::RegisterWqe|18.081|1.257|

这些是本机、固定 trace 前缀、一次运行的区间经验增长，不是渐近复杂度证明。源代码扫描路径仅用于解释已经测得的 CPU 样本与时间增长。

## 校验与证据

12 个 case 均需 strict verifier PASS，所有规模 baseline/perf/timed 的整个 run/ 文件集合逐文件 SHA256 相同。包含原始 native 日志、应用时间线、payload、模拟事件数、WQE/TA、完成计数与 summary。精确清单见 evidence/run-ledger.json 和 parity-*.json。完整输入、输出、resource-samples、perf-script 和计时 CSV 以 archives/ 无损保存。原始 perf.data 留在本地；发布副本仅对继承环境凭据字节等长脱敏，逐字节验证解码调用栈不变，详见 evidence/publication-redactions.json。准备和验证阶段的 wall/user/sys/RSS 在各 stage/resource.json，不与 ns3 CPU 混算。

## 后续候选（尚未实现）

结论及候选的定量排序见 conclusions.md。任何候选都必须保留现有 WQE/TA/Jetty 生命周期、事件顺序、完整日志与 payload 校验；本次不实现候选。

[全部外部阶段 wall/user/sys/RSS](evidence/external-phases.csv) · [增长图](evidence/scaling.svg)

## 回归与发布

回归 guard：PASS，wall 157.71s，峰值 RSS 608.9 MiB。原版与计时版各通过48个 Relay 场景，normal/-O 各120个 oracle案例和8个live faults；原版链还通过 Direct 26 runs 与 Planner/NoBalancing/ChunkRelay/legacy 回归。测量前后所有记录的 ELF SHA256 一致，原 native tracked source diff 为空。详见 evidence/regressions、evidence/timed-regressions 和 evidence/original-native-clean.txt。

[发布脱敏审计](evidence/publication-redactions.json)记录具体 profile、等长脱敏次数及完整调用栈字节一致性。全部未脱敏原件仍在本地 /workspace/prefill-cpu-raw；发布归档以经过审计的 export 为源。
