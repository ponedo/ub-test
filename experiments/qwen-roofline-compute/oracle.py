"""Independent integer Python model; never imports the production header."""
FIELDS=['flops','weight_hbm_bytes','input_hbm_bytes','intermediate_hbm_bytes','output_hbm_bytes','activation_hbm_bytes','total_hbm_bytes','compute_ps','memory_ps','roofline_ps']
def estimate(m,h=4096,i=1536,a=2,w=1,tflops=100,gbps=2692,configured_weight_bytes=None):
 if not all(isinstance(v,int) and v>0 for v in [h,i,a,w,tflops,gbps]) or not isinstance(m,int) or m<0:raise ValueError('invalid parameter')
 if configured_weight_bytes is not None and (not isinstance(configured_weight_bytes,int) or configured_weight_bytes<0):raise ValueError("invalid weight override")
 if m==0:return dict.fromkeys(FIELDS,0)
 f=6*m*h*i;weights=3*h*i*w if not configured_weight_bytes else configured_weight_bytes;inp=2*m*h*a;mid=6*m*i*a;out=m*h*a;act=inp+mid+out;hbm=weights+act
 cp=(f+tflops-1)//tflops;mp=(hbm*1000+gbps-1)//gbps
 return dict(zip(FIELDS,[f,weights,inp,mid,out,act,hbm,cp,mp,max(cp,mp)]))
def legacy(m,p):
 num=m*2*p['matrices']*p['model_dim']*p['ff_dim']*1000000;den=p['peak_gflops']*p['util_permille']
 return (num+den-1)//den+p['setup_ns']*1000
