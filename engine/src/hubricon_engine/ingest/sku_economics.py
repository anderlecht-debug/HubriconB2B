"""SKU Economics export -> sku_economics (the SKU<->ASIN bridge + fees)."""

import pandas as pd

from .headers import clean_int, clean_money, clean_str, dedupe_last, map_columns

SPEC = {
    "sku": {"synonyms": ["sku", "msku", "merchantsku", "sellersku"], "required": True, "cleaner": clean_str},
    "asin": {"synonyms": ["asin", "childasin"], "cleaner": clean_str},
    "units_sold": {"synonyms": ["unitssold", "netunitssold", "unitsordered"], "cleaner": clean_int},
    "avg_sales_price": {
        "synonyms": ["averagesalesprice", "avgsalesprice", "averagesellingprice", "averageprice"],
        "cleaner": clean_money,
    },
    "sales": {"synonyms": ["sales", "netsales", "orderedproductsales", "productsales"], "cleaner": clean_money},
    "referral_fees": {"synonyms": ["referralfee", "referralfees", "netreferralfee"], "cleaner": clean_money},
    "fba_fulfillment_fees": {
        "synonyms": ["fbafulfillmentfee", "fbafulfillmentfees", "netfbafulfillmentfee", "fulfillmentfee"],
        "cleaner": clean_money,
    },
    "storage_fees": {
        "synonyms": ["storagefee", "storagefees", "netstoragefee", "monthlystoragefee", "fbastoragefee"],
        "cleaner": clean_money,
    },
    "other_fees": {"synonyms": ["otherfees", "otherfee", "othertransactionfees"], "cleaner": clean_money},
    "net_proceeds": {"synonyms": ["netproceeds", "netproceedstotal"], "cleaner": clean_money},
}


def parse(df: pd.DataFrame, upload: dict):
    mapped = map_columns(df, SPEC)
    rows = []
    for record, source in zip(mapped.to_dict(orient="records"), df.to_dict(orient="records")):
        if not record["sku"]:
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
    rows = dedupe_last(rows, ("sku",))
    return "sku_economics", rows, "client_id,channel,sku,period_start,period_end"
