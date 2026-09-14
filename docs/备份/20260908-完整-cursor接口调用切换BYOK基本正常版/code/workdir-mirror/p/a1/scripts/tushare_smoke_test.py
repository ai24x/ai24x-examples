import os


def main() -> None:
    token = os.getenv("AI24X_TUSHARE_TOKEN", "").strip()
    if not token:
        raise SystemExit("Missing env: AI24X_TUSHARE_TOKEN")

    import tushare as ts  # type: ignore

    ts.set_token(token)
    pro = ts.pro_api()

    # Basic A-share daily
    df = pro.daily(ts_code="000001.SZ", start_date="20260101")
    print("A-share daily rows:", len(df))
    print(df.head(3))
    try:
        af = pro.adj_factor(ts_code="000001.SZ", start_date="20260101")
        print("A-share adj_factor rows:", len(af))
        print(af.head(3))
    except Exception as e:
        print("adj_factor not available:", e)

    # BSE daily (auto-pick a listed BSE symbol to verify coverage)
    try:
        basics = pro.stock_basic(exchange="BSE", list_status="L", fields="ts_code,symbol,name,list_date")
        if basics is None or getattr(basics, "empty", False):
            print("BSE stock_basic empty (no permission or no data)")
        else:
            picked = str(basics.iloc[0]["ts_code"])  # type: ignore[attr-defined]
            print("Picked BSE ts_code:", picked)
            df_bj = pro.daily(ts_code=picked, start_date="20260101")
            print("BSE daily rows:", len(df_bj))
            print(df_bj.head(3))
    except Exception as e:
        print("BSE stock_basic not available:", e)

    # Optional: realtime day bar (requires separate permission)
    try:
        rt = pro.rt_k(ts_code="000001.SZ")
        print("rt_k rows:", len(rt))
        print(rt.head(1))
    except Exception as e:
        print("rt_k not available:", e)


if __name__ == "__main__":
    main()

