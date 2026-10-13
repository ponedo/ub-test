#ifndef NANO_ROCE_RX_H
#define NANO_ROCE_RX_H

#include <nano/flit.h>
#include <systemc.h>

// ============================================================
// RoCE RX 流水线元件
//
// Ethernet Decap → QP RX → BTH Parser → Dispatch → Memory
//   → Completion Gen → ACK/NAK Gen → (回 TX)
// ============================================================

// ---- RoceDecap: 剥离以太网封装 ----
SC_MODULE(RoceDecap) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;

    SC_HAS_PROCESS(RoceDecap);
    RoceDecap(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            if (!f.valid || f.eth_type != ROCE_ETHERTYPE) continue;
            out.write(f);
        }
    }
};

// ---- QpRx: 每 QP PSN 验证 + 排序 ----
SC_MODULE(QpRx) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> out;

    uint32_t expected_psn;  // 下一个期望的 PSN

    SC_HAS_PROCESS(QpRx);
    QpRx(sc_module_name name) : sc_module(name), expected_psn(0) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            // PSN 验证: 只接受按序到达 (简化)
            if (f.psn != expected_psn) {
                // 乱序 — 简单丢弃, 依赖重传
                continue;
            }
            expected_psn++;
            out.write(f);
        }
    }
};

// ---- BthParser: 提取 opcode 并路由 ----
SC_MODULE(BthParser) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> data_out;   // 数据包 (WRITE/READ)
    sc_fifo_out<Flit> ack_out;    // ACK 包

    SC_HAS_PROCESS(BthParser);
    BthParser(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            switch (f.tp_opcode) {
                case 0x0A: // RDMA_WRITE_ONLY
                case 0x0C: // RDMA_READ_REQUEST
                    data_out.write(f);
                    break;
                case 0x11: // ACKNOWLEDGE
                    ack_out.write(f);
                    break;
                default:
                    data_out.write(f);
                    break;
            }
        }
    }
};

// ---- Dispatch: 按 opcode 分发到执行单元 ----
SC_MODULE(Dispatch) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> write_req;  // 写请求 → 内存
    sc_fifo_out<Flit> read_req;   // 读请求 → 内存
    sc_fifo_out<Flit> send_req;   // SEND → 接收队列
    sc_fifo_out<Flit> atomic_req; // 原子操作

    SC_HAS_PROCESS(Dispatch);
    Dispatch(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            switch (f.ta_opcode) {
                case 0x03: write_req.write(f); break; // WRITE
                case 0x06: read_req.write(f);  break; // READ
                case 0x00: send_req.write(f);   break; // SEND
                case 0x07: case 0x0B: atomic_req.write(f); break;
                default:   write_req.write(f);   break;
            }
        }
    }
};

// ---- MemoryModel: 模拟目标端内存 ----
SC_MODULE(MemoryModel) {
    sc_fifo_in<Flit>  write_in;
    sc_fifo_out<Flit> write_done;  // 写完成通知
    sc_fifo_in<Flit>  read_in;
    sc_fifo_out<Flit> read_resp;   // 读响应

    uint8_t mem[1024 * 1024];  // 1 MB 模拟内存

    // 直接读写内存 (用于测试预填充和 AtomicALU)
    void write_direct(uint64_t addr, const uint8_t* data, uint32_t len) {
        if (addr + len > sizeof(mem)) len = sizeof(mem) - addr;
        std::memcpy(mem + addr, data, len);
    }
    uint8_t* get_mem_ptr() { return mem; }

    SC_HAS_PROCESS(MemoryModel);
    MemoryModel(sc_module_name name) : sc_module(name) {
        std::memset(mem, 0, sizeof(mem));
        SC_THREAD(handle_writes);
        sensitive << write_in.data_written();
        SC_THREAD(handle_reads);
        sensitive << read_in.data_written();
    }

    void handle_writes() {
        while (true) {
            Flit f = write_in.read();
            wait(1, SC_NS);
            uint64_t addr = f.mem_addr;
            uint32_t len  = f.mem_len;
            if (addr + len > sizeof(mem)) len = sizeof(mem) - addr;
            // 写入 (用模式填充以便验证)
            for (uint32_t i = 0; i < len && i < 16; i++) {
                mem[addr + i] = f.inline_data[i];
            }
            // 通知完成
            Flit done = Flit::make_valid();
            done.ta_opcode = f.ta_opcode;
            done.mem_addr  = addr;
            done.mem_len   = len;
            done.psn       = f.psn;
            done.dst_addr  = f.src_addr;  // 响应路由回发起端
            done.src_addr  = f.dst_addr;
            write_done.write(done);
        }
    }

    void handle_reads() {
        while (true) {
            Flit f = read_in.read();
            wait(1, SC_NS);
            uint64_t addr = f.mem_addr;
            uint32_t len  = f.mem_len;
            if (addr + len > sizeof(mem)) len = sizeof(mem) - addr;
            // 构造读响应
            Flit resp = Flit::make_valid();
            resp.is_response = true;      // 标记为响应包
            resp.tp_opcode  = 0x10;       // RDMA_READ_RESPONSE_ONLY
            resp.ta_opcode  = 0x12;       // Read Response
            resp.mem_addr  = addr;
            resp.mem_len   = len;
            resp.psn       = f.psn;
            resp.dst_addr  = f.src_addr;
            resp.src_addr  = f.dst_addr;
            for (uint32_t i = 0; i < len && i < 16; i++) {
                resp.inline_data[i] = mem[addr + i];
            }
            resp.inline_len = (len < 16) ? len : 16;
            read_resp.write(resp);
        }
    }

    // 辅助: 读内存 (用于测试验证)
    uint8_t read_byte(uint64_t addr) const {
        if (addr < sizeof(mem)) return mem[addr];
        return 0;
    }
};

// ---- CompletionGen: 构建 CQE ----
SC_MODULE(CompletionGen) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> cqe_out;

    SC_HAS_PROCESS(CompletionGen);
    CompletionGen(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            // 简单的 CQE: 转发为完成通知
            cqe_out.write(f);
        }
    }
};

// ---- AckGen: 生成 ACK/NAK 响应 (BTH+AETH) ----
SC_MODULE(AckGen) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> ack_out;

    SC_HAS_PROCESS(AckGen);
    AckGen(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            // 构造 ACK 响应
            Flit ack = Flit::make_valid();
            ack.tp_opcode = 0x11;        // ACKNOWLEDGE
            ack.syndrome  = 0x00;        // ACK (success)
            ack.psn       = f.psn;
            ack.dst_addr  = f.dst_addr;  // 回给发起端
            ack.src_addr  = f.src_addr;
            ack.eth_type  = ROCE_ETHERTYPE;
            ack.udp_dport = ROCE_UDP_DPORT;
            ack.is_response = true;
            ack_out.write(ack);
        }
    }
};

// ---- RecvQueue: SEND 接收队列 ----
SC_MODULE(RecvQueue) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> done_out;   // 完成通知 → CompletionGen

    std::vector<Flit> messages;   // 收到的消息

    SC_HAS_PROCESS(RecvQueue);
    RecvQueue(sc_module_name name) : sc_module(name) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }
    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            messages.push_back(f);
            // 通知完成
            Flit done = Flit::make_valid();
            done.ta_opcode = 0x00;  // SEND
            done.psn       = f.psn;
            done.dst_addr  = f.src_addr;
            done.src_addr  = f.dst_addr;
            done_out.write(done);
        }
    }
};

// ---- AtomicALU: 原子操作执行单元 ----
SC_MODULE(AtomicALU) {
    sc_fifo_in<Flit>  in;
    sc_fifo_out<Flit> resp_out;   // 响应 → (回 TX 管线)

    uint8_t* mem;  // 指向 MemoryModel 的内存

    SC_HAS_PROCESS(AtomicALU);
    AtomicALU(sc_module_name name, uint8_t* m = nullptr)
        : sc_module(name), mem(m) {
        SC_THREAD(process);
        sensitive << in.data_written();
    }

    void process() {
        while (true) {
            Flit f = in.read();
            wait(1, SC_NS);
            uint64_t addr = f.mem_addr;

            Flit resp = Flit::make_valid();
            resp.is_response = true;
            resp.ta_opcode = 0x13;  // Atomic Response
            resp.psn       = f.psn;
            resp.dst_addr  = f.src_addr;
            resp.src_addr  = f.dst_addr;
            resp.mem_addr  = addr;
            resp.mem_len   = 8;

            if (mem && addr + 8 <= 1024*1024) {
                uint64_t old_val;
                std::memcpy(&old_val, mem + addr, 8);

                if (f.ta_opcode == 0x07) {  // CAS
                    uint64_t compare = f.operand_b;
                    uint64_t swap    = f.operand_a;
                    if (old_val == compare) {
                        std::memcpy(mem + addr, &swap, 8);
                    }
                    resp.operand_a = old_val;  // 返回旧值
                } else if (f.ta_opcode == 0x0B) {  // FAA
                    uint64_t add = f.operand_a;
                    uint64_t new_val = old_val + add;
                    std::memcpy(mem + addr, &new_val, 8);
                    resp.operand_a = old_val;  // 返回旧值
                }
                std::memcpy(resp.inline_data, &resp.operand_a, 8);
                resp.inline_len = 8;
            }

            resp_out.write(resp);
        }
    }
};

#endif // NANO_ROCE_RX_H
