# Multicast WRITE v2 native retry validation

Start with AUDIT.md and REPORT.md. This experiment is on the original dot cloud host. It retains v2 first-send wire format unchanged and adds only a separate source adapter plus a default-null test fault seam. No reliable-transport algorithm is implemented here.

## Reproduction

Use the project tree at this delivery commit. Reconstruct a disposable accepted native tree exactly as ../ub-multicast-v2/README.md: d6aa9e2 plus accepted-unicast-baseline.patch,network-replication.patch,lightweight-adapter.patch. Do not apply v2 yourself; reproduce.sh checks 108 baseline hashes and applies v2 then the test seam.

Run `bash experiments/ub-multicast-retransmission/reproduce.sh /path/to/native /path/to/fresh-private-output` with installed C++20,CMake,Ninja,Python3+psutil,OpenSSL development library. All stages sequential, native -j2, original guard unchanged. Assertions are mandatory. No giant Debug logs. Raw payloads and evidence remain private; compact packet/state/events evidence is delivered in results/.

For already patched/built tree: `python3 build.py --native NATIVE --out FRESH_BUILD`, then `python3 run.py --build FRESH_BUILD --out FRESH_RESULTS`. Optional --case selects exactly one planned case. Output paths must be fresh. Read both summary status and verifier result: bounded incomplete is not success; retry exhaustion is expected assertion, not graceful WQE failure.

## Fault meaning

The sink seam acts after actual switch decapsulation and downstream physical transmission, normal CBFC ingress/credit handling, and endpoint validation, but before TP sees the packet. This isolates TP loss recovery without inventing CBFC credit repair. It is a post-link transport delivery loss, not corrupt-link simulation or switch-buffer overflow. Duplicate injection repeats TP delivery of the actual received packet, not an additional link frame. Requests/ACK/transaction responses all use native handlers after injection.

The main request loss is B's last PSN11, leaving one outstanding request. GBN can replay more than one unconfirmed segment for other loss positions; this experiment does not claim selective recovery. Enabled native GBN, fast retransmission off, static 5us RTO, max attempts4,12KiB/target,1024B TA. These are explicit existing native parameters, not new timers. CC remains disabled as in accepted v2, CBFC remains enabled. No claim about CC-enabled integration.

Verifier mutation test: `python3 test-verifier.py PRIVATE/matrix/data-once`. It rejects missing physical transmission, wrong replay payload identity, missing fault activation, unwanted C traffic, missing/repeated target or group completion, premature success, broken credit balance, retained final descriptors and corrupt actual payload. Optimized Python is rejected explicitly.
