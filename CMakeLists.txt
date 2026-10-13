cmake_minimum_required(VERSION 3.16)
project(nano-ub LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# --- SystemC dependency via pkg-config ---
find_package(SystemCLanguage CONFIG QUIET)
if(NOT SystemCLanguage_FOUND)
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(SystemC REQUIRED systemc)
endif()

# --- Include paths ---
set(NANO_INCLUDE ${CMAKE_SOURCE_DIR}/include)

# --- 通用编译选项 ---
add_library(nano_common INTERFACE)
target_include_directories(nano_common INTERFACE
    ${NANO_INCLUDE}
    ${SystemC_INCLUDE_DIRS}
)
target_link_directories(nano_common INTERFACE ${SystemC_LIBRARY_DIRS})
if(SystemCLanguage_FOUND)
    target_link_libraries(nano_common INTERFACE SystemC::systemc)
else()
    target_link_libraries(nano_common INTERFACE ${SystemC_LIBRARIES})
endif()

# --- M00: SystemC 空转验证 ---
add_executable(m00_empty tests/m00_empty.cpp)
target_link_libraries(m00_empty nano_common)

# --- M01: Flit 单元测试 ---
add_executable(m01_flit tests/m01_flit.cpp)
target_link_libraries(m01_flit nano_common)

# --- M02: EtherLink 链路测试 ---
add_executable(m02_link
    tests/m02_link.cpp
    src/eth_link.cpp
)
target_link_libraries(m02_link nano_common)

# --- M03: RoCE TX 最小路径 ---
add_executable(m03_roce_tx tests/m03_roce_tx.cpp)
target_link_libraries(m03_roce_tx nano_common)

# --- M04: RoCE ping-pong ---
add_executable(m04_roce_pingpong
    tests/m04_roce_pingpong.cpp
    src/eth_link.cpp
)
target_link_libraries(m04_roce_pingpong nano_common)

# --- M05: RoCE RDMA READ ---
add_executable(m05_roce_read
    tests/m05_roce_read.cpp
    src/eth_link.cpp
)
target_link_libraries(m05_roce_read nano_common)

# --- M06: RoCE 完整 RC ---
add_executable(m06_roce_full
    tests/m06_roce_full.cpp
    src/eth_link.cpp
)
target_link_libraries(m06_roce_full nano_common)

# --- M07: UB Load/Store TX ---
add_executable(m07_ub_ls_tx tests/m07_ub_ls_tx.cpp)
target_link_libraries(m07_ub_ls_tx nano_common)

# --- M08: UB Load/Store ping-pong ---
add_executable(m08_ub_ls_pingpong
    tests/m08_ub_ls_pingpong.cpp
    src/eth_link.cpp
)
target_link_libraries(m08_ub_ls_pingpong nano_common)

# --- M09: UB URMA TX 完整路径 ---
add_executable(m09_ub_urma_tx tests/m09_ub_urma_tx.cpp)
target_link_libraries(m09_ub_urma_tx nano_common)

# --- M10: UB URMA 端到端 ---
add_executable(m10_ub_urma_e2e
    tests/m10_ub_urma_e2e.cpp
    src/eth_link.cpp
)
target_link_libraries(m10_ub_urma_e2e nano_common)

# --- M11: UB 完整排序 ---
add_executable(m11_ub_ordering tests/m11_ub_ordering.cpp)
target_link_libraries(m11_ub_ordering nano_common)

# --- M12: UB vs RoCE 对比 ---
add_executable(bench_ub bench/bench_ub.cpp src/eth_link.cpp)
target_link_libraries(bench_ub nano_common)

add_executable(bench_roce bench/bench_roce.cpp src/eth_link.cpp)
target_link_libraries(bench_roce nano_common)

add_executable(bench_full_latency bench/bench_full_latency.cpp)
target_link_libraries(bench_full_latency nano_common)

add_executable(bench_state_size bench/bench_state_size.cpp)
target_link_libraries(bench_state_size nano_common)

add_executable(bench_ordering_cost bench/bench_ordering_cost.cpp)
target_link_libraries(bench_ordering_cost nano_common)

add_executable(bench_loss_recovery bench/bench_loss_recovery.cpp)
target_link_libraries(bench_loss_recovery nano_common)

add_executable(bench_micro bench/bench_micro.cpp)
target_link_libraries(bench_micro nano_common)

# M12 experimental per-Jetty scheduling (FIFO / RR / DRR).
add_executable(m12_ub_fair_scheduler tests/m12_ub_fair_scheduler.cpp)
target_link_libraries(m12_ub_fair_scheduler nano_common)

# Pure-C++ scheduling correctness and microbenchmark (these targets do not
# require SystemC includes, but the top-level project still does).
add_executable(test_scheduler_core tests/test_core.cpp)
target_include_directories(test_scheduler_core PRIVATE ${NANO_INCLUDE})
add_executable(bench_scheduler_core bench/scheduler_microbench.cpp)
target_include_directories(bench_scheduler_core PRIVATE ${NANO_INCLUDE})

# Actual SystemC UB WRITE pipeline, experiment-only byte link and completion loop.
add_executable(scheduler_e2e bench/scheduler_e2e.cpp)
target_link_libraries(scheduler_e2e nano_common)
add_executable(m13_scheduler_guards tests/m13_scheduler_guards.cpp)
target_link_libraries(m13_scheduler_guards nano_common)
enable_testing()
foreach(test m00_empty m01_flit m02_link m03_roce_tx m04_roce_pingpong
             m05_roce_read m06_roce_full m07_ub_ls_tx m08_ub_ls_pingpong
             m09_ub_urma_tx m10_ub_urma_e2e m11_ub_ordering m12_ub_fair_scheduler
             m13_scheduler_guards test_scheduler_core)
    add_test(NAME ${test} COMMAND ${test})
endforeach()

add_executable(trace_e2e simulators/nano_ub/trace_e2e.cpp)
target_link_libraries(trace_e2e nano_common)
