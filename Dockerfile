FROM python:3.13.18-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev
COPY practice_fast.c ./
RUN gcc -O3 -ffp-contract=off -fPIC -shared $(python3-config --includes) practice_fast.c -o _practice_fast.so -lm

FROM python:3.13.18-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
WORKDIR /bot
COPY mechfight.py example_bot.py duel_bot.py royale.py practice2.py ./
COPY --from=builder /build/_practice_fast.so ./
USER 65534:65534
ENTRYPOINT ["python3", "-B", "-u", "/bot/royale.py"]
