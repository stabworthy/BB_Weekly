# BB Weekly Web App

This repo now includes a Streamlit web frontend for generating Blood Bowl Swiss pairings.

## Run locally

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Start the app:
   - `streamlit run streamlit_app.py`

## Deploy for free (Streamlit Community Cloud)

1. Push this repository to GitHub.
2. In Streamlit Community Cloud, click **Create app**.
3. Select this repo and branch `main`.
4. Set **Main file path** to `streamlit_app.py`.
5. Deploy.

The app supports:
- Using default CSV files committed in the repo
- Uploading fixtures and standings CSV files manually
- Downloading both compact and human-readable matchup outputs
