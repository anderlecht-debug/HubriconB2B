"""Daily Campaign report -> ppc_spend (the table built for the Ads API)."""

from datetime import datetime

import pandas as pd

from .headers import IngestError, clean_int, clean_money, clean_str, dedupe_last, map_columns

SPEC = {
    "report_date": {"synonyms": ["date", "startdate", "day"], "required": True, "cleaner": clean_str},
    "campaign_id": {"synonyms": ["campaignid"], "cleaner": clean_str},
    "campaign_name": {"synonyms": ["campaignname", "campaign"], "required": True, "cleaner": clean_str},
    "spend": {"synonyms": ["spend", "cost", "totalspend"], "required": True, "cleaner": clean_money},
    "sales": {"synonyms": ["7daytotalsales", "14daytotalsales", "sales", "totalsales"], "cleaner": clean_money},
    "clicks": {"synonyms": ["clicks"], "cleaner": clean_int},
    "impressions": {"synonyms": ["impressions"], "cleaner": clean_int},
}

DATE_FORMATS = ("%Y-%m-%d", "%b %d, %Y", "%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y")


def _to_iso_date(value: str) -> str:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    raise IngestError(f"Unrecognized date {value!r} in campaign report")


def parse(df: pd.DataFrame, upload: dict):
    mapped = map_columns(df, SPEC)
    rows = []
    for record, source in zip(mapped.to_dict(orient="records"), df.to_dict(orient="records")):
        if not record["campaign_name"] or not record["report_date"]:
            continue
        rows.append(
            {
                "client_id": upload["client_id"],
                "upload_id": upload["id"],
                "report_date": _to_iso_date(record["report_date"]),
                "campaign_id": record["campaign_id"] or record["campaign_name"],
                "campaign_name": record["campaign_name"],
                "spend": record["spend"],
                "sales": record["sales"],
                "clicks": record["clicks"],
                "impressions": record["impressions"],
                "raw": source,
            }
        )
    rows = dedupe_last(rows, ("campaign_id", "report_date"))
    return "ppc_spend", rows, "client_id,campaign_id,report_date"
