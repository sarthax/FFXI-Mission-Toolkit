"""FFXI server-source adapter contracts and built-in profiles."""
from .base import AdapterProbe, FieldMapping, LogicalRecord, SchemaProfile, ServerAdapter, TableShape
from .profile_adapters import CustomForkAdapter, DSPAdapter, LSBAdapter, TopazAdapter, TopazNextAdapter, adapter_for
from .profiles import DSP, LSB, TOPAZ, TOPAZ_NEXT
from .schema_coverage import TableMappingCoverage, compare_profile_coverage, profile_mapping_coverage, table_mapping_coverage

__all__ = [
    "AdapterProbe", "FieldMapping", "LogicalRecord", "SchemaProfile", "ServerAdapter", "TableShape",
    "CustomForkAdapter", "DSPAdapter", "LSBAdapter", "TopazAdapter", "TopazNextAdapter", "adapter_for",
    "DSP", "LSB", "TOPAZ", "TOPAZ_NEXT",
    "TableMappingCoverage", "compare_profile_coverage", "profile_mapping_coverage", "table_mapping_coverage",
]
