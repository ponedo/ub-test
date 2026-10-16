# CPU-clock calibration 2

Compiled record.c with `gcc -O2 -Wall -Wextra record.c -o record`.
The known hot loop was compiled from calibration-hotloop.c using `gcc -g -O2 -fno-omit-frame-pointer`.
Only a benign misleading-indentation warning was emitted for gate close; it is outside the error branch intentionally.

Collector and child were launched using `env -i` with only PATH, LANG, LC_ALL, HOME and LD_LIBRARY_PATH. Production execute.py additionally allows RELAY_GRAPH_TOOL and passes an explicit environment dictionary through guard.py subprocess.Popen(env=env). The collector uses execvp, so its child inherits this same dictionary; the perf analysis wrapper's own library path is not used to launch the workload.

152 samples, summed CPU-clock sample periods 1.535353520 seconds, child wait4 user CPU 1.538369 seconds, system CPU 0.000000 seconds; period/user CPU ratio 99.80398%. No PERF_RECORD_LOST, THROTTLE or UNTHROTTLE records observed. This does not guarantee complete collection. Official perf report attributes 100% of self samples to the known hot_loop. Clean DWARF chains contain hot_loop once, main, a stripped unknown libc frame, __libc_start_main and _start. Leaf IP offsets vary.

Main-thread user-CPU only, no child/thread inheritance, no kernel CPU attribution. An 8192-byte stack snapshot may truncate deep stacks. CPU sampling is statistical; short runs have few samples. Unresolved library frames are retained as unknown. Header lacks build-ID records, so analysis must use the exact preserved binaries and shared libraries from the capture.

For reproduction, run setup_perf.sh to obtain the exact recorded official Debian package versions locally; see perf-packages.sha256-urls. This setup script was prepared from existing downloaded artifacts and was not itself rerun during calibration.
