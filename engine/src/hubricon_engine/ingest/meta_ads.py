"""Meta Ads Manager campaign export (breakdown by day) -> ppc_spend (channel
shopify). Campaigns > Export with a daily breakdown prints one line per
campaign per day; Meta appends a totals line with a blank Campaign name,
which is skipped.

Rows take the shape ppc_campaign.py writes so the ad-efficiency model reads
both platforms alike. campaign_id and campaign_name are "Meta · " + the
campaign name: Meta's export carries no campaign id, and the prefix keeps a
Meta campaign and a Google campaign of the same name apart in a table keyed
on (client, campaign_id, date). Sales prefer "Purchases conversion value"
and fall back to "Website purchases conversion value" (the older column).
"""

import pandas as pd

from .headers import as_int, clean_int, clean_money, clean_str, dedupe_last, map_columns, to_iso_date

SPEC = {
    "report_date": {"synonyms": ["reportingstarts", "reportingstart", "day", "date"], "required": True, "cleaner": clean_str},
    "campaign_name": {"synonyms": ["campaignname", "campaign"], "required": True, "cleaner": clean_str},
    "spend": {"synonyms": ["amountspentusd", "amountspent", "spend"], "required": True, "cleaner": clean_money},
    "sales": {
        "synonyms": ["purchasesconversionvalue", "purchaseconversionvalue", "purchasesconversionvalueusd"],
        "cleaner": clean_money,
    },
    "sales_website": {
        "synonyms": ["websitepurchasesconversionvalue", "websitepurchaseconversionvalue",
                     "websitepurchasesconversionvalueusd"],
        "cleaner": clean_money,
    },
    "clicks": {"synonyms": ["linkclicks", "clicks", "clicksall"], "cleaner": clean_int},
    "impressions": {"synonyms": ["impressions"], "cleaner": clean_int},
}
PREFIX = "Meta · "
CHANNEL = "shopify"


def parse(df: pd.DataFrame, upload: dict):
    mapped = map_columns(df, SPEC)
    rows = []
    for record, source in zip(mapped.to_dict(orient="records"), df.to_dict(orient="records")):
        if not record["campaign_name"] or not record["report_date"]:
            continue  # Meta's totals line has no campaign name
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
                "sales": record["sales"] if record["sales"] is not None else record["sales_website"],
                "clicks": as_int(record["clicks"]),
                "impressions": as_int(record["impressions"]),
                "raw": source,
            }
        )
    rows = dedupe_last(rows, ("campaign_id", "report_date"))
    return "ppc_spend", rows, "client_id,campaign_id,report_date"
