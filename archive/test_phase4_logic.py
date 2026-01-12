
from backend.parser_beta import validate_and_correct, clean_amount

def test_clean_amount():
    cases = [
        ('l23', 123.0),
        ('S0.00', 50.0),
        ('2O0', 200.0),
        ('1,234.56', 1234.56),
        ('None', None),
        ('Tota1', None) # Should fail as not a number even after sub
    ]
    print("--- Testing clean_amount ---")
    for inp, expected in cases:
        res = clean_amount(inp)
        status = "✅" if res == expected else f"❌ (Got {res})"
        print(f"'{inp}' -> {expected} : {status}")

def test_validation_logic():
    print("\n--- Testing validate_and_correct ---")
    
    # Case 1: Missing Gross, derived from Items
    data1 = {
        'items': [{'line_amount': 100.0}, {'line_amount': 50.0}],
        'gross_total': None,
        'total_deductions': 0.0,
        'net_total': 150.0
    }
    d1, w1, c1 = validate_and_correct(data1)
    print(f"Case 1 (Missing Gross): Gross={d1['gross_total']} (Exp: 150.0) | {c1}")

    # Case 2: Math Error, trust Items
    data2 = {
        'items': [{'line_amount': 100.0}],
        'gross_total': 100.0,
        'total_deductions': 10.0,
        'net_total': 85.0 # Wrong, should be 90
    }
    d2, w2, c2 = validate_and_correct(data2)
    print(f"Case 2 (Math Error): Net={d2['net_total']} (Exp: 90.0) | {c2}")

    # Case 3: Missing Net
    data3 = {
        'gross_total': 200.0,
        'total_deductions': 20.0,
        'net_total': None
    }
    d3, w3, c3 = validate_and_correct(data3)
    print(f"Case 3 (Missing Net): Net={d3['net_total']} (Exp: 180.0) | {c3}")

    # Case 4: Inconsistent Gross vs Items (Tolerance Check)
    data4 = {
        'items': [{'line_amount': 100.0}, {'line_amount': 100.0}], # Sum 200
        'gross_total': 190.0, # Off by 10
        'net_total': 180.0,
        'total_deductions': 10.0
    }
    # Net + Ded = 190. Gross = 190. Item Sum = 200.
    # Logic: Gross matches Net+Ded, so Gross is likely right, items might be wrong (or extra charge).
    # Current logic: "Trust Sum(Items) if it matches Net+Ded". 
    # Here Net+Ded (190) != Sum(Items) (200). So it should just warn.
    d4, w4, c4 = validate_and_correct(data4)
    print(f"Case 4 (Ambiguous): Warn len={len(w4)} | {w4}")

if __name__ == "__main__":
    test_clean_amount()
    test_validation_logic()
