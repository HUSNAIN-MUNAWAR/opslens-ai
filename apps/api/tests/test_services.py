from app.services import import_preview


def test_import_preview_surfaces_validation_error():
    preview = import_preview([{"sku": "ABC", "name": "Product"}], "products")
    assert preview["status"] == "validation_failed"
    assert preview["records_invalid"] == 1
