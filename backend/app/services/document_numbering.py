"""
Document numbering service for auto-generating unique document numbers.
Uses database sequences with row-level locking for concurrency safety.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.system import DocumentSequence


DOCUMENT_TYPES = {
    "RECEIPT": ("REC", 5),
    "DELIVERY": ("DEL", 5),
    "TRANSFER": ("TRF", 5),
    "ADJUSTMENT": ("ADJ", 5),
    "PURCHASE_ORDER": ("PO", 5),
    "SALES_ORDER": ("SO", 5),
    "STOCK_COUNT": ("CNT", 5),
    "RETURN": ("RET", 5),
}


async def get_next_document_number(db: AsyncSession, document_type: str) -> str:
    """
    Generate next document number atomically.
    E.g., REC-00001, PO-00023
    """
    result = await db.execute(
        select(DocumentSequence)
        .where(DocumentSequence.document_type == document_type)
        .with_for_update()
    )
    seq = result.scalar_one_or_none()

    if seq is None:
        prefix, padding = DOCUMENT_TYPES.get(document_type, (document_type[:3].upper(), 5))
        seq = DocumentSequence(
            document_type=document_type,
            prefix=prefix,
            current_number="0",
            padding=str(padding),
        )
        db.add(seq)
        await db.flush()

    next_num = int(seq.current_number) + 1
    seq.current_number = str(next_num)
    prefix = seq.prefix
    padding = int(seq.padding)

    await db.flush()
    return f"{prefix}-{str(next_num).zfill(padding)}"
