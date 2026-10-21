// Test-only probe: link-rate precision and native CBFC cell accounting.
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/ub-port.h"
#include "ns3/ub-cbfc.h"
#include "ns3/ub-header.h"
#include "ns3/ub-link.h"
#include "ns3/ub-datalink.h"
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <type_traits>
#include <vector>
using namespace ns3;
static void Require(bool ok, const char* why) { if (!ok) throw std::runtime_error(why); }
// Like the native packet-rate fixture, drive the ordinary egress queue and
// port busy state. Unlike its recording link, use the actual UbLink delivery.
// The supported receive handler is a byte sink: this tests link service, not
// upper-layer ACK/credit processing or switch allocation.
struct LinkEvidence {
  struct Sent { uint32_t bytes; int64_t startPs; int64_t announcedCompletionPs; };
  std::vector<Sent> sent;
  std::vector<int64_t> receivedPs;
  std::vector<uint32_t> receivedBytes;
  void Announced(Ptr<Packet> p, Time duration) {
    sent.push_back({p->GetSize(), Simulator::Now().GetPicoSeconds(),
                   (Simulator::Now()+duration).GetPicoSeconds()});
  }
  void Received(Ptr<UbPort>, Ptr<Packet> p) {
    receivedPs.push_back(Simulator::Now().GetPicoSeconds());
    receivedBytes.push_back(p->GetSize());
  }
};
static void ProbeOrdinaryLink(DataRate rate) {
  auto leftNode = CreateObject<Node>();
  auto rightNode = CreateObject<Node>();
  auto left = CreateObject<UbPort>();
  auto right = CreateObject<UbPort>();
  leftNode->AddDevice(left);
  rightNode->AddDevice(right);
  left->SetAttribute("UbDataRate", DataRateValue(rate));
  right->SetAttribute("UbDataRate", DataRateValue(rate));
  left->SetAttribute("UbInterframeGap", TimeValue(Time(0)));
  auto link = CreateObject<UbLink>();
  link->SetAttribute("Delay", TimeValue(NanoSeconds(20)));
  left->Attach(link);
  right->Attach(link);
  LinkEvidence evidence;
  Require(left->TraceConnectWithoutContext("TraComEventNotify",
      MakeCallback(&LinkEvidence::Announced, &evidence)), "missing completion announcement trace");
  right->SetReceiveHandler(MakeCallback(&LinkEvidence::Received, &evidence));
  uint8_t credits[16] = {};
  credits[1] = 1;
  auto credit = UbDataLink::BuildControlCreditPacket(credits);
  Require(credit->GetSize() == 40, "unexpected native credit frame size");
  UbDatalinkPacketHeader header;
  header.SetPacketVL(1);
  auto data = Create<Packet>(160 - header.GetSerializedSize());
  data->AddHeader(header);
  Require(left->EnqueueToEgress({0, 0, credit}), "credit enqueue failed");
  Require(left->EnqueueToEgress({0, 1, data}), "data enqueue failed");
  left->TriggerTransmit();
  Require(left->IsBusy() && evidence.sent.size() == 1, "first send did not reserve busy port");
  left->TriggerTransmit();
  Require(evidence.sent.size() == 1, "busy port transmitted second packet early");
  Simulator::Run();
  Require(evidence.sent.size() == 2 && evidence.receivedPs.size() == 2,
          "ordinary link did not deliver both packets");
  Require(!left->IsBusy(), "ordinary port remained busy after completion");
  Require(evidence.sent[1].startPs == evidence.sent[0].announcedCompletionPs,
          "queued packet did not start at actual first completion boundary");
  std::cout << ",\"ordinary_link\":{\"propagation_ps\":20000,"
               "\"upper_layer_processing_tested\":false,\"packets\":[";
  for (size_t i = 0; i < evidence.sent.size(); ++i) {
    const auto& s = evidence.sent[i];
    const int64_t duration = rate.CalculateBytesTxTime(s.bytes).GetPicoSeconds();
    Require(duration > 0 && s.announcedCompletionPs == s.startPs + duration,
            "ordinary port serialization duration mismatch");
    Require(evidence.receivedBytes[i] == s.bytes &&
            evidence.receivedPs[i] == s.startPs + duration + 20000,
            "actual UbLink receive timing/size mismatch");
    if (i) std::cout << ',';
    std::cout << "{\"bytes\":" << s.bytes << ",\"send_ps\":" << s.startPs
              << ",\"announced_completion_ps\":" << s.announcedCompletionPs
              << ",\"observed_receive_ps\":" << evidence.receivedPs[i] << '}';
  }
  std::cout << "],\"busy_guard_passed\":true,\"final_port_idle\":true}";
  right->ClearReceiveHandler();
  left->TraceDisconnectWithoutContext("TraComEventNotify",
      MakeCallback(&LinkEvidence::Announced, &evidence));
}
int main() {
  try {
    Time::SetResolution(Time::PS);
    constexpr uint64_t rate = UINT64_C(3136000000000);
    DataRate direct(rate), parsed("3136Gbps");
    static_assert(std::is_same_v<decltype(direct.GetBitRate()), uint64_t>);
    Require(direct.GetBitRate() == rate && parsed.GetBitRate() == rate, "64-bit rate mismatch");
    auto port = CreateObject<UbPort>();
    port->SetAttribute("UbDataRate", DataRateValue(direct));
    DataRateValue observed;
    port->GetAttribute("UbDataRate", observed);
    Require(observed.Get().GetBitRate() == rate, "native UbPort rate mismatch");
    std::cout << "{\"status\":\"PASS\",\"rate_bps\":" << rate
              << ",\"resolution\":\"PS\",\"serialization\":[";
    bool first = true;
    for (uint32_t bytes : {1u,40u,64u,159u,160u,161u,1024u,4096u}) {
      // Independent integer nearest-picosecond oracle: bytes * 8 / rate seconds.
      const uint64_t numerator = uint64_t(bytes) * 8 * UINT64_C(1000000000000);
      const int64_t expected = (numerator + rate/2) / rate;
      const int64_t actual = direct.CalculateBytesTxTime(bytes).GetPicoSeconds();
      Require(actual > 0 && std::llabs(actual - expected) <= 1, "serialization precision mismatch");
      if (!first) std::cout << ',';
      first = false;
      std::cout << "{\"bytes\":" << bytes << ",\"actual_ps\":" << actual
                << ",\"rounded_ideal_ps\":" << expected << '}';
    }
    std::cout << "],\"cell_boundaries\":[";
    first = true;
    for (uint32_t bytes : {159u,160u,161u}) {
      auto cbfc = CreateObject<UbCbfc>();
      cbfc->Init(20,8,1,1,6553,32,0,0);
      UbDatalinkPacketHeader header;
      header.SetPacketVL(0);
      Require(header.GetSerializedSize() <= bytes, "boundary packet smaller than header");
      auto packet = Create<Packet>(bytes - header.GetSerializedSize());
      packet->AddHeader(header);
      Require(packet->GetSize() == bytes, "boundary packet size mismatch");
      const uint32_t cells = (bytes + 159) / 160;
      Require(cbfc->CbfcConsumeCrd(packet), "native CBFC consumption rejected");
      Require(cbfc->GetConsumedCells() == cells && cbfc->GetTxFreeCells(0) == 6553-int(cells),
              "native CBFC cell boundary mismatch");
      if (!first) std::cout << ',';
      first = false;
      std::cout << "{\"bytes\":" << bytes << ",\"consumed_cells\":" << cbfc->GetConsumedCells() << '}';
      cbfc->Dispose();
    }
    std::cout << ']';
    ProbeOrdinaryLink(direct);
    std::cout << "}\n";
    port->Dispose();
    Simulator::Destroy();
    return 0;
  } catch (const std::exception& e) {
    std::cerr << "FAIL: " << e.what() << '\n';
    return 1;
  }
}
