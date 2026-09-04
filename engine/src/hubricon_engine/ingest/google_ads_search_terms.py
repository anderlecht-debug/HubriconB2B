"""Google Ads search terms report (Insights and reports > Search terms >
Download) -> ppc_search_terms (channel shopify). Same preamble and
"Total: ..." trailers as the campaign download; the body is Search term,
Match type, Added/Excluded, Campaign, Ad group, Currency code, Impressions,
Clicks, Cost, Conversions, Conv. value ("Total conv. value" on older
accounts).

Rows take the shape ppc_search_terms.py writes: campaign_name is "Google · "
+ Campaign, targeting is the Keyword column when the download carries one
and "" otherwise (the table's key needs a value, not a NULL), sales_7d is
the conversion value and orders_7d the rounded conversion count — Google
attributes on its own window, not Amazon's seven days, and the column
name is the table's, not a claim about the window. units_7d is unknown.
"""

import pandas as pd

from .headers import as_int, clean_int, clean_money, clean_str, dedupe_last, is_total_row, map_columns

SPEC = {
    "campaign_name": {"synonyms": ["campaign", "campaignname"], "required": True, "cleaner": clean_str},
    "ad_group_name": {"synonyms": ["adgroup", "adgroupname"], "cleaner": clean_str},
    "targeting": {"synonyms": ["keyword", "keywordtext", "targeting"], "cleaner": clean_str},
    "match_type": {"synonyms": ["matchtype", "searchtermmatchtype"], "cleaner": clean_str},
    "search_term": {"synonyms": ["searchterm"], "required": True, "cleaner": clean_str},
    "impressions": {"synonyms": ["impressions", "impr"], "cleaner": clean_int},
    "clicks": {"synonyms": ["clicks"], "cleaner": clean_int},
    "spend": {"synonyms": ["cost", "spend"], "required": True, "cleaner": clean_money},
    "sales_7d": {"synonyms": ["convvalue", "totalconvvalue", "conversionvalue", "allconvvalue"], "cleaner": clean_money},
    "orders_7d": {"synonyms": ["conversions", "allconv"], "cleaner": clean_int},
}
PREFIX = "Google · "
CHANNEL = "shopify"


def parse(df: pd.DataFrame, upload: dict):
    mapped = map_columns(df, SPEC)
    rows = []
    for record, source in zip(mapped.to_dict(orient="records"), df.to_dict(orient="records")):
        if not record["search_term"] or is_total_row(record["search_term"]):
            continue
        if not record["campaign_name"] or is_total_row(record["campaign_name"]):
            continue
        rows.append(
            {
                "client_id": upload["client_id"],
                "upload_id": upload["id"],
                "channel": CHANNEL,
                "period_start": upload["period_start"],
                "period_end": upload["period_end"],
                "campaign_name": PREFIX + record["campaign_name"],
                "ad_group_name": record["ad_group_name"] or "",
                "targeting": record["targeting"] or "",
                "match_type": record["match_type"],
                "search_term": record["search_term"],
                "impressions": as_int(record["impressions"]),
                "clicks": as_int(record["clicks"]),
                "spend": record["spend"],
                "sales_7d": record["sales_7d"],
                "orders_7d": as_int(record["orders_7d"]),
                "units_7d": None,
                "raw": source,
            }
        )
    rows = dedupe_last(rows, ("campaign_name", "ad_group_name", "targeting", "search_term"))
    return (
        "ppc_search_terms",
        rows,
        "client_id,period_start,period_end,campaign_name,ad_group_name,targeting,search_term",
    )
