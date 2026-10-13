#ifndef NANO_ROCE_TX_H
#define NANO_ROCE_TX_H

#include <nano/flit.h>
#include <systemc.h>

// ============================================================
// RoCE TX 流水线元件
//
// Doorbell → QP TX → BTH Builder → Ethernet Encap
// ============================================================

// ---- Doorbell: 验证 WR 并转发 ----
SC_MODULE(Doorbell) {
    sc_fifo_in<Flit>  wr_in;   // 主机 WR 输入
    sc_fifo_out<Flit> wr_out;  // 验证后输出

    SC_HAS_PROCESS(Doorbell);
    Doorbell(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << wr_in.data_written();
    }
    void process() {
        while (true) {
            Flit f = wr_in.read();
            wait(1, SC_NS);
            if (!f.valid) continue;  // 丢弃无效
            // 验证: 必须指定 opcode 和地址
            if (f.ta_opcode == 0 && f.mem_len == 0) continue;
            wr_out.write(f);
        }
    }
};

// ---- QP TX: PSN 分配 + QPN 打标 ----
SC_MODULE(QpTx) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;

    uint32_t next_psn;   // 下一个 PSN
    uint32_t src_qp;     // 源 QP 号
    uint32_t dest_qp;    // 目标 QP 号

    SC_HAS_PROCESS(QpTx);
    QpTx(sc_module_name name, uint32_t sqp = 1, uint32_t dqp = 1)
        : sc_module(name), next_psn(0), src_qp(sqp), dest_qp(dqp) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            f.psn = next_psn++;  // 分配 PSN
            f.src_addr = src_qp; // 源 QPN
            f.dst_addr = dest_qp;// 目标 QPN
            out.write(f);
        }
    }
};

// ---- BTH Builder: 构建 BTH 头部 ----
SC_MODULE(BthBuilder) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;

    uint16_t pkey;

    SC_HAS_PROCESS(BthBuilder);
    BthBuilder(sc_module_name name, uint16_t pk = 0xFFFF)
        : sc_module(name), pkey(pk) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            // 如果是 ACK 或 Read Response, 保留已有 tp_opcode
            if (f.is_response) {
                f.eth_type  = ROCE_ETHERTYPE;
                f.udp_dport = ROCE_UDP_DPORT;
                out.write(f);
                continue;
            }

            // 根据 ta_opcode 设置 BTH opcode
            switch (f.ta_opcode) {
                case 0x03: f.tp_opcode = 0x0A; break; // WRITE → RDMA_WRITE_ONLY
                case 0x06: f.tp_opcode = 0x0C; break; // READ  → RDMA_READ_REQUEST
                case 0x07: f.tp_opcode = 0x13; break; // CAS   → COMPARE_SWAP
                case 0x0B: f.tp_opcode = 0x14; break; // FAA   → FETCH_ADD
                case 0x00: f.tp_opcode = 0x04; break; // SEND  → SEND_ONLY
                default:   f.tp_opcode = 0x0A; break; // 默认 WRITE
            }

            // 设置 RoCE 标志
            f.eth_type  = ROCE_ETHERTYPE;
            f.udp_dport = ROCE_UDP_DPORT;
            f.nlp       = f.tp_opcode;  // 复用为 opcode 标记

            out.write(f);
        }
    }
};

// ---- Ethernet Encap: 封装以太网帧 ----
SC_MODULE(RoceEncap) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;

    uint64_t src_mac;
    uint64_t dst_mac;

    SC_HAS_PROCESS(RoceEncap);
    RoceEncap(sc_module_name name,
              uint64_t smac = 0xAABBCCDDEE01ULL,
              uint64_t dmac = 0xAABBCCDDEE02ULL)
        : sc_module(name), src_mac(smac), dst_mac(dmac) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(4, SC_NS);  // 4 cy: smaller RoCE header
            // 以太网封装: flit 已携带所有字段
            // 这里仅标记完成封装
            out.write(f);
        }
    }
};

#endif // NANO_ROCE_TX_H
