"""Inventory Age / Manage Inventory Health export -> inventory_health. A
snapshot keyed on the upload's date, like inventory_levels. Amazon's seven
estimated-ais-* buckets (aged inventory surcharge by age band) are summed
into estimated_aged_surcharge; None when the export carries none of them,
so a model cannot mistake "column absent" for "no surcharge"."""

import pandas as pd

from .headers import as_int, clean_bool, clean_int, clean_money, clean_pct, clean_str, dedupe_last, map_columns

SPEC = {
    "sku": {"synonyms": ["sku", "msku", "sellersku", "merchantsku"], "cleaner": clean_str},
    "fnsku": {"synonyms": ["fnsku"], "cleaner": clean_str},
    "asin": {"synonyms": ["asin"], "cleaner": clean_str},
    "product_name": {"synonyms": ["productname", "title", "itemname"], "cleaner": clean_str},
    "condition": {"synonyms": ["condition"], "cleaner": clean_str},
    "available": {
        "synonyms": ["available", "availablequantity", "fulfillablequantity", "afnfulfillablequantity", "sellable"],
        "cleaner": clean_int,
    },
    "pending_removal": {"synonyms": ["pendingremovalquantity", "pendingremoval"], "cleaner": clean_int},
    "inv_age_0_to_90": {"synonyms": ["invage0to90days", "inventoryage0to90days", "0to90days"], "cleaner": clean_int},
    "inv_age_91_to_180": {"synonyms": ["invage91to180days", "inventoryage91to180days", "91to180days"], "cleaner": clean_int},
    "inv_age_181_to_270": {"synonyms": ["invage181to270days", "inventoryage181to270days", "181to270days"], "cleaner": clean_int},
    "inv_age_271_to_365": {"synonyms": ["invage271to365days", "inventoryage271to365days", "271to365days"], "cleaner": clean_int},
    "inv_age_365_plus": {
        "synonyms": ["invage365plusdays", "inventoryage365plusdays", "365plusdays", "invage365days"],
        "cleaner": clean_int,
    },
    "units_shipped_t7": {"synonyms": ["unitsshippedt7", "unitsshippedlast7days", "unitsshipped7days"], "cleaner": clean_int},
    "units_shipped_t30": {"synonyms": ["unitsshippedt30", "unitsshippedlast30days", "unitsshipped30days"], "cleaner": clean_int},
    "units_shipped_t60": {"synonyms": ["unitsshippedt60", "unitsshippedlast60days", "unitsshipped60days"], "cleaner": clean_int},
    "units_shipped_t90": {"synonyms": ["unitsshippedt90", "unitsshippedlast90days", "unitsshipped90days"], "cleaner": clean_int},
    "sell_through": {"synonyms": ["sellthrough", "sellthroughrate"], "cleaner": clean_pct},
    "days_of_supply": {
        "synonyms": ["daysofsupply", "daysofsupplyatamazonfulfillmentnetwork", "estimateddaysofsupply"],
        "cleaner": clean_int,
    },
    "estimated_excess_quantity": {
        "synonyms": ["estimatedexcessquantity", "estimatedexcess", "excessquantity"],
        "cleaner": clean_int,
    },
    "item_volume": {"synonyms": ["itemvolume", "itemvolumecubicfeet"], "cleaner": clean_money},
    "storage_volume": {"synonyms": ["storagevolume", "totalstoragevolume", "storagevolumecubicfeet"], "cleaner": clean_money},
    "estimated_storage_cost_next_month": {
        "synonyms": ["estimatedstoragecostnextmonth", "estimatedmonthlystoragecost"],
        "cleaner": clean_money,
    },
    "ais_181_210": {"synonyms": ["estimatedais181210days"], "cleaner": clean_money},
    "ais_211_240": {"synonyms": ["estimatedais211240days"], "cleaner": clean_money},
    "ais_241_270": {"synonyms": ["estimatedais241270days"], "cleaner": clean_money},
    "ais_271_300": {"synonyms": ["estimatedais271300days"], "cleaner": clean_money},
    "ais_301_330": {"synonyms": ["estimatedais301330days"], "cleaner": clean_money},
    "ais_331_365": {"synonyms": ["estimatedais331365days"], "cleaner": clean_money},
    "ais_365_plus": {"synonyms": ["estimatedais365plusdays"], "cleaner": clean_money},
    "recommended_action": {"synonyms": ["recommendedaction", "recommendedactions", "alert"], "cleaner": clean_str},
    "low_inventory_level_fee_applied": {
        "synonyms": ["lowinventorylevelfeeapplied", "lowinventorylevelfee"],
        "cleaner": clean_bool,
    },
    "your_price": {"synonyms": ["yourprice", "price"], "cleaner": clean_money},
    "sales_price": {"synonyms": ["salesprice", "saleprice"], "cleaner": clean_money},
    "currency": {"synonyms": ["currency", "currencycode"], "cleaner": clean_str},
    "healthy_inventory_level": {"synonyms": ["healthyinventorylevel", "healthyinventorylevelunits"], "cleaner": clean_int},
    "storage_type": {"synonyms": ["storagetype", "sizetier"], "cleaner": clean_str},
    "weeks_of_cover_t30": {"synonyms": ["weeksofcovert30", "weeksofcover30days", "weeksofcover"], "cleaner": clean_money},
}
AIS_FIELDS = ("ais_181_210", "ais_211_240", "ais_241_270", "ais_271_300", "ais_301_330", "ais_331_365", "ais_365_plus")
INT_FIELDS = (
    "available", "pending_removal",
    "inv_age_0_to_90", "inv_age_91_to_180", "inv_age_181_to_270", "inv_age_271_to_365", "inv_age_365_plus",
    "units_shipped_t7", "units_shipped_t30", "units_shipped_t60", "units_shipped_t90",
    "days_of_supply", "estimated_excess_quantity", "healthy_inventory_level",
)


def parse(df: pd.DataFrame, upload: dict):
    mapped = map_columns(df, SPEC)
    rows = []
    for record, source in zip(mapped.to_dict(orient="records"), df.to_dict(orient="records")):
        sku = record["sku"] or record["fnsku"]
        if not sku:
            continue
        surcharges = [record[k] for k in AIS_FIELDS if record[k] is not None]
        row = {k: v for k, v in record.items() if k not in AIS_FIELDS}
        row.update(
            {
                "client_id": upload["client_id"],
                "upload_id": upload["id"],
                "snapshot_date": upload["period_start"],
                "sku": sku,
                "currency": record["currency"] or "USD",
                "estimated_aged_surcharge": round(sum(surcharges), 2) if surcharges else None,
                **{k: as_int(record[k]) for k in INT_FIELDS},
                "raw": source,
            }
        )
        rows.append(row)
    rows = dedupe_last(rows, ("sku",))
    return "inventory_health", rows, "client_id,sku,snapshot_date"
