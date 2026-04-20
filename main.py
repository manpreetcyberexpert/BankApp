class BankAnalyser:
    def __init__(self, df):
        self.df = df
        self.clean_data()

    def clean_data(self):
        self.df.columns = [str(c).lower().strip().replace(" ", "_") for c in self.df.columns]

        # Date
        if 'date' in self.df.columns:
            self.df['date'] = pd.to_datetime(self.df['date'], errors='coerce')

        # Amount
        if 'amount' in self.df.columns:
            self.df['amount'] = pd.to_numeric(self.df['amount'], errors='coerce').fillna(0)

        # Credit / Debit handling
        if 'credit' in self.df.columns:
            self.df['credit'] = pd.to_numeric(self.df['credit'], errors='coerce').fillna(0)
        else:
            self.df['credit'] = 0

        if 'debit' in self.df.columns:
            self.df['debit'] = pd.to_numeric(self.df['debit'], errors='coerce').fillna(0)
        else:
            self.df['debit'] = 0

        # Final amount
        self.df['final_amount'] = self.df['credit'] - self.df['debit']

        # Time breakdown
        if 'date' in self.df.columns:
            self.df['hour'] = self.df['date'].dt.hour
            self.df['only_date'] = self.df['date'].dt.date

    def get_top_insights(self):
        df = self.df
        insights = {}

        # -------------------------------
        # 🔝 Top Accounts
        # -------------------------------
        if 'account_number' in df.columns:
            insights['top_involved_accounts'] = df['account_number'].value_counts().head(10).to_dict()

        # -------------------------------
        # 🏦 Banks
        # -------------------------------
        if 'bank_name' in df.columns:
            insights['top_banks'] = df['bank_name'].value_counts().head(10).to_dict()

        # -------------------------------
        # 💰 Received / Sent
        # -------------------------------
        if 'account_number' in df.columns:
            received = df[df['final_amount'] > 0]
            sent = df[df['final_amount'] < 0]

            insights['top_received_accounts'] = received.groupby('account_number')['final_amount'] \
                .sum().sort_values(ascending=False).head(10).to_dict()

            insights['top_sent_accounts'] = sent.groupby('account_number')['final_amount'] \
                .sum().abs().sort_values(ascending=False).head(10).to_dict()

        # -------------------------------
        # 🔁 UTR
        # -------------------------------
        if 'utr' in df.columns:
            insights['top_utr'] = df['utr'].value_counts().head(10).to_dict()

        # -------------------------------
        # 📲 UPI
        # -------------------------------
        if 'description' in df.columns:
            upi = df['description'].str.extract(r'([\w\.-]+@[\w\.-]+)')[0]
            insights['top_upi'] = upi.value_counts().head(10).to_dict()

        # -------------------------------
        # 📅 Dates
        # -------------------------------
        if 'only_date' in df.columns:
            insights['top_dates'] = df['only_date'].value_counts().head(10).to_dict()

        # -------------------------------
        # ⏰ Hours
        # -------------------------------
        if 'hour' in df.columns:
            insights['top_hours'] = df['hour'].value_counts().head(10).to_dict()

        # -------------------------------
        # 🚨 Bulk Flow (IMPORTANT)
        # -------------------------------
        if 'account_number' in df.columns:
            insights['bulk_inflow'] = df[df['final_amount'] > 0] \
                .groupby('account_number')['final_amount'] \
                .sum().sort_values(ascending=False).head(5).to_dict()

            insights['bulk_outflow'] = df[df['final_amount'] < 0] \
                .groupby('account_number')['final_amount'] \
                .sum().abs().sort_values(ascending=False).head(5).to_dict()

        # -------------------------------
        # 🚨 Suspicious
        # -------------------------------
        if 'account_number' in df.columns:
            freq = df['account_number'].value_counts()
            insights['high_frequency_accounts'] = freq[freq > 50].to_dict()

        insights['repeated_amounts'] = int(df.duplicated(['final_amount']).sum())

        return insights
