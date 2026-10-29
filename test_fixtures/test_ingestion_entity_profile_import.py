"""The capture ingestion implementation must import the packaged Entity Profile API, not the retired root launcher."""


def test_ingestion_impl_imports_and_uses_packaged_entity_profile():
    from workbench.captures.ingestion import _build_index_impl as impl
    assert impl.entity_profile.__name__ == "workbench.devtools.entities.profile"
    assert callable(impl.entity_profile.init_db) and callable(impl.entity_profile.record_field)
    assert "capture" in impl.entity_profile.CONFIDENCE
