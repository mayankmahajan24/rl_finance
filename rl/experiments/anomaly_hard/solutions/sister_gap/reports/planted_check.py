import sys, numpy as np, pandas as pd, warnings
warnings.simplefilter('ignore')
sys.path.insert(0,'/home/user/rl_finance/rl/experiments/anomaly_hard/solutions/sister_gap')
import score as M
src='wt/rl/tasks/proto/anomaly_hard_train/anomhard-train-001/environment/data/transactions.csv'
d=pd.read_csv(src,parse_dates=['date'])
K=['date','ticker','source_id']
def run(df):
    parts=[]
    for tk,g in df.groupby('ticker',sort=False):
        r=M.score_company(g); r.insert(1,'ticker',tk); parts.append(r)
    return df[K].merge(pd.concat(parts),on=K,how='left')
base=run(d)   # the code's own output on the panel as given: the reference the planted problems are judged against
ref=d.merge(base,on=K)
y0=d.date.min()+pd.Timedelta(days=365)
# series eligible: never discarded after year one, as reported on >95% of rows (no standing problem of their own)
g=ref[ref.date>=y0].groupby(['ticker','source_id']).treatment.agg(lambda t:(t=='as reported').mean())
elig=[k for k,v in g.items() if v>0.95]
print('eligible series',len(elig),elig)
ONE={'dropout':(0.03,0.03),'volume spike':(3.0,3.0),'count flood':(4.0,1.0),'dollar spike':(1.0,2.2)}
STEP={'step up x1.5':(1.5,1.5),'step down x0.6':(0.6,0.6),'count only x1.5':(1.5,1.0),'dollars only x0.7':(1.0,0.7)}
rows=[]
for seed in range(6):
    rng=np.random.default_rng(seed); p=d.copy(); ev=[]
    days=pd.date_range(y0+pd.Timedelta(days=30),d.date.max()-pd.Timedelta(days=100))
    used={}
    def free(tk,a,b):
        return all(b<x or a>y for x,y in used.get(tk,[]))
    for name,(mc,ma) in list(ONE.items())*2+list(STEP.items()):
        for _ in range(200):
            tk,s=elig[rng.integers(len(elig))]; a=days[rng.integers(len(days))]
            n=1 if name in ONE else 60
            b=a+pd.Timedelta(days=n-1)
            if free(tk,a-pd.Timedelta(days=45),b+pd.Timedelta(days=45)): break
        used.setdefault(tk,[]).append((a,b))
        m=(p.ticker==tk)&(p.source_id==s)&p.date.between(a,b)
        p.loc[m,'ct']=np.maximum(1,np.round(p.loc[m,'ct']*mc)); p.loc[m,'amt']=np.round(p.loc[m,'amt']*ma,2)
        ev.append((name,tk,s,a,b))
    out=run(p)
    z=d.merge(out,on=K).merge(base[K+['clean_ct','clean_amt']].rename(columns={'clean_ct':'b_ct','clean_amt':'b_amt'}),on=K)
    z['raw_ct']=p.ct.to_numpy(); z['raw_amt']=p.amt.to_numpy()
    lg=lambda x:np.log(np.maximum(x.astype(float),.01))
    z['e_raw']=.5*((lg(z.raw_ct)-lg(z.ct)).abs()+(lg(z.raw_amt)-lg(z.amt)).abs())
    z['e_cl']=.5*((lg(z.clean_ct.fillna(z.raw_ct))-lg(z.ct)).abs()+(lg(z.clean_amt.fillna(z.raw_amt))-lg(z.amt)).abs())
    hit=pd.Series(False,index=z.index)
    for name,tk,s,a,b in ev:
        m=(z.ticker==tk)&(z.source_id==s)&z.date.between(a,b); hit|=(z.ticker==tk)&(z.source_id==s)&z.date.between(a,b+pd.Timedelta(days=30))
        q=z[m]
        rows.append(dict(kind='one day' if name in ONE else 'step',name=name,n=len(q),treated=(q.treatment!='as reported').mean(),
                         first=(q.treatment.iloc[0]!='as reported'),raw=q.e_raw.sum(),cl=q.e_cl.sum(),
                         lateok=(q.e_cl.iloc[14:]<0.1).mean() if len(q)>14 else np.nan,conf=q.confidence.mean(),big=d[(d.ticker==tk)&(d.source_id==s)].ct.median()>=100))
    o=z[~hit&(z.date>=y0)]
    ch=((o.clean_ct.fillna(-1)-o.b_ct.fillna(-1)).abs()>1e-6)|((o.clean_amt.fillna(-1)-o.b_amt.fillna(-1)).abs()>1e-6)
    mv=.5*((lg(o.clean_ct.fillna(1))-lg(o.b_ct.fillna(1))).abs()+(lg(o.clean_amt.fillna(1))-lg(o.b_amt.fillna(1))).abs()); rows.append(dict(kind='elsewhere',name='rows changed elsewhere',n=len(o),treated=ch.mean(),raw=ch.sum(),cl=(mv>0.05).sum(),conf=(o.confidence<.5).sum()-(o.clean_ct.isna()).sum()))
r=pd.DataFrame(rows)
for (k,nm),q in r[r.kind!='elsewhere'].groupby(['kind','name']):
    print(k,nm,'events',len(q),'rows',q.n.sum(),'treated share %.3f'%((q.treated*q.n).sum()/q.n.sum()),'first day %.2f'%q['first'].mean(),'error removed %.3f'%(1-q.cl.sum()/q.raw.sum()),'late ok %.3f'%q.lateok.mean(),'conf %.2f'%q.conf.mean())
for k,q in r[r.kind!='elsewhere'].groupby('kind'):
    print('ALL',k,len(q),q.n.sum(),'treated %.3f'%((q.treated*q.n).sum()/q.n.sum()),'first %.3f'%q['first'].mean(),'removed %.3f'%(1-q.cl.sum()/q.raw.sum()),'late %.3f'%q.lateok.mean())
for (k,b),q in r[r.kind!='elsewhere'].groupby(['kind','big']):
    print('SIZE',k,'100+ a day' if b else 'under 100',len(q),q.n.sum(),'treated %.3f'%((q.treated*q.n).sum()/q.n.sum()),'first %.3f'%q['first'].mean(),'removed %.3f'%(1-q.cl.sum()/q.raw.sum()),'late %.3f'%q.lateok.mean())
e=r[r.kind=='elsewhere']; print('moved>5%',int(e.cl.sum()),'%.4f'%(e.cl.sum()/e.n.sum()),'distrusted not blank',int(e.conf.sum())); print('elsewhere rows',int(e.n.sum()),'changed',int(e.raw.sum()),'%.4f'%(e.raw.sum()/e.n.sum()))
