#include <nano/eval/latency_model.h>

#include <iomanip>
#include <iostream>
#include <vector>

using nano::eval::HostPathParams;
using nano::eval::LatencyBreakdown;
using nano::eval::RawPathParams;

namespace {

void print_row(const LatencyBreakdown& b) {
    std::cout << std::left << std::setw(14) << b.stack
              << std::right << std::setw(10) << std::fixed << std::setprecision(1)
              << b.raw_nic_ns
              << std::setw(10) << b.host_ns
              << std::setw(10) << b.total_ns
              << std::setw(10) << std::setprecision(0) << b.cycles
              << "\n";
}

} // namespace

int main(int argc, char** argv) {
    RawPathParams raw;
    HostPathParams host;

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        auto next = [&]() -> const char* {
            if (i + 1 >= argc) {
                std::cerr << "missing value for " << arg << "\n";
                std::exit(2);
            }
            return argv[++i];
        };
        if (arg == "--payload-bytes") raw.payload_bytes = std::stoul(next());
        else if (arg == "--link-delay-ns") raw.link_delay_ns = std::stod(next());
        else if (arg == "--ub-raw-ns") raw.ub_loadstore_raw_ns = std::stod(next());
        else if (arg == "--roce-raw-ns") raw.roce_raw_ns = std::stod(next());
        else if (arg == "--pcie-mmio-ns") host.pcie_mmio_ns = std::stod(next());
        else if (arg == "--pcie-dma-read-ns") host.pcie_dma_read_wqe_ns = std::stod(next());
        else if (arg == "--pcie-dma-write-ns") host.pcie_dma_write_cqe_ns = std::stod(next());
        else if (arg == "--cqe-poll-ns") host.cqe_poll_ns = std::stod(next());
        else if (arg == "--onchip-bus-ns") host.onchip_bus_ns = std::stod(next());
        else {
            std::cerr << "unknown option: " << arg << "\n";
            return 2;
        }
    }

    std::vector<LatencyBreakdown> rows = {
        nano::eval::ub_loadstore_latency(raw, host),
        nano::eval::ub_urma_latency(raw, host),
        nano::eval::roce_bf_latency(raw, host),
        nano::eval::roce_dma_latency(raw, host),
    };

    std::cout << "=== Nano-UB host-visible latency model ===\n";
    std::cout << "payload=" << raw.payload_bytes
              << "B link=" << raw.link_delay_ns
              << "ns pipeline_ub_ls=" << raw.ub_loadstore_raw_ns
              << "ns pipeline_roce=" << raw.roce_raw_ns << "ns\n\n";
    std::cout << std::left << std::setw(14) << "stack"
              << std::right << std::setw(10) << "pipe_ns"
              << std::setw(10) << "host_ns"
              << std::setw(10) << "total_ns"
              << std::setw(10) << "cycles"
              << "\n";
    for (const auto& row : rows) print_row(row);

    const double ratio_dma = rows[3].total_ns / rows[0].total_ns;
    const double ratio_bf = rows[2].total_ns / rows[0].total_ns;
    std::cout << "\n";
    std::cout << "roce_dma / ub_loadstore = " << std::fixed << std::setprecision(2)
              << ratio_dma << "x\n";
    std::cout << "roce_bf  / ub_loadstore = " << ratio_bf << "x\n";
    std::cout << "note: pipe_ns comes from current Nano-UB SystemC pipeline; host_ns "
              << "adds the PCIe/on-chip path that OpenURMA includes.\n";
    return 0;
}
