#!/usr/bin/env python3
"""Regression checks for Feature Checker dimension policies."""
from feature_checker import implementation_dimension, validation_dimension

def main():
    assert implementation_dimension([])=="NO_IMPLEMENTATION_RECORDS"
    assert implementation_dimension([{"status":"VERIFIED"}])=="IMPLEMENTATIONS_VERIFIED"
    assert implementation_dimension([{"status":"IMPLEMENTED"}])=="IMPLEMENTATIONS_PRESENT_UNVERIFIED"
    assert implementation_dimension([{"status":"FAILED"}])=="CONTRADICTED"
    assert validation_dimension([])=="NO_VALIDATION_RECORDS"
    assert validation_dimension([{"status":"VERIFIED"}])=="VALIDATIONS_VERIFIED"
    assert validation_dimension([{"status":"VERIFIED"},{"status":"UNKNOWN"}])=="PARTIALLY_VALIDATED"
    assert validation_dimension([{"status":"FAILED"}])=="VALIDATION_FAILED"
    print("feature checker dimension policy self-test: PASS")

if __name__=="__main__":
    main()
