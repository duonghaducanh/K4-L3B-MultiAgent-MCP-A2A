import itertools
TARGET = 0.929917
buckets = [(0.94, 86), (0.8, 10), (0.72, 4)]

def brier(c, y):   # y=1 correct
    return 1 - (c - y)**2
def lin(c, y):
    return 1 - abs(c - y)
def rew(c, y):
    return c if y else 1 - c
def rew2(c, y):
    return 1.0 if y else (1 - c)
def conly(c, y):
    return c if y else 0.0
def logloss_like(c, y):
    import math
    p = c if y else 1 - c
    return 1 + math.log(max(p, 1e-9)) / math.log(0.5) * 0  # placeholder

FORMS = {"brier": brier, "lin": lin, "rew": rew, "rew2": rew2, "conly": conly}

for name, f in FORMS.items():
    hits = []
    # distribute wrong counts across the three buckets (all orders of magnitude)
    for n94 in range(0, 87):
        for n8 in range(0, 11):
            for n72 in range(0, 5):
                if n94 + n8 + n72 > 15: continue
                tot = 0.0
                for (c, n), nw in zip(buckets, (n94, n8, n72)):
                    tot += (n - nw) * f(c, 1) + nw * f(c, 0)
                s = tot / 100.0
                if abs(s - TARGET) < 1e-9:
                    hits.append((n94, n8, n72))
    print(f"{name:8s} exact-hits={hits}")

print()
print("candidate table under brier:")
for n94, n8, n72 in [(0,10,0),(0,9,1),(0,10,0),(1,9,0),(0,8,2)]:
    tot = 0.0
    for (c, n), nw in zip(buckets, (n94, n8, n72)):
        tot += (n - nw) * brier(c, 1) + nw * brier(c, 0)
    print(f"  wrong@(.94,.8,.72)=({n94},{n8},{n72}) total={n94+n8+n72:2d} score={tot/100:.6f}")

print()
print("under-confidence hypothesis (all correct):")
tot = sum(n * brier(c, 1) for c, n in buckets)
print(f"  all-correct score = {tot/100:.6f}")
