"""Sponsored Products Search Term report -> ppc_search_terms."""

import pandas as pd

from .headers import clean_int, clean_money, clean_str, dedupe_last, map_columns

SPEC = {
    "campaign_name": {"synonyms": ["campaignname", "campaign"], "required": True, "cleaner": clean_str},
    "ad_group_name": {"synonyms": ["adgroupname", "adgroup"], "cleaner": clean_str},
    "targeting": {"synonyms": ["targeting", "keyword", "keywordtext"], "cleaner": clean_str},
    "match_type": {"synonyms": ["matchtype"], "cleaner": clean_str},
    "search_term": {"synonyms": ["customersearchterm", "searchterm"], "required": True, "cleaner": clean_str},
    "impressions": {"synonyms": ["impressions"], "cleaner": clean_int},
    "clicks": {"synonyms": ["clicks"], "cleaner": clean_int},
    "spend": {"synonyms": ["spend", "cost", "totalspend"], "required": True, "cleaner": clean_money},
    "sales_7d": {"synonyms": ["7daytotalsales", "sales7d", "totalsales", "7daytotalsalesusd"], "cleaner": clean_money},
    "orders_7d": {"synonyms": ["7daytotalorders", "orders7d"], "cleaner": clean_int},
    "units_7d": {"synonyms": ["7daytotalunits", "units7d"], "cleaner": clean_int},
}


def parse(df: pd.DataFrame, upload: dict):
    mapped = map_columns(df, SPEC)
    rows = []
    for record, source in zip(mapped.to_dict(orient="records"), df.to_dict(orient="records")):
        if not record["campaign_name"] or not record["search_term"]:
            continue
        record["ad_group_name"] = record["ad_group_name"] or ""
        record["targeting"] = record["targeting"] or ""
        rows.append(
            {
                **record,
                "client_id": upload["client_id"],
                "upload_id": upload["id"],
                "period_start": upload["period_start"],
                "period_end": upload["period_end"],
                "raw": source,
            }
        )
    rows = dedupe_last(rows, ("campaign_name", "ad_group_name", "targeting", "search_term"))
    return (
        "ppc_search_terms",
        rows,
        "client_id,period_start,period_end,campaign_name,ad_group_name,targeting,search_term",
    )
