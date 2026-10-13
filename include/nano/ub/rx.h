#ifndef NANO_UB_RX_H
#define NANO_UB_RX_H

#include <nano/flit.h>
#include <systemc.h>
#include <functional>

// ============================================================
// UB RX 流水线元件 — §8.3 Load/Store (TP Bypass)
//
// UB Decap → NTH Parser → BTAH Parser → Memory / Completion
// ============================================================

// ---- UB Decap: 剥离以太网帧 ----
SC_MODULE(UbDecap) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;

    SC_HAS_PROCESS(UbDecap);
    UbDecap(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            if (!f.valid || f.eth_type != UB_ETHERTYPE) continue;
            out.write(f);
        }
    }
};

// ---- NTH Parser: 按 NLP 路由 ----
// TP_BYPASS (0x01) → bypass transport, 直接送事务层
// RTP (0x10) → 可靠传输 (M09+)
// UTP (0x11) → 不可靠传输 (M09+)
SC_MODULE(NthParser) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> bypass_out;  // TP_BYPASS → 直接送 BTAH Parser
    sc_fifo_out<Flit> tp_out;      // RTP/UTP → 送传输层 (预留)

    SC_HAS_PROCESS(NthParser);
    NthParser(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            switch (f.nlp) {
                case 0x01: // TP_BYPASS
                    bypass_out.write(f);
                    break;
                default:
                    tp_out.write(f);
                    break;
            }
        }
    }
};

// ---- BTAH Parser: 分离请求和响应 ----
SC_MODULE(BtahParser) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> req_out;   // 请求 → 执行单元
    sc_fifo_out<Flit> resp_out;  // 响应 → 完成处理

    SC_HAS_PROCESS(BtahParser);
    BtahParser(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            // 判断是请求还是响应
            // Read(0x06)/Write(0x03)/CAS(0x07) 等是请求
            // Read Response(0x12)/Atomic Resp(0x13) 是响应
            switch (f.ta_opcode) {
                case 0x11: // TAACK (WRITE/SEND completion)
                case 0x12: // Read Response
                case 0x13: // Atomic Response
                    resp_out.write(f);
                    break;
                default:
                    req_out.write(f);
                    break;
            }
        }
    }
};

// ---- UB Memory: UB Load/Store 内存模型 ----
SC_MODULE(UbMemory) {
    sc_fifo_in<Flit>  req_in;    // 请求 (Read/Write)
    sc_fifo_out<Flit> resp_out;  // 响应 (Read Response)

    // Optional experiment hooks; default memory behavior remains unchanged.
    std::function<void(const Flit&, uint8_t*)> bulk_write;
    bool complete_writes = false;
    uint8_t mem[1024 * 1024];  // 1 MB

    // 直接写内存 (测试用)
    void write_direct(uint64_t addr, const uint8_t* data, uint32_t len) {
        if (addr + len > sizeof(mem)) len = sizeof(mem) - addr;
        std::memcpy(mem + addr, data, len);
    }
    uint8_t* get_mem_ptr() { return mem; }

    SC_HAS_PROCESS(UbMemory);
    UbMemory(sc_module_name name) : sc_module(name) {
        std::memset(mem, 0, sizeof(mem));
        SC_THREAD(process);
        sensitive << req_in.data_written();
    }
    void process() {
        while (true) {
            Flit f = req_in.read();
            wait(4, SC_NS);  // 4 cy: DRAM access
            uint64_t addr = f.mem_addr;
            uint32_t len  = f.mem_len;
            if (addr + len > sizeof(mem)) len = sizeof(mem) - addr;

            if (f.ta_opcode == 0x03) {  // Write (Store)
                for (uint32_t i = 0; i < len && i < 16; i++) {
                    mem[addr + i] = f.inline_data[i];
                }
                if (bulk_write) bulk_write(f, mem);
                if (complete_writes) resp_out.write(f);
                // Default Store has no response.
            } else if (f.ta_opcode == 0x06) {  // Read (Load)
                Flit resp = Flit::make_valid();
                resp.is_response = true;
                resp.ta_opcode = 0x12;   // Read Response
                resp.mem_addr  = addr;
                resp.mem_len   = len;
                resp.psn       = f.psn;
                resp.tassn     = f.tassn;
                resp.dst_addr  = f.src_addr;  // 路由回发起端
                resp.src_addr  = f.dst_addr;
                resp.nlp       = f.nlp;
                resp.eth_type  = UB_ETHERTYPE;
                for (uint32_t i = 0; i < len && i < 16; i++) {
                    resp.inline_data[i] = mem[addr + i];
                }
                resp.inline_len = (len < 16) ? len : 16;
                resp_out.write(resp);
            }
        }
    }
};

// ============================================================
// UB URMA RX 流水线元件
//
// NthParser(tp_out) → RTPH Parser → TP Channel RX → PSN Reorder
//   → BTAH Parser → Order Tracker(TGT) → Trans Dispatch
//   → Memory → Completion Gen → Completion Reorder → TAACK Gen
// ============================================================

// ---- RTPH Parser: 分离数据包 vs ACK 包 ----
SC_MODULE(RtphParser) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> data_out;   // RTP 数据包
    sc_fifo_out<Flit> ack_out;    // TPACK/TPNAK

    SC_HAS_PROCESS(RtphParser);
    RtphParser(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            switch (f.tp_opcode) {
                case 0x02: // TPACK/TPNAK
                case 0x05: // TPSACK
                    ack_out.write(f);
                    break;
                default:
                    data_out.write(f);  // RTP_DATA (0x01) 等
                    break;
            }
        }
    }
};

// ---- TP Channel RX: 每主机 PSN 窗口验证 ----
SC_MODULE(TpChannelRx) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;

    uint32_t expected_psn;

    SC_HAS_PROCESS(TpChannelRx);
    TpChannelRx(sc_module_name name) : sc_module(name), expected_psn(0) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            if (f.psn != expected_psn) continue;  // 简化: 丢弃乱序
            expected_psn++;
            out.write(f);
        }
    }
};

// ---- PSN Reorder: 乱序重组缓冲区 ----
SC_MODULE(PsnReorder) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;

    SC_HAS_PROCESS(PsnReorder);
    PsnReorder(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            // 简化: 按序到达, 直接透传
            out.write(f);
        }
    }
};

// ---- Order Tracker (Target): ROT 模式 SO 门控 (§7.3.3.3) ----
// 目标端维护 TASSN 记录板: 按序提交事务
// SO 操作必须等待前序所有 TASSN 到达
SC_MODULE(OrderTrackerTgt) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;

    uint16_t next_tassn;  // 下一个期望的 TASSN

    SC_HAS_PROCESS(OrderTrackerTgt);
    OrderTrackerTgt(sc_module_name name)
        : sc_module(name), next_tassn(1) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            if (f.service_mode == 2) {  // ROT: 按 TASSN 顺序
                if (f.tassn != next_tassn) {
                    // 乱序 — 丢弃, 依赖重传
                    continue;
                }
                next_tassn++;
            }
            out.write(f);
        }
    }
};

// ---- Transaction Dispatch: 按 opcode 分发 ----
SC_MODULE(TransDispatch) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> write_out;   // HBM Write
    sc_fifo_out<Flit> read_out;    // HBM Read
    sc_fifo_out<Flit> atomic_out;  // Atomic ALU
    sc_fifo_out<Flit> send_out;    // Jetty Recv

    SC_HAS_PROCESS(TransDispatch);
    TransDispatch(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            switch (f.ta_opcode) {
                case 0x03: write_out.write(f); break;  // WRITE
                case 0x06: read_out.write(f);  break;  // READ
                case 0x07: case 0x0B: atomic_out.write(f); break;
                case 0x00: send_out.write(f);   break;  // SEND
                default:   write_out.write(f);   break;
            }
        }
    }
};

// ---- Completion Gen: 将请求翻转为 ATAH 响应 ----
SC_MODULE(UbCompletionGen) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> cqe_out;   // 完成通知 → TAACK Gen

    SC_HAS_PROCESS(UbCompletionGen);
    UbCompletionGen(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            // 构造 ATAH 响应
            Flit resp = Flit::make_valid();
            resp.is_response = true;
            resp.ta_opcode = 0x11;   // TAACK
            resp.tassn     = f.tassn;
            resp.psn       = f.psn;
            resp.rc_id     = f.rc_id;
            resp.sim_wr_id = f.sim_wr_id;
            resp.mem_addr  = f.mem_addr;
            resp.mem_len   = f.mem_len;
            resp.odr       = f.odr;
            resp.dst_addr  = f.src_addr;
            resp.src_addr  = f.dst_addr;
            resp.nlp       = 0x10;   // RTP
            resp.eth_type  = UB_ETHERTYPE;
            resp.syndrome  = 0;       // 成功
            cqe_out.write(resp);
        }
    }
};

// ---- Completion Reorder: 按序/乱序完成缓冲区 ----
SC_MODULE(UbCompletionReorder) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;

    SC_HAS_PROCESS(UbCompletionReorder);
    UbCompletionReorder(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            out.write(f);  // 简化: 直接透传
        }
    }
};

// ---- TAACK Gen: 构建事务 ACK (§7.4) ----
// ROI/ROT 模式下生成 TAACK, ROL 模式下融合到 TPACK
SC_MODULE(TaackGen) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> taack_out;  // TAACK 响应 (回 TX)

    SC_HAS_PROCESS(TaackGen);
    TaackGen(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            // TAACK 已在 CompletionGen 中构造, 这里直接转发
            taack_out.write(f);
        }
    }
};

#endif // NANO_UB_RX_H
