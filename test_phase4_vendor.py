
from backend.parser_beta import fix_vendor_name

def test_vendor_matching():
    cases = [
        ('Aman Traders', 'Aman Traders'),       # Exact
        ('Aman Trcders', 'Aman Traders'),       # 1 Typo
        ('Sharma Bros', 'Sharma Brothers'),     # Abbr/Mismatch (Might fail if score < 0.82)
        ('Shrma Brothers', 'Sharma Brothers'),  # Typo
        ('Apollo Pharmcy', 'Apollo Pharmacy'),  # Typo
        ('Unknown Store', 'Unknown Store'),     # No match
        ('R.K. Ent.', 'R.K. Enterprises'),      # Abbr
        ('Reliance Frsh', 'Reliance Fresh')     # Typo
    ]
    
    print("--- Testing Vendor Fuzzy Match ---")
    for inp, expected in cases:
        res = fix_vendor_name(inp)
        status = "✅" if res == expected else f"Change? ({res})"
        if res != inp and res != expected: status = f"❌ Wrong Fix ({res})"
        if res == inp and res != expected: status = f"⚠️ No Fix (Score too low?)"
            
        print(f"'{inp}' -> '{res}' : {status}")

if __name__ == "__main__":
    test_vendor_matching()
