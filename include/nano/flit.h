#ifndef NANO_FLIT_H
#define NANO_FLIT_H

#include "common.h"
#include <array>
#include <cstring>
#include <iostream>
#include <ostream>

// ============================================================
// Flit — 内部 flit 元数据 (64 字节, 4 × 64-bit lanes)
// ============================================================
//
// Lane 0: 网络层摘要 (UB: NTH, RoCE: BTH 摘要)
// Lane 1: 传输头字段 (UB: RTPH, RoCE: PSN/syndrome)
// Lane 2: 标志位
// Lane 3: 事务头字段 (UB: BTAH, RoCE: cookies)
//
// + 扩展数据区域 (地址/长度/操作数)
// ============================================================

struct Flit {
    // Simulator-only correlation token, never a UB wire-header field.
    // Set by the fair scheduler and echoed by experimental completions.
    uint64_t sim_wr_id;

    // ---- Lane 0: 网络层摘要 ----
    uint32_t dst_addr;    // DCNA[23:0] / DestQP[23:0]
    uint32_t src_addr;    // SCNA[23:0] / SrcQP
    uint8_t  nlp;         // NLP / opcode
    bool     valid;       // flit 有效

    // ---- Lane 1: 传输头字段 ----
    uint32_t psn;         // 包序列号 (24-bit)
    uint32_t tpmsn;       // 传输消息序列号 (24-bit)
    uint8_t  tp_opcode;   // TPOpcode / BTH opcode
    uint8_t  syndrome;    // RSPST / AETH syndrome

    // ---- Lane 2: 标志位 ----
    uint8_t  service_mode; // ROI/ROT/ROL/UNO
    bool     is_response;  // 是否是响应包
    bool     is_last;      // A/F bit — 事务最后一个包
    bool     fence;        // Fence 位 — 阻塞后续 WR

    // ---- Lane 3: 事务头字段 ----
    uint8_t  ta_opcode;   // TAOpcode
    uint16_t tassn;       // INI_TASSN — 事务序列号
    uint8_t  odr;         // ODR[1:0] — 执行顺序标签
    uint32_t rc_id;       // INI_RC_ID — 发起端资源标识符

    // ---- 扩展数据 ----
    uint64_t mem_addr;    // 内存地址
    uint32_t mem_len;     // 数据长度
    uint32_t rkey;        // 远端 key
    uint64_t operand_a;   // swap/add 操作数
    uint64_t operand_b;   // compare 操作数 (CAS only)

    // ---- 以太网封装用 ----
    uint16_t eth_type;    // Ethertype
    uint16_t udp_dport;   // UDP 目标端口 (RoCE)

    // ---- 原始负载数据 (小数据内联, 大数据走扩展) ----
    uint8_t  inline_data[16]; // 小负载内联
    uint8_t  inline_len;      // 内联数据长度

    // 默认构造函数
    Flit() { std::memset(this, 0, sizeof(*this)); }

    // 简便构造: 设置 valid
    static Flit make_valid() {
        Flit f;
        f.valid = true;
        return f;
    }

    // 打印摘要
    void dump(std::ostream& os = std::cout) const {
        os << "Flit{valid=" << valid
           << " dst=0x" << std::hex << dst_addr << std::dec
           << " src=0x" << std::hex << src_addr << std::dec
           << " nlp=0x" << std::hex << (int)nlp << std::dec
           << " psn=" << psn
           << " tp_op=0x" << std::hex << (int)tp_opcode << std::dec;
        if (ta_opcode) os << " ta_op=0x" << std::hex << (int)ta_opcode << std::dec;
        if (mem_len)   os << " mem[0x" << std::hex << mem_addr << std::dec
                          << "+" << mem_len << "]";
        os << "}";
    }
};

// operator<< 重载 (SystemC sc_fifo 需要)
inline std::ostream& operator<<(std::ostream& os, const Flit& f) {
    f.dump(os);
    return os;
}

// 确保 Flit 大小合理
static_assert(sizeof(Flit) >= FLIT_BYTES, "Flit too small");

#endif // NANO_FLIT_H
