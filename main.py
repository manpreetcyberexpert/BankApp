def get_top_insights(self):
    df = self.df
    insights = {}

    # Helper
    def exists(col):
        return col in df.columns

    # -------------------------------
    # Top Accounts
    # -------------------------------
    if exists('account_number'):
        insights['top_involved_accounts'] = df['account_number'].value_counts().head(10).to_dict()
    else:
        insights['top_involved_accounts'] = {}

    # -------------------------------
    # Banks
    # -------------------------------
    if exists('bank_name'):
        insights['top_banks'] = df['bank_name'].value_counts().head(10).to_dict()
    else:
        insights['top_banks'] = {}

    # -------------------------------
    # Credit/Debit safety
    # -------------------------------
    df['credit'] = pd.to_numeric(df.get('credit', 0), errors='coerce').fillna(0)
    df['debit'] = pd.to_numeric(df.get('debit', 0), errors='coerce').fillna(0)
    df['final_amount'] = df['credit'] - df['debit']

    # -------------------------------
    # Received / Sent
    # -------------------------------
    if exists('account_number'):
        received = df[df['final_amount'] > 0]
        sent = df[df['final_amount'] < 0]

        insights['top_received_accounts'] = (
            received.groupby('account_number')['final_amount']
            .sum().sort_values(ascending=False).head(10).to_dict()
        ) if not received.empty else {}

        insights['top_sent_accounts'] = (
            sent.groupby('account_number')['final_amount']
            .sum().abs().sort_values(ascending=False).head(10).to_dict()
        ) if not sent.empty else {}

    # -------------------------------
    # UTR
    # -------------------------------
    if exists('utr'):
        insights['top_utr'] = df['utr'].value_counts().head(10).to_dict()
    else:
        insights['top_utr'] = {}

    # -------------------------------
    # UPI
    # -------------------------------
    if exists('description'):
        upi = df['description'].astype(str).str.extract(r'([\w\.-]+@[\w\.-]+)')[0]
        insights['top_upi'] = upi.value_counts().head(10).to_dict()
    else:
        insights['top_upi'] = {}

    # -------------------------------
    # Dates / Time
    # -------------------------------
    if exists('date'):
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df['only_date'] = df['date'].dt.date
        df['hour'] = df['date'].dt.hour

        insights['top_dates'] = df['only_date'].value_counts().head(10).to_dict()
        insights['top_hours'] = df['hour'].value_counts().head(10).to_dict()
    else:
        insights['top_dates'] = {}
        insights['top_hours'] = {}

    # -------------------------------
    # Bulk Flow
    # -------------------------------
    if exists('account_number'):
        insights['bulk_inflow'] = (
            df[df['final_amount'] > 0]
            .groupby('account_number')['final_amount']
            .sum().sort_values(ascending=False).head(5).to_dict()
        )

        insights['bulk_outflow'] = (
            df[df['final_amount'] < 0]
            .groupby('account_number')['final_amount']
            .sum().abs().sort_values(ascending=False).head(5).to_dict()
        )

    # -------------------------------
    # Suspicious
    # -------------------------------
    if exists('account_number'):
        freq = df['account_number'].value_counts()
        insights['high_frequency_accounts'] = freq[freq > 50].to_dict()
    else:
        insights['high_frequency_accounts'] = {}

    insights['repeated_amounts'] = int(df.duplicated(['final_amount']).sum())

    return insights
