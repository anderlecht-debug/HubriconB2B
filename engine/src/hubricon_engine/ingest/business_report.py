"""Business Report "Detail Page Sales and Traffic by Child Item" -> asin_traffic."""

import pandas as pd

from .headers import clean_int, clean_money, clean_pct, clean_str, dedupe_last, map_columns

SPEC = {
    "parent_asin": {"synonyms": ["parentasin"], "cleaner": clean_str},
    "child_asin": {"synonyms": ["childasin", "asin"], "required": True, "cleaner": clean_str},
    "title": {"synonyms": ["title", "productname"], "cleaner": clean_str},
    "sessions": {"synonyms": ["sessions", "sessionstotal", "sessionscombinedtotal"], "cleaner": clean_int},
    "page_views": {"synonyms": ["pageviews", "pageviewstotal", "pageviewscombinedtotal"], "cleaner": clean_int},
    "buy_box_pct": {
        "synonyms": ["buyboxpercentage", "featuredofferbuyboxpercentage", "featuredofferpercentage"],
        "cleaner": clean_pct,
    },
    "units_ordered": {"synonyms": ["unitsordered"], "required": True, "cleaner": clean_int},
    "ordered_product_sales": {"synonyms": ["orderedproductsales"], "required": True, "cleaner": clean_money},
    "total_order_items": {"synonyms": ["totalorderitems"], "cleaner": clean_int},
    "unit_session_pct": {"synonyms": ["unitsessionpercentage"], "cleaner": clean_pct},
}


def parse(df: pd.DataFrame, upload: dict):
    mapped = map_columns(df, SPEC)
    rows = []
    for record, source in zip(mapped.to_dict(orient="records"), df.to_dict(orient="records")):
        if not record["child_asin"]:
            continue
        rows.append(
            {
                **record,
                "client_id": upload["client_id"],
                "upload_id": upload["id"],
                "channel": "amazon",
                "period_start": upload["period_start"],
                "period_end": upload["period_end"],
                "raw": source,
            }
        )
    rows = dedupe_last(rows, ("child_asin",))
    return "asin_traffic", rows, "client_id,channel,child_asin,period_start,period_end"
