from app.models.core import Approval


def test_approval_status_enum_uses_values_not_names():
    enum_type = Approval.__table__.c.status.type
    values = list(enum_type.enums)

    assert values == ['pending', 'approved', 'rejected', 'overridden']
