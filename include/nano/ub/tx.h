#ifndef NANO_UB_TX_H
#define NANO_UB_TX_H

#include <nano/flit.h>
#include <systemc.h>
#include <algorithm>

// ============================================================
// UB TX 流水线元件 — §8.3 Load/Store (TP Bypass)
//
// Load/Store Engine → BTAH Builder → NTH Builder → UB Encap
// ============================================================

// ---- Load/Store Engine: 主机 load/store 入口 ----
// CPU 的内存请求直接进入此引擎, 不走 WR/CQE 机制
// 旁路了 Doorbell/Jetty/OrderTracker/TPChannel 整条链
SC_MODULE(LsEngine) {
    sc_fifo_in<Flit>  req_in;    // load/store 请求 (addr, len, type)
    sc_fifo_out<Flit> req_out;   // 转发到 BTAH Builder

    SC_HAS_PROCESS(LsEngine);
    LsEngine(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << req_in.data_written();
    }
    void process() {
        while (true) {
            Flit f = req_in.read();
            wait(1, SC_NS);
            if (!f.valid) continue;

            // 设置 NLP = TP_BYPASS (§8.3)
            f.nlp = 0x01;  // TP_BYPASS

            // 设置默认源/目标 CNA (可外部配置)
            if (f.src_addr == 0) f.src_addr = 0x000001;
            if (f.dst_addr == 0) f.dst_addr = 0x000002;

            req_out.write(f);
        }
    }
};

// ---- BTAH Builder: 打上 Base Transaction Header (§7.2.1) ----
SC_MODULE(BtahBuilder) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;

    uint16_t next_tassn;  // 事务序列号

    SC_HAS_PROCESS(BtahBuilder);
    BtahBuilder(sc_module_name name) : sc_module(name), next_tassn(1) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            // 响应包保留原始 TASSN, 不重新分配
            if (f.is_response) {
                out.write(f);
                continue;
            }

            // 分配 INI_TASSN
            f.tassn = next_tassn++;

            // 设置 INI_RC_ID (发起端资源标识符)
            if (f.rc_id == 0) f.rc_id = 0x00001;

            // ODR — 执行顺序标签: Load/Store 默认 NO (无序)
            // 0=NO, 1=RO, 2=SO
            if (f.odr == 0) f.odr = 0;  // NO

            out.write(f);
        }
    }
};

// ---- NTH Builder: 打上 Network Transport Header (§5.2.2) ----
SC_MODULE(NthBuilder) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;

    SC_HAS_PROCESS(NthBuilder);
    NthBuilder(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            // NLP = TP_BYPASS (已在 LsEngine 设置)
            // CNA 地址已设
            // 其他 NTH 字段: CCI, LBF, SL 等用默认值 0

            out.write(f);
        }
    }
};

// ---- UB Encap: UB 以太网封装 (Ethertype 0x88B5) ----
// UB 不需要 UDP 头部, 直接 Ethernet + NTH + TPH + TAH
SC_MODULE(UbEncap) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;

    uint64_t src_mac;
    uint64_t dst_mac;

    SC_HAS_PROCESS(UbEncap);
    UbEncap(sc_module_name name,
            uint64_t smac = 0xAABBCCDDEE01ULL,
            uint64_t dmac = 0xAABBCCDDEE02ULL)
        : sc_module(name), src_mac(smac), dst_mac(dmac) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(11, SC_NS);  // 11 cy: byte-stream frame build
            f.eth_type = UB_ETHERTYPE;  // 0x88B5
            out.write(f);
        }
    }
};

// ============================================================
// UB URMA TX 流水线元件 — 完整传输层
//
// Doorbell → Jetty Scheduler → Order Tracker(INI) → BTAH Builder
//   → TPG Group → TP Channel TX → Congestion Window
//   → Retransmit Buffer → RTPH Builder → NTH Builder → UB Encap
// ============================================================

// ---- UbDoorbell: 验证 WR 并转发 ----
SC_MODULE(UbDoorbell) {
    sc_fifo_in<Flit>  wr_in;
    sc_fifo_out<Flit> wr_out;

    SC_HAS_PROCESS(UbDoorbell);
    UbDoorbell(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << wr_in.data_written();
    }
    void process() {
        while (true) {
            Flit f = wr_in.read();
            wait(1, SC_NS);
            if (!f.valid) continue;
            // 验证: 必须有 opcode
            if (f.ta_opcode == 0 && f.mem_len == 0) continue;
            wr_out.write(f);
        }
    }
};

// ---- Jetty Scheduler: 轮询 WR 分发 + Fence 门控 (§7.3.2.2) ----
// 每个 Jetty 代表一个本地应用端点
// Fence: F 位为 1 时, 阻塞后续 WR 直到前序完成
// 收到 comp_in 上的完成通知时解除门控
SC_MODULE(JettyScheduler) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;
    sc_fifo_in<Flit>  comp_in;   // 完成通知 (来自 TAACK)

    bool fence_active;

    SC_HAS_PROCESS(JettyScheduler);
    JettyScheduler(sc_module_name name)
        : sc_module(name), fence_active(false) {
        SC_THREAD(process);
        sensitive << in.data_written();
        SC_THREAD(handle_comp);
        sensitive << comp_in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            if (fence_active) {
                // Fence 门控中: 阻塞直到 fence 清除
                // 把 flit 存起来等 fence 解除
                wait(comp_in.data_written_event());
                fence_active = false;
            }
            if (f.fence) fence_active = true;
            out.write(f);
        }
    }
    void handle_comp() {
        while (true) {
            comp_in.read();
            fence_active = false;  // 完成通知解除 Fence
        }
    }
};

// ---- Order Tracker (Initiator): ROI 模式 SO 门控 (§7.3.3.2) ----
// NO (odr=0): 无序, 直接通过
// RO (odr=1): 相对有序, 在同一发起端内保持顺序
// SO (odr=2): 严格有序, 等待前序所有 RO 完成
SC_MODULE(OrderTrackerIni) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;
    sc_fifo_in<Flit>  comp_in;   // 完成通知 (RO 完成时解除 SO 门控)

    bool safe_ordering;
    sc_event ordered_done;
    uint32_t ro_count;   // 未完成的 RO 操作数
    bool     so_blocked; // SO 被 RO 阻塞中
    Flit     so_pending; // 被阻塞的 SO 请求

    SC_HAS_PROCESS(OrderTrackerIni);
    OrderTrackerIni(sc_module_name name, bool safe = false)
        : sc_module(name), safe_ordering(safe), ro_count(0), so_blocked(false) {
        SC_THREAD(process);
        sensitive << in.data_written();
        SC_THREAD(handle_comp);
        sensitive << comp_in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            if (safe_ordering) {
                while (f.odr == 2 && ro_count > 0) wait(ordered_done);
                if (f.odr == 1 || f.odr == 2) ++ro_count;
                out.write(f);
                continue;
            }
            if (f.odr == 2 && ro_count > 0) {
                // SO 被 RO 阻塞
                so_blocked = true;
                so_pending = f;
                continue;
            }
            if (f.odr == 1) ro_count++;  // RO: 计数
            out.write(f);
        }
    }
    void handle_comp() {
        while (true) {
            Flit completed = comp_in.read();
            if (safe_ordering) {
                if ((completed.odr == 1 || completed.odr == 2) && ro_count > 0)
                    --ro_count;
                ordered_done.notify(SC_ZERO_TIME);
                continue;
            }
            if (ro_count > 0) ro_count--;
            if (so_blocked && ro_count == 0) {
                so_blocked = false;
                out.write(so_pending);  // 放行被阻塞的 SO
            }
        }
    }
};

// ---- TPG Group: 选择 TP 通道 (§6.4.3) ----
// TPG = TP Group, 映射到远端主机
// 从池中选择一个 TP Channel
SC_MODULE(TpgGroup) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;

    bool preserve_rc_id;  // Opt-in: RC identity is distinct from the one TP channel.
    uint32_t tp_channel_id;  // 选中的 TP 通道 ID

    SC_HAS_PROCESS(TpgGroup);
    TpgGroup(sc_module_name name, uint32_t tpid = 1, bool preserve_rc = false)
        : sc_module(name), preserve_rc_id(preserve_rc), tp_channel_id(tpid) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            // 设置 TP 通道 ID
            if (!preserve_rc_id) f.rc_id = tp_channel_id;  // 复用 rc_id 作为 TP 通道标识
            out.write(f);
        }
    }
};

// ---- TP Channel TX: PSN/TPMSN 分配 + 每主机传输状态 (§6.4) ----
SC_MODULE(TpChannelTx) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;

    uint32_t next_psn;    // 下一个 PSN (24-bit)
    uint32_t next_tpmsn;  // 下一个 TPMSN

    SC_HAS_PROCESS(TpChannelTx);
    TpChannelTx(sc_module_name name)
        : sc_module(name), next_psn(0), next_tpmsn(0) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            if (f.service_mode == 3) {  // UNO: 不需要 PSN
                f.psn = 0xFFFFFF;  // 标记为 UNO
            } else {
                f.psn = next_psn++;
                if (next_psn > 0xFFFFFF) next_psn = 0;
            }
            f.tpmsn = next_tpmsn++;
            out.write(f);
        }
    }
};

// ---- Congestion Window: LDCP 窗口 (§6.6, MVP 中仅 advisory) ----
SC_MODULE(CongestionWindow) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;

    uint32_t window_size;

    SC_HAS_PROCESS(CongestionWindow);
    CongestionWindow(sc_module_name name, uint32_t win = 256)
        : sc_module(name), window_size(win) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            // MVP: 窗口无限, 直接通过
            out.write(f);
        }
    }
};

// ---- Retransmit Buffer: 保存传输中副本 (GoBackN) ----
// 存储已发出但未 ACK 的 flit 副本
// 超时或 NAK 时重传
SC_MODULE(RetransmitBuffer) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;
    sc_fifo_in<Flit>  ack_in;    // ACK/NAK 输入 (预留)

    bool exact_ack;  // Opt-in no-wrap experiment: retire only matching PSN.
    std::vector<Flit> buffer;    // 传输中副本

    SC_HAS_PROCESS(RetransmitBuffer);
    RetransmitBuffer(sc_module_name name, bool exact = false) : sc_module(name), exact_ack(exact) {
        SC_THREAD(forward);
        sensitive << in.data_written();
        SC_THREAD(handle_acks);
        sensitive << ack_in.data_written();
    }
    void forward() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            buffer.push_back(f);  // 保存副本
            out.write(f);
        }
    }
    void handle_acks() {
        while (true) {
            Flit f = ack_in.read();
            wait(1, SC_NS);
            // 简化: 收到 ACK 就清空缓冲区
            if (!exact_ack) buffer.clear();
            else {
                auto it = std::find_if(buffer.begin(), buffer.end(),
                    [&](const Flit& sent) { return sent.psn == f.psn; });
                if (it != buffer.end()) buffer.erase(it);
            }
        }
    }
};

// ---- RTPH/UTPH Builder: 打上传输头部 (§6.2.1) ----
// RTP (service_mode!=UNO): 设 TPOpcode=RTP_DATA, NLP=RTP, PSN 已在 TP Channel 分配
// UTP (service_mode==UNO): 设 TPOpcode=UTP, NLP=UTP, 无 PSN
SC_MODULE(RtphBuilder) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;

    SC_HAS_PROCESS(RtphBuilder);
    RtphBuilder(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            if (f.service_mode == 3) {  // UNO
                // UTPH: 无 PSN, 无重传
                f.nlp = 0x11;        // UTP
                f.tp_opcode = 0x00;  // UTP
            } else {
                // RTPH: 可靠传输
                f.nlp = 0x10;        // RTP
                f.tp_opcode = 0x01;  // RTP_DATA
            }
            f.syndrome = 0;  // RSPST = 正常
            out.write(f);
        }
    }
};

#endif // NANO_UB_TX_H
