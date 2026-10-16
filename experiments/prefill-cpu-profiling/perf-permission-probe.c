#include <linux/perf_event.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <stdio.h>
#include <errno.h>
#include <string.h>
int main(){struct perf_event_attr a={0};a.type=PERF_TYPE_SOFTWARE;a.size=sizeof(a);a.config=PERF_COUNT_SW_CPU_CLOCK;a.exclude_kernel=1;a.exclude_hv=1;int fd=syscall(__NR_perf_event_open,&a,0,-1,-1,0);printf("perf_event_open user CPU clock fd=%d errno=%d %s\n",fd,errno,strerror(errno));return fd<0;}
