#include <nano/eth_link.h>
#include <iostream>

EtherLink::EtherLink(sc_module_name name,
                     sc_time delay_,
                     double jitter_,
                     double loss_rate_,
                     unsigned seed)
    : sc_module(name)
    , delay(delay_)
    , jitter(jitter_)
    , loss_rate(loss_rate_)
    , rng_(seed)
    , dist_(0.0, 1.0)
{
    SC_THREAD(forward_a_to_b);
    sensitive << a_to_link.data_written();
    dont_initialize();

    SC_THREAD(forward_b_to_a);
    sensitive << b_to_link.data_written();
    dont_initialize();
}

sc_time EtherLink::apply_jitter(sc_time base) {
    if (jitter == 0.0) return base;
    double r = dist_(rng_) * 2.0 - 1.0;  // [-1, 1]
    double factor = 1.0 + r * jitter;
    if (factor < 0.0) factor = 0.0;
    return base * factor;
}

void EtherLink::forward_a_to_b() {
    while (true) {
        Flit flit = a_to_link.read();

        // 丢包判定
        if (dist_(rng_) < loss_rate) {
            continue;  // 丢掉
        }

        // 延迟
        wait(apply_jitter(delay));

        // 转发
        link_to_b.write(flit);
    }
}

void EtherLink::forward_b_to_a() {
    while (true) {
        Flit flit = b_to_link.read();

        if (dist_(rng_) < loss_rate) {
            continue;
        }

        wait(apply_jitter(delay));

        link_to_a.write(flit);
    }
}
