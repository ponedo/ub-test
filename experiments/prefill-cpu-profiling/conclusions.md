# 实测结论与未实现候选

50K 的主要 CPU 成本在 TP→Jetty 反向查找及其调用路径：`GetJettiesUsingTpn` 子树覆盖 76.01% 实际 CPU 栈样本。这个比例包含下游函数，不能与它们相加。预注册的“lifecycle ID lookup 可能主导”假设未得到支持：它覆盖 4.07% 样本，计时版累计 wall 为 13.699s。

|A|samples|GetJettiesUsingTpn inclusive %|GetJettyLiveTps inclusive %|ResolveLiveTp inclusive %|ResolveWqeLifecycleLocalId inclusive %|
|---:|---:|---:|---:|---:|---:|
|5000|430|38.605|21.628|11.628|0.233|
|10000|1330|52.406|29.474|14.962|1.278|
|20000|4888|66.080|34.002|16.858|2.619|
|50000|30439|76.008|31.506|14.813|4.070|

## 事件数量与每事件成本

|A|simulator events|remote WQEs / verified target segments|layer latency ps|baseline user+sys s|CPU µs/event|
|---:|---:|---:|---:|---:|---:|
|5000|483679|9850 / 9850|136649168|4.177|8.636|
|10000|915282|19674 / 19674|271031968|14.224|15.541|
|20000|1796121|39354 / 39354|543165776|50.446|28.086|
|50000|4487239|98386 / 98386|1353604768|312.944|69.741|

A 增长10倍时，baseline 整进程 wall 增长 69.39 倍（区间经验指数 1.841），事件数增长 9.28 倍。结合 CPU 栈路径占比上升，可支持“每事件扫描/查找成本变贵导致超线性 wall”的判断；不将四个点当作渐近 O(A²) 的证明。

源代码解释与测量互相对应：native `ub-transaction.cc:591` 的 GetJettiesUsingTpn 遍历 m_jettyRtpReferences，为每个引用调用 GetJettyLiveTps，并按 Jetty 顺序收集结果；`ub-transaction.cc:794` 在 TP 可继续发送时调用它。GetJettyLiveTps (`:494`) 解析生命周期身份并创建返回 vector；ResolveLiveTp (`ub-transport-channel-manager.cc:457`) 有锁和有效性检查。采样中的树迭代、解析、分配/释放成本与此路径一致。仅看到循环不足以得出本结论，主要证据是四档真实样本和资源测量。

## CreateJetty / ACK / 注册是否主导？

- `UbFunction::CreateJetty`：98386 次，inclusive wall 0.622318s，约占计时 main 0.189%。
- `UbJetty::Init`：98386 次，inclusive wall 0.039006s，约占计时 main 0.012%。
- `Jetty.AckWindow.ResizeReset`：98386 次，inclusive wall 0.033410s，约占计时 main 0.010%。
- `UbJettyManager::RegisterJetty`：98386 次，inclusive wall 0.079903s，约占计时 main 0.024%。
- `UbJettyManager::RegisterWqe`：98386 次，inclusive wall 0.020560s，约占计时 main 0.006%。
- `UbJettyManager::ResolveWqeLifecycleLocalId`：98386 次，inclusive wall 13.699424s，约占计时 main 4.170%。
- `UbFunction::SubmitWqe`：98386 次，inclusive wall 14.456861s，约占计时 main 4.400%。

这些时间有嵌套，不能求和。显式 ACK ResizeReset 不含默认构造分配，因此只能排除已测的显式初始化为 CPU 主因，不能据此说 ACK 内存占用不重要。没有实现 Jetty 复用、ACK 改造或生命周期缓存。

## 最多三个候选，均未实现

1. 优先研究保持顺序和 generation 语义的 TP→Jetty 反向索引，减少 GetJettiesUsingTpn 对全部绑定的扫描。必须在创建、替换、解绑、drain/dispose、TP复用和TPG成员变化时同步维护，返回顺序与原 map 扫描一致；用原实现作 oracle，验证 fault/销毁/重建、随机绑定序列和完整事件/payload逐字节一致。不能移除 ResolveLiveTp 生命周期检查。

2. 在上述热点路径内研究避免临时 vector 分配的遍历接口，仍逐项做同样的有效性解析并保持次序。先用调用栈确认分配归属；需验证空/单TP/TPG、失效generation、成员变更、重入和故障路径，保持所有日志和模型。其收益与候选1重叠，不能将采样比例当成可叠加提速。

3. 次级研究为 ResolveWqeLifecycleLocalId 的“是否占用”查询维护计数索引；优先级由实测占比限制。需要覆盖相同 WQE ID 跨 Jetty、scope回绕、完成/取消/解绑及generation变化，保持原 ID 选择结果及生命周期行为；当前无实现。

## 校验与限制

完整 file-hash parity 包含每个规模的 native日志、应用时间线和 payload，并非仅比较最终延迟。小规模5K也执行相同完整校验。CPU百分比来自采样，不是定点 wall 占比。unknown叶样本、未解析内联帧、8192字节栈深限制、单次固定顺序试验和0.5秒wall轮询精度均限制精确归因；报告中的负扰动不能理解为优化收益。没有运行100K或降低任何日志/校验强度。原始 DWARF 栈含继承环境凭据，原件保留本地，发布副本进行等长脱敏；脱敏前后完整 perf script 字节一致，样本与调用栈归因未变。
