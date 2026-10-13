#ifndef NANO_EXPERIMENTAL_SERIALIZED_LINK_H
#define NANO_EXPERIMENTAL_SERIALIZED_LINK_H
#include <nano/flit.h>
#include <systemc.h>
#include <functional>
#include <vector>
#include <algorithm>

namespace nano_ub_experiment {
// Experiment-only byte transport. These 64-byte chunks are serializer words,
// NOT independent UB transport packets. One WR remains one PSN/transaction.
// Header cost is an assumed 64 B, not a UB encoder or hardware timing claim.
struct Delivery {
    Flit flit;
    sc_time ready;
};
inline std::ostream& operator<<(std::ostream& o, const Delivery& d) { return o << d.flit; }
SC_MODULE(SerializedLink) {
    sc_fifo_in<Flit> a_in, b_in;
    sc_fifo_out<Flit> a_out, b_out;
    sc_fifo<Delivery> ab_flight, ba_flight;
    double gbps;
    sc_time propagation;
    std::function<std::vector<uint8_t>(const Flit&)> source_payload;
    std::function<void(const Flit&, const std::vector<uint8_t>&)> received_payload;
    std::function<void(const char*, const Flit&, unsigned, unsigned)> trace;
    SC_HAS_PROCESS(SerializedLink);
    SerializedLink(sc_module_name name, double rate = 100.0)
        : sc_module(name), ab_flight("ab_flight", 128), ba_flight("ba_flight", 128),
          gbps(rate), propagation(50, SC_NS) {
        SC_THREAD(ab_serialize); SC_THREAD(ba_serialize);
        SC_THREAD(ab_deliver); SC_THREAD(ba_deliver);
    }
    void serialize(bool forward) {
        auto& input = forward ? a_in : b_in;
        auto& flight = forward ? ab_flight : ba_flight;
        while (true) {
            Flit f = input.read();
            auto data = forward ? source_payload(f) : std::vector<uint8_t>{};
            std::vector<uint8_t> copied;
            const unsigned wire_bytes = 64 + data.size();
            trace(forward ? "tx_start" : "ack_tx_start", f, wire_bytes, 0);
            for (unsigned off = 0; off < wire_bytes; off += 64) {
                unsigned n = std::min(64u, wire_bytes - off);
                wait(sc_time(8.0 * n / gbps, SC_NS));
                if (forward && off >= 64)
                    copied.insert(copied.end(), data.begin() + off - 64,
                                  data.begin() + off - 64 + n);
                trace(forward ? "tx_chunk" : "ack_chunk", f, n, off);
            }
            if (forward) received_payload(f, copied);
            trace(forward ? "tx_end" : "ack_tx_end", f, wire_bytes, 0);
            flight.write({f, sc_time_stamp() + propagation});
        }
    }
    void deliver(bool forward) {
        auto& flight = forward ? ab_flight : ba_flight;
        auto& output = forward ? b_out : a_out;
        while (true) {
            auto d = flight.read();
            if (d.ready > sc_time_stamp()) wait(d.ready - sc_time_stamp());
            trace(forward ? "rx_wire" : "ack_rx_wire", d.flit, 0, 0);
            output.write(d.flit);
        }
    }
    void ab_serialize() { serialize(true); }
    void ba_serialize() { serialize(false); }
    void ab_deliver() { deliver(true); }
    void ba_deliver() { deliver(false); }
};
} // namespace
#endif
