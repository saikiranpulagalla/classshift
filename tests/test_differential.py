from __future__ import annotations

import random

from classshift.input_validator import parse_dataset, parse_outages
from classshift.optimizer import optimize_period
from classshift.solution_validator import validate_solution
from scripts.brute_force_oracle import brute_force_period


def make(seed):
    rng=random.Random(seed); n=rng.randint(1,4); m=rng.randint(n,min(6,n+2))
    rooms=[]
    feature_sets=[]
    for i in range(m):
        feats={f for f in ["a","b","c"] if rng.random()<0.65}; feature_sets.append(feats)
        rooms.append({"id":f"R{i}","label":f"R{i}","capacity":rng.randint(20,40),"features":sorted(feats),"step_free_status":rng.choice(["VERIFIED","UNKNOWN","NOT_VERIFIED"]),"enabled":True})
    lessons=[]
    for i in range(n):
        r=rooms[i]
        # baseline requirements are guaranteed compatible with original room
        subset=[f for f in r["features"] if rng.random()<0.6]
        step=(r["step_free_status"]=="VERIFIED" and rng.random()<0.25)
        students=rng.randint(10,r["capacity"])
        lessons.append({"id":f"L{i}","label":f"L{i}","period_id":"MON_P1","original_room_id":r["id"],"student_count":students,"required_features":subset,"requires_step_free":step,"locked":rng.random()<0.12})
    raw={"periods":[{"id":"MON_P1","label":"Monday · Period 1","order":1}],"rooms":rooms,"lessons":lessons}
    outage_count=1 if m==1 else rng.randint(1,min(2,m))
    outage_ids=rng.sample([r["id"] for r in rooms],outage_count)
    outages=[{"room_id":rid,"period_ids":["MON_P1"]} for rid in outage_ids]
    return raw,outages


def test_differential_small_random_cases():
    for seed in range(40):
        raw,out_raw=make(seed); ds=parse_dataset(raw); out=parse_outages(out_raw,ds)
        prod=optimize_period(ds,out,"MON_P1"); feasible,best=brute_force_period(ds,out,"MON_P1")
        if feasible:
            assert prod.status.value=="OPTIMAL", f"seed={seed}"
            assert prod.move_count==best, f"seed={seed}"
            assert validate_solution(ds,out,prod.assignments or (),prod.move_count).valid, f"seed={seed}"
        else:
            assert prod.status.value=="INFEASIBLE", f"seed={seed}"
