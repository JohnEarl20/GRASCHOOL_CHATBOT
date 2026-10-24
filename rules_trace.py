"""Draft forward-chaining engine for the Enrollment Requirements Advisor.
Facts are tuples, e.g. ("student_type","transferee"). Variables start with '?'.
Negation ("not", fact) is negation-as-failure on BASE facts only (closed-world),
or on 'fees_paid' style facts, so rule order never changes the result.
Each cycle: match all rules against the facts at the START of the cycle,
then fire every new conclusion (so a derived fact is usable from the next cycle).
"""
RULES = [
 ("R1",  [("student_type","freshman")],   ("needs","form138")),
 ("R2",  [("student_type","freshman")],   ("needs","psa_birth_certificate")),
 ("R3",  [("student_type","transferee")], ("needs","tor")),
 ("R4",  [("student_type","transferee")], ("needs","honorable_dismissal")),
 ("R5",  [("student_type","returning")],  ("needs","clearance")),
 ("R6",  [("needs","?d"), ("not",("has","?d"))], ("missing","?d")),
 ("R7",  [("missing","?d")],              ("docs_incomplete",)),
 ("R8",  [("student_type","freshman"),("has","form138"),("has","psa_birth_certificate")], ("docs_complete",)),
 ("R9",  [("student_type","transferee"),("has","tor"),("has","honorable_dismissal")],     ("docs_complete",)),
 ("R10", [("student_type","returning"),("has","clearance")],                              ("docs_complete",)),
 ("R11", [("docs_complete",),("fees_paid",)],               ("eligible","official_enrollment")),
 ("R12", [("docs_complete",),("not",("fees_paid",))],       ("next_step","pay_assessment")),
 ("R13", [("docs_incomplete",)],                            ("next_step","submit_missing_documents")),
]
def subst(t,b): return tuple(b.get(x,x) for x in t)
def match(cond,facts,b):
    if cond[0]=="not":
        pat=subst(cond[1],b)
        return [b] if pat not in facts else []
    out=[]
    for f in facts:
        if len(f)!=len(cond): continue
        nb=dict(b); ok=True
        for c,v in zip(cond,f):
            if c.startswith("?"):
                if nb.setdefault(c,v)!=v: ok=False;break
            elif c!=v: ok=False;break
        if ok: out.append(nb)
    return out
def fire(rule,facts):
    rid,conds,concl=rule; bs=[{}]
    for c in conds: bs=[nb for b in bs for nb in match(c,facts,b)]
    return [(subst(concl,b),b) for b in bs]
def forward(facts):
    facts=set(facts); log=[]; cycle=0
    while True:
        cycle+=1; new={}
        for r in RULES:
            for concl,b in fire(r,facts):
                if concl not in facts and concl not in new: new[concl]=(r[0],b)
        if not new: break
        for c,(rid,b) in new.items(): log.append((cycle,rid,b,c))
        facts|=set(new)
    return facts,log
def run(name,facts):
    print("==",name); print("initial:",sorted(facts))
    final,log=forward(facts)
    for cyc,rid,b,c in log: print(f" cycle {cyc}: {rid} {b or ''} -> {c}")
    print("final next_step/eligible:",sorted(f for f in final if f[0] in("next_step","eligible")))
    return final
if __name__=="__main__":
    # Case 1 = the hand-worked trace in the proposal (made-up student)
    f=run("Case 1 transferee, has TOR, no honorable dismissal, fees unpaid",
          {("student_type","transferee"),("has","tor")})
    assert ("next_step","submit_missing_documents") in f and ("missing","honorable_dismissal") in f
    assert ("missing","tor") not in f and ("eligible","official_enrollment") not in f
    # Case 2-6: test suite for rules
    f=run("Case 2 freshman complete, fees paid",{("student_type","freshman"),("has","form138"),("has","psa_birth_certificate"),("fees_paid",)})
    assert ("eligible","official_enrollment") in f and ("docs_incomplete",) not in f
    f=run("Case 3 freshman complete, fees unpaid",{("student_type","freshman"),("has","form138"),("has","psa_birth_certificate")})
    assert ("next_step","pay_assessment") in f and ("eligible","official_enrollment") not in f
    f=run("Case 4 returning, no clearance",{("student_type","returning")})
    assert ("missing","clearance") in f
    f=run("Case 5 freshman missing both",{("student_type","freshman")})
    assert {("missing","form138"),("missing","psa_birth_certificate")}<=f
    f=run("Case 6 returning complete paid",{("student_type","returning"),("has","clearance"),("fees_paid",)})
    assert ("eligible","official_enrollment") in f
    print("ALL ASSERTIONS PASSED")
