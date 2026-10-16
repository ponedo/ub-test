#define _GNU_SOURCE
#include <linux/perf_event.h>
#include <asm/perf_regs.h>
#include <sys/syscall.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <sys/wait.h>
#include <sys/resource.h>
#include <unistd.h>
#include <signal.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
struct section { uint64_t offset,size; };
struct file_header {uint64_t magic,size,attr_size;struct section attrs,data,event_types;uint64_t flags[4];};
struct file_attr {struct perf_event_attr attr;struct section ids;};
static pid_t child_pid=-1;
static void die(const char *s){int saved=errno;if(child_pid>0){kill(child_pid,SIGKILL);while(waitpid(child_pid,NULL,0)<0 && errno==EINTR){}}errno=saved;perror(s);exit(1);}
static void put(FILE *f,const void *p,size_t n){if(fwrite(p,1,n,f)!=n)die("write");}
int main(int argc,char **argv){
 if(argc<5 || strcmp(argv[3],"--")){fprintf(stderr,"Usage: %s OUTPUT.data HZ -- PROGRAM [ARGS...]\n",argv[0]);return 2;}
 unsigned hz=atoi(argv[2]);if(hz<1||hz>10000)return 2;
 FILE *out=fopen(argv[1],"wb+e");if(!out)die("output");
 int gate[2];if(pipe(gate))die("pipe");pid_t pid=fork();if(pid<0)die("fork");
 if(!pid){close(gate[1]);char c; if(read(gate[0],&c,1)!=1)_exit(127);close(gate[0]);execvp(argv[4],argv+4);perror("exec");_exit(127);}close(gate[0]);child_pid=pid;
 struct file_attr fa={0};struct perf_event_attr *a=&fa.attr;
 a->size=sizeof(*a);a->type=PERF_TYPE_SOFTWARE;a->config=PERF_COUNT_SW_CPU_CLOCK;a->sample_freq=hz;a->freq=1;
 a->sample_type=PERF_SAMPLE_IP|PERF_SAMPLE_TID|PERF_SAMPLE_TIME|PERF_SAMPLE_PERIOD|PERF_SAMPLE_CALLCHAIN|PERF_SAMPLE_REGS_USER|PERF_SAMPLE_STACK_USER;
 a->sample_regs_user=((1ULL<<PERF_REG_X86_64_MAX)-1) & ~((1ULL<<PERF_REG_X86_DS)|(1ULL<<PERF_REG_X86_ES)|(1ULL<<PERF_REG_X86_FS)|(1ULL<<PERF_REG_X86_GS));a->sample_stack_user=8192;
 a->disabled=1;a->enable_on_exec=1;a->inherit=0;a->exclude_kernel=1;a->exclude_hv=1;a->exclude_callchain_user=1;
 a->mmap=1;a->mmap_data=1;a->mmap2=1;a->comm=1;a->task=1;a->sample_id_all=1;a->watermark=1;a->wakeup_watermark=65536;
 int fd=syscall(__NR_perf_event_open,a,pid,-1,-1,PERF_FLAG_FD_CLOEXEC);if(fd<0){kill(pid,SIGKILL);die("perf_event_open");}
 long page=sysconf(_SC_PAGESIZE);size_t ring_size=page*1024UL;
 struct perf_event_mmap_page *meta=mmap(NULL,page+ring_size,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);if(meta==MAP_FAILED){kill(pid,SIGKILL);die("mmap");}
 struct file_header h={.magic=0x32454c4946524550ULL,.size=sizeof(h),.attr_size=sizeof(fa)};
 h.attrs.offset=sizeof(h);h.attrs.size=sizeof(fa);h.data.offset=sizeof(h)+sizeof(fa);
 put(out,&h,sizeof(h));put(out,&fa,sizeof(fa));
 if(write(gate[1],"x",1)!=1)die("gate write");close(gate[1]);
 uint64_t tail=0,bytes=0,samples=0,lost=0,lost_records=0,period_sum=0,throttle=0,unthrottle=0;struct rusage usage={0};int done=0,status=0;unsigned char *ring=(unsigned char*)meta+page;
 unsigned char *buf=malloc(ring_size);if(!buf)die("malloc");
 for(;;){uint64_t head=__atomic_load_n(&meta->data_head,__ATOMIC_ACQUIRE);
  while(tail<head){struct perf_event_header eh;size_t pos=tail&(ring_size-1),n=sizeof(eh);size_t first=ring_size-pos<n?ring_size-pos:n;memcpy(&eh,ring+pos,first);if(first<n)memcpy((char*)&eh+first,ring,n-first);
   if(eh.size<sizeof(eh)||eh.size>ring_size){fprintf(stderr,"Invalid ring record\n");kill(pid,SIGKILL);return 1;}
   n=eh.size;first=ring_size-pos<n?ring_size-pos:n;memcpy(buf,ring+pos,first);if(first<n)memcpy(buf+first,ring,n-first);
   if(eh.type==PERF_RECORD_SAMPLE){
    if(n<40){errno=EIO;die("short sample");}
    uint64_t period;memcpy(&period,buf+32,8);period_sum+=period;samples++;
   }
   if(eh.type==PERF_RECORD_LOST){if(n<24){errno=EIO;die("short LOST");}uint64_t l;memcpy(&l,buf+16,8);lost+=l;lost_records++;}
   if(eh.type==PERF_RECORD_THROTTLE)throttle++;
   if(eh.type==PERF_RECORD_UNTHROTTLE)unthrottle++;
   put(out,buf,n);bytes+=n;tail+=n;
  }
  __atomic_store_n(&meta->data_tail,tail,__ATOMIC_RELEASE);
  if(done)break;
  pid_t waited=wait4(pid,&status,WNOHANG,&usage);
  if(waited<0){if(errno==EINTR)continue;die("wait4");}
  if(waited==pid){child_pid=-1;if(ioctl(fd,PERF_EVENT_IOC_DISABLE,0)<0)die("disable");done=1;continue;}
  struct pollfd pfd={.fd=fd,.events=POLLIN};if(poll(&pfd,1,100)<0 && errno!=EINTR)die("poll");
 }
 h.data.size=bytes;h.flags[0]=1ULL<<6;struct section arch={h.data.offset+bytes+sizeof(struct section),12};put(out,&arch,sizeof(arch));uint32_t alen=8;put(out,&alen,4);put(out,"x86_64\0",8);if(fseek(out,0,SEEK_SET))die("seek header");put(out,&h,sizeof(h));if(fclose(out))die("close output");munmap(meta,page+ring_size);close(fd);
 fprintf(stderr,"CPU samples=%lu period_sum_ns=%lu lost_records=%lu lost_samples_reported=%lu throttle_records=%lu unthrottle_records=%lu bytes=%lu child_user_seconds=%.6f child_system_seconds=%.6f child_exit=%d\n",samples,period_sum,lost_records,lost,throttle,unthrottle,bytes,usage.ru_utime.tv_sec+usage.ru_utime.tv_usec/1e6,usage.ru_stime.tv_sec+usage.ru_stime.tv_usec/1e6,WIFEXITED(status)?WEXITSTATUS(status):-1);
 if(!lost_records)fprintf(stderr,"No PERF_RECORD_LOST records observed; this is not a guarantee of complete sampling.\n");
 return WIFEXITED(status)?WEXITSTATUS(status):128+WTERMSIG(status);
}
