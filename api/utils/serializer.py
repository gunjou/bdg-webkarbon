# api/utils/serializer.py
import uuid
from datetime import datetime, date, time
from decimal import Decimal

from sqlalchemy.engine import Row, RowMapping


def serialize_value(obj):
    """Ubah hasil query / tipe Python menjadi tipe yang aman untuk JSON."""
    if isinstance(obj, (list, tuple)):
        return [serialize_value(item) for item in obj]
    if isinstance(obj, (dict, RowMapping)):
        return {k: serialize_value(v) for k, v in obj.items()}
    if isinstance(obj, Row):
        return serialize_value(obj._mapping)
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, uuid.UUID):
        return str(obj)
    # datetime harus dicek sebelum date (datetime adalah subclass date)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, time):
        return obj.strftime("%H:%M")
    return obj
