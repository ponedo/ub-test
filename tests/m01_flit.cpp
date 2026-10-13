#include <nano/flit.h>
#include <cassert>
#include <iostream>

int main() {
    std::cout << "=== M01: Flit 单元测试 ===" << std::endl;

    // 1. 默认构造: 全部清零
    {
        Flit f;
        assert(f.valid == false);
        assert(f.psn == 0);
        assert(f.mem_addr == 0);
        std::cout << "  [PASS] 默认构造: 全零" << std::endl;
    }

    // 2. make_valid
    {
        Flit f = Flit::make_valid();
        assert(f.valid == true);
        std::cout << "  [PASS] make_valid" << std::endl;
    }

    // 3. 字段赋值 (模拟 UB Load/Store 读请求)
    {
        Flit f = Flit::make_valid();
        f.ta_opcode = 0x06;  // Read
        f.mem_addr  = 0x1000;
        f.mem_len   = 8;
        f.src_addr  = 0x000001;
        f.dst_addr  = 0x000002;
        f.nlp       = 0x01;  // TP_BYPASS
        f.eth_type  = UB_ETHERTYPE;

        assert(f.ta_opcode == 0x06);
        assert(f.mem_addr  == 0x1000);
        assert(f.mem_len   == 8);
        assert(f.src_addr  == 0x000001);
        assert(f.dst_addr  == 0x000002);
        assert(f.nlp       == 0x01);
        assert(f.eth_type  == UB_ETHERTYPE);

        std::cout << "  [PASS] 字段赋值 (UB Load/Store)" << std::endl;
        f.dump(std::cout);
        std::cout << std::endl;
    }

    // 4. 字段赋值 (模拟 RoCE RDMA WRITE)
    {
        Flit f = Flit::make_valid();
        f.ta_opcode = 0x03;       // WRITE
        f.mem_addr  = 0x2000;
        f.mem_len   = 64;
        f.dst_addr  = 1;          // DestQP
        f.tp_opcode = 0x0A;       // RDMA_WRITE_ONLY
        f.eth_type  = ROCE_ETHERTYPE;
        f.udp_dport = ROCE_UDP_DPORT;
        f.rkey      = 0x5678;

        assert(f.ta_opcode == 0x03);
        assert(f.mem_addr  == 0x2000);
        assert(f.mem_len   == 64);
        assert(f.dst_addr  == 1);
        assert(f.tp_opcode == 0x0A);
        assert(f.eth_type  == ROCE_ETHERTYPE);
        assert(f.udp_dport == ROCE_UDP_DPORT);
        assert(f.rkey      == 0x5678);

        std::cout << "  [PASS] 字段赋值 (RoCE RDMA WRITE)" << std::endl;
        f.dump(std::cout);
        std::cout << std::endl;
    }

    // 5. 原子操作字段
    {
        Flit f = Flit::make_valid();
        f.ta_opcode = 0x07;       // ATOMIC_CAS
        f.operand_a = 0x42;       // swap
        f.operand_b = 0x99;       // compare
        f.mem_addr  = 0x3000;

        assert(f.operand_a == 0x42);
        assert(f.operand_b == 0x99);

        std::cout << "  [PASS] 原子操作字段" << std::endl;
    }

    // 6. ODR 标签
    {
        Flit f = Flit::make_valid();
        f.odr = 0;  // NO
        assert(f.odr == 0);
        f.odr = 1;  // RO
        assert(f.odr == 1);
        f.odr = 2;  // SO
        assert(f.odr == 2);

        std::cout << "  [PASS] ODR 执行顺序标签" << std::endl;
    }

    std::cout << "=== 全部通过 (" << sizeof(Flit) << " B) ===" << std::endl;
    return 0;
}
