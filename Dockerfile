FROM golang:1.26.1-bookworm@sha256:ab3d6955bbc813a0f3fdf220c1d817dd89c0b3f283777db8ece4a32fe7858edd AS build
WORKDIR /src
COPY third_party/mechbot/go.mod ./
COPY third_party/mechbot/mech ./mech
COPY third_party/mechbot/cmd/bot ./cmd/bot
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o /mechbot ./cmd/bot

FROM python:3.13.18-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
WORKDIR /bot
COPY mechfight.py example_bot.py duel_bot.py royale.py practice2.py practice3.py ./
COPY --from=build --chmod=755 /mechbot ./mechbot
COPY third_party/mechbot/LICENSE ./third_party/mechbot/
USER 65534:65534
ENTRYPOINT ["python3", "-B", "-u", "/bot/royale.py"]
