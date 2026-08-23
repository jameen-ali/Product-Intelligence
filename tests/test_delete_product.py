import pytest
from uuid import uuid4
from app.models.entities import Product, Source
from app.core.db import SessionLocal

def test_delete_product_endpoint(app_client):
    db = SessionLocal()
    # 1. Create temporary product entity
    test_prod_name = f"Test Delete Motor {uuid4().hex[:6]}"
    p = Product(name=test_prod_name, model_number="DEL-999", manufacturer="TestCorp", category="Motors")
    db.add(p)
    db.commit()
    db.refresh(p)
    product_id = str(p.id)

    # Add source to product
    s = Source(product_id=p.id, type="datasheet", name="Test Datasheet", authority_rank=1)
    db.add(s)
    db.commit()
    raw_p_id = p.id
    db.close()

    # 2. Verify product exists via GET /products/{id}
    res_get = app_client.get(f"/products/{product_id}")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == test_prod_name

    # 3. Delete product via DELETE /products/{id}
    res_del = app_client.delete(f"/products/{product_id}")
    assert res_del.status_code == 200
    data_del = res_del.json()
    assert data_del["success"] is True
    assert data_del["product_id"] == product_id

    # 4. Verify product 404 on GET /products/{id}
    res_get2 = app_client.get(f"/products/{product_id}")
    assert res_get2.status_code == 404

    # 5. Verify product deleted from PostgreSQL database
    db2 = SessionLocal()
    deleted_p = db2.query(Product).filter(Product.id == raw_p_id).first()
    assert deleted_p is None
    deleted_s = db2.query(Source).filter(Source.product_id == raw_p_id).first()
    assert deleted_s is None
    db2.close()

def test_delete_nonexistent_product_returns_404(app_client):
    fake_id = str(uuid4())
    res = app_client.delete(f"/products/{fake_id}")
    assert res.status_code == 404
