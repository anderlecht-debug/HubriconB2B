from hubricon_engine.ingest.headers import clean_int, clean_money, clean_pct, normalize


def test_normalize_strips_decoration():
    assert normalize("(Child) ASIN") == "childasin"
    assert normalize("7 Day Total Orders (#)") == "7daytotalorders"
    assert normalize("afn-fulfillable-quantity") == "afnfulfillablequantity"
    assert normalize("Ordered Product Sales") == "orderedproductsales"


def test_clean_money_variants():
    assert clean_money("US$1,234.56") == 1234.56
    assert clean_money("$19.98") == 19.98
    assert clean_money("1.234,56") == 1234.56   # EU thousands/decimal
    assert clean_money("12,34") == 12.34        # lone decimal comma
    assert clean_money("1,234") == 1234         # lone thousands comma
    assert clean_money("(12.34)") == -12.34     # parens negative
    assert clean_money("-929.09") == -929.09
    assert clean_money("") is None
    assert clean_money("N/A") is None


def test_clean_int_and_pct():
    assert clean_int("1,204") == 1204
    assert clean_pct("92.5%") == 92.5
