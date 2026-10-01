#!/usr/bin/env python3
"""Regression checks for Feature Checker dimension policies and Phase C compatibility."""
from workbench.core.services import feature_checker as legacy_checker
from workbench.devtools.features import checker


def main():
    assert legacy_checker.implementation_dimension is checker.implementation_dimension
    assert legacy_checker.validation_dimension is checker.validation_dimension
    assert checker.implementation_dimension([])=="NO_IMPLEMENTATION_RECORDS"
    assert checker.implementation_dimension([{"status":"VERIFIED"}])=="IMPLEMENTATIONS_VERIFIED"
    assert checker.implementation_dimension([{"status":"IMPLEMENTED"}])=="IMPLEMENTATIONS_PRESENT_UNVERIFIED"
    assert checker.implementation_dimension([{"status":"FAILED"}])=="CONTRADICTED"
    assert checker.validation_dimension([])=="NO_VALIDATION_RECORDS"
    assert checker.validation_dimension([{"status":"VERIFIED"}])=="VALIDATIONS_VERIFIED"
    assert checker.validation_dimension([{"status":"VERIFIED"},{"status":"UNKNOWN"}])=="PARTIALLY_VALIDATED"
    assert checker.validation_dimension([{"status":"FAILED"}])=="VALIDATION_FAILED"
    print("feature checker Development migration self-test: PASS")


if __name__=="__main__":
    main()
