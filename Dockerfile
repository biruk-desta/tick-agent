FROM python:3.13.18-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
WORKDIR /bot
COPY mechfight.py example_bot.py ./
USER 65534:65534
ENTRYPOINT ["python3", "-B", "-u", "/bot/example_bot.py"]
