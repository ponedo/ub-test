# persistent-exhaust

Same persistent drop; allow native attempt exhaustion; outer100us cap.

Fixed controls and artifact contract: ../../experiment-plan.md. Single switch,3 targets,12288B per target,1024B TA,100Gbps20ns,CBFC on,CC off. Native static RTO5us,attempt setting4 except disabled comparison. No independent recovery machinery. Command: micro --loss=persistent-exhaust --out=FRESH_CASE. Required evidence: packets.csv,events.csv,windows.csv; completed processes also summary,ports,payload files; exhausted process retains host assertion and resource outcome. All traces are bounded Events/Summary, not Debug.
