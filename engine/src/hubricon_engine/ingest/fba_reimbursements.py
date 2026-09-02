"""Reimbursements report -> fba_reimbursements. What Amazon has already paid
back for lost, damaged or returned units; the reimbursement model reconciles
this against the inventory ledger to find what it has not paid back."""

import pandas as pd

from .headers import as_int, clean_int, clean_money, clean_str, dedupe_last, map_columns, row_key, to_iso_date

SPEC = {
    "approval_date": {"synonyms": ["approvaldate", "date", "approvaldateutc"], "cleaner": clean_str},
    "reimbursement_id": {"synonyms": ["reimbursementid"], "required": True, "cleaner": clean_str},
    "case_id": {"synonyms": ["caseid"], "cleaner": clean_str},
    "amazon_order_id": {"synonyms": ["amazonorderid", "orderid"], "cleaner": clean_str},
    "reason": {"synonyms": ["reason"], "required": True, "cleaner": clean_str},
    "sku": {"synonyms": ["sku", "msku", "sellersku", "merchantsku"], "cleaner": clean_str},
    "fnsku": {"synonyms": ["fnsku"], "cleaner": clean_str},
    "asin": {"synonyms": ["asin"], "cleaner": clean_str},
    "product_name": {"synonyms": ["productname", "title", "itemname"], "cleaner": clean_str},
    "condition": {"synonyms": ["condition"], "cleaner": clean_str},
    "currency": {"synonyms": ["currencyunit", "currency", "currencycode"], "cleaner": clean_str},
    "amount_per_unit": {"synonyms": ["amountperunit"], "cleaner": clean_money},
    "amount_total": {"synonyms": ["amounttotal", "amount", "totalamount"], "cleaner": clean_money},
    "quantity_reimbursed_cash": {"synonyms": ["quantityreimbursedcash"], "cleaner": clean_int},
    "quantity_reimbursed_inventory": {"synonyms": ["quantityreimbursedinventory"], "cleaner": clean_int},
    "quantity_reimbursed_total": {"synonyms": ["quantityreimbursedtotal"], "cleaner": clean_int},
    "original_reimbursement_id": {"synonyms": ["originalreimbursementid"], "cleaner": clean_str},
    "original_reimbursement_type": {"synonyms": ["originalreimbursementtype"], "cleaner": clean_str},
}
INT_FIELDS = ("quantity_reimbursed_cash", "quantity_reimbursed_inventory", "quantity_reimbursed_total")


def parse(df: pd.DataFrame, upload: dict):
    mapped = map_columns(df, SPEC)
    rows = []
    for record, source in zip(mapped.to_dict(orient="records"), df.to_dict(orient="records")):
        sku = record["sku"] or record["fnsku"]  # inventory-only reimbursements can leave sku blank
        if not record["reimbursement_id"] or not sku or not record["reason"]:
            continue
        approval_date = to_iso_date(record["approval_date"])
        rows.append(
            {
                **record,
                "client_id": upload["client_id"],
                "upload_id": upload["id"],
                "row_key": row_key(record["reimbursement_id"], sku, record["reason"], approval_date),
                "approval_date": approval_date,
                "sku": sku,
                "currency": record["currency"] or "USD",
                **{k: as_int(record[k]) for k in INT_FIELDS},
                "raw": source,
            }
        )
    rows = dedupe_last(rows, ("row_key",))
    return "fba_reimbursements", rows, "client_id,row_key"
