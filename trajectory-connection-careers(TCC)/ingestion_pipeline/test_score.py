def normalize(val: float, min_val: float, max_val: float) -> float:
    return max(0.0, min(1.0, (val - min_val) / (max_val - min_val)))

def encode_activity(level: str) -> float:
    return {"low": 0.3, "medium": 0.6, "high": 1.0}.get(level.lower(), 0.5)

val1 = normalize(8, 0, 15) * 0.30
val2 = encode_activity("medium") * 0.20
val3 = normalize(len(["github"]), 1, 4) * 0.15
val4 = 0.1473 * 0.20
val5 = normalize(len(["a", "b", "c"]), 1, 5) * 0.15
total = val1 + val2 + val3 + val4 + val5

print(f"val1: {val1}")
print(f"val2: {val2}")
print(f"val3: {val3}")
print(f"val4: {val4}")
print(f"val5: {val5}")
print(f"Total: {total}")
