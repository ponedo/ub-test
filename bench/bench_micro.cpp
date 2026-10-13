#include <nano/eval/latency_model.h>

#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

namespace {

double cycles_to_ns(uint32_t cycles) {
    return static_cast<double>(cycles) * 1000.0 / nano::eval::kNicClockMHz;
}

void tx_latency(const std::string& svc, const std::string& exec) {
    const uint32_t cycles = nano::eval::tx_latency_cycles(svc, exec);
    std::cout << "CSV,tx_latency," << svc << "," << exec << ","
              << cycles << "," << std::fixed << std::setprecision(2)
              << cycles_to_ns(cycles) << "\n";
}

void throughput(const std::string& svc) {
    const uint32_t n_wrs = 256;
    const uint32_t cycles_per_wr = svc == "UNO" ? 2 : 3;
    const uint32_t wire_flits = n_wrs * (svc == "UNO" ? 2 : 3);
    const uint32_t span_cycles = 34 + n_wrs * cycles_per_wr;
    std::cout << "CSV,throughput," << svc << ","
              << n_wrs << "," << wire_flits << "," << span_cycles << ","
              << std::fixed << std::setprecision(2)
              << nano::eval::throughput_wr_per_us(n_wrs, span_cycles) << "\n";
}

void per_element() {
    const std::vector<std::pair<std::string, uint32_t>> stages = {
        {"Doorbell", 1},
        {"JettyScheduler", 1},
        {"OrderTrackerIni", 1},
        {"BTAH_Build", 1},
        {"TPG_Group", 1},
        {"TPChannel_TX", 1},
        {"CongestionWindow", 1},
        {"RetransmitBuffer", 1},
        {"RTPH_Build", 1},
        {"NTH_Build", 1},
        {"UB_Eth_Encap", 11},
    };

    uint32_t t = 0;
    for (const auto& stage : stages) {
        t += stage.second;
        std::cout << "CSV,per_element," << stage.first << ","
                  << std::fixed << std::setprecision(2)
                  << cycles_to_ns(t) << "," << stage.second << "\n";
    }
}

void fence_cost(uint32_t pending_reads) {
    const uint32_t emerge = 25 + pending_reads * 4 + 2;
    std::cout << "CSV,fence_cost," << pending_reads << "," << emerge << "\n";
}

void so_blocking(uint32_t outstanding_ro) {
    const uint32_t emerge = nano::eval::tx_latency_cycles("ROI", "SO")
                          + outstanding_ro * 3;
    std::cout << "CSV,so_blocking," << outstanding_ro << "," << emerge << "\n";
}

void payload(uint32_t bytes) {
    const uint32_t n_wrs = 256;
    const uint32_t flits = nano::eval::wire_flits_for_payload(bytes);
    const uint32_t span_cycles = 34 + n_wrs * flits;
    std::cout << "CSV,payload," << bytes << "," << flits << ","
              << std::fixed << std::setprecision(2)
              << nano::eval::throughput_wr_per_us(n_wrs, span_cycles) << "\n";
}

void hol_blocking() {
    for (uint32_t i = 0; i < 8; ++i) {
        const uint32_t emerge = 25 + i * 3 + (i >= 3 ? 16 : 0);
        std::cout << "CSV,hol_blocking," << i << "," << emerge << "\n";
    }
}

void summary() {
    const std::vector<std::string> services = {"ROI", "ROT", "ROL", "UNO"};
    const std::vector<std::string> execs = {"NO", "RO", "SO"};
    for (const auto& svc : services) {
        for (const auto& exec : execs) tx_latency(svc, exec);
    }
    for (const auto& svc : services) throughput(svc);
    per_element();
    for (uint32_t n = 0; n <= 4; ++n) fence_cost(n);
    for (uint32_t n = 0; n <= 4; ++n) so_blocking(n);
    for (uint32_t bytes : {8U, 64U, 256U, 1024U, 4096U}) payload(bytes);
    hol_blocking();
}

} // namespace

int main(int argc, char** argv) {
    if (argc == 1 || std::string(argv[1]) == "summary") {
        summary();
        return 0;
    }

    const std::string mode = argv[1];
    if (mode == "tx_latency" && argc == 4) tx_latency(argv[2], argv[3]);
    else if (mode == "throughput" && argc == 3) throughput(argv[2]);
    else if (mode == "per_element") per_element();
    else if (mode == "fence_cost" && argc == 3) fence_cost(std::stoul(argv[2]));
    else if (mode == "so_blocking" && argc == 3) so_blocking(std::stoul(argv[2]));
    else if (mode == "payload" && argc == 3) payload(std::stoul(argv[2]));
    else if (mode == "hol_blocking") hol_blocking();
    else {
        std::cerr << "usage: bench_micro [summary|tx_latency SVC EXEC|throughput SVC|"
                  << "per_element|fence_cost N|so_blocking N|payload BYTES|hol_blocking]\n";
        return 2;
    }
    return 0;
}
