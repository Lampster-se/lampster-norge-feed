name: Generate norsk feed

on:
  schedule:
    - cron: "0 3 * * *"   # kör varje natt kl 03:00
  workflow_dispatch:       # så du kan köra manuellt från GitHub också
  push:
    branches:
      - main

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repo
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install requests lxml

      - name: Run script
        run: python generate_feed.py

      - name: Commit and push feed
        run: |
          git config user.name "github-actions"
          git config user.email "actions@github.com"
          git add norsk-feed.xml
          git commit -m "Update norsk feed"
          git push
