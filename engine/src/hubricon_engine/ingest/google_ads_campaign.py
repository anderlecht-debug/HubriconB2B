"""Google Ads campaign report (Campaigns > Download > CSV) -> ppc_spend
(channel shopify). The download opens with a two-line preamble ("Campaign
report" and the date range) that readers.py's header finder skips because
the rows beneath are wider, then Day, Campaign, Campaign state, Budget,
Impressions, Clicks, Cost, Conversions, Conv. value (older accounts print
"Total conv. value"), and closes with "Total: ..." trailer lines, which
are sums and are skipped.

campaign_id and campaign_name are "Google · " + Campaign for the same
reason meta_ads.py prefixes: the export has no id and the ad table is keyed
on the campaign id per client and day.
"""

import pandas as pd

from .headers import as_int, clean_int, clean_money, clean_str, dedupe_last, is_total_row, map_columns, to_iso_date

SPEC = {
    "report_date": {"synonyms": ["day", "date"], "required": True, "cleaner": clean_str},
    "campaign_name": {"synonyms": ["campaign", "campaignname"], "required": True, "cleaner": clean_str},
    "spend": {"synonyms": ["cost", "spend"], "required": True, "cleaner": clean_money},
    "sales": {"synonyms": ["convvalue", "totalconvvalue", "conversionvalue", "allconvvalue"], "cleaner": clean_money},
    "clicks": {"synonyms": ["clicks"], "cleaner": clean_int},
    "impressions": {"synonyms": ["impressions", "impr"], "cleaner": clean_int},
}
PREFIX = "Google · "
CHANNEL = "shopify"


def parse(df: pd.DataFrame, upload: dict):
    mapped = map_columns(df, SPEC)
    rows = []
    for record, source in zip(mapped.to_dict(orient="records"), df.to_dict(orient="records")):
        if not record["report_date"] or is_total_row(record["report_date"]):
            continue
        if not record["campaign_name"] or is_total_row(record["campaign_name"]):
            continue
        name = PREFIX + record["campaign_name"]
        rows.append(
            {
                "client_id": upload["client_id"],
                "upload_id": upload["id"],
                "channel": CHANNEL,
                "report_date": to_iso_date(record["report_date"]),
                "campaign_id": name,
                "campaign_name": name,
                "spend": record["spend"],
                "sales": record["sales"],
                "clicks": as_int(record["clicks"]),
                "impressions": as_int(record["impressions"]),
                "raw": source,
            }
        )
    rows = dedupe_last(rows, ("campaign_id", "report_date"))
    return "ppc_spend", rows, "client_id,campaign_id,report_date"
