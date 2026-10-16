#pragma once
extern "C" void cpu_scope_enter(unsigned);
extern "C" void cpu_scope_leave();
struct CpuScope { explicit CpuScope(unsigned id){cpu_scope_enter(id);} ~CpuScope(){cpu_scope_leave();} };
