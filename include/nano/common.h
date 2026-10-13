#ifndef NANO_COMMON_H
#define NANO_COMMON_H

#include <cstddef>
#include <cstdint>

// ============================================================
// Nano-UB: 公共类型与常量定义
// ============================================================

// --- UB 协议常量 ---
constexpr uint16_t UB_ETHERTYPE  = 0x88B5;  // 本地实验用
constexpr uint16_t ROCE_ETHERTYPE = 0x8915; // RoCEv2
constexpr uint16_t ROCE_UDP_DPORT = 4791;

// --- 内部 flit 元数据大小 ---
constexpr size_t FLIT_BYTES = 64;

#endif // NANO_COMMON_H
