#include <nano/eval/latency_model.h>

#include <iomanip>
#include <iostream>
#include <vector>

int main(int argc, char** argv) {
    uint32_t operations = 1024;
    uint32_t ro_before_so = 32;

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        auto next = [&]() -> const char* {
            if (i + 1 >= argc) {
                std::cerr << "missing value for " << arg << "\n";
                std::exit(2);
            }
            return argv[++i];
        };
        if (arg == "--n-ops") operations = std::stoul(next());
        else if (arg == "--ro-before-so") ro_before_so = std::stoul(next());
        else {
            std::cerr << "unknown option: " << arg << "\n";
            return 2;
        }
    }

    const std::vector<std::string> modes = {
        "NO", "RO", "SO", "FENCE", "UNO", "RTP",
    };

    std::cout << "=== Nano-UB ordering cost model ===\n";
    std::cout << "n_ops=" << operations
              << " ro_before_so=" << ro_before_so << "\n\n";
    std::cout << std::left << std::setw(10) << "mode"
              << std::right << std::setw(10) << "ops"
              << std::setw(12) << "mean_ns"
              << std::setw(12) << "p99_ns"
              << std::setw(16) << "throughput_Mops"
              << "\n";

    for (const auto& mode : modes) {
        const auto c = nano::eval::ordering_cost(mode, operations, ro_before_so);
        std::cout << std::left << std::setw(10) << c.mode
                  << std::right << std::setw(10) << c.operations
                  << std::setw(12) << std::fixed << std::setprecision(2)
                  << c.mean_ns
                  << std::setw(12) << c.p99_ns
                  << std::setw(16) << c.throughput_mops
                  << "\n";
    }
    return 0;
}
