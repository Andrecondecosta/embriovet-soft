import pandas as pd


def filter_stock_view(stock_df, garanhao, owner_filters=None, min_palhetas=0, include_zero=False):
    if stock_df.empty:
        return stock_df

    df = stock_df[stock_df["garanhao"] == garanhao].copy()

    if owner_filters:
        df = df[df["proprietario_nome"].isin(owner_filters)]

    if min_palhetas and min_palhetas > 0:
        df = df[df["existencia_atual"].fillna(0) >= min_palhetas]

    if not include_zero:
        df = df[df["existencia_atual"].fillna(0) > 0]

    return df


def summarize_stock_by_owner(stock_df):
    if stock_df.empty:
        return pd.DataFrame(columns=["Proprietário", "Total Palhetas"])

    resumo = stock_df.groupby("proprietario_nome")["existencia_atual"].sum().reset_index()
    resumo.columns = ["Proprietário", "Total Palhetas"]
    return resumo.sort_values("Total Palhetas", ascending=False)


def stock_kpis(stock_df, to_py):
    if stock_df.empty:
        return [
            ("lotes", 0),
            ("palhetas", 0),
            ("proprietários", 0),
            ("qualidade média", "0%"),
        ]

    qualidade_media = round(float(to_py(stock_df["qualidade"].mean()) or 0), 1)
    return [
        ("lotes", len(stock_df)),
        ("palhetas", int(to_py(stock_df["existencia_atual"].sum()) or 0)),
        ("proprietários", stock_df["proprietario_nome"].nunique()),
        ("qualidade média", f"{qualidade_media}%"),
    ]


def filter_transfer_history(transf_df, transf_ext_df, garanhao, owner_filters=None):
    transf_f = transf_df[transf_df["garanhao"] == garanhao].copy() if not transf_df.empty else transf_df
    transf_ext_f = transf_ext_df[transf_ext_df["garanhao"] == garanhao].copy() if not transf_ext_df.empty else transf_ext_df

    if owner_filters:
        if not transf_f.empty:
            transf_f = transf_f[
                (transf_f["proprietario_origem"].isin(owner_filters))
                | (transf_f["proprietario_destino"].isin(owner_filters))
            ]
        if not transf_ext_f.empty:
            transf_ext_f = transf_ext_f[transf_ext_f["proprietario_origem"].isin(owner_filters)]

    return transf_f, transf_ext_f


def filter_lot_transfer_history(transf_df, transf_ext_df, garanhao, owner_name):
    transf_lote = pd.DataFrame()
    transf_ext_lote = pd.DataFrame()

    if not transf_df.empty:
        transf_lote = transf_df[
            (transf_df["garanhao"] == garanhao)
            & (
                (transf_df["proprietario_origem"] == owner_name)
                | (transf_df["proprietario_destino"] == owner_name)
            )
        ].copy()

    if not transf_ext_df.empty:
        transf_ext_lote = transf_ext_df[
            (transf_ext_df["garanhao"] == garanhao)
            & (transf_ext_df["proprietario_origem"] == owner_name)
        ].copy()

    return transf_lote, transf_ext_lote
