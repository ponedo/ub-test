#include <nano/eval/latency_model.h>

#include <iomanip>
#include <iostream>
#include <vector>

int main(int argc, char** argv) {
    uint32_t operations = 10000;
    uint32_t window = 32;
    double base_latency_ns = 440.0;
    double rto_ns = 500.0;

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
        else if (arg == "--window") window = std::stoul(next());
        else if (arg == "--base-latency-ns") base_latency_ns = std::stod(next());
        else if (arg == "--rto-ns") rto_ns = std::stod(next());
        else {
            std::cerr << "unknown option: " << arg << "\n";
            return 2;
        }
    }

    const std::vector<double> losses = {
        0.0, 0.0001, 0.001, 0.005, 0.01, 0.02,
    };

    std::cout << "loss_rate,operations,window,expected_retransmits,mean_ns,goodput_mops\n";
    for (double loss : losses) {
        const auto r = nano::eval::gobackn_loss_model(
            loss, operations, window, base_latency_ns, rto_ns);
        std::cout << std::fixed << std::setprecision(4) << r.loss_rate << ","
                  << r.operations << ","
                  << r.window << ","
                  << r.expected_retransmits << ","
                  << std::setprecision(2) << r.mean_ns << ","
                  << r.goodput_mops << "\n";
    }
    return 0;
}
