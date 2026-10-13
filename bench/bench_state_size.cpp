#include <nano/eval/latency_model.h>

#include <iomanip>
#include <iostream>

int main() {
    std::cout << "local_endpoints,remote_hosts,memory_regions,ub_bytes,roce_bytes,roce_over_ub\n";
    for (uint64_t n = 1; n <= 4096; n <<= 1) {
        for (uint64_t m = 1; m <= 4096; m <<= 1) {
            const auto s = nano::eval::state_size(n, m, n);
            const double ratio = static_cast<double>(s.roce_bytes)
                               / static_cast<double>(s.ub_bytes);
            std::cout << s.local_endpoints << ","
                      << s.remote_hosts << ","
                      << s.memory_regions << ","
                      << s.ub_bytes << ","
                      << s.roce_bytes << ","
                      << std::fixed << std::setprecision(2) << ratio << "\n";
        }
    }
    return 0;
}
