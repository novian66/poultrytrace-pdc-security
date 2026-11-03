#!/usr/bin/env python3
"""Deterministic synthetic PoultryTrace Stage 11 data, stdlib-only."""
import csv, hashlib, json, random
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dataset'
OUT.mkdir(parents=True,exist_ok=True)
r=random.Random(20261027)
pub=[]; farm=[]; doc=[]; distribution=[]; quality=[]; summary=[]
for idx in range(101,201):
    bid=f'BRL-2026-{idx:03d}'
    farmid=f'FARM-{((idx-101)%10)+1:03d}'
    hatchid=f'HATCH-{((idx-101)%4)+1:03d}'
    pop=5000 + r.randrange(-600,601,100)
    status=['harvested','shipped','received'][((idx-101)//10)%3]
    b=dict(batchId=bid,farmId=farmid,hatcheryId=hatchid,population=pop,status=status)
    perf=dict(batchId=bid,fcr=round(r.uniform(1.42,1.94),2),mortalityRate=round(r.uniform(1.00,4.85),2),productionCostIdr=r.randrange(74000000,118000001,250000))
    pub.append(b); farm.append(perf)
    doc.append(dict(batchId=bid,docContractId=f'DOC-{idx:04d}',docUnitPriceIdr=r.randrange(5000,9501,100),contractVolume=pop))
    distribution.append(dict(batchId=bid,distributionContractId=f'DST-{idx:04d}',distributionPricePerKgIdr=r.randrange(900,2901,50)))
    quality.append(dict(batchId=bid,auditId=f'AUD-{idx:04d}',temperatureC=round(r.uniform(-1.0,4.0),1),inspectionStatus='passed' if idx%13 else 'review'))
    summary.append(dict(**b,**{k:v for k,v in perf.items() if k!='batchId'}))

def jsonl(name, rows):
    p=OUT/name
    with p.open('w',encoding='utf-8',newline='\n') as f:
        for item in rows:f.write(json.dumps(item,ensure_ascii=False,separators=(',',':'))+'\n')
    return p
paths=[jsonl('batches_public.jsonl',pub),jsonl('farm_performance_private.jsonl',farm),jsonl('future_doc_contract_NOT_DEPLOYED.jsonl',doc),jsonl('future_rpa_distribution_NOT_DEPLOYED.jsonl',distribution),jsonl('future_quality_audit_NOT_DEPLOYED.jsonl',quality)]
summary_csv=OUT/'ground_truth_RESTRICTED.csv'
with summary_csv.open('w',newline='',encoding='utf-8') as f:
    writer=csv.DictWriter(f,fieldnames=list(summary[0])); writer.writeheader();writer.writerows(summary)
paths.append(summary_csv)
manifest={'seed':20261027,'count':len(pub),'batchIds':[pub[0]['batchId'],pub[-1]['batchId']], 'activeCollection':'pdc_farm_integrator','stage10Chaincode':'poultry-traceability:1.0 sequence1','notDeployedCollections':['pdc_doc_contract','pdc_rpa_distribution','pdc_quality_audit'], 'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
assert len(pub)==len(farm)==len(set(i['batchId'] for i in pub))==100
assert all(x['batchId']==y['batchId'] for x,y in zip(pub,farm))
print('Generated 100 public and 100 active private records + 3 future-only datasets')
print('Public IDs:',pub[0]['batchId'],'..',pub[-1]['batchId'])
