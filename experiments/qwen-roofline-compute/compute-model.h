// SPDX-License-Identifier: GPL-2.0-only
#pragma once
#include <algorithm>
#include <cstdint>
#include <limits>
#include <stdexcept>
namespace expert_roofline {
struct Estimate {
    uint64_t flops=0, weights=0, input=0, intermediate=0, output=0;
    uint64_t activations=0, hbm=0, computePs=0, memoryPs=0, totalPs=0;
};
inline uint64_t Checked(__uint128_t n) {
    if(n>std::numeric_limits<uint64_t>::max()) throw std::overflow_error("roofline integer overflow");
    return uint64_t(n);
}
inline uint64_t Ceil(__uint128_t n,uint64_t d) {
    if(!d) throw std::invalid_argument("roofline zero denominator");
    return Checked(n/d+(n%d!=0));
}
inline Estimate Calculate(uint32_t m,uint32_t h,uint32_t i,uint32_t activationBytes,
                          uint32_t weightElementBytes,uint64_t tflops,uint64_t gbps,uint64_t configuredWeightBytes=0) {
    if(!h||!i||!activationBytes||!weightElementBytes||!tflops||!gbps)
        throw std::invalid_argument("roofline parameters must be positive");
    Estimate x;if(!m)return x;
    x.flops=Checked(__uint128_t(6)*m*h*i);
    x.weights=configuredWeightBytes?configuredWeightBytes:Checked(__uint128_t(3)*h*i*weightElementBytes);
    // Separate gate/up/down GEMMs; fused SiLU+multiply; no inter-GEMM cache.
    x.input=Checked(__uint128_t(2)*m*h*activationBytes);
    x.intermediate=Checked(__uint128_t(6)*m*i*activationBytes);
    x.output=Checked(__uint128_t(m)*h*activationBytes);
    x.activations=Checked(__uint128_t(x.input)+x.intermediate+x.output);
    x.hbm=Checked(__uint128_t(x.weights)+x.activations);
    // TFLOPS and decimal GB/s; time is integer picoseconds, rounded up.
    x.computePs=Ceil(x.flops,tflops);
    x.memoryPs=Ceil(__uint128_t(x.hbm)*1000,gbps);
    x.totalPs=std::max(x.computePs,x.memoryPs);
    if(x.totalPs>=UINT64_C(1000000000000000))throw std::overflow_error("roofline compute bound");
    return x;
}
}
