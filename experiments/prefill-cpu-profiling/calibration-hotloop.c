#include <time.h>
volatile unsigned long sum;
__attribute__((noinline)) void hot_loop(void) { for(unsigned long i=0;i<10000000;i++) sum += i; }
int main(void) { struct timespec s,n; clock_gettime(CLOCK_MONOTONIC,&s); do {hot_loop();clock_gettime(CLOCK_MONOTONIC,&n);} while(n.tv_sec-s.tv_sec<2); }
