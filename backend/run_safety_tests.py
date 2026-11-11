"""
Adversarial Safety Test Suite Runner.
Verifies that 100% of malicious / dangerous queries are rejected by SQLValidator.
"""

import sys
from app.safety.validator import SQLValidator
from app.safety.adversarial_corpus import ADVERSARIAL_CORPUS


def run_safety_tests() -> bool:
    print("==================================================")
    print("SchemaSense: Running Adversarial Safety Test Suite")
    print("==================================================")
    
    # We configure validator with some sample allowed tables
    validator = SQLValidator(allowed_tables={"orders", "customers", "users", "schema_tables", "messages"})
    
    total = len(ADVERSARIAL_CORPUS)
    rejected_count = 0
    failures = []
    
    for case in ADVERSARIAL_CORPUS:
        name = case["name"]
        sql = case["sql"]
        res = validator.validate(sql)
        
        if not res.is_valid:
            rejected_count += 1
            print(f" [PASS - REJECTED] {name:<30} Reason: {res.error_message}")
        else:
            failures.append((name, sql, res.sanitized_sql))
            print(f" [FAIL - ALLOWED!] {name:<30} SQL: {sql}")
            
    rejection_rate = (rejected_count / total) * 100.0
    print("\n--------------------------------------------------")
    print(f"Total Cases: {total} | Rejected: {rejected_count} | Allowed: {len(failures)}")
    print(f"Rejection Rate: {rejection_rate:.1f}% (Required: 100.0%)")
    print("--------------------------------------------------")
    
    if rejected_count == total:
        print(" SUCCESS: 100% of adversarial safety cases rejected.")
        return True
    else:
        print(f"❌ FAILURE: {len(failures)} safety tests bypassed validation!")
        return False


if __name__ == "__main__":
    success = run_safety_tests()
    sys.exit(0 if success else 1)

