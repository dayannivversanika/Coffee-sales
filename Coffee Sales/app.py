import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# =====================================================
# 1. KONFIGURASI HALAMAN
# =====================================================

st.set_page_config(
    page_title="Coffee Sales Business Intelligence",
    page_icon="☕",
    layout="wide"
)

# Menggunakan Path.cwd() atau langsung nama file agar aman dijalankan di berbagai environment
DB_PATH = Path("coffee_sales_dw.sqlite")


# =====================================================
# 2. MEMBACA DATA MART
# =====================================================

@st.cache_data
def load_data(db_path, last_modified):
    conn = sqlite3.connect(db_path)

    query = """
    SELECT
        f.transaction_id,
        d.date,
        d.year,
        d.quarter,
        d.month,
        d.month_name,
        d.weekday,
        d.weekday_sort,
        d.is_weekend,
        p.coffee_name,
        t.hour_of_day,
        t.time_of_day,
        pay.cash_type,
        f.sales_amount

    FROM fact_sales f

    JOIN dim_date d
        ON f.date_key = d.date_key

    JOIN dim_product p
        ON f.product_key = p.product_key

    JOIN dim_time t
        ON f.time_key = t.time_key

    JOIN dim_payment pay
        ON f.payment_key = pay.payment_key
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    df["date"] = pd.to_datetime(df["date"])
    df["sales_amount"] = pd.to_numeric(
        df["sales_amount"], errors="coerce"
    )
    df["hour_of_day"] = pd.to_numeric(
        df["hour_of_day"], errors="coerce"
    )

    return df.dropna(
        subset=["date", "sales_amount", "coffee_name"]
    )


if not DB_PATH.exists():
    st.error(
        "Database coffee_sales_dw.sqlite tidak ditemukan. "
        "Letakkan file database di folder yang sama dengan app.py."
    )
    st.stop()

df = load_data(str(DB_PATH), DB_PATH.stat().st_mtime)

if df.empty:
    st.error("Data Mart tidak memiliki data transaksi.")
    st.stop()


# =====================================================
# 3. JUDUL DAN DESKRIPSI
# =====================================================

st.title("☕ Coffee Sales Business Intelligence")
st.caption(
    "Dashboard analisis kinerja penjualan dan pendukung "
    "pengambilan keputusan bisnis kedai kopi."
)

st.divider()


# =====================================================
# 4. FILTER SIDEBAR
# =====================================================

st.sidebar.header("Filter Dashboard")

min_date = df["date"].min().date()
max_date = df["date"].max().date()

selected_dates = st.sidebar.date_input(
    "Rentang tanggal",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

if isinstance(selected_dates, (tuple, list)):
    if len(selected_dates) == 2:
        start_date, end_date = selected_dates
    elif len(selected_dates) == 1:
        start_date = end_date = selected_dates[0]
    else:
        start_date, end_date = min_date, max_date
else:
    start_date = end_date = selected_dates

products = sorted(df["coffee_name"].dropna().unique())

selected_products = st.sidebar.multiselect(
    "Pilih produk",
    options=products,
    default=products
)

hours = sorted(
    df["hour_of_day"].dropna().astype(int).unique()
)

selected_hours = st.sidebar.slider(
    "Rentang jam transaksi",
    min_value=int(min(hours)),
    max_value=int(max(hours)),
    value=(int(min(hours)), int(max(hours)))
)

# Menerapkan filter
filtered_df = df[
    (df["date"].dt.date >= start_date)
    & (df["date"].dt.date <= end_date)
    & (df["coffee_name"].isin(selected_products))
    & (df["hour_of_day"].between(
        selected_hours[0], selected_hours[1]
    ))
].copy()

if filtered_df.empty:
    st.warning(
        "Tidak ada transaksi yang sesuai dengan filter. "
        "Silakan ubah pilihan filter."
    )
    st.stop()

st.sidebar.caption(
    f"{len(filtered_df):,} transaksi ditemukan."
)


# =====================================================
# 5. FUNGSI FORMAT RUPIAH
# =====================================================

def format_rupiah(value):
    return "Rp " + f"{value:,.2f}"


# =====================================================
# 6. KPI OVERVIEW
# =====================================================

total_revenue = filtered_df["sales_amount"].sum()
total_transactions = filtered_df["transaction_id"].nunique()
average_transaction = (
    total_revenue / total_transactions
    if total_transactions else 0
)

top_product = (
    filtered_df.groupby("coffee_name")["sales_amount"]
    .sum()
    .idxmax()
)

top_product_revenue = (
    filtered_df.groupby("coffee_name")["sales_amount"]
    .sum()
    .max()
)

st.subheader("Key Performance Indicators")

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Total Pendapatan",
    format_rupiah(total_revenue)
)

c2.metric(
    "Jumlah Transaksi",
    f"{total_transactions:,}"
)

c3.metric(
    "Rata-rata Transaksi",
    format_rupiah(average_transaction)
)

c4.metric(
    "Produk Pendapatan Tertinggi",
    top_product
)

st.caption(
    f"Pendapatan produk {top_product}: "
    f"{format_rupiah(top_product_revenue)}"
)

st.divider()


# =====================================================
# 7. NAVIGASI HALAMAN
# =====================================================

tab_overview, tab_product, tab_time, tab_olap, tab_data = st.tabs(
    [
        "Overview",
        "Product Analysis",
        "Time Analysis",
        "OLAP Analysis",
        "Data Explorer"
    ]
)


# =====================================================
# 8. OVERVIEW
# =====================================================

with tab_overview:

    st.subheader("Tren Penjualan")

    daily = (
        filtered_df.groupby("date", as_index=False)
        .agg(
            total_penjualan=("sales_amount", "sum"),
            jumlah_transaksi=("transaction_id", "nunique")
        )
        .sort_values("date")
    )

    fig_daily = px.line(
        daily,
        x="date",
        y="total_penjualan",
        markers=True,
        title="Tren Pendapatan Harian",
        labels={
            "date": "Tanggal",
            "total_penjualan": "Pendapatan"
        }
    )

    st.plotly_chart(
        fig_daily,
        use_container_width=True
    )

    monthly = (
        filtered_df.groupby(
            ["year", "month", "month_name"],
            as_index=False
        )
        .agg(total_penjualan=("sales_amount", "sum"))
        .sort_values(["year", "month"])
    )

    monthly["periode"] = (
        monthly["month_name"] + " " +
        monthly["year"].astype(str)
    )

    fig_monthly = px.bar(
        monthly,
        x="periode",
        y="total_penjualan",
        title="Pendapatan Bulanan",
        labels={
            "periode": "Periode",
            "total_penjualan": "Pendapatan"
        }
    )

    fig_monthly.update_layout(xaxis_tickangle=-45)

    st.plotly_chart(
        fig_monthly,
        use_container_width=True
    )


# =====================================================
# 9. PRODUCT ANALYSIS
# =====================================================

with tab_product:

    st.subheader("Analisis Kinerja Produk")

    product_summary = (
        filtered_df.groupby("coffee_name", as_index=False)
        .agg(
            jumlah_transaksi=("transaction_id", "nunique"),
            total_penjualan=("sales_amount", "sum"),
            rata_rata_transaksi=("sales_amount", "mean")
        )
        .sort_values("total_penjualan", ascending=False)
    )

    col1, col2 = st.columns(2)

    with col1:
        fig_product_revenue = px.bar(
            product_summary.sort_values("total_penjualan"),
            x="total_penjualan",
            y="coffee_name",
            orientation="h",
            title="Pendapatan Berdasarkan Produk",
            labels={
                "total_penjualan": "Pendapatan",
                "coffee_name": "Produk"
            }
        )

        st.plotly_chart(
            fig_product_revenue,
            use_container_width=True
        )

    with col2:
        fig_product_count = px.bar(
            product_summary.sort_values("jumlah_transaksi"),
            x="jumlah_transaksi",
            y="coffee_name",
            orientation="h",
            title="Jumlah Transaksi Berdasarkan Produk",
            labels={
                "jumlah_transaksi": "Jumlah Transaksi",
                "coffee_name": "Produk"
            }
        )

        st.plotly_chart(
            fig_product_count,
            use_container_width=True
        )

    st.subheader("Tabel Kinerja Produk")

    st.dataframe(
        product_summary.style.format({
            "total_penjualan": "Rp {:,.2f}",
            "rata_rata_transaksi": "Rp {:,.2f}"
        }),
        use_container_width=True,
        hide_index=True
    )


# =====================================================
# 10. TIME ANALYSIS
# =====================================================

with tab_time:

    st.subheader("Analisis Pola Waktu")

    col1, col2 = st.columns(2)

    with col1:
        hourly = (
            filtered_df.groupby("hour_of_day", as_index=False)
            .agg(
                total_penjualan=("sales_amount", "sum"),
                jumlah_transaksi=("transaction_id", "nunique")
            )
            .sort_values("hour_of_day")
        )

        fig_hour = px.bar(
            hourly,
            x="hour_of_day",
            y="jumlah_transaksi",
            title="Jumlah Transaksi Berdasarkan Jam",
            labels={
                "hour_of_day": "Jam",
                "jumlah_transaksi": "Jumlah Transaksi"
            }
        )

        st.plotly_chart(
            fig_hour,
            use_container_width=True
        )

    with col2:
        weekday_order = [
            "Monday", "Tuesday", "Wednesday",
            "Thursday", "Friday", "Saturday", "Sunday"
        ]

        weekday_summary = (
            filtered_df.groupby("weekday", as_index=False)
            .agg(
                total_penjualan=("sales_amount", "sum"),
                jumlah_transaksi=("transaction_id", "nunique")
            )
        )

        weekday_summary["weekday"] = pd.Categorical(
            weekday_summary["weekday"],
            categories=weekday_order,
            ordered=True
        )

        weekday_summary = weekday_summary.sort_values("weekday")

        fig_weekday = px.bar(
            weekday_summary,
            x="weekday",
            y="total_penjualan",
            title="Pendapatan Berdasarkan Hari",
            labels={
                "weekday": "Hari",
                "total_penjualan": "Pendapatan"
            }
        )

        st.plotly_chart(
            fig_weekday,
            use_container_width=True
        )

    st.subheader("Heatmap Transaksi Berdasarkan Hari dan Jam")

    heatmap_data = (
        filtered_df.groupby(
            ["weekday", "hour_of_day"]
        )["transaction_id"]
        .nunique()
        .reset_index(name="jumlah_transaksi")
    )

    heatmap_pivot = heatmap_data.pivot(
        index="weekday",
        columns="hour_of_day",
        values="jumlah_transaksi"
    ).fillna(0)

    heatmap_pivot = heatmap_pivot.reindex(
        [day for day in weekday_order if day in heatmap_pivot.index]
    )

    fig_heatmap = px.imshow(
        heatmap_pivot,
        aspect="auto",
        color_continuous_scale="Blues",
        labels={
            "x": "Jam",
            "y": "Hari",
            "color": "Jumlah Transaksi"
        },
        title="Kepadatan Transaksi Berdasarkan Hari dan Jam"
    )

    st.plotly_chart(
        fig_heatmap,
        use_container_width=True
    )


# =====================================================
# 11. OLAP ANALYSIS
# =====================================================

with tab_olap:

    st.subheader("Analisis OLAP Interaktif")

    olap_operation = st.selectbox(
        "Pilih operasi OLAP",
        [
            "Roll-up",
            "Drill-down",
            "Slice",
            "Dice"
        ]
    )

    if olap_operation == "Roll-up":

        level = st.selectbox(
            "Tingkat agregasi",
            ["Bulanan", "Kuartalan", "Tahunan"]
        )

        if level == "Bulanan":
            result = (
                filtered_df.groupby(
                    ["year", "month", "month_name"],
                    as_index=False
                )
                .agg(
                    jumlah_transaksi=("transaction_id", "nunique"),
                    total_penjualan=("sales_amount", "sum")
                )
                .sort_values(["year", "month"])
            )

            result["periode"] = (
                result["month_name"] + " " +
                result["year"].astype(str)
            )

        elif level == "Kuartalan":
            result = (
                filtered_df.groupby(
                    ["year", "quarter"],
                    as_index=False
                )
                .agg(
                    jumlah_transaksi=("transaction_id", "nunique"),
                    total_penjualan=("sales_amount", "sum")
                )
                .sort_values(["year", "quarter"])
            )

            result["periode"] = (
                result["quarter"] + " " +
                result["year"].astype(str)
            )

        else:
            result = (
                filtered_df.groupby("year", as_index=False)
                .agg(
                    jumlah_transaksi=("transaction_id", "nunique"),
                    total_penjualan=("sales_amount", "sum")
                )
                .sort_values("year")
            )

            result["periode"] = result["year"].astype(str)

        st.dataframe(
            result,
            use_container_width=True,
            hide_index=True
        )

        fig = px.bar(
            result,
            x="periode",
            y="total_penjualan",
            title=f"OLAP Roll-up {level}",
            labels={
                "periode": "Periode",
                "total_penjualan": "Pendapatan"
            }
        )

        st.plotly_chart(fig, use_container_width=True)

    elif olap_operation == "Drill-down":

        years = sorted(filtered_df["year"].unique())

        year_choice = st.selectbox(
            "Pilih tahun",
            years
        )

        year_data = filtered_df[
            filtered_df["year"] == year_choice
        ]

        quarters = sorted(year_data["quarter"].unique())

        quarter_choice = st.selectbox(
            "Pilih kuartal",
            quarters
        )

        quarter_data = year_data[
            year_data["quarter"] == quarter_choice
        ]

        monthly_detail = (
            quarter_data.groupby(
                ["month", "month_name"],
                as_index=False
            )
            .agg(
                jumlah_transaksi=("transaction_id", "nunique"),
                total_penjualan=("sales_amount", "sum")
            )
            .sort_values("month")
        )

        st.write("Detail bulanan pada kuartal terpilih")
        st.dataframe(
            monthly_detail,
            use_container_width=True,
            hide_index=True
        )

        if not monthly_detail.empty:
            month_choice = st.selectbox(
                "Telusuri ke tanggal pada bulan",
                monthly_detail["month"].tolist(),
                format_func=lambda x: pd.Timestamp(
                    year=int(year_choice),
                    month=int(x),
                    day=1
                ).strftime("%B")
            )

            daily_detail = (
                quarter_data[
                    quarter_data["month"] == month_choice
                ]
                .groupby("date", as_index=False)
                .agg(
                    jumlah_transaksi=("transaction_id", "nunique"),
                    total_penjualan=("sales_amount", "sum")
                )
                .sort_values("date")
            )

            st.write("Detail harian")
            st.dataframe(
                daily_detail,
                use_container_width=True,
                hide_index=True
            )

    elif olap_operation == "Slice":

        product_choice = st.selectbox(
            "Pilih produk",
            sorted(filtered_df["coffee_name"].unique())
        )

        slice_data = filtered_df[
            filtered_df["coffee_name"] == product_choice
        ]

        slice_summary = (
            slice_data.groupby(
                ["year", "month", "month_name"],
                as_index=False
            )
            .agg(
                jumlah_transaksi=("transaction_id", "nunique"),
                total_penjualan=("sales_amount", "sum")
            )
            .sort_values(["year", "month"])
        )

        st.metric(
            "Total Pendapatan Produk",
            format_rupiah(slice_data["sales_amount"].sum())
        )

        st.dataframe(
            slice_summary,
            use_container_width=True,
            hide_index=True
        )

        fig = px.line(
            slice_summary,
            x="month_name",
            y="total_penjualan",
            color="year",
            markers=True,
            title=f"Slice Penjualan Produk {product_choice}",
            labels={
                "month_name": "Bulan",
                "total_penjualan": "Pendapatan",
                "year": "Tahun"
            }
        )

        st.plotly_chart(fig, use_container_width=True)

    elif olap_operation == "Dice":

        col1, col2 = st.columns(2)

        with col1:
            dice_product = st.selectbox(
                "Produk",
                sorted(filtered_df["coffee_name"].unique()),
                key="dice_product"
            )

            dice_months = st.multiselect(
                "Bulan",
                sorted(filtered_df["month"].unique()),
                default=sorted(filtered_df["month"].unique()),
                key="dice_months"
            )

        with col2:
            dice_hours = st.slider(
                "Rentang jam",
                int(filtered_df["hour_of_day"].min()),
                int(filtered_df["hour_of_day"].max()),
                (
                    int(filtered_df["hour_of_day"].min()),
                    int(filtered_df["hour_of_day"].max())
                ),
                key="dice_hours"
            )

            dice_year = st.selectbox(
                "Tahun",
                sorted(filtered_df["year"].unique()),
                key="dice_year"
            )

        dice_data = filtered_df[
            (filtered_df["coffee_name"] == dice_product)
            & (filtered_df["year"] == dice_year)
            & (filtered_df["month"].isin(dice_months))
            & (filtered_df["hour_of_day"].between(
                dice_hours[0], dice_hours[1]
            ))
        ]

        dice_summary = (
            dice_data.groupby(
                ["month", "month_name", "hour_of_day"],
                as_index=False
            )
            .agg(
                jumlah_transaksi=("transaction_id", "nunique"),
                total_penjualan=("sales_amount", "sum")
            )
            .sort_values(["month", "hour_of_day"])
        )

        st.metric(
            "Pendapatan sesuai kombinasi filter",
            format_rupiah(dice_data["sales_amount"].sum())
        )

        st.dataframe(
            dice_summary,
            use_container_width=True,
            hide_index=True
        )

        if not dice_summary.empty:
            fig = px.density_heatmap(
                dice_summary,
                x="hour_of_day",
                y="month_name",
                z="total_penjualan",
                histfunc="sum",
                title="Dice: Pendapatan berdasarkan Bulan dan Jam",
                labels={
                    "hour_of_day": "Jam",
                    "month_name": "Bulan",
                    "total_penjualan": "Pendapatan"
                }
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )
        else:
            st.info("Tidak ada transaksi pada kombinasi filter ini.")


# =====================================================
# 12. DATA EXPLORER
# =====================================================

with tab_data:

    st.subheader("Data Transaksi Hasil Filter")

    st.write(
        f"Menampilkan {len(filtered_df):,} baris transaksi."
    )

    st.dataframe(
        filtered_df.sort_values("date", ascending=False),
        use_container_width=True,
        hide_index=True
    )

    csv_data = filtered_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        label="Unduh Data Hasil Filter (CSV)",
        data=csv_data,
        file_name="coffee_sales_filtered.csv",
        mime="text/csv"
    )


# =====================================================
# 13. FOOTER
# =====================================================

st.divider()

st.caption(
    "Coffee Sales Business Intelligence | "
    "Data Mart: SQLite | Visualization: Plotly | "
    "Framework: Streamlit"
)
